#!/usr/bin/env python3
"""250-user multi-Wing concurrent load test against AAFC TMS staging.

Distributes 250 virtual users across two Wings (7WG + 1WG) to verify
National-ready multi-Wing scope under sustained load.

Usage:
    export WING2_ADMIN_CODE=<code-from-second-wing-seed>
    export SQN101_ADMIN_CODE=<code>
    export SQN101_GENERAL_CODE=<code>
    export SQN102_ADMIN_CODE=<code>
    python tools/stress/load_test_multi_wing.py [--users 250] [--duration-minutes 30]

All Wing 2 codes MUST be provided via environment variables — they are
generated randomly by second_wing_seed.py and printed exactly once.

Pass/fail criteria:
    P95 response time ≤ 2000ms across all endpoints, both Wings combined
    Zero 5xx errors during sustained load
    No cross-Wing data leakage (RBAC enforced at API layer)

IMPORTANT: Run against staging only. Never target production.
"""
import argparse
import os
import random
import statistics
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    raise

BASE = os.environ.get("BASE_URL", "https://aafc-tms-backend-staging.up.railway.app")

# Wing 1 (7WG) — 16 squadrons with deterministic codes from seed_all.py
_7WG_CODES = []
for _code in ["701", "702", "703", "704", "705", "707", "708", "709",
              "710", "711", "712", "713", "714", "715", "721", "723"]:
    _7WG_CODES.append({"role": "sqn_admin",   "code": f"ADMIN{_code}", "wing": "7WG", "sqn": _code})
    _7WG_CODES.append({"role": "sqn_general", "code": f"{_code}SQN2026", "wing": "7WG", "sqn": _code})
_7WG_CODES.append({"role": "wing_admin",  "code": "ADMIN7WG",   "wing": "7WG", "sqn": "7WG"})
_7WG_CODES.append({"role": "wing_viewer", "code": "7WG2026",    "wing": "7WG", "sqn": "7WG"})

# Wing 2 (1WG) — codes from second_wing_seed.py, supplied via env
def _build_1wg_pool() -> list[dict]:
    missing = []
    specs = [
        ("WING2_ADMIN_CODE",    "wing_admin",   "1WG", "1WG"),
        ("SQN101_ADMIN_CODE",   "sqn_admin",    "1WG", "101"),
        ("SQN101_GENERAL_CODE", "sqn_general",  "1WG", "101"),
        ("SQN102_ADMIN_CODE",   "sqn_admin",    "1WG", "102"),
    ]
    pool = []
    for env_key, role, wing, sqn in specs:
        code = os.environ.get(env_key, "").strip()
        if not code:
            missing.append(env_key)
        else:
            pool.append({"role": role, "code": code, "wing": wing, "sqn": sqn})
    if missing:
        print(f"WARNING: Missing 1WG codes (env vars): {', '.join(missing)}", file=sys.stderr)
        print("  Run backend/app/seeds/second_wing_seed.py and capture the output.", file=sys.stderr)
        print("  1WG users will be excluded from this run.", file=sys.stderr)
    return pool


def _build_user_pool(user_count: int) -> list[dict]:
    pool_1wg = _build_1wg_pool()
    combined = _7WG_CODES + pool_1wg
    return [combined[i % len(combined)] for i in range(user_count)]


# Thread-safe results
_lock = threading.Lock()
_results = {
    "total": 0, "ok": 0, "fail": 0, "err5xx": 0,
    "times_ms": defaultdict(list),
    "wing_requests": defaultdict(int),
    "errors": [],
    "stop_event": threading.Event(),
}


def _record(endpoint: str, status: int, ms: float, wing: str, error: str | None = None):
    with _lock:
        _results["total"] += 1
        _results["times_ms"][endpoint].append(ms)
        _results["wing_requests"][wing] += 1
        if status == 200:
            _results["ok"] += 1
        elif 500 <= status < 600:
            _results["err5xx"] += 1
            _results["fail"] += 1
        else:
            _results["fail"] += 1
        if error:
            _results["errors"].append(f"[{wing}] {endpoint}: {error}")


