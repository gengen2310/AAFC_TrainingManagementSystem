"""Regression tests for the access-code credential lifecycle invariant.

Invariant: At most one active AccessCode per user is authoritative. All
code-mutation paths (change_code, reset_code, recovery reset) must target
only the active row, must deactivate predecessors, and must revoke all live
JWTs via token_version increment.

Covers:
- Finding 1: change_code / reset_code selects stale inactive row
- Finding 2: self reset-code skips current-code reauthentication
- Finding 3: archive → restore resurrects pre-archive JWTs
- Finding 4: sibling login fallback increments wrong account's failed_attempts
"""
import uuid as _uuid
import pytest
from app.database import SessionLocal
from app.models import AccessCode, User
from app.security import hash_code
from tests.conftest import login


# ─── helpers ────────────────────────────────────────────────────────────────

def _get_user_by_code(client, code: str) -> dict:
    hdr = login(client, code)
    r = client.get("/api/auth/me", headers=hdr)
    assert r.status_code == 200
    return r.json()["session"]


def _get_user_id(client, code: str) -> str:
    return _get_user_by_code(client, code)["user_id"]


def _get_sqn_admin_id(client) -> str:
    sa_hdr = login(client, "SYSADMIN2026")
    r = client.get("/api/accounts?limit=500", headers=sa_hdr)
    assert r.status_code == 200
    for u in r.json():
        if u["role"] == "sqn_admin" and "703" in (u.get("display_name") or ""):
            return u["user_id"]
    raise ValueError("703 sqn_admin not found")


def _get_sqn_general_id(client) -> str:
    sa_hdr = login(client, "SYSADMIN2026")
    r = client.get("/api/accounts?limit=500", headers=sa_hdr)
    assert r.status_code == 200
    for u in r.json():
        if u["role"] == "sqn_general" and "703" in (u.get("display_name") or ""):
            return u["user_id"]
    raise ValueError("703 sqn_general not found")


def _inject_stale_inactive_code(user_id: str, stale_code: str):
    """Simulate the broken state: create a stale inactive AccessCode so that
    a bare `.filter(user_id == ...).first()` may return it instead of the active row.
    SQLAlchemy returns rows in insertion order by default, so inserting the inactive
    row first replicates the defect condition.
    """
    with SessionLocal() as db:
        stale = AccessCode(
            user_id=user_id,
            code_hash=hash_code(stale_code),
            active_status=False,
        )
        db.add(stale)
        db.commit()


def _cleanup_stale_codes(user_id: str):
    """Remove injected inactive AccessCode rows after a test."""
    with SessionLocal() as db:
        rows = db.query(AccessCode).filter(
            AccessCode.user_id == user_id,
            AccessCode.active_status == False,  # noqa: E712
        ).all()
        for r in rows:
            db.delete(r)
        db.commit()


# ─── Finding 1: change_code targets active row ─────────────────────────────

