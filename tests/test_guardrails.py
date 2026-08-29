"""The request guardrails: opt-in token auth, rate limiting, and store bounds."""

import asyncio
from typing import Any

import httpx
import pytest

from cascade import benchmark_run, guardrails
from cascade.api import app, store
from cascade.contracts import RunMode, ScenarioControls
from cascade.guardrails import TokenBucket
from cascade.tools.fake_toolbox import FakeToolBox
from cascade.workflow import MAX_ACTIVE_RUNS, MAX_RETAINED_RUNS, RunStore


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def setup_function() -> None:
    store.reset()
    store.event_delay = 0.0
    store.toolbox_factory = FakeToolBox


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


GOLDEN_CONTROLS = {
    "delay_hours": 18,
    "priority_emphasis": "BALANCED",
    "alternative_sailing_failure": True,
}


# -- token bucket ------------------------------------------------------------


def test_token_bucket_enforces_burst_and_refills() -> None:
    now = [0.0]
    bucket = TokenBucket(2, 1.0, clock=lambda: now[0])
    assert bucket.allow("client-a")
    assert bucket.allow("client-a")
    assert not bucket.allow("client-a")
    now[0] += 1.0
    assert bucket.allow("client-a")
    assert not bucket.allow("client-a")


def test_token_bucket_keys_are_independent() -> None:
    bucket = TokenBucket(1, 0.0, clock=lambda: 0.0)
    assert bucket.allow("client-a")
    assert not bucket.allow("client-a")
    assert bucket.allow("client-b")


def test_token_bucket_prunes_idle_clients() -> None:
    now = [0.0]
    bucket = TokenBucket(2, 1.0, clock=lambda: now[0])
    bucket.allow("stale")
    now[0] += 10.0
    bucket.allow("fresh")
    bucket._prune(now[0])
    assert "stale" not in bucket._buckets
    assert "fresh" in bucket._buckets


# -- shared-secret auth ------------------------------------------------------


@pytest.mark.anyio
async def test_posts_require_the_token_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CASCADE_API_TOKEN", "sekret")
    async with client() as http:
        missing = await http.post("/api/reset")
        wrong = await http.post("/api/reset", headers={"X-Cascade-Token": "nope"})
        right = await http.post("/api/reset", headers={"X-Cascade-Token": "sekret"})
        read = await http.get("/api/health")
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert right.status_code == 200
    assert read.status_code == 200  # reads stay open even with auth on


@pytest.mark.anyio
async def test_auth_is_off_when_no_token_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CASCADE_API_TOKEN", raising=False)
    async with client() as http:
        response = await http.post("/api/reset")
    assert response.status_code == 200


# -- rate limiting -----------------------------------------------------------


@pytest.mark.anyio
async def test_mutations_beyond_the_bucket_get_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guardrails, "_limiter", TokenBucket(1, 0.0, clock=lambda: 0.0))
    monkeypatch.setattr(guardrails, "_limiter_built", True)
    async with client() as http:
        first = await http.post("/api/reset")
        second = await http.post("/api/reset")
        read = await http.get("/api/health")
    assert first.status_code == 200
    assert second.status_code == 429
    assert read.status_code == 200  # reads and SSE are never rate limited


def test_limiter_can_be_disabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guardrails, "_limiter", None)
    monkeypatch.setattr(guardrails, "_limiter_built", False)
    monkeypatch.setenv("CASCADE_RATE_LIMIT_BURST", "0")
    assert guardrails._get_limiter() is None


def test_limiter_reads_env_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(guardrails, "_limiter", None)
    monkeypatch.setattr(guardrails, "_limiter_built", False)
    monkeypatch.setenv("CASCADE_RATE_LIMIT_BURST", "5")
    monkeypatch.setenv("CASCADE_RATE_LIMIT_PER_SECOND", "0.5")
    limiter = guardrails._get_limiter()
    assert limiter is not None
    assert limiter.capacity == 5.0
    assert limiter.refill_per_second == 0.5


# -- bounded stores ----------------------------------------------------------


class _FakeRun:
    """Just enough of a run for _make_room: a finished flag and a cancel hook."""

    def __init__(self, finished: bool) -> None:
        self.finished = finished
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


@pytest.mark.anyio
async def test_active_runs_are_capped_by_cancelling_the_oldest() -> None:
    local = RunStore(toolbox_factory=FakeToolBox, event_delay=0.0)
    controls = ScenarioControls()
    runs = [local.create(controls, RunMode.LIVE_STUB) for _ in range(MAX_ACTIVE_RUNS + 2)]
    try:
        assert len(local._runs) == MAX_ACTIVE_RUNS
        assert local.get(runs[0].run_id) is None
        assert local.get(runs[1].run_id) is None
        assert local.get(runs[-1].run_id) is runs[-1]
        # An evicted run still terminates cleanly, so any open SSE stream on it
        # sees the finished flag and ends instead of hanging.
        for _ in range(100):
            if runs[0].finished and runs[1].finished:
                break
            await asyncio.sleep(0.01)
        assert runs[0].finished
        assert runs[1].finished
    finally:
        local.reset()


def test_finished_runs_are_evicted_beyond_retention() -> None:
    local = RunStore()
    fakes: dict[str, Any] = local._runs
    for index in range(MAX_RETAINED_RUNS + 5):
        fakes[f"run-{index}"] = _FakeRun(finished=True)
    fakes["watched"] = _FakeRun(finished=False)
    local._make_room()
    assert len(fakes) < MAX_RETAINED_RUNS
    assert "run-0" not in fakes
    assert "watched" in fakes


def test_benchmark_store_applies_the_same_bounds() -> None:
    local = benchmark_run.BenchmarkStore()
    runs = [_FakeRun(finished=False) for _ in range(benchmark_run.MAX_ACTIVE_BENCHMARKS + 2)]
    fakes: dict[str, Any] = local._runs
    for index, run in enumerate(runs):
        fakes[f"bench-{index}"] = run
    local._make_room()
    assert runs[0].cancelled
    assert runs[1].cancelled
    assert "bench-0" not in fakes
    assert len(fakes) == benchmark_run.MAX_ACTIVE_BENCHMARKS - 1


@pytest.mark.anyio
async def test_run_flood_through_the_api_stays_bounded() -> None:
    async with client() as http:
        created = []
        for _ in range(MAX_ACTIVE_RUNS + 2):
            response = await http.post("/api/runs", json={**GOLDEN_CONTROLS, "mode": "LIVE_STUB"})
            assert response.status_code == 201
            created.append(response.json())
        oldest = await http.get(f"/api/runs/{created[0]['run_id']}")
        newest = await http.get(f"/api/runs/{created[-1]['run_id']}")
    assert oldest.status_code == 404
    assert newest.status_code == 200
