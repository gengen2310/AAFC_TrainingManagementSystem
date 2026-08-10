"""Health endpoints — reachable unauthenticated (load-balancer probes), and
must never echo a raw driver exception (Stage 2, Final System Assurance pass:
health_db()/ready() previously returned str(e) directly, which for a Postgres
outage can include the internal hostname -- not a credential, but still
backend-internals disclosure to an unauthenticated caller)."""


def test_health_root_unauthenticated(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_db_unauthenticated_happy_path(client):
    r = client.get("/api/health/db")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok"}


def test_health_ready_unauthenticated_happy_path(client):
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ready"
    assert isinstance(d["squadrons"], int)


def test_health_ready_includes_build_commit(client):
    """REM-112: a build fingerprint lets a freshness check compare deployed
    staging against the latest backend/-touching commit on main, instead of a
    REM-111-class gap (a merged endpoint 404ing on staging for ~24h) only
    being caught by luck. Defaults to "local" outside Railway (RAILWAY_
    GIT_COMMIT_SHA unset), matching the same fallback convention both
    frontends already use for their own build fingerprints."""
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json()["commit"] == "local"


def test_health_db_failure_does_not_leak_raw_exception(client, monkeypatch):
    from sqlalchemy.orm import Session

    def _boom(self, *a, **kw):
        raise RuntimeError("could not connect to host internal-db.railway.internal: secret detail")

    monkeypatch.setattr(Session, "execute", _boom)
    r = client.get("/api/health/db")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "degraded"
    assert d["db"] == "error"
    assert "railway.internal" not in r.text


def test_health_ready_failure_does_not_leak_raw_exception(client, monkeypatch):
    from sqlalchemy.orm import Query

    def _boom(self, *a, **kw):
        raise RuntimeError("could not connect to host internal-db.railway.internal: secret detail")

    monkeypatch.setattr(Query, "count", _boom)
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "not_ready"
    assert d["error"] == "error"
    assert d["commit"] == "local"
    assert "railway.internal" not in r.text
