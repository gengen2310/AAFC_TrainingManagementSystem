"""Break-glass reset tests (spec 2026-08-29, plan Task 5)."""
import sys
import unittest.mock
import pytest

from app.database import SessionLocal
from app.models import AccessCode, AuditLog, User
from app.security import hash_code


def _sa_user(db):
    return db.query(User).filter(User.role == "system_admin").first()


# ── guard: --i-understand required ──────────────────────────────────────────

def test_main_refuses_without_i_understand(capsys):
    from scripts.breakglass_reset_sa import main
    with unittest.mock.patch.object(
        sys, "argv", ["breakglass_reset_sa", "--user-code", "System Admin"]
    ):
        rc = main()
    assert rc == 2
    captured = capsys.readouterr()
    assert "Refusing" in captured.err


# ── reset_system_admin function-level tests ──────────────────────────────────

def test_refuses_unknown_display_name():
    from scripts.breakglass_reset_sa import reset_system_admin
    db = SessionLocal()
    try:
        with pytest.raises(SystemExit, match="No system_admin found"):
            reset_system_admin(db, "Nobody Here At All")
    finally:
        db.rollback()
        db.close()


def test_refuses_non_system_admin_display_name():
    """A display_name that exists but belongs to a non-system_admin is rejected."""
    from scripts.breakglass_reset_sa import reset_system_admin
    db = SessionLocal()
    try:
        with pytest.raises(SystemExit, match="No system_admin found"):
            reset_system_admin(db, "National Admin")
    finally:
        db.rollback()
        db.close()


def test_success_deactivates_codes_clears_lockout_bumps_version_writes_audit():
    """Uses a dedicated throwaway system_admin to avoid mutating the shared seed user."""
    from scripts.breakglass_reset_sa import reset_system_admin
    from app.database import utcnow
    from app.models.organisations import NationalEntity
    from app.security import generate_code, hash_code
    db = SessionLocal()
    try:
        nat = db.query(NationalEntity).first()
        assert nat is not None

        # Create a dedicated user for this test so the shared seed "System Admin"
        # is never touched. reset_system_admin calls db.commit() internally.
        tmp_name = "BreakglassTestOnly"
        tmp = User(display_name=tmp_name, role="system_admin", national_id=nat.id,
                   active_status=True, token_version=3)
        db.add(tmp)
        db.flush()

        plain = generate_code(12)
        ac1 = AccessCode(user_id=tmp.id, code_hash=hash_code(plain),
                         active_status=True, failed_attempts=5)  # simulate lockout
        db.add(ac1)
        db.commit()

        token_version_before = 3
        uid, new_code = reset_system_admin(db, tmp_name)

        # Exactly one active code: the new one.
        active_codes = db.query(AccessCode).filter(
            AccessCode.user_id == tmp.id, AccessCode.active_status == True
        ).all()
        assert len(active_codes) == 1

        # The new code verifies correctly.
        from app.security import verify_code
        assert verify_code(new_code, active_codes[0].code_hash)

        # The old code's lockout was cleared (failed_attempts reset to 0).
        db.refresh(ac1)
        assert ac1.failed_attempts == 0

        # token_version bumped.
        db.refresh(tmp)
        assert tmp.token_version == token_version_before + 1

        # Audit row has no principal.
        row = db.query(AuditLog).filter(
            AuditLog.object_id == uid,
            AuditLog.action == "breakglass_reset",
        ).order_by(AuditLog.timestamp.desc()).first()
        assert row is not None
        assert row.user_id is None

    finally:
        # Archive the throwaway user so the shared test DB is clean.
        try:
            tmp_obj = db.query(User).filter(User.display_name == "BreakglassTestOnly").first()
            if tmp_obj:
                tmp_obj.is_archived = True
                tmp_obj.active_status = False
                db.commit()
        except Exception:
            db.rollback()
        db.close()
