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

# Despite this script's filename, both staging and production build from the
# same backend/Dockerfile and run this exact entrypoint (confirmed via each
# environment's Railway service config) -- GUNICORN_WORKERS defaults to the
# existing value (2) so production's behaviour is unchanged unless this env
# var is explicitly set. If raised, DB_POOL_SIZE/DB_POOL_MAX_OVERFLOW (see
# app/config.py) must be reduced proportionally so
# workers * (pool_size + max_overflow) stays safely under the target
# Postgres's max_connections -- this script does not calculate that for you.
WORKERS="${GUNICORN_WORKERS:-2}"
echo "[entrypoint] Starting gunicorn ($WORKERS workers)..."
exec gunicorn app.main:app \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8000 \
    -w "$WORKERS" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
