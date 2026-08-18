"""Benchmark routes and SSE, verified against an injected fake runner.

The API layer must be correct independently of what the simulator computes, so
these tests never call the real engine. They inject a tiny deterministic
``BenchmarkResult`` and assert on the transport: status codes, event ordering,
playback labelling, store isolation, and failure surfacing.
"""

import asyncio
from datetime import date, datetime
from typing import Any

import httpx
import pytest

from cascade.api import app, benchmark_store, store
from cascade.benchmark_run import PLAYBACK_NOTICE
from cascade.contracts import (
    AgentName,
    ArmResult,
    AuditVerdict,
    BenchmarkConfig,
    BenchmarkEventKind,
    BenchmarkResult,
    BlindAuditSummary,
    DailyKpi,
    DateWindow,
    DecisionSource,
    FleetArm,
    FleetDecision,
    FleetDecisionType,
    FleetMetrics,
    RecordedDecision,
    SeriesProvenance,
)

DAYS = 3
CALIBRATION = DateWindow(label="calibration", start=date(2023, 1, 1), end=date(2024, 2, 29))
BLIND = DateWindow(label="blind", start=date(2024, 4, 1), end=date(2024, 4, 3))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def setup_function() -> None:
    store.reset()
    benchmark_store.reset()
    benchmark_store.day_delay = 0.0
    benchmark_store.runner = fake_runner


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def make_daily(index: int) -> DailyKpi:
    return DailyKpi(
        date=date(2024, 4, 1 + index),
        day_index=index,
        arrivals=10,
        berthings=9,
        departures=9,
        queue_length=index,
        mean_wait_days=float(index),
        rolling_wait_days=float(index),
        active_berths=4,
        teu_waiting=100.0 * index,
        utilisation=0.8,
    )


def make_metrics() -> FleetMetrics:
    return FleetMetrics(
        peak_wait_days=2.0,
        peak_wait_date=date(2024, 4, 3),
        recovery_date=date(2024, 4, 3),
        days_above_two_day_wait=1,
        mean_wait_days=1.0,
        mean_port_stay_hours=30.0,
        port_stay_inflation_pct=12.0,
        vessels_served=27,
        teu_served=40000.0,
        missed_connection_proxy=3,
        wait_cost_usd=1_000_000.0,
    )


def make_arm(arm: FleetArm, *, with_decision: bool = False) -> ArmResult:
    decisions: list[RecordedDecision] = []
    if with_decision:
        decisions.append(
            RecordedDecision(
                date=date(2024, 4, 2),
                day_index=1,
                agent=AgentName.COORDINATOR,
                decision=FleetDecision(
                    type=FleetDecisionType.WORKFORCE_SURGE,
                    surge_level=1,
                    rationale="Rolling wait crossed the surge threshold.",
                ),
                accepted=True,
                source=DecisionSource.SCRIPTED,
                effective_date=date(2024, 4, 2),
            )
        )
    return ArmResult(
        arm=arm,
        label=arm.value.replace("_", " ").title(),
        provenance=(
            SeriesProvenance.RECONSTRUCTED
            if arm is FleetArm.HISTORICAL
            else SeriesProvenance.SIMULATED
        ),
        is_simulation=arm is not FleetArm.HISTORICAL,
        daily=[make_daily(i) for i in range(DAYS)],
        metrics=make_metrics(),
        decisions=decisions,
        blind_audit=BlindAuditSummary(
            total_reads=DAYS,
            max_lookahead_seconds=0.0,
            violations=0,
            verdict=AuditVerdict.PASS,
        ),
    )


def fake_runner(config: BenchmarkConfig) -> BenchmarkResult:
    return BenchmarkResult(
        benchmark_id="fake",
        config=config,
        calibration_window=CALIBRATION,
        blind_window=BLIND,
        historical_arm_provenance=SeriesProvenance.RECONSTRUCTED,
        arms=[make_arm(arm, with_decision=arm is FleetArm.CASCADE_AGENTIC) for arm in config.arms],
        comparisons=[],
        anchor_comparisons=[],
        fixture_hashes={"crisis_arrivals.json": "0" * 64},
        runtime_ms=7,
        notice=PLAYBACK_NOTICE,
    )


