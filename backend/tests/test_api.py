"""Integration tests for the FastAPI endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_plugins_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/plugins")
    assert r.status_code == 200
    data = r.json()
    assert "plugins" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_analyze_returns_job_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/analyze", json={"credentials": {}, "llm_provider": "ollama", "report_llm": "ollama"})
    assert r.status_code == 200
    data = r.json()
    assert "job_id" in data


@pytest.mark.asyncio
async def test_status_404_for_unknown_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/status/nonexistent-job-id")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_report_404_for_unknown_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/report/nonexistent-job-id")
    assert r.status_code == 404
