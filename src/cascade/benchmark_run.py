"""Benchmark run orchestration and cinematic playback.

This mirrors the shape of ``workflow.py`` for Act 2 without sharing any of its
state: a store of runs, one run object per benchmark, an append-only event log,
and an async condition variable the SSE endpoint waits on.

One thing differs from Act 1 on purpose. A workflow run streams events as the
stage machine produces them. A benchmark run computes the whole deterministic
result FIRST, then replays it day by day so the three arms race across the
chart at a watchable speed. That is playback, not a live run, and the
distinction is carried in the payload rather than left to the narrator: every
``BenchmarkCreated`` and ``BenchmarkState`` carries ``PLAYBACK_NOTICE``, and the
UI is expected to show it. Replay never impersonates live.
"""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from cascade.contracts import (
    ArmResult,
    BenchmarkConfig,
    BenchmarkCreated,
    BenchmarkEvent,
    BenchmarkEventKind,
    BenchmarkResult,
    BenchmarkStage,
    BerthPoolConfig,
    CreateBenchmarkRequest,
    FleetArm,
    FleetWorldConfig,
    RecordedDecision,
    ReserveBerthTranche,
    ServiceModelConfig,
)

BENCHMARK_LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "benchmarks"

PLAYBACK_NOTICE = (
    "Completed deterministic simulation - animated playback. Every figure is "
    "computed in full before the first frame is streamed; the day-by-day "
    "animation replays a finished result and is not a live run."
)

DEFAULT_ARMS = [
    FleetArm.HISTORICAL,
    FleetArm.REACTIVE_BASELINE,
    FleetArm.CASCADE_AGENTIC,
]

# Berth pool for the Singapore container terminals as an effective-berth
# abstraction. The active count is a starting point only: calibrate.py fits the
# effective berth count on the pre-crisis window, and the fitted value is what
# the benchmark runs with. The two reserve tranches mirror the two capacity
# levers PSA actually pulled in 2024 (see plan/prd_main.md section 11.2).
DEFAULT_BERTHS = BerthPoolConfig(
    active_berths=42,
    reserve_tranches=[
        ReserveBerthTranche(
            tranche_id="KEPPEL_REACTIVATION",
            label="Reactivated Keppel Terminal berths",
            berths=4,
            activation_lead_days=14,
            available_from=None,
            basis=(
                "PSA reopened previously retired Keppel Terminal berths and yard "
                "space during the 2024 congestion. The 14-day lead is our own "
                "conservative estimate for standing a berth back up, not a "
                "published figure."
            ),
        ),
        ReserveBerthTranche(
            tranche_id="TUAS_PHASE1_ADDITIONAL",
            label="Additional Tuas Port phase 1 berths",
            berths=3,
            activation_lead_days=7,
            available_from=None,
            basis=(
                "Tuas Port phase 1 berths were being commissioned progressively "
                "through 2024. Modelled as a reserve tranche with a short lead."
            ),
        ),
    ],
)

# Starting point for the service model. Every one of these numbers is refitted
# by calibrate.py against the pre-crisis window before any crisis day is run.
DEFAULT_SERVICE = ServiceModelConfig(
    base_hours=2.0,
    cranes_per_berth=4.0,
    moves_per_crane_hour=28.0,
    teu_per_move=1.6,
    efficiency=1.0,
    congestion_alpha=0.15,
    congestion_queue_ref=20.0,
    congestion_cap=3.0,
    surge_alpha_factor=0.75,
    surge_efficiency_gain=0.06,
    fast_connection_speedup=0.92,
)


def default_world(seed: int) -> FleetWorldConfig:
    return FleetWorldConfig(seed=seed, berths=DEFAULT_BERTHS, service=DEFAULT_SERVICE)


def config_from_request(request: CreateBenchmarkRequest) -> BenchmarkConfig:
    return BenchmarkConfig(
        seed=request.seed,
        arms=list(request.arms or DEFAULT_ARMS),
        world=default_world(request.seed),
        brain=request.brain,
    )


BenchmarkRunner = Callable[[BenchmarkConfig], BenchmarkResult]


def warm_engine() -> None:
    """Pay the engine's cold-start costs ahead of the first request.

    The first calibration fit is a coordinate search costing tens of seconds
    of CPU; every later benchmark reads it from the in-process cache. Calling
    this at boot moves that wait off the first Run benchmark click.
    """
    from cascade.engine.fleet.benchmark import warm_calibration

    warm_calibration(config_from_request(CreateBenchmarkRequest()).world)


def default_runner(config: BenchmarkConfig) -> BenchmarkResult:
    """Import the engine lazily so the API module stays cheap to import."""
    from cascade.engine.fleet.benchmark import run_benchmark

    return run_benchmark(config)


