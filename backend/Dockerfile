FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary gunicorn
# Debian's own default postgresql-client (15 on bookworm, 17 on trixie) is older
# than production/staging's Postgres server (17.x/18.x) -- pg_dump refuses to dump
# from a server *newer* than itself, so this pulls the newest client (18) from the
# official PGDG apt repository, matching the fix already applied and proven in
# .github/workflows/backup-postgresql.yml for the same class of version mismatch
# (GAP-16/GAP-18). Without this, System Console's "Download PostgreSQL Backup"
# button (system.py's pg_dump subprocess, run inside this same container) would
# hit the identical failure the GitHub Actions workflow was fixed for.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg2 lsb-release \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN chmod +x docker-entrypoint-staging.sh
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health').status==200 else 1)"
CMD ["./docker-entrypoint-staging.sh"]
