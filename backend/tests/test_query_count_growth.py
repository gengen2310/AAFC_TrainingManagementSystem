"""C9 (2026-10-11): no training/planning GET may gain queries per row.

Every GET route on routers/training.py and routers/planning.py (the C5 parity
harness's route table, all path params resolved) is requested as a Squadron
Admin and a National Admin, then 703's year grows by parade nights with two
sessions each, and every route is requested again. A route whose SQL
statement count grows with the data has an N+1.

Measured on 2026-10-11: 80 of 82 routes constant. Two are linear per parade
night by design (they run the conflict detector per night, bounded by one
Squadron's year, <= ~60 nights): plan-review (2/night) and schedule export
(1/night). They are pinned at that rate so they cannot get worse; anything
else that grows fails. Runs in a subprocess on a fresh seed.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PER_NIGHT_ALLOWED = {
    "GET /planning/years/{year_id}/plan-review": 2,
    "GET /planning/years/{year_id}/schedule/export.xlsx": 1,
}

SCRIPT = r'''
import json, os, sys, datetime as dt
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "tests"))
from fastapi.testclient import TestClient
from sqlalchemy import event
from app.main import app
from app.database import SessionLocal, engine
from app.seeds.seed_all import seed_all
import test_training_planning_extraction_parity as P
seed_all()
c = TestClient(app)
def hdr(code):
    return {"Authorization": "Bearer " + c.post("/api/auth/login", json={"code": code}).json()["token"]}
db = SessionLocal(); routes = P._routes(P._ids(db)); db.close()
n = {"v": 0}
event.listen(engine, "before_cursor_execute", lambda *a, **k: n.__setitem__("v", n["v"] + 1))
def measure(h):
    out = {}
    for key, path in routes:
        n["v"] = 0
        status = c.get(path if path.startswith("/api") else "/api" + path, headers=h).status_code
        out[key] = [status, n["v"]]
    return out
H = {code: hdr(code) for code in ("ADMIN703", "ADMINNATIONAL")}
before = {code: measure(h) for code, h in H.items()}
nights = 0
for i in range(30):
    d = (dt.date(2026, 1, 6) + dt.timedelta(days=7 * i + 3)).isoformat()
    pn = c.post("/api/parade-nights", json={"date": d, "start_time": "18:30", "end_time": "21:30"},
                headers=H["ADMIN703"])
    if pn.status_code not in (200, 201):
        continue
    pid = pn.json().get("parade_night_id") or pn.json().get("id")
    ok = [c.post("/api/sessions", json={"parade_night_id": pid, "period_number": per,
                                        "cadet_group": "senior"}, headers=H["ADMIN703"]).status_code
          for per in (1, 2)]
    nights += all(s in (200, 201) for s in ok)
after = {code: measure(h) for code, h in H.items()}
print(json.dumps({"nights": nights, "before": before, "after": after}))
'''


def test_no_get_route_gains_queries_per_row():
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp}/c9.db", "ENVIRONMENT": "test",
               "JWT_SECRET": "test-secret-test-secret-test-secret",
               "SECRET_KEY": "test-secret-test-secret-test-secret", "API_RATE_LIMIT": "1000000"}
        out = subprocess.run([sys.executable, "-c", SCRIPT], cwd=BACKEND, env=env,
                             capture_output=True, text=True, timeout=600)
        assert out.returncode == 0, out.stderr[-3000:]
        res = json.loads(out.stdout.strip().splitlines()[-1])
    nights = res["nights"]
    assert nights >= 5, f"only {nights} parade nights could be added; the growth step proves nothing"
    # A wrong path prefix once made every route 404 with 0 queries and the
    # test passed vacuously: require the routes to actually answer.
    ok = sum(1 for routes in res["after"].values() for status, _ in routes.values() if status == 200)
    total = sum(len(routes) for routes in res["after"].values())
    assert ok >= 0.9 * total, f"only {ok}/{total} route requests returned 200"
    grew = []
    for code, routes in res["before"].items():
        for key, (status, b) in routes.items():
            a = res["after"][code][key][1]
            allowed = PER_NIGHT_ALLOWED.get(key, 0) * nights
            if a - b > allowed:
                grew.append(f"{code} {key}: {b} -> {a} queries (+{a - b}, allowed +{allowed})")
    assert grew == [], "query count grows with data (N+1):\n" + "\n".join(grew)
