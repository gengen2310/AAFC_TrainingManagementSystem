# Security model
See the root `SECURITY.md` for the full threat model, controls, limitations and the
production hardening checklist. In short: hashed access codes, JWT in HTTP-only cookies,
server-side RBAC + tenancy (IDOR-tested), Proxy/Intervention with mandatory reason + audit,
append-only audit log, formula-injection neutralisation on import, security headers, CORS
lockdown, generic 500s.

---

## V6 — Access-code security invariants (backend-enforced)

These invariants are tested in `backend/tests/test_accounts.py` (42 tests).

| Invariant | Enforcement |
|---|---|
| `code_hash` never returned by any API endpoint | `_account_out()` serialiser excludes it; no endpoint bypasses this |
| Existing plaintext codes never returned by any endpoint | Only `new_code` (one-time) is ever returned |
| `new_code` returned exactly once — in the create or reset-code response | After that point the code cannot be retrieved; it is stored only as a hash |
| Codes stored as PBKDF2-SHA256 hashes (passlib) only | `hash_code()` in `security.py`; raw codes never persisted |
| Codes never stored in frontend JS, localStorage, or sessionStorage | Verified: 0 uses in `connected-frontend/index.html` |
| Flight assignment does not expand scope or permissions | `_scope_type()` check on flight write; RBAC unchanged after assignment |
| All account and flight mutations audited | `audit()` call in every write endpoint before return |
| Actor cannot disable their own account | 400 `cannot_disable_self` if `uid == p.user_id` |
| SQN admin cannot create accounts outside own squadron | 403 `out_of_scope` if `sqn_id != p.squadron_id` |
| Wing admin cannot create accounts outside own wing | 403 `out_of_scope` if sqn's `wing_id != p.wing_id` |

## V6 — `_CREATE_AUTHORITY` map

```python
_CREATE_AUTHORITY = {
    "system_admin":   {"system_admin","national_admin","national_viewer","auditor",
                       "wing_admin","wing_viewer","sqn_admin","sqn_general"},
    "national_admin": {"national_admin","national_viewer","auditor",
                       "wing_admin","wing_viewer","sqn_admin","sqn_general"},
    "wing_admin":     {"wing_viewer","sqn_admin","sqn_general"},
    "sqn_admin":      {"sqn_general"},
}
```

Roles not in this map (`national_viewer`, `wing_viewer`, `sqn_general`, `auditor`) cannot create any accounts.

## V6 — `_WRITE_BLOCKED` fast-path

```python
_WRITE_BLOCKED = ("sqn_general", "wing_viewer", "national_viewer", "auditor")
```

Any account write request from these roles is rejected 403 before any scope check runs.
