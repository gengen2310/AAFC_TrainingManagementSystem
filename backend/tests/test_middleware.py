"""Regression tests for HTTP middleware: X-Request-ID, X-Response-Time-ms."""


def test_x_request_id_generated_when_not_sent(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "X-Request-ID" in r.headers
    val = r.headers["X-Request-ID"]
    # Generated value should be a non-empty UUID-like string
    assert len(val) > 8


def test_x_request_id_echoed_when_sent(client):
    custom_id = "test-correlation-abc123"
    r = client.get("/api/health", headers={"X-Request-ID": custom_id})
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID") == custom_id


def test_x_response_time_ms_present(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "X-Response-Time-ms" in r.headers
    float(r.headers["X-Response-Time-ms"])  # must be parseable as a number


def test_different_requests_get_different_ids(client):
    r1 = client.get("/api/health")
    r2 = client.get("/api/health")
    assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]
