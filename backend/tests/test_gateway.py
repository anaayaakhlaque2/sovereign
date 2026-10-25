"""
Tests for FastAPI Gateway REST API.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.gateway.app import app
from backend.gateway.database import init_db


@pytest.mark.asyncio
async def test_gateway_endpoints():
    init_db()
    # Test client using ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # State
        res = await client.get("/api/cluster/state")
        assert res.status_code == 200
        data = res.json()
        assert "nodes" in data
        assert "algorithm" in data

        # Algorithm switch
        res = await client.post("/api/cluster/algorithm", json={"algorithm": "ring"})
        assert res.status_code == 200
        assert res.json()["algorithm"] == "ring"

        # Export JSON
        res = await client.get("/api/export/json")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        # Export CSV
        res = await client.get("/api/export/csv")
        assert res.status_code == 200
        assert "election_id" in res.text
