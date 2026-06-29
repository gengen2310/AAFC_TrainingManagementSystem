#!/usr/bin/env python3
"""Smoke test suite for AAFC TMS — local demo.

Tests that all key flows are reachable and returning expected status codes.
Run this against a live local server before packaging or deploying.

Usage:
    cd <project_root>
    python tools/stress/smoke_test.py

Requirements: requests (pip install requests)
"""
import sys
import requests

BASE = "http://localhost:8000"
CODES = {
    "SYSADMIN2026": "system_admin",
    "ADMINNATIONAL": "national_admin",
    "ADMIN7WG": "wing_admin",
    "ADMIN703": "sqn_admin",
    "703SQN2026": "sqn_general",
    "AUDITOR2026": "auditor",
}

PASS = 0
FAIL = 0
RESULTS = []


def check(label, ok, detail=""):
    global PASS, FAIL
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))


def login(code):
    r = requests.post(f"{BASE}/api/auth/login", json={"code": code})
    if r.status_code == 200:
        return r.cookies
    return None


def get(path, cookies=None, expected=200):
    r = requests.get(f"{BASE}{path}", cookies=cookies)
    check(f"GET {path}", r.status_code == expected,
          f"got {r.status_code}" if r.status_code != expected else "")
    return r


def post(path, body, cookies=None, expected=200):
    r = requests.post(f"{BASE}{path}", json=body, cookies=cookies)
    check(f"POST {path}", r.status_code == expected,
          f"got {r.status_code}" if r.status_code != expected else "")
    return r


def section(title):
    RESULTS.append(f"\n  {title}")


print("\nAAFC TMS — Smoke Test")
print("=" * 50)

# ── Health ──
section("Health")
get("/api/health")
get("/api/health/db")
get("/api/health/ready")

# ── Auth security (run before any successful logins so no session cookie leaks) ──
section("Auth security")
r = requests.post(f"{BASE}/api/auth/login", json={"code": "WRONG"})
check("Invalid code → 401", r.status_code == 401)
r = requests.get(f"{BASE}/api/auth/me")
check("Unauthenticated /me → 401", r.status_code == 401)

# ── Auth ──
section("Authentication")
for code, role in CODES.items():
    r = requests.post(f"{BASE}/api/auth/login", json={"code": code})
    check(f"Login {role}", r.status_code == 200 and r.json().get("session", {}).get("role") == role)

# ── System Admin endpoints ──
section("System Admin Console")
cookies = login("SYSADMIN2026")
if cookies:
    get("/api/system/overview", cookies)
    get("/api/system/health", cookies)
    get("/api/system/version", cookies)
    get("/api/system/scope-map", cookies)
    get("/api/system/audit-summary", cookies)
    get("/api/system/backups", cookies)
    post("/api/system/maintenance/enable",
         {"confirm": "ENABLE MAINTENANCE", "message": "Smoke test"}, cookies)
    get("/api/system/maintenance", cookies)
    post("/api/system/maintenance/disable", {}, cookies)
else:
    check("System admin login", False, "Could not log in")

# ── Scope denial ──
section("Scope denial")
sqn_cookies = login("ADMIN703")
if sqn_cookies:
    r = requests.get(f"{BASE}/api/system/overview", cookies=sqn_cookies)
    check("SQN admin cannot access /system/overview", r.status_code == 403)
    r = requests.get(f"{BASE}/api/system/health", cookies=sqn_cookies)
    check("SQN admin cannot access /system/health", r.status_code == 403)

# ── Organisations ──
section("Organisations")
nat_cookies = login("ADMINNATIONAL")
if nat_cookies:
    get("/api/wings", nat_cookies)
    get("/api/squadrons", nat_cookies)

# ── Accounts ──
section("Account Management")
if sqn_cookies:
    get("/api/accounts", sqn_cookies)

# ── Curriculum ──
section("Curriculum")
if sqn_cookies:
    get("/api/curriculum", sqn_cookies)

# ── Planning ──
section("Planning")
if sqn_cookies:
    get("/api/planning/years", sqn_cookies)

# ── Audit ──
section("Audit")
aud_cookies = login("AUDITOR2026")
if aud_cookies:
    get("/api/system/audit-summary", aud_cookies)
    r = requests.get(f"{BASE}/api/system/overview", cookies=aud_cookies)
    check("Auditor cannot access /system/overview", r.status_code == 403)

# ── Summary ──
print()
for line in RESULTS:
    print(line)
print()
print(f"  Passed: {PASS}  Failed: {FAIL}")
print()
if FAIL == 0:
    print("  All smoke tests passed.")
else:
    print(f"  {FAIL} test(s) FAILED — review above.")
    sys.exit(1)
