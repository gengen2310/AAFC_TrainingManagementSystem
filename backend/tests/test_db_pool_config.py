"""Regression coverage for per-environment DB connection pool sizing
(app/database.py's build_pool_kwargs), added after the staging load test
traced a QueuePool exhaustion to production-sized pool defaults being
applied to staging's differently-constrained Postgres. See
docs/release/qualification_gap_register.md GAP-09.
"""
from app.database import build_pool_kwargs


def test_sqlite_never_receives_pool_kwargs():
    # SQLAlchemy's SQLite driver doesn't support pool_size/max_overflow/pool_timeout.
    assert build_pool_kwargs(True, pool_size=8, max_overflow=4, pool_timeout=30) == {}


def test_postgres_receives_exact_configured_values():
    kwargs = build_pool_kwargs(False, pool_size=8, max_overflow=4, pool_timeout=30)
    assert kwargs == {
        "pool_size": 8,
        "max_overflow": 4,
        "pool_timeout": 30,
        "pool_recycle": 1800,
    }


def test_production_defaults_stay_under_postgres_max_connections():
    """Production's committed defaults (app/config.py) times its 2-worker
    entrypoint default must stay well under Postgres's real, load-tested
    connection ceiling. Production runs on Railway-native Postgres (GAP-18
    fix, 2026-08 -- see deployment/backup-dr.md), not a Supabase Session
    Pooler; an earlier version of this test enforced a stale "15 connections"
    Supabase-pooler premise that no longer applies. The real ceiling is
    Postgres's own max_connections=100 (docs/release/qualification_gap_register.md
    GAP-28/GAP-29) -- GAP-29 documents a real incident where sizing reasoned
    from that stale premise (raising workers/pool sizes without re-checking
    the real constraint) blew past 100 and produced a >50% server error rate
    on staging before being reverted. This assertion keeps meaningful headroom
    under the real ceiling, not just squeaking under the old, wrong number --
    a regression here means someone changed a default without re-checking the
    constraint it was chosen for."""
    from app.config import Settings

    defaults = Settings()
    workers = 2  # docker-entrypoint-staging.sh's GUNICORN_WORKERS default
    kwargs = build_pool_kwargs(
        False, defaults.DB_POOL_SIZE, defaults.DB_POOL_MAX_OVERFLOW, defaults.DB_POOL_TIMEOUT
    )
    total_connections = workers * (kwargs["pool_size"] + kwargs["max_overflow"])
    assert total_connections < 50, (
        f"{workers} workers x (pool_size+overflow)={kwargs['pool_size']}+{kwargs['max_overflow']} "
        f"= {total_connections} connections -- should stay well under Postgres's real "
        f"max_connections=100 ceiling (GAP-28/29), with room for other connections "
        f"(migrations, admin tools, other services) sharing the same database"
    )
