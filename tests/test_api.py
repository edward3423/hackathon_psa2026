import asyncio
import json

import httpx
import pytest

import cascade.api as api
from cascade.api import app, store
from cascade.tools.fake_toolbox import FakeToolBox

CONSTRAINT = "Respect the reefer plug limit; rush at most 34 pharmaceutical reefers."
GOLDEN_CONTROLS = {
    "delay_hours": 18,
    "priority_emphasis": "BALANCED",
    "alternative_sailing_failure": True,
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def setup_function() -> None:
    store.reset()
    store.event_delay = 0.0
    store.toolbox_factory = FakeToolBox


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def drive_run(http: httpx.AsyncClient, run_id: str, decision: str = "APPROVED") -> None:
    """Post the dispute resolution and approval as the run reaches each pause."""
    resolved = False
    decided = False
    for _ in range(2000):
        state = (await http.get(f"/api/runs/{run_id}")).json()
        if not resolved and state["stage"] == "DISPUTE" and state["active_dispute"]:
            response = await http.post(
                f"/api/runs/{run_id}/dispute-resolution",
                json={
                    "dispute_id": state["active_dispute"]["dispute_id"],
                    "confirmed_constraint": CONSTRAINT,
                },
            )
            resolved = response.status_code == 200
        elif not decided and state["stage"] == "AWAITING_APPROVAL":
            response = await http.post(
                f"/api/runs/{run_id}/approval",
                json={"plan_archetype": "OPTIMIZED_HYBRID", "decision": decision},
            )
            decided = response.status_code == 200
        elif state["stage"] in {"COMPLETE", "FAILED"}:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("run did not complete")


async def create_run(http: httpx.AsyncClient, mode: str = "LIVE_STUB") -> dict:
    response = await http.post("/api/runs", json={**GOLDEN_CONTROLS, "mode": mode})
    assert response.status_code == 201, response.text
    return response.json()


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.split("\n\n"):
        lines = [line for line in block.strip().splitlines() if line]
        if not lines or lines[0].startswith(":"):
            continue
        name = lines[0].removeprefix("event: ")
        data = json.loads(lines[1].removeprefix("data: "))
        events.append((name, data))
    return events


@pytest.mark.anyio
async def test_health_and_scenario_are_available() -> None:
    async with client() as http:
        assert (await http.get("/api/health")).json()["status"] == "ok"
        scenario = (await http.get("/api/scenario")).json()
    assert scenario["alert"]["delay_hours"] == 18
    assert scenario["synthetic_notice"]


@pytest.mark.anyio
async def test_run_rejects_unsupported_delay() -> None:
    async with client() as http:
        response = await http.post("/api/runs", json={**GOLDEN_CONTROLS, "delay_hours": 30})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_live_gemini_without_key_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    async with client() as http:
        response = await http.post("/api/runs", json={**GOLDEN_CONTROLS, "mode": "LIVE_GEMINI"})
    assert response.status_code == 409
    assert "DEMO_REPLAY" in response.json()["detail"]


@pytest.mark.anyio
async def test_sse_stream_survives_pauses_and_resumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api, "KEEPALIVE_SECONDS", 0.002)
    async with client() as http:
        created = await create_run(http)
        driver = asyncio.create_task(drive_run(http, created["run_id"]))
        collected = ""
        async with http.stream("GET", created["events_url"]) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            async for chunk in response.aiter_text():
                collected += chunk
                if "stream_end" in collected:
                    break
        await driver

    assert ": keep-alive" in collected  # emitted while paused for the human
    events = parse_sse(collected)
    trace_kinds = [data["kind"] for name, data in events if name == "trace"]
    assert trace_kinds[0] == "RUN_STARTED"
    assert "DISPUTE_OPENED" in trace_kinds
    assert "HUMAN_DECISION" in trace_kinds
    assert "APPROVAL_REQUIRED" in trace_kinds
    assert "ACTION_DISPATCHED" in trace_kinds
    assert trace_kinds[-1] == "RUN_COMPLETED"
    assert trace_kinds.index("DISPUTE_OPENED") < trace_kinds.index("HUMAN_DECISION")
    assert trace_kinds.index("APPROVAL_REQUIRED") < trace_kinds.index("ACTION_DISPATCHED")
    assert events[-1][0] == "stream_end"

    async with client() as http:
        state = (await http.get(f"/api/runs/{created['run_id']}")).json()
    assert state["stage"] == "COMPLETE"
    assert state["results"]["plan_comparison"]["recommended"] == "OPTIMIZED_HYBRID"
    assert state["results"]["dispatched_actions"]
    assert state["results"]["receipts"]
    assert state["active_dispute"]["resolved_by_human"] is True
    assert state["active_dispute"]["confirmed_constraint"] == CONSTRAINT


