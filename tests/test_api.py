import httpx
import pytest

from cascade.api import app, store


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def setup_function() -> None:
    store.reset()


@pytest.mark.anyio
async def test_health_and_scenario_are_available() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/health")).json()["status"] == "ok"

        scenario = (await client.get("/api/scenario")).json()
    assert scenario["alert"]["delay_hours"] == 18
    assert scenario["synthetic_notice"]


@pytest.mark.anyio
async def test_run_streams_ordered_agent_events() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/runs",
            json={
                "delay_hours": 18,
                "priority_emphasis": "BALANCED",
                "alternative_sailing_failure": True,
            },
        )
        events = await client.get(created.json()["events_url"])
    assert created.status_code == 201
    assert events.status_code == 200
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "event: trace" in events.text
    assert "Coordinator Agent" in events.text
    assert "Impact Agent" in events.text
    assert "Yard Agent" in events.text
    assert "Recovery Agent" in events.text


@pytest.mark.anyio
async def test_run_rejects_unsupported_delay() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/runs",
            json={
                "delay_hours": 30,
                "priority_emphasis": "BALANCED",
                "alternative_sailing_failure": False,
            },
        )

    assert response.status_code == 422