class BenchmarkRun:
    """One benchmark: compute the whole result, then replay it as events."""

    def __init__(
        self,
        benchmark_id: str,
        config: BenchmarkConfig,
        runner: BenchmarkRunner = default_runner,
        *,
        day_delay: float = 0.0,
        playback_speed: float = 1.0,
    ) -> None:
        self.benchmark_id = benchmark_id
        self.config = config
        self.stage = BenchmarkStage.READY
        self.events: list[BenchmarkEvent] = []
        self.result: BenchmarkResult | None = None
        self.error: str | None = None
        self.finished = False
        self._runner = runner
        self._day_delay = day_delay / playback_speed if playback_speed else day_delay
        self._cond = asyncio.Condition()
        self._task: asyncio.Task[None] | None = None

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        self._task = asyncio.create_task(self._run_safely())

    def cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def _run_safely(self) -> None:
        try:
            await self._execute()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a failed run must surface, not crash the app
            self.stage = BenchmarkStage.FAILED
            self.error = str(exc)
            await self._emit(
                kind=BenchmarkEventKind.BENCHMARK_FAILED,
                message="Benchmark failed; no result was produced.",
                error=str(exc),
            )
        finally:
            async with self._cond:
                self.finished = True
                self._cond.notify_all()

    async def _execute(self) -> None:
        self.stage = BenchmarkStage.RUNNING
        await self._emit(
            kind=BenchmarkEventKind.BENCHMARK_STARTED,
            message=(
                f"Running {len(self.config.arms)} arms over the blind window "
                f"with seed {self.config.seed}."
            ),
        )
        # The simulation is synchronous and CPU-bound; keep the event loop free
        # so keep-alives keep flowing while it runs.
        result = await asyncio.to_thread(self._runner, self.config)
        self.result = result
        await self._replay(result)
        self.stage = BenchmarkStage.COMPLETE
        await self._emit(
            kind=BenchmarkEventKind.BENCHMARK_COMPLETED,
            message=PLAYBACK_NOTICE,
        )

    async def _replay(self, result: BenchmarkResult) -> None:
        """Stream the finished result day by day so the arms race together."""
        for arm in result.arms:
            await self._emit(
                kind=BenchmarkEventKind.ARM_STARTED,
                arm=arm.arm,
                message=f"{arm.label} ({arm.provenance.value.lower()}).",
            )
        decisions = _decisions_by_day(result.arms)
        longest = max((len(arm.daily) for arm in result.arms), default=0)
        for index in range(longest):
            if self._day_delay:
                await asyncio.sleep(self._day_delay)
            for arm in result.arms:
                if index >= len(arm.daily):
                    continue
                day = arm.daily[index]
                await self._emit(
                    kind=BenchmarkEventKind.DAY_TICK,
                    arm=arm.arm,
                    day=day,
                    message=f"{day.date.isoformat()} rolling wait {day.rolling_wait_days:.2f} d.",
                )
                for decision in decisions.get((arm.arm, day.date.isoformat()), ()):
                    await self._emit(
                        kind=BenchmarkEventKind.DECISION_TAKEN,
                        arm=arm.arm,
                        decision=decision,
                        message=decision.decision.rationale,
                    )
        for arm in result.arms:
            await self._emit(
                kind=BenchmarkEventKind.ARM_COMPLETED,
                arm=arm.arm,
                message=(
                    f"{arm.label}: peak wait {arm.metrics.peak_wait_days:.2f} d, "
                    f"recovery {arm.metrics.recovery_date or 'not reached'}."
                ),
            )

    # -- event log -----------------------------------------------------------

    async def _emit(self, **fields: object) -> BenchmarkEvent:
        event = BenchmarkEvent(
            event_id=f"{self.benchmark_id[:8]}-{len(self.events) + 1:04d}",
            sequence=len(self.events) + 1,
            timestamp=datetime.now(UTC),
            **fields,
        )
        async with self._cond:
            self.events.append(event)
            self._cond.notify_all()
        self._log_event(event)
        return event

    def _log_event(self, event: BenchmarkEvent) -> None:
        # Per-benchmark JSONL debug log, mirroring workflow runs. Logging must
        # never break a run, so filesystem trouble is swallowed.
        if event.kind is BenchmarkEventKind.DAY_TICK:
            return
        try:
            BENCHMARK_LOG_DIR.mkdir(parents=True, exist_ok=True)
            path = BENCHMARK_LOG_DIR / f"{self.benchmark_id}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                if event.sequence == 1:
                    header = {
                        "benchmark_id": self.benchmark_id,
                        "config": self.config.model_dump(mode="json"),
                    }
                    handle.write(json.dumps({"benchmark_header": header}) + "\n")
                handle.write(event.model_dump_json() + "\n")
        except OSError:
            pass

    async def wait_events(
        self, index: int, timeout: float
    ) -> tuple[list[BenchmarkEvent], bool] | None:
        """New events after ``index``, or None on timeout (keep-alive)."""
        async with self._cond:
            if len(self.events) > index or self.finished:
                return list(self.events[index:]), self.finished
            try:
                await asyncio.wait_for(self._cond.wait(), timeout)
            except TimeoutError:
                return None
            return list(self.events[index:]), self.finished


def _decisions_by_day(
    arms: list[ArmResult],
) -> dict[tuple[FleetArm, str], list[RecordedDecision]]:
    grouped: dict[tuple[FleetArm, str], list[RecordedDecision]] = {}
    for arm in arms:
        for decision in arm.decisions:
            grouped.setdefault((arm.arm, decision.date.isoformat()), []).append(decision)
    return grouped


class BenchmarkStore:
    """In-memory benchmark registry. Deliberately separate from RunStore."""

    def __init__(self, runner: BenchmarkRunner = default_runner, day_delay: float = 0.0) -> None:
        self._runs: dict[str, BenchmarkRun] = {}
        self.runner = runner
        self.day_delay = day_delay

    def create(self, request: CreateBenchmarkRequest) -> BenchmarkRun:
        run = BenchmarkRun(
            benchmark_id=str(uuid4()),
            config=config_from_request(request),
            runner=self.runner,
            day_delay=self.day_delay,
            playback_speed=request.playback_speed,
        )
        self._runs[run.benchmark_id] = run
        run.start()
        return run

    def get(self, benchmark_id: str) -> BenchmarkRun | None:
        return self._runs.get(benchmark_id)

    def reset(self) -> None:
        for run in self._runs.values():
            run.cancel()
        self._runs.clear()


def created_response(run: BenchmarkRun) -> BenchmarkCreated:
    return BenchmarkCreated(
        benchmark_id=run.benchmark_id,
        stage=run.stage,
        events_url=f"/api/benchmarks/{run.benchmark_id}/events",
        playback_notice=PLAYBACK_NOTICE,
    )
