# Account Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A System Administrator who loses their access code can regain access without a hard-coded secret, a plaintext code, or an unauthenticated reset endpoint.

**Architecture:** Assembled from parts that already exist. Session invalidation reuses `User.token_version` (the JWT carries `tv`; `dependencies.py:117` rejects a mismatch). Mail reuses `app/email_service.py`. Lockout and audit are untouched. Only two new things exist: four `User` columns and a `recovery_tokens` table.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, passlib (codes), hashlib SHA-256 (tokens), smtplib.

**Spec:** `docs/superpowers/specs/2026-08-29-account-recovery-design.md`

## Global Constraints

- Plaintext access codes are never stored, logged or emailed.
- Plaintext recovery tokens are never stored or logged. `token_hash` is SHA-256.
- `POST /api/auth/forgot-code` returns one byte-identical body for every outcome.
- Recovery never applies to archived or disabled accounts.
- A missing recovery email must never block login.
- Token expiry: **20 minutes** (reset), **24 hours** (email verification).
- Recovery-enabled roles: `system_admin`, `national_admin`, `wing_admin`, `sqn_admin`.
- Every new endpoint writes an audit row.

---

### Task 1: Data model and migration

**Files:**
- Modify: `backend/app/models/organisations.py` (class `User`)
- Create: `backend/app/models/recovery.py`
- Create: `backend/alembic/versions/<rev>_v59_account_recovery.py`
- Test: `backend/tests/test_account_recovery.py`

**Interfaces:**
- Produces: `User.recovery_email`, `User.recovery_email_verified_at`, `User.recovery_email_updated_at`, `User.recovery_email_updated_by`; model `RecoveryToken` with `user_id`, `token_hash`, `purpose`, `expires_at`, `consumed_at`, `created_ip`.

- [ ] **Step 1: Write the failing test**

```python
def test_user_carries_recovery_email_fields():
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.role == "system_admin").first()
        assert u.recovery_email is None
        assert u.recovery_email_verified_at is None
    finally:
        db.close()
```

- [ ] **Step 2: Run it and watch it fail** — `AttributeError: recovery_email`
- [ ] **Step 3: Add the columns**

```python
    # Recovery channel. Verified only when recovery_email_verified_at is set;
    # an unverified address is never used to send a reset link.
    recovery_email: Mapped[str | None] = mapped_column(String(254), nullable=True, index=True)
    recovery_email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    recovery_email_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    recovery_email_updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
```

- [ ] **Step 4: Add the token model** in `recovery.py`, `__tablename__ = "recovery_tokens"`.
- [ ] **Step 5: Migration** — `down_revision` = output of `alembic heads`. Adds four columns and the table. No backfill: there is no address to invent.
- [ ] **Step 6: Run tests, update `test_compute_alembic_head.py`, commit.**

---

### Task 2: Token service

**Files:**
- Create: `backend/app/services_recovery.py`
- Test: `backend/tests/test_account_recovery.py`

**Interfaces:**
- Produces: `RECOVERY_ROLES`, `hash_token(raw) -> str`, `mint_token(db, user, purpose, ttl_minutes, ip) -> str`, `consume_token(db, raw, purpose) -> User | None`, `is_recovery_eligible(user) -> bool`.

- [ ] **Step 1: Failing tests** — token is single-use; expired token rejected; a newer token supersedes an older one; unknown token returns None; archived/disabled ineligible.
- [ ] **Step 2: Watch them fail** — `ModuleNotFoundError`
- [ ] **Step 3: Implement**

```python
RECOVERY_ROLES = frozenset({"system_admin", "national_admin", "wing_admin", "sqn_admin"})

def hash_token(raw: str) -> str:
    # SHA-256, not passlib: a 256-bit random token needs no slow KDF, and a
    # salted hash cannot be looked up by value.
    return hashlib.sha256(raw.encode()).hexdigest()

def is_recovery_eligible(u) -> bool:
    return bool(u) and not u.is_archived and u.active_status \
        and u.role in RECOVERY_ROLES \
        and bool(u.recovery_email) and u.recovery_email_verified_at is not None
```

`mint_token` invalidates the user's outstanding unconsumed tokens of the same purpose before inserting. `consume_token` rejects consumed/expired, marks consumed, and returns the user.

- [ ] **Step 4: Run and pass. Commit.**

---

### Task 3: Recovery email set and verify

**Files:**
- Modify: `backend/app/routers/accounts.py`, `backend/app/routers/auth.py`, `backend/app/email_service.py`