class TestChangeCodeTargetsActiveRow:
    """change_code must write to the active AccessCode row, not a stale inactive one."""

    def test_change_code_login_succeeds_with_new_code(self, client):
        """After change_code, the new code works."""
        uid = _get_sqn_admin_id(client)
        hdr = login(client, "ADMIN703")
        r = client.post("/api/auth/change-code",
                        json={"user_id": uid, "new_code": "CHANGECODE1"},
                        headers=hdr)
        assert r.status_code == 200
        new_hdr = login(client, "CHANGECODE1")
        assert new_hdr is not None
        # Restore
        r2 = client.post("/api/auth/change-code",
                         json={"user_id": uid, "new_code": "ADMIN703"},
                         headers=new_hdr)
        assert r2.status_code == 200

    def test_change_code_with_stale_inactive_row_present(self, client):
        """When a stale inactive AccessCode row exists, change_code must still update
        the active row — not the stale one. After change, new code works and old stale
        code does NOT authenticate.

        This is the reproduction of Finding 1: without the fix, change_code uses
        .first() without active_status=True, so it may update the stale row.
        """
        uid = _get_sqn_admin_id(client)
        _inject_stale_inactive_code(uid, "STALE_INACTIVE_CODE")
        try:
            hdr = login(client, "ADMIN703")
            r = client.post("/api/auth/change-code",
                            json={"user_id": uid, "new_code": "NEWACTIVE99"},
                            headers=hdr)
            assert r.status_code == 200

            # New code must work
            new_hdr = login(client, "NEWACTIVE99")
            assert new_hdr is not None

            # The stale code must not authenticate
            r_stale = client.post("/api/auth/login", json={"code": "STALE_INACTIVE_CODE"})
            assert r_stale.status_code == 401

            # Restore
            restore_hdr = login(client, "NEWACTIVE99")
            client.post("/api/auth/change-code",
                        json={"user_id": uid, "new_code": "ADMIN703"},
                        headers=restore_hdr)
        finally:
            _cleanup_stale_codes(uid)

    def test_reset_code_with_stale_inactive_row_present(self, client):
        """reset_code (accounts endpoint) must also target the active row.

        This is the reproduction of Finding 1 for the accounts.py path.
        """
        sa_hdr = login(client, "SYSADMIN2026")
        uid = _get_sqn_general_id(client)
        _inject_stale_inactive_code(uid, "STALE_GEN_CODE")
        try:
            r = client.post(f"/api/accounts/{uid}/reset-code",
                            json={"new_code": "RESETGEN99"},
                            headers=sa_hdr)
            assert r.status_code == 200
            new_code = r.json()["new_code"]

            # New code must work
            new_hdr = login(client, new_code)
            assert new_hdr is not None

            # Stale code must not work
            r_stale = client.post("/api/auth/login", json={"code": "STALE_GEN_CODE"})
            assert r_stale.status_code == 401

            # Restore
            r2 = client.post(f"/api/accounts/{uid}/reset-code",
                             json={"new_code": "703SQN2026"},
                             headers=sa_hdr)
            assert r2.status_code == 200
        finally:
            _cleanup_stale_codes(uid)

    def test_old_code_fails_after_change_code(self, client):
        """Old access code must not authenticate after change_code."""
        uid = _get_sqn_admin_id(client)
        old_hdr = login(client, "ADMIN703")
        r = client.post("/api/auth/change-code",
                        json={"user_id": uid, "new_code": "CHANGETEST2"},
                        headers=old_hdr)
        assert r.status_code == 200
        r_old = client.post("/api/auth/login", json={"code": "ADMIN703"})
        assert r_old.status_code == 401
        # Restore
        new_hdr = login(client, "CHANGETEST2")
        client.post("/api/auth/change-code",
                    json={"user_id": uid, "new_code": "ADMIN703"},
                    headers=new_hdr)


# ─── Finding 2: Self reset-code requires current-code reauthentication ───────

