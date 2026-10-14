"""S-D hardening (2026-10-11): creating the first System Admin is audited.

staging_seed creates a system_admin from STAGING_BOOTSTRAP_SYSADMIN_CODE
whenever none exists. It forces a code change and tells the operator to
remove the variables, but wrote no audit row, so an account created this way
(including a re-run after every System Admin had been deleted) left no trace
in the audit log. Runs in a subprocess on a fresh SQLite file: the suite's
shared DB already has a System Admin.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = r'''
import json
from app.database import Base, engine, SessionLocal
import app.models  # noqa
Base.metadata.create_all(engine)
from app.seeds.staging_seed import staging_seed
from app.models import AuditLog, User
staging_seed(); staging_seed()          # second run must be a no-op
db = SessionLocal()
rows = db.query(AuditLog).filter(AuditLog.action == "system_admin_bootstrapped").all()
admins = db.query(User).filter(User.role == "system_admin").all()
print(json.dumps({"rows": len(rows), "admins": len(admins),
                  "object_id": rows[0].object_id if rows else None,
                  "admin_id": admins[0].id if admins else None,
                  "new": rows[0].new_value if rows else None}))
'''


def test_bootstrapping_the_first_system_admin_writes_one_audit_row():
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp}/boot.db", "ENVIRONMENT": "test",
               "STAGING_BOOTSTRAP_SYSADMIN_CODE": "BOOT-CODE-0001-XYZ",
               "STAGING_BOOTSTRAP_SYSADMIN_RECOVERY_EMAIL": "boot@example.org"}
        out = subprocess.run([sys.executable, "-c", SCRIPT], cwd=BACKEND, env=env,
                             capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, out.stderr[-2000:]
        res = json.loads(out.stdout.strip().splitlines()[-1])
    assert res["admins"] == 1
    assert res["rows"] == 1
    assert res["object_id"] == res["admin_id"]
    assert "BOOT-CODE" not in (res["new"] or "")