**Interfaces:**
- Consumes: `mint_token`, `consume_token`.
- Produces: `POST /api/accounts/{uid}/recovery-email`, `POST /api/auth/verify-recovery-email`, `mask_email(addr) -> str`, `send_mail(to, subject, body) -> bool`.

- [ ] **Step 1: Failing tests** — setting requires the caller's current access code; a wrong code is 403; setting clears verification; verifying sets it; masked in reads; another user cannot read it.
- [ ] **Step 2: Watch them fail**
- [ ] **Step 3: Implement.** `send_mail` returns `False` rather than raising, and logs without the token or address when `SMTP_HOST` is unset.
- [ ] **Step 4: Run and pass. Commit.**

---

### Task 4: Forgot and reset

**Files:**
- Modify: `backend/app/routers/auth.py`

**Interfaces:**
- Produces: `POST /api/auth/forgot-code`, `POST /api/auth/reset-code`.

- [ ] **Step 1: Failing tests**

```python
def test_forgot_code_response_is_identical_for_every_outcome(client):
    bodies = set()
    for payload in [{"email": "verified@example.com"},
                    {"email": "nobody@example.com"},
                    {"email": "archived@example.com"},
                    {"email": "unverified@example.com"}]:
        r = client.post("/api/auth/forgot-code", json=payload)
        assert r.status_code == 200
        bodies.add(r.text)          # the BYTES, not a shape
    assert len(bodies) == 1, bodies
```

Plus: reset replaces the code; the old code stops working; exactly one active
`AccessCode` remains; `token_version` increments; the token cannot be reused.

- [ ] **Step 2: Watch them fail** — 404
- [ ] **Step 3: Implement.** Always 200 with the constant body. Eligible ⇒ mint + send. Ineligible ⇒ do the same work (dummy hash) and send nothing.
- [ ] **Step 4: Run and pass. Commit.**

---

### Task 5: Break-glass script

**Files:**
- Create: `backend/scripts/breakglass_reset_sa.py`
- Test: `backend/tests/test_breakglass.py`

- [ ] **Step 1: Failing tests** — refuses without `--i-understand`; refuses an unknown user; refuses a non-`system_admin`; on success deactivates other codes, clears lockout, bumps `token_version`, writes an audit row with no principal.
- [ ] **Step 2: Watch them fail**
- [ ] **Step 3: Implement.** Prints the code once to stdout; stores only the hash.
- [ ] **Step 4: Run and pass. Commit.**

---

### Task 6: Last System Administrator — disable and delete

**Files:**
- Modify: `backend/app/routers/accounts.py` (`disable_account` ~:629, `delete_account` ~:725)

`_last_active_system_admin_count()` already guards demote (`:456`) and archive
(`:688`). Disable and delete are unguarded.

- [ ] **Step 1: Failing tests** — with exactly one active `system_admin`, disable is 409 and delete is 409; with two, both proceed under normal authority.
- [ ] **Step 2: Watch them fail** — the calls currently succeed
- [ ] **Step 3: Implement**

```python
    if (u.role == "system_admin" and u.active_status
            and _last_active_system_admin_count(db) <= 1):
        raise HTTPException(409, detail={
            "error": "last_active_system_admin",
            "message": "This is the last active System Administrator. Create or "
                       "activate another System Administrator before removing "
                       "this account."})
```

- [ ] **Step 4: Run and pass. Commit.**

---

## Self-review

**Spec coverage.** §4 → T1. §5 → T4. §6 → T4. §7 → T4. §8 → T3. §9 → T3
(`send_mail` boolean). §10 → T5. §11 → T6. §12 → audit calls in T3–T6. §13 → the
tests in each task. §3a's `setup/status` warning is **not** covered by any task —
added as Task 7 below rather than left as a gap.

**Placeholders.** None: every step names its file and shows its code.

**Type consistency.** `hash_token`, `mint_token`, `consume_token`,
`is_recovery_eligible`, `RECOVERY_ROLES`, `send_mail`, `mask_email` are used in
later tasks exactly as Task 2 and Task 3 define them.

---

### Task 7: Surface System Admins without a verified recovery email

**Files:**
- Modify: `backend/app/routers/setup.py`

Spec §3a: existing administrators are not retro-fitted, so the gap must be
visible instead.

- [ ] **Step 1: Failing test** — `GET /api/setup/status` reports
      `system_admins_without_recovery_email` as a count.
- [ ] **Step 2: Watch it fail** — `KeyError`
- [ ] **Step 3: Implement** the count. It is reported, never a blocking step —
      the same mistake the cadet row made.
- [ ] **Step 4: Run and pass. Commit.**