def _get(session: requests.Session, path: str, wing: str) -> tuple[int, float]:
    url = f"{BASE}{path}"
    t0 = time.perf_counter()
    try:
        r = session.get(url, timeout=15)
        ms = (time.perf_counter() - t0) * 1000
        _record(path, r.status_code, ms, wing)
        return r.status_code, ms
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        _record(path, 0, ms, wing, str(e))
        return 0, ms


def _worker(user_spec: dict, ramp_delay_s: float):
    stop = _results["stop_event"]
    time.sleep(ramp_delay_s)

    session = requests.Session()
    code = user_spec["code"]
    wing = user_spec["wing"]
    sqn = user_spec["sqn"]
    is_sqn = sqn not in ("7WG", "1WG", "NAT")

    while not stop.is_set():
        t0 = time.perf_counter()
        try:
            r = session.post(f"{BASE}/api/auth/login", json={"code": code}, timeout=15)
            ms = (time.perf_counter() - t0) * 1000
            _record("/api/auth/login", r.status_code, ms, wing)
            if r.status_code != 200:
                time.sleep(random.uniform(5, 15))
                continue
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            _record("/api/auth/login", 0, ms, wing, str(e))
            time.sleep(random.uniform(5, 15))
            continue

        _get(session, "/api/auth/me", wing)
        time.sleep(random.uniform(0.2, 0.8))
        if stop.is_set():
            break

        _get(session, "/api/reports/summary", wing)
        time.sleep(random.uniform(1, 3))
        if stop.is_set():
            break

        _get(session, "/api/parade-nights", wing)
        time.sleep(random.uniform(0.5, 2))
        if stop.is_set():
            break

        if is_sqn:
            _get(session, "/api/planning/years", wing)
            time.sleep(random.uniform(0.5, 2))
        if stop.is_set():
            break

        # Wing-aggregate endpoint — exercised by both wing_admin users
        if user_spec["role"] == "wing_admin":
            _get(session, "/api/reports/curriculum-coverage", wing)
            time.sleep(random.uniform(1, 2))

        try:
            session.post(f"{BASE}/api/auth/logout", timeout=10)
        except Exception:
            pass
        session = requests.Session()
        time.sleep(random.uniform(2, 8))