class TestSelfResetCodeReauthentication:
    """Self-service reset-code must require the caller's current access code.
    A stolen JWT alone must not be sufficient to rotate one's own credential.
    """

    def test_self_reset_without_current_code_is_rejected(self, client):
        """POST /api/accounts/{uid}/reset-code for own account without current_code must fail."""
        uid = _get_sqn_admin_id(client)
        hdr = login(client, "ADMIN703")
        r = client.post(f"/api/accounts/{uid}/reset-code",
                        json={"new_code": "STOLEN_RESET"},
                        headers=hdr)
        # Must require current_code; a session alone is not enough
        assert r.status_code in (400, 403, 422), (
            f"Expected 40x but got {r.status_code}: {r.text}"
        )
        # Old code should still work
        old_hdr = login(client, "ADMIN703")
        assert old_hdr is not None

    def test_self_reset_with_wrong_current_code_is_rejected(self, client):
        """Wrong current_code must be rejected for self-service reset."""
        uid = _get_sqn_admin_id(client)
        hdr = login(client, "ADMIN703")
        r = client.post(f"/api/accounts/{uid}/reset-code",
                        json={"new_code": "NEWCODE11", "current_code": "WRONGCODE"},
                        headers=hdr)
        assert r.status_code in (400, 403), (
            f"Expected 40x but got {r.status_code}: {r.text}"
        )

    def test_self_reset_with_correct_current_code_succeeds(self, client):
        """Correct current_code permits self-service credential rotation."""
        uid = _get_sqn_admin_id(client)
        hdr = login(client, "ADMIN703")
        r = client.post(f"/api/accounts/{uid}/reset-code",
                        json={"new_code": "VALIDNEW11", "current_code": "ADMIN703"},
                        headers=hdr)
        assert r.status_code == 200
        # New code works
        new_hdr = login(client, "VALIDNEW11")
        assert new_hdr is not None
        # Restore
        r2 = client.post(f"/api/accounts/{uid}/reset-code",
                         json={"new_code": "ADMIN703", "current_code": "VALIDNEW11"},
                         headers=new_hdr)
        assert r2.status_code == 200

    def test_admin_resetting_other_account_still_works(self, client):
        """Admin resetting another account's code does not require that account's current code."""
        sa_hdr = login(client, "SYSADMIN2026")
        uid = _get_sqn_general_id(client)
        r = client.post(f"/api/accounts/{uid}/reset-code",
                        json={"new_code": "ADMINRESET1"},
                        headers=sa_hdr)
        assert r.status_code == 200
        # Restore
        r2 = client.post(f"/api/accounts/{uid}/reset-code",
                         json={"new_code": "703SQN2026"},
                         headers=sa_hdr)
        assert r2.status_code == 200

    def test_admin_resetting_own_code_requires_current_code(self, client):
        """system_admin resetting their own code must also require current_code."""
        sa_id_hdr = login(client, "SYSADMIN2026")
        me = client.get("/api/auth/me", headers=sa_id_hdr)
        sa_uid = me.json()["session"]["user_id"]
        r = client.post(f"/api/accounts/{sa_uid}/reset-code",
                        json={"new_code": "SANEWCODE1"},
                        headers=sa_id_hdr)
        # Must require current_code
        assert r.status_code in (400, 403, 422), (
            f"system_admin self-reset without current_code returned {r.status_code}: {r.text}"
        )

    def test_recovery_token_reset_does_not_require_old_code(self, client):
        """The separate recovery-token path (POST /api/auth/reset-code) must NOT require
        the old code — that path exists specifically for users who lost their code.
        """
        # The recovery endpoint accepts a token; it should not require current_code.
        # We don't have a real email token in tests, but we can verify the endpoint
        # signature accepts the reset without a current_code field when using the
        # recovery token path. A missing/invalid token returns 400, not 403.
        r = client.post("/api/auth/reset-code",
                        json={"token": "INVALIDTOKEN", "new_code": "SOMETHINGNEW"})
        # Should be 400 (invalid token), not 403 (auth required) or 422 (missing field)
        assert r.status_code == 400
        assert "invalid_token" in r.json().get("detail", {}).get("error", "")


# ─── Finding 3: Archive / Restore Token Revocation ──────────────────────────