@pytest.mark.anyio
async def test_rejection_completes_with_no_actions() -> None:
    async with client() as http:
        created = await create_run(http)
        await drive_run(http, created["run_id"], decision="REJECTED")
        state = (await http.get(f"/api/runs/{created['run_id']}")).json()
    assert state["stage"] == "COMPLETE"
    assert state["results"]["dispatched_actions"] == []
    kinds = [event["kind"] for event in state["trace"]]
    assert "ACTION_DISPATCHED" not in kinds
    assert kinds[-1] == "RUN_COMPLETED"


@pytest.mark.anyio
async def test_dispute_resolution_conflicts_are_rejected() -> None:
    async with client() as http:
        created = await create_run(http)
        run_id = created["run_id"]
        # Wait until the dispute is open.
        for _ in range(1000):
            state = (await http.get(f"/api/runs/{run_id}")).json()
            if state["stage"] == "DISPUTE":
                break
            await asyncio.sleep(0.005)
        wrong = await http.post(
            f"/api/runs/{run_id}/dispute-resolution",
            json={"dispute_id": "disp-nope", "confirmed_constraint": CONSTRAINT},
        )
        early_approval = await http.post(
            f"/api/runs/{run_id}/approval",
            json={"plan_archetype": "OPTIMIZED_HYBRID", "decision": "APPROVED"},
        )
    assert wrong.status_code == 409
    assert early_approval.status_code == 409


@pytest.mark.anyio
async def test_replay_mode_is_labeled_and_honors_pauses() -> None:
    async with client() as http:
        created = await create_run(http, mode="DEMO_REPLAY")
        assert created["mode"] == "DEMO_REPLAY"
        driver = asyncio.create_task(drive_run(http, created["run_id"]))
        collected = ""
        async with http.stream("GET", created["events_url"]) as response:
            async for chunk in response.aiter_text():
                collected += chunk
                if "stream_end" in collected:
                    break
        await driver
        state = (await http.get(f"/api/runs/{created['run_id']}")).json()

    events = parse_sse(collected)
    assert events[0][0] == "mode"
    assert events[0][1]["label"] == "DEMO REPLAY"
    trace_events = [data for name, data in events if name == "trace"]
    assert trace_events, "replay must stream the captured sequence"
    assert all("DEMO REPLAY" in event["assumptions"] for event in trace_events)
    kinds = [event["kind"] for event in trace_events]
    assert "DISPUTE_OPENED" in kinds
    assert "APPROVAL_REQUIRED" in kinds
    assert kinds.index("APPROVAL_REQUIRED") < kinds.index("ACTION_DISPATCHED")
    assert state["mode"] == "DEMO_REPLAY"
    assert state["stage"] == "COMPLETE"
    assert state["results"]["dispatched_actions"]


@pytest.mark.anyio
async def test_query_param_mode_overrides_body() -> None:
    async with client() as http:
        response = await http.post("/api/runs?mode=DEMO_REPLAY", json=GOLDEN_CONTROLS)
    assert response.status_code == 201
    assert response.json()["mode"] == "DEMO_REPLAY"


@pytest.mark.anyio
async def test_reset_restores_pristine_state() -> None:
    async with client() as http:
        created = await create_run(http)
        reset = await http.post("/api/reset")
        missing = await http.get(f"/api/runs/{created['run_id']}")
    assert reset.status_code == 200
    assert reset.json()["alert"]["delay_hours"] == 18
    assert missing.status_code == 404