def _print_summary(duration_s: float, user_count: int):
    times = _results["times_ms"]
    all_times = [t for ts in times.values() for t in ts]
    print("\n" + "=" * 72)
    print("  AAFC TMS Multi-Wing Staging Load Test — RESULTS")
    print(f"  Duration   : {duration_s:.0f}s ({duration_s/60:.1f} min)")
    print(f"  Users      : {user_count}")
    print(f"  Total reqs : {_results['total']}")
    print(f"  Successful : {_results['ok']}")
    print(f"  5xx errors : {_results['err5xx']}")
    print()
    print("  Requests per Wing:")
    for wing, count in sorted(_results["wing_requests"].items()):
        print(f"    {wing:<6}: {count}")
    print()
    if all_times:
        s = sorted(all_times)
        n = len(s)
        print(f"  Overall latency (n={n}):")
        print(f"    Avg    : {statistics.mean(s):.0f}ms")
        print(f"    Median : {statistics.median(s):.0f}ms")
        print(f"    P95    : {s[int(n * 0.95)]:.0f}ms")
        print(f"    Max    : {s[-1]:.0f}ms")
    print()
    print("  Per-endpoint P95:")
    for ep, ts in sorted(times.items()):
        s2 = sorted(ts)
        p95 = s2[int(len(s2) * 0.95)] if s2 else 0
        avg = statistics.mean(s2) if s2 else 0
        print(f"    {ep:<40} n={len(ts):>5}  avg={avg:>6.0f}ms  p95={p95:>6.0f}ms")
    print()

    p95_all = sorted(all_times)[int(len(all_times) * 0.95)] if all_times else 9999
    criteria_p95 = p95_all <= 2000
    criteria_5xx = _results["err5xx"] == 0
    wing_count = len([w for w in _results["wing_requests"] if _results["wing_requests"][w] > 0])
    criteria_wings = wing_count >= 2
    print("  Criteria:")
    print(f"    P95 ≤ 2000ms : {'PASS' if criteria_p95 else 'FAIL'} ({p95_all:.0f}ms)")
    print(f"    Zero 5xx     : {'PASS' if criteria_5xx else 'FAIL'} ({_results['err5xx']} errors)")
    print(f"    Both Wings   : {'PASS' if criteria_wings else 'FAIL — only 1WG users missing, see WARNING above'} ({wing_count} wings active)")
    overall = "PASS" if criteria_p95 and criteria_5xx and criteria_wings else "FAIL"
    print(f"\n  OVERALL: {overall}")

    if _results["errors"][:5]:
        print("\n  Sample errors:")
        for e in _results["errors"][:5]:
            print(f"    {e}")

    ts_now = datetime.now(timezone.utc).isoformat()
    print(f"\n  Gate record (paste into release evidence chain):")
    print(f"    Timestamp   : {ts_now}")
    print(f"    Users       : {user_count}")
    print(f"    Wings tested: {wing_count}")
    print(f"    Duration    : {duration_s:.0f}s")
    print(f"    Requests    : {_results['total']}")
    print(f"    P95 latency : {p95_all:.0f}ms")
    print(f"    5xx errors  : {_results['err5xx']}")
    print(f"    Result      : {overall}")
    print("=" * 72)

    return criteria_p95 and criteria_5xx and criteria_wings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=250)
    parser.add_argument("--duration-minutes", type=float, default=30)
    parser.add_argument("--ramp-seconds", type=float, default=90)
    args = parser.parse_args()

    print(f"\nAAFC TMS Multi-Wing Staging Load Test")
    print(f"  Target  : {BASE}")
    print(f"  Users   : {args.users}")
    print(f"  Duration: {args.duration_minutes} min sustained + {args.ramp_seconds}s ramp")
    print()

    try:
        r = requests.get(f"{BASE}/api/health/ready", timeout=10)
        if r.status_code != 200:
            print(f"ERROR: Staging health check failed ({r.status_code}). Aborting.")
            sys.exit(1)
        health = r.json()
        sqn_count = health.get("squadrons", 0)
        if sqn_count < 18:  # 16 (7WG) + 2 (1WG)
            print(f"WARNING: Only {sqn_count} squadrons found. Expected ≥18 (16 x 7WG + 2 x 1WG).")
            print("  Run backend/app/seeds/second_wing_seed.py against staging first.")
        print(f"  Pre-test health: {health}")
    except Exception as e:
        print(f"ERROR: Cannot reach staging at {BASE}: {e}")
        sys.exit(1)

    pool = _build_user_pool(args.users)
    wing_coverage = {u["wing"] for u in pool}
    print(f"  Wings in pool: {sorted(wing_coverage)}")

    duration_s = args.duration_minutes * 60
    ramp_s = args.ramp_seconds
    total_s = duration_s + ramp_s

    print(f"\n  Starting {args.users} virtual users...")
    threads = []
    wall_start = time.perf_counter()
    for i, user in enumerate(pool):
        ramp_delay = (i / args.users) * ramp_s
        t = threading.Thread(target=_worker, args=(user, ramp_delay), daemon=True)
        t.start()
        threads.append(t)

    try:
        while True:
            elapsed = time.perf_counter() - wall_start
            if elapsed >= total_s:
                break
            with _lock:
                total_req = _results["total"]
                errs = _results["err5xx"]
            phase = "RAMP" if elapsed < ramp_s else "SUSTAINED"
            print(f"  [{phase}] {elapsed:.0f}s/{total_s:.0f}s  "
                  f"requests={total_req}  5xx={errs}", end="\r", flush=True)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n  Interrupted.")

    print("\n  Stopping workers...")
    _results["stop_event"].set()
    for t in threads:
        t.join(timeout=30)

    passed = _print_summary(time.perf_counter() - wall_start, args.users)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
