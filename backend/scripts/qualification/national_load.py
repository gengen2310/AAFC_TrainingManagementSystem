"""Mixed-workflow national load driver for the qualification dataset.

Virtual users sign in the production way (lookup -> login) with the
deterministic codes from seed_national_dataset.py, then loop realistic
workflows with think time:

  sqn_admin (60%)     me, dashboard charts, years, term planner, cadets,
                      parade nights, weekly program, and a PLANNING EDIT
                      (PATCH a session's notes with optimistic version)
  sqn_general (15%)   me, cadets, parade nights, weekly program
  wing_admin (15%)    Wing overview / phase coverage / not-delivered reports
  national (5%)       national overview, accounts, Service Desk tickets, audit
  public (5%)         submits a Service Desk ticket (no sign-in)
  + occasional curriculum CSV import PREVIEW (200 rows) by national admins

Records every request (endpoint template, status, latency, bytes) and samples
PostgreSQL connections and gunicorn CPU/RSS once a second. LOCAL ONLY.

  python -m scripts.qualification.national_load --users 100 --duration 180 \
      --base http://127.0.0.1:8400 --pg "postgresql://aafc@127.0.0.1:55418/aafc_qual" \
      --out results-100.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import subprocess
import threading
import time
from collections import defaultdict
from urllib.parse import urlparse

import httpx

N_WINGS, SQN_PER_WING = 6, 10


def sqn_codes():
    out = []
    for w in range(N_WINGS):
        for q in range(SQN_PER_WING):
            out.append((f"Q{w + 1}W", f"{9 - w % 9}{w:01d}{q:02d}"[:4]))
    return out


class Recorder:
    def __init__(self):
        self.lock = threading.Lock()
        self.rows = []  # (t, endpoint, status, ms, bytes)

    def add(self, ep, status, ms, size):
        with self.lock:
            self.rows.append((time.time(), ep, status, ms, size))


def call(rec, s, method, base, path, ep, **kw):
    t0 = time.perf_counter()
    try:
        r = s.request(method, base + path, **kw)
        rec.add(ep, r.status_code, (time.perf_counter() - t0) * 1000, len(r.content))
        return r
    except Exception:
        rec.add(ep, 0, (time.perf_counter() - t0) * 1000, 0)
        return None


def sign_in(rec, s, base, body, code):
    r = call(rec, s, "POST", base, "/api/auth/lookup", "POST /auth/lookup", json=body)
    if r is None or r.status_code != 200:
        return False
    r = call(rec, s, "POST", base, "/api/auth/login", "POST /auth/login",
             json={"code": code, "user_id": r.json()["user_id"]})
    if r is None or r.status_code != 200:
        return False
    s.headers["Authorization"] = "Bearer " + r.json()["token"]
    return True


THINK = (0.5, 2.0)   # seconds between a user's actions; --think overrides


def think():
    time.sleep(random.uniform(*THINK))


def run_user(kind, rec, base, stop, rng):
    s = httpx.Client(timeout=60)
    wings = sorted({w for w, _ in sqn_codes()})
    wing, sqn = rng.choice(sqn_codes())
    if kind == "public":
        sqns = []
        while not stop.is_set():
            if not sqns:
                r = call(rec, s, "GET", base, "/api/public/squadrons", "GET /public/squadrons")
                sqns = r.json() if r is not None and r.status_code == 200 else []
            if sqns:
                q = rng.choice(sqns)
                call(rec, s, "POST", base, "/api/service-desk/tickets", "POST /service-desk/tickets", json={
                    "rank": "CDT", "first_name": "Load", "last_name": "Test", "email": "load@example.com",
                    "squadron_id": q.get("squadron_id") or q.get("id"), "category": "other",
                    "description": "Qualification load ticket - automated, please ignore."})
            time.sleep(rng.uniform(5, 15))
        return
    if kind in ("sqn_admin", "sqn_general"):
        role, code = kind, f"QA{sqn}{'ADM' if kind == 'sqn_admin' else 'GEN'}"
        body = {"unit_type": "squadron", "identifier": sqn, "role": role}
    elif kind == "wing_admin":
        wing = rng.choice(wings)
        body, code = {"unit_type": "wing", "identifier": wing, "role": "wing_admin"}, f"QA{wing}ADM"
    else:
        body, code = {"unit_type": "national", "role": "national_admin"}, "QANATADM"
    while not stop.is_set() and not sign_in(rec, s, base, body, code):
        time.sleep(rng.uniform(2, 5))
    year_id, nights, sessions = None, [], []
    while not stop.is_set():
        if kind in ("sqn_admin", "sqn_general"):
            call(rec, s, "GET", base, "/api/auth/me", "GET /auth/me")
            if year_id is None:
                r = call(rec, s, "GET", base, "/api/planning/years", "GET /planning/years")
                ys = r.json() if r is not None and r.status_code == 200 else []
                ys = ys if isinstance(ys, list) else ys.get("planning_years", [])
                year_id = next((y["planning_year_id"] for y in ys if y.get("planning_year_id")), None)
            if kind == "sqn_admin":      # sqn_general is denied the cadet list by design (sensitive data)
                call(rec, s, "GET", base, "/api/cadets", "GET /cadets")
            r = call(rec, s, "GET", base, f"/api/parade-nights?planning_year_id={year_id}", "GET /parade-nights")
            if r is not None and r.status_code == 200 and not nights:
                nights = [n["parade_night_id"] for n in r.json()][:40]
            if nights:
                pn = rng.choice(nights)
                r = call(rec, s, "GET", base, f"/api/planning/parade-dates/{pn}/weekly-program", "GET weekly-program")
                if r is not None and r.status_code == 200:
                    sessions = [x for x in r.json().get("sessions", []) if x.get("session_id")]
            if kind == "sqn_admin":
                call(rec, s, "GET", base, "/api/dashboard/charts?window=term", "GET dashboard/charts")
                if year_id and rng.random() < 0.3:
                    call(rec, s, "GET", base, f"/api/planning/years/{year_id}/term-planner", "GET term-planner")
                if sessions and rng.random() < 0.5:
                    x = rng.choice(sessions)
                    call(rec, s, "PATCH", base, f"/api/planning/sessions/{x['session_id']}", "PATCH planning/session",
                         json={"notes": f"load {time.time():.0f}", "version": x.get("version")})
        elif kind == "wing_admin":
            for p in ("/api/reports/wing-overview", "/api/reports/wing-phase-coverage", "/api/reports/wing-not-delivered"):
                call(rec, s, "GET", base, p, "GET " + p[4:])
                think()
        else:
            for p, ep in (("/api/reports/national-overview", "GET /reports/national-overview"),
                          ("/api/accounts", "GET /accounts"),
                          ("/api/service-desk/tickets", "GET /service-desk/tickets"),
                          ("/api/audit?limit=100", "GET /audit")):
                call(rec, s, "GET", base, p, ep)
                think()
            if rng.random() < 0.2:
                csv = "Training Phase,Experiential Code,Title\n" + "".join(
                    f"B. Initial,LOAD{i:04d},Load item {i}\n" for i in range(200))
                call(rec, s, "POST", base, "/api/curriculum/import-csv?owning_level=national&preview=true",
                     "POST curriculum/import-csv preview", files={"file": ("c.csv", csv.encode(), "text/csv")})
        think()


def sampler(pg, base, stop, out):
    u = urlparse(pg)
    psql = ["psql", "-h", u.hostname, "-p", str(u.port), "-U", u.username, "-d", u.path.lstrip("/"), "-tAc"]
    while not stop.is_set():
        row = {"t": time.time()}
        try:
            row["db_conn"] = subprocess.run(psql + ["select count(*) from pg_stat_activity where datname=current_database()"],
                                            capture_output=True, text=True, timeout=5).stdout.strip()
            row["db_active"] = subprocess.run(psql + ["select count(*) from pg_stat_activity where datname=current_database() and state='active'"],
                                              capture_output=True, text=True, timeout=5).stdout.strip()
            # Server = the process listening on the port plus its workers (works for
            # gunicorn and for `uvicorn --workers`, whose children are spawned).
            port = str(urlparse(base).port)
            root = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                                  capture_output=True, text=True).stdout.split()
            pids = set(root)
            for r in root:
                pids |= set(subprocess.run(["pgrep", "-P", r], capture_output=True, text=True).stdout.split())
            if pids:
                ps = subprocess.run(["ps", "-o", "pcpu=,rss=", "-p", ",".join(sorted(pids))],
                                    capture_output=True, text=True).stdout.split("\n")
                vals = [l.split() for l in ps if l.strip()]
                row["cpu"] = sum(float(v[0]) for v in vals)
                row["rss_mb"] = sum(int(v[1]) for v in vals) / 1024
                row["procs"] = len(vals)
        except Exception as e:  # noqa: BLE001
            row["err"] = str(e)
        out.append(row)
        time.sleep(1)


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))] if xs else 0


def summarise(rec, samples, users, duration):
    by = defaultdict(list)
    for _, ep, st, ms, size in rec.rows:
        by[ep].append((st, ms, size))
    lat = [ms for _, _, st, ms, _ in rec.rows]
    statuses = defaultdict(int)
    for _, _, st, _, _ in rec.rows:
        statuses[str(st)] += 1
    errs = sum(v for k, v in statuses.items() if k == "0" or k.startswith("5"))
    out = {"users": users, "duration_s": duration, "requests": len(rec.rows),
           "throughput_rps": round(len(rec.rows) / duration, 1),
           "p50_ms": round(pct(lat, .50)), "p95_ms": round(pct(lat, .95)), "p99_ms": round(pct(lat, .99)),
           "status_counts": dict(statuses), "error_rate": round(errs / max(1, len(rec.rows)), 4),
           "db_conn_max": max((int(s.get("db_conn") or 0) for s in samples), default=0),
           "db_active_max": max((int(s.get("db_active") or 0) for s in samples), default=0),
           "cpu_pct_max": max((s.get("cpu", 0) for s in samples), default=0),
           "rss_mb_max": round(max((s.get("rss_mb", 0) for s in samples), default=0)),
           "server_procs": max((s.get("procs", 0) for s in samples), default=0),
           "endpoints": {}}
    for ep, xs in sorted(by.items()):
        ms = [m for _, m, _ in xs]
        out["endpoints"][ep] = {"n": len(xs), "p50": round(pct(ms, .5)), "p95": round(pct(ms, .95)),
                                "p99": round(pct(ms, .99)), "max_kb": round(max(s for _, _, s in xs) / 1024, 1),
                                "non2xx": sum(1 for st, _, _ in xs if not 200 <= st < 300)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8400")
    ap.add_argument("--pg", required=True)
    ap.add_argument("--users", type=int, default=50)
    ap.add_argument("--duration", type=int, default=120)
    ap.add_argument("--ramp", type=int, default=20)
    ap.add_argument("--out", required=True)
    ap.add_argument("--think", default="0.5,2.0",
                    help="min,max seconds between a user's actions (aggressive default; real staff ~8,20)")
    a = ap.parse_args()
    global THINK
    THINK = tuple(float(x) for x in a.think.split(","))
    if urlparse(a.base).hostname not in ("127.0.0.1", "localhost"):
        raise SystemExit("REFUSED: the qualification load driver only targets a local server.")
    rec, stop, samples = Recorder(), threading.Event(), []
    mix = ["sqn_admin"] * 60 + ["sqn_general"] * 15 + ["wing_admin"] * 15 + ["national"] * 5 + ["public"] * 5
    random.Random(7).shuffle(mix)   # every stage size gets a representative role mix
    threads = [threading.Thread(target=sampler, args=(a.pg, a.base, stop, samples), daemon=True)]
    for i in range(a.users):
        rng = random.Random(i)
        t = threading.Thread(target=run_user, args=(mix[i % 100], rec, a.base, stop, rng), daemon=True)
        threads.append(t)
    threads[0].start()
    for i, t in enumerate(threads[1:]):
        t.start()
        time.sleep(a.ramp / max(1, a.users))
    time.sleep(max(0, a.duration - a.ramp))
    stop.set()
    time.sleep(3)
    res = summarise(rec, samples, a.users, a.duration)
    res["think_s"] = list(THINK)
    json.dump(res, open(a.out, "w"), indent=2)
    print(json.dumps({k: v for k, v in res.items() if k != "endpoints"}, indent=1))


if __name__ == "__main__":
    main()
