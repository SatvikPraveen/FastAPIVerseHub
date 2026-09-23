# File: app/tests/test_observability.py
"""Request correlation, security headers and Prometheus metrics."""

from httpx import AsyncClient


async def test_incoming_request_id_is_propagated(async_client: AsyncClient):
    response = await async_client.get("/health/live", headers={"X-Request-ID": "trace-abc-12345"})
    assert response.headers["X-Request-ID"] == "trace-abc-12345"


async def test_malformed_request_id_is_replaced(async_client: AsyncClient):
    response = await async_client.get("/health/live", headers={"X-Request-ID": "bad id!"})
    assert response.headers["X-Request-ID"] != "bad id!"
    assert len(response.headers["X-Request-ID"]) == 32


async def test_error_envelope_carries_request_id(async_client: AsyncClient):
    response = await async_client.get("/nope", headers={"X-Request-ID": "trace-err-99999"})
    assert response.status_code == 404
    assert response.json()["request_id"] == "trace-err-99999"


async def test_security_headers_present(async_client: AsyncClient):
    response = await async_client.get("/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in response.headers
    assert "Content-Security-Policy" in response.headers
    # HSTS only makes sense behind TLS in production
    assert "Strict-Transport-Security" not in response.headers


async def test_metrics_endpoint_exposes_route_templates(async_client: AsyncClient):
    await async_client.get("/health/live")
    await async_client.get("/api/v1/courses/999999")  # 404 but a matched template

    response = await async_client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert 'http_requests_total{method="GET",path="/health/live",status="200"}' in body
    assert 'path="/api/v1/courses/{course_id}"' in body
    # raw paths must never become labels
    assert 'path="/api/v1/courses/999999"' not in body
    assert "http_request_duration_seconds_bucket" in body


async def test_metrics_endpoint_is_not_self_counted(async_client: AsyncClient):
    await async_client.get("/metrics")
    body = (await async_client.get("/metrics")).text
    assert 'path="/metrics"' not in body
