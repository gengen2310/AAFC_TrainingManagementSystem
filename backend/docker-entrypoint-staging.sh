#!/bin/sh
# Staging container entrypoint.
# Runs Alembic migrations, bootstraps system_admin on first start, then serves.
set -e

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head
echo "[entrypoint] Migrations complete."

# Bootstrap only when no system_admin exists.
# The seed is idempotent and reads STAGING_BOOTSTRAP_SYSADMIN_CODE from env.
# It produces no plaintext secrets in any log output.
SYSADMIN_COUNT=$(python -c "
from app.database import SessionLocal
from app.models import User
db = SessionLocal()
n = db.query(User).filter_by(role='system_admin').count()
db.close()
print(n)
")

if [ "$SYSADMIN_COUNT" = "0" ]; then
    echo "[entrypoint] No system_admin found — running bootstrap seed..."
    python -m app.seeds.staging_seed
else
    echo "[entrypoint] system_admin already exists — skipping bootstrap."
fi

echo "[entrypoint] Starting gunicorn (2 workers)..."
exec gunicorn app.main:app \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8000 \
    -w 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