def failing_runner(config: BenchmarkConfig) -> BenchmarkResult:
    raise RuntimeError("fixture manifest hash mismatch")


async def wait_for_completion(http: httpx.AsyncClient, benchmark_id: str) -> dict[str, Any]:
    for _ in range(2000):
        state = (await http.get(f"/api/benchmarks/{benchmark_id}")).json()
        if state["stage"] in {"COMPLETE", "FAILED"}:
            return dict(state)
        await asyncio.sleep(0.005)
    raise AssertionError("benchmark never finished")


@pytest.mark.anyio
async def test_create_returns_201_with_playback_notice() -> None:
    async with client() as http:
        response = await http.post("/api/benchmarks", json={"seed": 42})
        assert response.status_code == 201
        body = response.json()
        assert body["stage"] in {"READY", "RUNNING"}
        assert body["events_url"] == f"/api/benchmarks/{body['benchmark_id']}/events"
        # The honesty label is part of the payload, not the narration.
        assert "animated playback" in body["playback_notice"]
        await wait_for_completion(http, body["benchmark_id"])


@pytest.mark.anyio
async def test_completed_state_carries_result_and_config() -> None:
    async with client() as http:
        created = (await http.post("/api/benchmarks", json={"seed": 7})).json()
        state = await wait_for_completion(http, created["benchmark_id"])
        assert state["stage"] == "COMPLETE"
        assert state["error"] is None
        result = state["result"]
        assert result is not None
        assert state["config"]["seed"] == 7
        assert result["config"]["seed"] == 7
        assert [arm["arm"] for arm in result["arms"]] == [
            "HISTORICAL",
            "REACTIVE_BASELINE",
            "CASCADE_AGENTIC",
        ]


@pytest.mark.anyio
async def test_since_trims_already_streamed_events() -> None:
    async with client() as http:
        created = (await http.post("/api/benchmarks", json={"seed": 42})).json()
        full = await wait_for_completion(http, created["benchmark_id"])
        total = len(full["events"])
        assert total > DAYS
        trimmed = (
            await http.get(f"/api/benchmarks/{created['benchmark_id']}", params={"since": total})
        ).json()
        assert trimmed["events"] == []
        assert trimmed["result"] is not None


@pytest.mark.anyio
async def test_event_sequence_is_ordered_and_complete() -> None:
    async with client() as http:
        created = (await http.post("/api/benchmarks", json={"seed": 42})).json()
        state = await wait_for_completion(http, created["benchmark_id"])
        events = state["events"]
        kinds = [event["kind"] for event in events]
        assert kinds[0] == BenchmarkEventKind.BENCHMARK_STARTED.value
        assert kinds[-1] == BenchmarkEventKind.BENCHMARK_COMPLETED.value
        assert kinds.count(BenchmarkEventKind.ARM_STARTED.value) == 3
        assert kinds.count(BenchmarkEventKind.ARM_COMPLETED.value) == 3
        assert kinds.count(BenchmarkEventKind.DAY_TICK.value) == 3 * DAYS
        assert kinds.count(BenchmarkEventKind.DECISION_TAKEN.value) == 1
        # Every arm starts before any day ticks, so the chart draws three lines
        # from the first frame rather than growing one at a time.
        assert kinds.index(BenchmarkEventKind.DAY_TICK.value) > max(
            index
            for index, kind in enumerate(kinds)
            if kind == BenchmarkEventKind.ARM_STARTED.value
        )
        sequences = [event["sequence"] for event in events]
        assert sequences == list(range(1, len(events) + 1))


