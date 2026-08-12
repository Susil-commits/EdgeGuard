"""Integration tests for the /health and /v1/nodes API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_register_node(client):
    response = await client.post(
        "/v1/nodes/register",
        json={
            "hostname": "test-node-01",
            "site": "lab",
            "environment": "test",
            "os": "Oracle Linux 9",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] in ("registered", "already_registered")


@pytest.mark.asyncio
async def test_register_node_idempotent(client):
    """Registering the same hostname twice should return the same node ID."""
    payload = {"hostname": "idempotent-node", "site": "test"}
    r1 = await client.post("/v1/nodes/register", json=payload)
    r2 = await client.post("/v1/nodes/register", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
