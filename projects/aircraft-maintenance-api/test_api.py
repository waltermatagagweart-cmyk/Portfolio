"""
Integration tests for the Aircraft Maintenance Log API.
Runs against a real PostgreSQL instance (set DATABASE_URL, or defaults to
postgresql+asyncpg://postgres:postgres@localhost:5432/maintenance_log_test).

These tests exercise the actual HTTP layer via httpx.ASGITransport, so they
catch routing, validation, and serialization bugs — not just unit-level logic.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from main import app, AsyncSessionLocal, RATE_LIMIT_MAX_REQUESTS, DEMO_USERNAME

# Matches main.py's DEMO_PASSWORD default — tests don't override that env var.
DEMO_PASSWORD = "aircraft-demo"

BASE_URL = "http://test"

# Rows this suite creates, identified by their natural keys, so we can wipe
# them before AND after a run — makes the suite safely re-runnable without a
# fresh database each time.
_TEST_AIRCRAFT_REGS = ("5Y-TST", "5Y-BAD", "5Y-DBG")
_TEST_TECH_LICENSES = ("TS-99999", "XX-00001")


async def _cleanup_test_rows():
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM aircraft WHERE registration_number = ANY(:regs)"),
            {"regs": list(_TEST_AIRCRAFT_REGS)},
        )
        await session.execute(
            text("DELETE FROM technician WHERE license_number = ANY(:licenses)"),
            {"licenses": list(_TEST_TECH_LICENSES)},
        )
        await session.commit()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _clean_test_data():
    """Wipe this suite's rows before and after the session so reruns don't collide."""
    await _cleanup_test_rows()
    yield
    await _cleanup_test_rows()


@pytest_asyncio.fixture(scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def auth_headers(client):
    """A valid bearer token for the demo account, for tests that exercise
    write-route logic (validation, FK/constraint errors) past the auth gate."""
    resp = await client.post("/auth/token", data={"username": DEMO_USERNAME, "password": DEMO_PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_and_get_aircraft(client, auth_headers):
    payload = {
        "registration_number": "5Y-TST",
        "model_id": 1,
        "msn": "TEST-0001",
        "total_airframe_hours": 100.0,
        "total_airframe_cycles": 50,
        "status": "Active",
    }
    resp = await client.post("/aircraft", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    created = resp.json()
    assert created["registration_number"] == "5Y-TST"
    aircraft_id = created["aircraft_id"]

    resp2 = await client.get(f"/aircraft/{aircraft_id}")
    assert resp2.status_code == 200
    assert resp2.json()["msn"] == "TEST-0001"


@pytest.mark.asyncio
async def test_get_nonexistent_aircraft_404(client):
    resp = await client.get("/aircraft/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_aircraft_invalid_status_rejected(client, auth_headers):
    """Pydantic validation should reject an out-of-domain status before it hits the DB."""
    payload = {
        "registration_number": "5Y-BAD",
        "model_id": 1,
        "status": "Flying",  # not one of Active/In Maintenance/Stored/Retired
    }
    resp = await client.post("/aircraft", json=payload, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_aircraft_pagination(client):
    resp = await client.get("/aircraft?skip=0&limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) <= 2


@pytest.mark.asyncio
async def test_create_technician_invalid_cert_rejected(client, auth_headers):
    payload = {
        "license_number": "XX-00001",
        "first_name": "Test",
        "last_name": "Person",
        "certification_type": "Wizard",  # not a real cert type
    }
    resp = await client.post("/technicians", json=payload, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_technician_and_get(client, auth_headers):
    payload = {
        "license_number": "TS-99999",
        "first_name": "Amina",
        "last_name": "Njoroge",
        "certification_type": "A&P",
        "email": "amina.njoroge@example.com",
    }
    resp = await client.post("/technicians", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    tech_id = resp.json()["technician_id"]

    resp2 = await client.get(f"/technicians/{tech_id}")
    assert resp2.status_code == 200
    assert resp2.json()["last_name"] == "Njoroge"


@pytest.mark.asyncio
async def test_create_event_requires_valid_aircraft(client, auth_headers):
    """A maintenance event referencing a non-existent aircraft should fail (FK violation -> 400)."""
    payload = {
        "aircraft_id": 999999,
        "event_date": "2026-01-01",
        "event_type": "Scheduled Inspection",
        "description": "Bogus event",
        "aircraft_hours_at_event": 10.0,
        "work_status": "Completed",
    }
    resp = await client.post("/events", json=payload, headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_event_component_hours_without_component_rejected(client, auth_headers):
    """Schema rule: component_hours_at_event requires component_id to be set."""
    payload = {
        "aircraft_id": 1,
        "component_id": None,
        "event_date": "2026-01-01",
        "event_type": "Scheduled Inspection",
        "description": "Airframe-level event with bogus component hours",
        "aircraft_hours_at_event": 10.0,
        "component_hours_at_event": 5.0,  # invalid: no component_id
        "work_status": "Completed",
    }
    resp = await client.post("/events", json=payload, headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_fleet_status_report(client):
    resp = await client.get("/reports/fleet-status")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    if body:
        row = body[0]
        assert "registration_number" in row
        assert "open_work_items" in row


@pytest.mark.asyncio
async def test_overdue_inspections_report(client):
    resp = await client.get("/reports/overdue-inspections")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_component_location_report(client):
    resp = await client.get("/reports/component-location")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---- AUTH ----

@pytest.mark.asyncio
async def test_write_route_without_token_rejected(client):
    """POST/PUT routes must require a bearer token; GETs already proved public above."""
    payload = {"registration_number": "5Y-NOA", "model_id": 1}
    resp = await client.post("/aircraft", json=payload)
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client):
    resp = await client.post("/auth/token", data={"username": DEMO_USERNAME, "password": "wrong-password"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_success_then_write_with_token(client):
    login_resp = await client.post("/auth/token", data={"username": DEMO_USERNAME, "password": DEMO_PASSWORD})
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert body["token_type"] == "bearer"
    token = body["access_token"]

    payload = {"registration_number": "5Y-DBG", "model_id": 1, "msn": "AUTH-TEST-0001"}
    resp = await client.post("/aircraft", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    assert resp.json()["registration_number"] == "5Y-DBG"


@pytest.mark.asyncio
async def test_write_route_with_garbage_token_rejected(client):
    resp = await client.post(
        "/aircraft",
        json={"registration_number": "5Y-NOA", "model_id": 1},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401


# ---- RATE LIMITING ----

@pytest.mark.asyncio
async def test_rate_limit_returns_429_with_headers(client):
    """
    Fires requests tagged with a synthetic X-Forwarded-For IP that no other
    test in this session uses, so this test's counter starts fresh at 0
    regardless of how much traffic earlier tests generated (the limiter's
    state is shared process-wide for the whole session-scoped client).
    """
    headers = {"X-Forwarded-For": "203.0.113.55"}
    last = None
    for _ in range(RATE_LIMIT_MAX_REQUESTS + 5):
        last = await client.get("/aircraft?limit=1", headers=headers)
        if last.status_code == 429:
            break
    assert last.status_code == 429
    assert last.headers.get("Retry-After") is not None
    assert last.headers.get("X-RateLimit-Remaining") == "0"


@pytest.mark.asyncio
async def test_health_exempt_from_rate_limit(client):
    """/health must stay reachable even from an IP that just got rate-limited,
    so Render's own health checks can't be starved by demo traffic."""
    headers = {"X-Forwarded-For": "203.0.113.55"}
    resp = await client.get("/health", headers=headers)
    assert resp.status_code == 200
