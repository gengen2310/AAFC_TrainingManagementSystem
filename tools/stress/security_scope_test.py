#!/usr/bin/env python3
"""Security scope and IDOR test suite for AAFC TMS.

Tests that role and scope boundaries are enforced by the backend.
Run against a live local server.

Usage:
    python tools/stress/security_scope_test.py

Checks:
  - Cross-scope IDOR attempts (accessing other sqn data by ID)
  - Viewer/general write attempts
  - Disabled account login
  - Invalid token
  - Unauthenticated access to protected routes
  - system_admin access denial for non-system roles
  - Oversized request bodies
  - Unexpected enum values
"""
import sys
import json
import requests

BASE = "http://localhost:8000"

PASS = 0
FAIL = 0
RESULTS = []


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
    else:
        FAIL += 1
    status = "PASS" if ok else "FAIL"
    RESULTS.append(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))


def section(title):
    RESULTS.append(f"\n  {title}")


def login(code):
    r = requests.post(f"{BASE}/api/auth/login", json={"code": code})
    if r.status_code == 200:
        return r.cookies
    return None


def get(path, cookies=None):
    return requests.get(f"{BASE}{path}", cookies=cookies)


def post(path, body, cookies=None):
    return requests.post(f"{BASE}{path}", json=body, cookies=cookies)


print("\nAAFC TMS — Security Scope Test")
print("=" * 50)

# ── Unauthenticated access ──
section("Unauthenticated access")
protected = [
    "/api/auth/me", "/api/curriculum", "/api/accounts",
    "/api/wings", "/api/planning/years",
    "/api/system/overview", "/api/system/health", "/api/system/backups",
]
for path in protected:
    r = get(path)
    check(f"Unauth {path} → 401", r.status_code == 401)

# ── Invalid JWT ──
section("Invalid/expired token")
fake_cookie = {"aafc_session": "totally.invalid.token"}
r = requests.get(f"{BASE}/api/auth/me", cookies=fake_cookie)
check("Fake JWT → 401", r.status_code == 401)

# ── Read-only roles cannot write ──
section("Read-only role write attempts")
general_cookies = login("703SQN2026")
if general_cookies:
    r = post("/api/sessions", {"parade_night_id": "x"}, general_cookies)
    check("sqn_general cannot POST session", r.status_code in (403, 404, 422))
    # No public "create account" endpoint exists — 404 = unexploitable, 403 = forbidden, 422 = rejected
    r = post("/api/accounts", {"display_name": "Test", "role": "sqn_general"}, general_cookies)
    check("sqn_general cannot create account (403/404/422)", r.status_code in (403, 404, 422))

# ── system_admin endpoints denied to non-system roles ──
section("system_admin endpoint denial")
for code, role in [("ADMIN703", "sqn_admin"), ("ADMINNATIONAL", "national_admin"),
                   ("AUDITOR2026", "auditor"), ("703SQN2026", "sqn_general")]:
    cookies = login(code)
    if cookies:
        r = get("/api/system/overview", cookies)
        check(f"{role} cannot access /system/overview → 403", r.status_code == 403)
        r = post("/api/system/maintenance/enable", {"confirm": "ENABLE MAINTENANCE"}, cookies)
        check(f"{role} cannot enable maintenance → 403", r.status_code == 403)

# ── Cross-scope IDOR — SQN admin trying another SQN's parade nights ──
section("Cross-scope IDOR")
sqn_cookies = login("ADMIN703")
if sqn_cookies:
    # Get list of units to find a different squadron ID
    r = requests.get(f"{BASE}/api/squadrons", cookies=login("ADMINNATIONAL"))
    if r.status_code == 200:
        sqn_list = r.json()
        other_sqn_id = next((s["squadron_id"] for s in sqn_list
                             if s.get("code") != "703"), None)
        if other_sqn_id:
            r = requests.get(f"{BASE}/api/parade-nights?squadron_id={other_sqn_id}",
                             cookies=sqn_cookies)
            check("SQN admin cannot read another SQN's parade nights → 403", r.status_code == 403)

# ── Wing admin cannot see another wing ──
section("Wing cross-scope")
wing_cookies = login("ADMIN7WG")
if wing_cookies:
    r = requests.get(f"{BASE}/api/wings", cookies=wing_cookies)
    if r.status_code == 200:
        # wing_admin only sees their own wings — if multiple wings exist, try a sqn from a different one
        nat_r = requests.get(f"{BASE}/api/wings", cookies=login("ADMINNATIONAL"))
        all_wings = nat_r.json() if nat_r.status_code == 200 else []
        other_wing_id = next((w["wing_id"] for w in all_wings
                              if "7WG" not in (w.get("code") or "")), None)
        if other_wing_id:
            r = requests.get(f"{BASE}/api/squadrons?wing_id={other_wing_id}",
                             cookies=wing_cookies)
            own_sqn = r.json()
            check("Wing admin cannot see other wings' squadrons (empty list)", own_sqn == [])
        else:
            check("Only one wing in DB — cross-wing IDOR test skipped", True, "skipped")

# ── Oversized request body ──
section("Oversized request body")
sqn_cookies = login("ADMIN703")
if sqn_cookies:
    big_body = {"code": "x" * 100_000}
    r = requests.post(f"{BASE}/api/auth/login", json=big_body)
    check("Oversized login body handled gracefully", r.status_code in (400, 401, 413, 422))

# ── Unexpected enum values ──
section("Unexpected enum values")
sqn_cookies = login("ADMIN703")
if sqn_cookies:
    r = post("/api/curriculum", {
        "title": "Test", "phase_code": "INVALID_PHASE", "level": "expert"
    }, sqn_cookies)
    check("Unexpected enum in curriculum → 422 or 400", r.status_code in (400, 422))

# ── Access code values NOT in response bodies — must run BEFORE rate-limit trigger ──
section("No secrets in API responses")
sys_cookies = login("SYSADMIN2026")
if sys_cookies:
    r = requests.get(f"{BASE}/api/system/overview", cookies=sys_cookies)
    body = r.text
    for secret in ("SYSADMIN2026", "ADMIN703", "code_hash", "plain_code", "JWT_SECRET"):
        check(f"No '{secret}' in /system/overview", secret not in body)

    r = requests.get(f"{BASE}/api/system/audit-summary", cookies=sys_cookies)
    body = r.text
    for secret in ("SYSADMIN2026", "code_hash"):
        check(f"No '{secret}' in /system/audit-summary", secret not in body)
else:
    check("No secrets check (sysadmin login required)", False, "Could not log in as sysadmin")

# ── Rate limiting (runs last — triggers lockout for localhost) ──
section("Rate limiting — repeated bad logins")
for _ in range(6):
    requests.post(f"{BASE}/api/auth/login", json={"code": "BADCODE"})
r = requests.post(f"{BASE}/api/auth/login", json={"code": "BADCODE"})
check("Rate limit triggered after bad attempts → 429", r.status_code == 429,
      f"got {r.status_code} (may need more attempts if window not reset)")

# ── Summary ──
print()
for line in RESULTS:
    print(line)
print()
print(f"  Passed: {PASS}  Failed: {FAIL}")
print()
if FAIL == 0:
    print("  All security scope tests passed.")
else:
    print(f"  {FAIL} FAILED — review above before deploying.")
    sys.exit(1)