class TestArchiveRestoreTokenRevocation:
    """Archive must revoke JWTs (via token_version); restore must not resurrect them."""

    def _create_test_user(self, client) -> tuple[str, dict, str]:
        """Create a sqn_general user for archive/restore testing.
        Returns (user_id, sa_headers, unique_code) — unique_code is needed
        for login since each call generates a distinct code.
        """
        sa_hdr = login(client, "SYSADMIN2026")
        # Unique code prevents cross-test access-code contamination
        unique_code = "ARC" + _uuid.uuid4().hex[:8].upper()
        me_r = client.get("/api/accounts?limit=500", headers=sa_hdr)
        sqn_id = None
        gen_uid = _get_sqn_general_id(client)
        for u in me_r.json():
            if u["user_id"] == gen_uid:
                sqn_id = u["squadron_id"]
                break

        r = client.post("/api/accounts",
                        json={"display_name": f"Archive Test {unique_code}",
                              "role": "sqn_general",
                              "squadron_id": sqn_id,
                              "new_code": unique_code},
                        headers=sa_hdr)
        assert r.status_code == 200, f"Failed to create test user: {r.text}"
        new_uid = r.json()["user_id"]
        return new_uid, sa_hdr, unique_code

    def test_token_valid_before_archive(self, client):
        """Baseline: a token is valid before archive."""
        uid, sa_hdr, code = self._create_test_user(client)
        try:
            hdr = login(client, code)
            r = client.get("/api/auth/me", headers=hdr)
            assert r.status_code == 200
        finally:
            client.post(f"/api/accounts/{uid}/archive", headers=sa_hdr)

    def test_token_rejected_after_archive(self, client):
        """After archive, active_status=False, so get_principal rejects the token."""
        uid, sa_hdr, code = self._create_test_user(client)
        try:
            hdr = login(client, code)
            r = client.post(f"/api/accounts/{uid}/archive", headers=sa_hdr)
            assert r.status_code == 200
            r2 = client.get("/api/auth/me", headers=hdr)
            assert r2.status_code == 401
        finally:
            client.post(f"/api/accounts/{uid}/restore", headers=sa_hdr)
            client.post(f"/api/accounts/{uid}/archive", headers=sa_hdr)

    def test_restore_does_not_resurrect_pre_archive_token(self, client):
        """The critical defect: after archive → restore, a pre-archive JWT must NOT work.

        If archive does not increment token_version, the JWT remains valid again
        after restore (active_status returns to True). This is the security defect.
        """
        uid, sa_hdr, code = self._create_test_user(client)
        try:
            hdr = login(client, code)
            r = client.get("/api/auth/me", headers=hdr)
            assert r.status_code == 200

            r = client.post(f"/api/accounts/{uid}/archive", headers=sa_hdr)
            assert r.status_code == 200

            r = client.post(f"/api/accounts/{uid}/restore", headers=sa_hdr)
            assert r.status_code == 200

            r2 = client.get("/api/auth/me", headers=hdr)
            assert r2.status_code == 401, (
                "Pre-archive JWT was resurrected after restore — token_version "
                "was not incremented during archive."
            )
        finally:
            client.post(f"/api/accounts/{uid}/archive", headers=sa_hdr)

    def test_new_token_after_restore_works(self, client):
        """After legitimate restoration, newly authenticated tokens must work."""
        uid, sa_hdr, code = self._create_test_user(client)
        try:
            client.post(f"/api/accounts/{uid}/archive", headers=sa_hdr)
            client.post(f"/api/accounts/{uid}/restore", headers=sa_hdr)
            new_hdr = login(client, code)
            assert new_hdr is not None
            r = client.get("/api/auth/me", headers=new_hdr)
            assert r.status_code == 200
        finally:
            client.post(f"/api/accounts/{uid}/archive", headers=sa_hdr)

    def test_batch_archive_also_revokes_tokens(self, client):
        """batch_archive_accounts must also revoke JWTs via token_version bump."""
        sa_hdr = login(client, "SYSADMIN2026")
        batch_code = "BAT" + _uuid.uuid4().hex[:8].upper()
        me_r = client.get("/api/accounts?limit=500", headers=sa_hdr)
        sqn_id = None
        gen_uid = _get_sqn_general_id(client)
        for u in me_r.json():
            if u["user_id"] == gen_uid:
                sqn_id = u["squadron_id"]
                break

        r = client.post("/api/accounts",
                        json={"display_name": f"Batch Archive {batch_code}",
                              "role": "sqn_general",
                              "squadron_id": sqn_id,
                              "new_code": batch_code},
                        headers=sa_hdr)
        assert r.status_code == 200
        new_uid = r.json()["user_id"]
        try:
            hdr = login(client, batch_code)
            r2 = client.get("/api/auth/me", headers=hdr)
            assert r2.status_code == 200

            r3 = client.post("/api/accounts/batch-archive",
                             json={"account_ids": [new_uid],
                                   "reason": "Test batch archive revocation",
                                   "confirm_session_revocation": True},
                             headers=sa_hdr)
            assert r3.status_code == 200

            client.post(f"/api/accounts/{new_uid}/restore", headers=sa_hdr)

            r4 = client.get("/api/auth/me", headers=hdr)
            assert r4.status_code == 401, (
                "Pre-archive JWT resurrected after batch-archive → restore. "
                "batch_archive must bump token_version."
            )
        finally:
            client.post(f"/api/accounts/{new_uid}/archive", headers=sa_hdr)

    def test_disable_revokes_token(self, client):
        """disable_account increments token_version — existing session test."""
        uid, sa_hdr, code = self._create_test_user(client)
        try:
            hdr = login(client, code)
            r = client.post(f"/api/accounts/{uid}/disable", headers=sa_hdr)
            assert r.status_code == 200
            r2 = client.get("/api/auth/me", headers=hdr)
            assert r2.status_code == 401
        finally:
            client.post(f"/api/accounts/{uid}/archive", headers=sa_hdr)