@pytest.mark.anyio
async def test_day_ticks_advance_in_lockstep_across_arms() -> None:
    async with client() as http:
        created = (await http.post("/api/benchmarks", json={"seed": 42})).json()
        state = await wait_for_completion(http, created["benchmark_id"])
        ticks = [
            event for event in state["events"] if event["kind"] == BenchmarkEventKind.DAY_TICK.value
        ]
        assert [tick["day"]["day_index"] for tick in ticks] == [0, 0, 0, 1, 1, 1, 2, 2, 2]
        assert [tick["arm"] for tick in ticks[:3]] == [
            "HISTORICAL",
            "REACTIVE_BASELINE",
            "CASCADE_AGENTIC",
        ]


@pytest.mark.anyio
async def test_sse_stream_replays_every_event_then_ends() -> None:
    async with client() as http:
        created = (await http.post("/api/benchmarks", json={"seed": 42})).json()
        url = created["events_url"]
        names: list[str] = []
        async with http.stream("GET", url, timeout=30.0) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    names.append(line.removeprefix("event: "))
                    if names[-1] == "stream_end":
                        break
        assert names[0] == "notice"
        assert names[-1] == "stream_end"
        assert names.count("benchmark") == 1 + 3 + 3 * DAYS + 1 + 3 + 1


@pytest.mark.anyio
async def test_subscriber_joining_after_completion_still_gets_everything() -> None:
    async with client() as http:
        created = (await http.post("/api/benchmarks", json={"seed": 42})).json()
        state = await wait_for_completion(http, created["benchmark_id"])
        names: list[str] = []
        async with http.stream("GET", created["events_url"], timeout=30.0) as response:
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    names.append(line.removeprefix("event: "))
                    if names[-1] == "stream_end":
                        break
        assert names.count("benchmark") == len(state["events"])


@pytest.mark.anyio
async def test_selected_arms_are_honoured() -> None:
    async with client() as http:
        created = (
            await http.post(
                "/api/benchmarks",
                json={"seed": 1, "arms": ["REACTIVE_BASELINE", "CASCADE_AGENTIC"]},
            )
        ).json()
        state = await wait_for_completion(http, created["benchmark_id"])
        result = state["result"]
        assert [arm["arm"] for arm in result["arms"]] == [
            "REACTIVE_BASELINE",
            "CASCADE_AGENTIC",
        ]


@pytest.mark.anyio
async def test_runner_failure_surfaces_as_failed_stage() -> None:
    benchmark_store.runner = failing_runner
    async with client() as http:
        created = (await http.post("/api/benchmarks", json={"seed": 42})).json()
        state = await wait_for_completion(http, created["benchmark_id"])
        assert state["stage"] == "FAILED"
        assert state["result"] is None
        assert "manifest hash mismatch" in str(state["error"])
        kinds = [event["kind"] for event in state["events"]]
        assert kinds[-1] == BenchmarkEventKind.BENCHMARK_FAILED.value


@pytest.mark.anyio
async def test_unknown_benchmark_is_404() -> None:
    async with client() as http:
        assert (await http.get("/api/benchmarks/nope")).status_code == 404
        assert (await http.get("/api/benchmarks/nope/events")).status_code == 404


@pytest.mark.anyio
async def test_benchmark_store_is_isolated_from_run_store() -> None:
    async with client() as http:
        created = (await http.post("/api/benchmarks", json={"seed": 42})).json()
        await wait_for_completion(http, created["benchmark_id"])
        # A benchmark must not appear as a workflow run, nor disturb the scenario.
        assert (await http.get(f"/api/runs/{created['benchmark_id']}")).status_code == 404
        assert (await http.get("/api/scenario")).status_code == 200
        assert (await http.post("/api/reset")).status_code == 200
        assert (await http.get(f"/api/benchmarks/{created['benchmark_id']}")).status_code == 404


@pytest.mark.anyio
async def test_playback_speed_shortens_the_replay() -> None:
    benchmark_store.day_delay = 0.02
    async with client() as http:
        created = (
            await http.post("/api/benchmarks", json={"seed": 42, "playback_speed": 20})
        ).json()
        start = datetime.now()
        await wait_for_completion(http, created["benchmark_id"])
        # DAYS days at 0.02 s would be 0.06 s unsped; at 20x it must be far less
        # than the unsped time plus the polling slack.
        assert (datetime.now() - start).total_seconds() < 0.5
