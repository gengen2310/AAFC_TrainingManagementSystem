#!/bin/sh
# Staging entrypoint: run migrations, seed on first start, then serve.
set -e

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

USER_COUNT=$(python -c "
from app.database import SessionLocal
from app.models import User
db = SessionLocal()
count = db.query(User).count()
db.close()
print(count)
")

if [ "$USER_COUNT" = "0" ]; then
  echo "[entrypoint] Empty database — running staging seed (codes printed below)..."
  python -m app.seeds.staging_seed
else
  echo "[entrypoint] Database already has $USER_COUNT users — skipping seed."
fi

echo "[entrypoint] Starting gunicorn (2 workers)..."
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8000 \
  -w 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