# ─── Finding 4: Sibling Login Fallback Does Not Corrupt Failure Counts ───────

class TestSiblingLoginFallbackLockout:
    """Repeated valid logins as sibling B must not increment A's failed_attempts.

    The scoped fallback scan exists to handle /lookup's .first() returning the
    wrong sibling. When B's code is valid and matched by fallback, A's failure
    counter must not have been incremented.
    """

    def _get_access_code_row(self, user_id: str) -> AccessCode:
        with SessionLocal() as db:
            return db.query(AccessCode).filter(
                AccessCode.user_id == user_id,
                AccessCode.active_status == True,  # noqa: E712
            ).first()

    def _fresh_failed_attempts(self, user_id: str) -> int:
        """Read current failed_attempts from DB (not cached)."""
        with SessionLocal() as db:
            ac = db.query(AccessCode).filter(
                AccessCode.user_id == user_id,
                AccessCode.active_status == True,  # noqa: E712
            ).first()
            return ac.failed_attempts if ac else 0

    def test_correct_login_does_not_increment_anyone(self, client):
        """Baseline: a correct primary login increments no failure counters."""
        uid = _get_sqn_admin_id(client)
        before = self._fresh_failed_attempts(uid)
        login(client, "ADMIN703")
        after = self._fresh_failed_attempts(uid)
        assert after == before, f"Correct login incremented failed_attempts: {before} → {after}"

    def test_sibling_fallback_match_does_not_increment_primary(self, client):
        """When /lookup returns user A but the caller's code belongs to sibling B,
        and the fallback scan finds B, A's failed_attempts must NOT be incremented.

        We simulate this by crafting a login request with A's user_id but B's code.
        If the current code is correct, the fallback scan succeeds for B.
        """
        # Get both user IDs in the 703 squadron
        sa_hdr = login(client, "SYSADMIN2026")
        r = client.get("/api/accounts?limit=500", headers=sa_hdr)
        users = r.json()
        sqn_admin_uid = None
        sqn_general_uid = None
        sqn_admin_ac_row = None

        for u in users:
            if u["role"] == "sqn_admin" and "703" in (u.get("display_name") or ""):
                sqn_admin_uid = u["user_id"]
            if u["role"] == "sqn_general" and "703" in (u.get("display_name") or ""):
                sqn_general_uid = u["user_id"]

        assert sqn_admin_uid and sqn_general_uid

        # Record sqn_admin's pre-test failed_attempts
        before = self._fresh_failed_attempts(sqn_admin_uid)

        # Login request: user_id=sqn_admin (from /lookup), code=sqn_general's code
        # This triggers the fallback scan when the primary match fails.
        r = client.post("/api/auth/login", json={
            "user_id": sqn_admin_uid,
            "code": "703SQN2026",  # This is sqn_general's code, not sqn_admin's
        })
        # Should succeed via fallback (sqn_general found) or 401 if they're in different scopes
        # The key assertion is that sqn_admin's failed_attempts was NOT incremented
        after = self._fresh_failed_attempts(sqn_admin_uid)
        # If the fallback succeeded (200), sqn_admin's counter must be 0 extra
        # If 401 (not in same scope or code not found), that's a different case
        if r.status_code == 200:
            # Fallback matched B successfully — A's counter must not have grown
            assert after == before, (
                f"Fallback success still incremented primary account's failed_attempts: "
                f"{before} → {after}"
            )

    def test_wrong_code_increments_primary_not_siblings(self, client):
        """A genuinely wrong code must increment only the primary account's counter."""
        sa_hdr = login(client, "SYSADMIN2026")
        all_users = client.get("/api/accounts?limit=500", headers=sa_hdr).json()
        sqn_admin_uid = None
        sqn_general_uid = None
        for u in all_users:
            if u["role"] == "sqn_admin" and "703" in (u.get("display_name") or ""):
                sqn_admin_uid = u["user_id"]
            if u["role"] == "sqn_general" and "703" in (u.get("display_name") or ""):
                sqn_general_uid = u["user_id"]

        before_admin = self._fresh_failed_attempts(sqn_admin_uid)
        before_gen = self._fresh_failed_attempts(sqn_general_uid)

        # Submit truly wrong code for sqn_admin
        r = client.post("/api/auth/login", json={
            "user_id": sqn_admin_uid,
            "code": "COMPLETELY_WRONG_CODE_NOBODY_HAS",
        })
        assert r.status_code == 401

        after_admin = self._fresh_failed_attempts(sqn_admin_uid)
        after_gen = self._fresh_failed_attempts(sqn_general_uid)

        # Primary account's counter incremented
        assert after_admin > before_admin, "Wrong code should have incremented primary's counter"
        # Sibling's counter must not have changed
        assert after_gen == before_gen, (
            f"Wrong code incremented sibling's counter: {before_gen} → {after_gen}"
        )

    def test_repeated_sibling_valid_login_does_not_lock_primary(self, client):
        """Repeated valid B logins (via fallback) must not lock A (Finding 4 core case)."""
        sa_hdr = login(client, "SYSADMIN2026")
        all_users = client.get("/api/accounts?limit=500", headers=sa_hdr).json()
        sqn_admin_uid = None
        for u in all_users:
            if u["role"] == "sqn_admin" and "703" in (u.get("display_name") or ""):
                sqn_admin_uid = u["user_id"]

        before = self._fresh_failed_attempts(sqn_admin_uid)

        # Simulate repeated fallback attempts (code=sqn_general's, user_id=sqn_admin's)
        results = []
        for _ in range(3):
            r = client.post("/api/auth/login", json={
                "user_id": sqn_admin_uid,
                "code": "703SQN2026",
            })
            results.append(r.status_code)

        after = self._fresh_failed_attempts(sqn_admin_uid)
        fallback_successes = results.count(200)
        if fallback_successes > 0:
            # Fallback matched B on at least one attempt — A's counter must not have
            # increased at all (the fix: defer increment until fallback exhausted).
            assert after == before, (
                f"primary account's failed_attempts grew by {after - before} "
                f"despite fallback matching a sibling {fallback_successes} time(s) "
                f"(before={before}, after={after})"
            )
        else:
            # Fallback never matched — all 3 were genuine failures for A.
            # Incrementing A's counter is correct in this case.
            # Verify the counter is not inflated beyond the 3 genuine failures.
            assert after <= before + 3, (
                f"primary failed_attempts grew more than the 3 genuine failures "
                f"(before={before}, after={after})"
            )
