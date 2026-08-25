"""Assemble the Red Sea 2024 crisis benchmark: arms, metrics, comparisons.

This module is the only place that decides what a benchmark *is*. It is pure
and synchronous - no clock, no network, no I/O beyond reading the committed
fixtures - so the same config and seed always produce the same
``BenchmarkResult``.

Three honesty rules are enforced here rather than asserted in prose:

1. **One world for every simulated arm.** Calibration runs once, on the
   calibration slice only, and the fitted world it produces is handed
   unchanged to every simulated arm. The arms differ in their policy and in
   nothing else, so a win cannot come from a kinder parameter set.
2. **The historical arm is never simulated.** It is the reconstructed curve
   from the ground-truth fixture, carried through with
   ``provenance=RECONSTRUCTED``, ``is_simulation=False`` and a caveat that
   travels with it into the payload.
3. **Anchors are compared, not fitted.** Recorded scalars are held next to
   what the simulation produced, with an explicit tolerance and a plain
   pass/fail. Nothing in this module tunes anything to close a gap.
"""

import math
import threading
import time
from datetime import date
from typing import TYPE_CHECKING

from cascade.contracts import (
    AnchorComparison,
    ArmComparison,
    ArmResult,
    BenchmarkConfig,
    BenchmarkResult,
    BlindSlice,
    CalibrationReport,
    CalibrationSlice,
    DailyKpi,
    DateWindow,
    FleetArm,
    FleetBrainMode,
    FleetMetrics,
    FleetWorldConfig,
    GroundTruthFixture,
    SeriesProvenance,
)
from cascade.engine.fleet.calibrate import calibrate
from cascade.engine.fleet.feed import BlindFeed, SimClock, day_start
from cascade.engine.fleet.metrics import compute_metrics
from cascade.engine.fleet.policies import (
    AgenticFleetPolicy,
    ReactiveBaselinePolicy,
    brain_decision_source,
    make_agentic_policy,
)
from cascade.engine.fleet.simulate import simulate
from cascade.fixtures import (
    CRISIS_ARRIVALS_FILE,
    CRISIS_GROUND_TRUTH_FILE,
    load_crisis_arrivals,
    load_crisis_ground_truth,
    load_crisis_manifest,
)

if TYPE_CHECKING:
    from cascade.agents.base import FleetBrain

BENCHMARK_NOTICE = (
    "A controlled policy comparison, not a reproduction of history. The "
    "REACTIVE_BASELINE and CASCADE arms are discrete-event simulations of the "
    "recorded 2024 arrival stream, run blind: no arm can read a day it has not "
    "yet reached. They share one world, one calibration and one stream, and "
    "differ only in policy, so the comparison between them is the result this "
    "benchmark stands behind. The HISTORICAL arm is a reconstruction, not a "
    "measurement, and its derivation ships with it. The simulation does not "
    "reproduce the recorded 2024 congestion and is not claimed to: Singapore's "
    "recorded daily port calls and volumes measure throughput, which congestion "
    "suppresses, so the crisis that made June 2024 the port's busiest month by "
    "reputation made it the quietest by arrival count. The recorded anchors are "
    "published alongside the simulated figures so that gap stays visible. No "
    "figure here is a per-vessel prediction of what any real ship actually did."
)

HISTORICAL_CAVEAT = (
    "Reconstructed, not measured. No public source publishes a daily "
    "berth-waiting series for Singapore; this curve's shape comes from the "
    "recorded IMF PortWatch arrival stream and its scale from two recorded "
    "anchors. See historical_curve_method in fixtures/crisis_ground_truth.json."
)

ARM_LABELS: dict[FleetArm, str] = {
    FleetArm.HISTORICAL: "Recorded 2024 (reconstructed)",
    FleetArm.REACTIVE_BASELINE: "Reactive baseline",
    FleetArm.CASCADE_AGENTIC: "CASCADE agentic",
    FleetArm.CASCADE_NO_EXTRA_CAPACITY: "CASCADE, no extra capacity",
}

#: Simulated arms are scored against the reactive baseline. It is the only fair
#: comparator: same engine, same world, same arrival stream, different policy.
COMPARISON_BASE = FleetArm.REACTIVE_BASELINE

#: Anchors this benchmark can speak to at all, with the tolerance each is held
#: to and the arm whose figure is compared. Anchors the simulation has no
#: quantity for (re-handlings, off-schedule percentages, group-wide volumes)
#: are deliberately absent rather than approximated: they stay in the fixture
#: as context and are never scored.
ANCHOR_TOLERANCES: dict[str, float] = {
    "peak_berthing_delay_days": 2.0,
    "recovered_wait_days": 1.0,
    "port_stay_inflation_pct": 12.0,
}

#: Why each row lands where it does. Written once, from the structure of the
#: model rather than from any particular run's numbers, so a run that happens
#: to fall inside tolerance still carries the reason not to read it as proof.
ANCHOR_INTERPRETATIONS: dict[str, str] = {
    "peak_berthing_delay_days": (
        "Expected to under-predict. The recorded peak was driven largely by "
        "vessels arriving off-schedule - 90% in 2024 against 77% in 2023 - and "
        "PortWatch records the day a ship arrived, not the day it was due, so "
        "that bunching is absent from the stream the simulation is fed."
    ),
    "recovered_wait_days": (
        "Read with care. This is the baseline's wait on the last day of the "
        "window, not a recovery: the reactive arm never recovers, because it "
        "never adds capacity. The recorded port recovered because PSA "
        "reactivated Keppel berths and hired around 1,500 staff. Proximity to "
        "the recorded figure here is coincidence, not agreement."
    ),
    "port_stay_inflation_pct": (
        "Expected to over-predict. The simulated figure compounds the recorded "
        "rise in volume per call with the model's own congestion feedback, "
        "while the recorded +22% is the net outcome at a port that was actively "
        "adding capacity throughout the period."
    ),
}


def _historical_arm(truth: GroundTruthFixture, window: DateWindow, charter: float) -> ArmResult:
    """The recorded arm: the reconstructed curve, carried through untouched.

    Only the two fields the curve actually contains are populated. Arrivals,
    berthings, queue lengths and utilisation are left at zero rather than
    invented, because the reconstruction says nothing about them and a
    plausible-looking fabricated number is worse than an obvious blank.
    """
    points = [
        point for point in truth.historical_wait_curve if window.start <= point.date <= window.end
    ]
    daily = [
        DailyKpi(
            date=point.date,
            day_index=(point.date - window.start).days,
            arrivals=0,
            berthings=0,
            departures=0,
            queue_length=0,
            mean_wait_days=point.wait_days,
            rolling_wait_days=point.wait_days,
            active_berths=0,
            teu_waiting=0.0,
            utilisation=0.0,
        )
        for point in points
    ]
    if not daily:
        raise ValueError("the reconstructed curve does not cover the blind window")

    peak_index = max(range(len(daily)), key=lambda i: (daily[i].rolling_wait_days, -i))
    return ArmResult(
        arm=FleetArm.HISTORICAL,
        label=ARM_LABELS[FleetArm.HISTORICAL],
        provenance=truth.historical_curve_provenance,
        is_simulation=False,
        daily=daily,
        metrics=FleetMetrics(
            peak_wait_days=daily[peak_index].rolling_wait_days,
            peak_wait_date=daily[peak_index].date,
            recovery_date=_recovery_from_curve(daily, peak_index),
            days_above_two_day_wait=sum(1 for day in daily if day.rolling_wait_days > 2.0),
            mean_wait_days=sum(day.rolling_wait_days for day in daily) / len(daily),
            # Port stay, throughput and TEU are not reconstructible from a wait
            # curve. Zero here means "this arm has no such figure", and the UI
            # must not draw it as one.
            mean_port_stay_hours=0.0,
            port_stay_inflation_pct=0.0,
            vessels_served=0,
            teu_served=0.0,
            missed_connection_proxy=0,
            wait_cost_usd=sum(day.rolling_wait_days for day in daily) * charter,
        ),
        decisions=[],
        caveat=HISTORICAL_CAVEAT,
    )


def _recovery_from_curve(daily: list[DailyKpi], peak_index: int) -> date | None:
    """First post-peak day whose wait stays at or under two days for five days.

    The same rule ``compute_metrics`` applies to the simulated arms, restated
    here only because the historical arm has no vessel records to run it on.
    """
    for start in range(peak_index + 1, len(daily)):
        window = daily[start : start + 5]
        if len(window) < 5:
            return None
        if all(day.rolling_wait_days <= 2.0 for day in window):
            return window[0].date
    return None


def _make_brain(mode: FleetBrainMode) -> "FleetBrain":
    """Resolve the brain for the agentic arms.

    SCRIPTED is the default and the scored configuration. The live modes are
    constructed lazily so a run with no API key and no network still works, and
    each of them falls back to the scripted brain per epoch anyway.
    """
    from cascade.agents.scripted import ScriptedFleetBrain

    if mode is FleetBrainMode.LIVE_GEMINI:
        from cascade.agents.live_gemini import GeminiBrain

        return GeminiBrain.create()
    if mode is FleetBrainMode.LIVE_CLAUDE:
        from cascade.agents.local_claude import ClaudeBrain

        return ClaudeBrain.create()
    return ScriptedFleetBrain()


def _simulated_arm(
    arm: FleetArm,
    config: BenchmarkConfig,
    world: FleetWorldConfig,
    blind: BlindSlice,
    report: CalibrationReport,
    charter: float,
) -> ArmResult:
    """Run one simulated arm on a feed of its own over the same blind window."""
    feed = BlindFeed(blind, SimClock(day_start(blind.window.start)))
    if arm is FleetArm.REACTIVE_BASELINE:
        outcome = simulate(
            world,
            feed,
            ReactiveBaselinePolicy(),
            window=blind.window,
            rolling_window_days=config.rolling_window_days,
        )
    else:
        brain = _make_brain(config.brain)
        policy = (
            AgenticFleetPolicy(brain, world)
            if arm is FleetArm.CASCADE_AGENTIC
            else make_agentic_policy(brain, world, allow_reserve_activation=False)
        )
        outcome = simulate(
            world,
            feed,
            policy,
            window=blind.window,
            rolling_window_days=config.rolling_window_days,
            decision_source=brain_decision_source(brain),
        )

    return ArmResult(
        arm=arm,
        label=ARM_LABELS[arm],
        provenance=SeriesProvenance.SIMULATED,
        is_simulation=True,
        daily=outcome.daily,
        metrics=compute_metrics(
            outcome.daily,
            outcome.records,
            # The arm's own 2023-calibrated port stay, so inflation is measured
            # against the same world that produced it and not against a figure
            # borrowed from another arm.
            baseline_port_stay_hours=report.simulated_mean_port_stay_hours,
            charter_rate_usd_per_day=charter,
            recovery_threshold_days=config.recovery_threshold_days,
            recovery_sustain_days=config.recovery_sustain_days,
        ),
        decisions=outcome.decisions,
        blind_audit=outcome.blind_audit,
        calibration=report,
        caveat=(
            "No reserve capacity: prioritisation levers only. The stress arm "
            "exists to show how much of the result survives without berths."
            if arm is FleetArm.CASCADE_NO_EXTRA_CAPACITY
            else None
        ),
    )


def _ordinal(when: date | None) -> float | None:
    return None if when is None else float(when.toordinal())


def recovery_rank(days_above_threshold: int, recovered_at: float | None) -> float:
    """How well an arm came through the crisis, lower being better.

    ``recovery_date`` alone cannot answer this. It is the first sustained quiet
    run *after the peak*, which says nothing about whether the peak was ever a
    problem: an arm that never crossed the two-day threshold has its recovery
    date land the day after its peak, and gets ``None`` only when that peak
    happens to fall within the sustain window of the last day. Ranking on it
    directly therefore put an arm that never breached at all - the best
    outcome available - level with one that breached and never came back, and
    made the comparison turn on where in the window a harmless peak fell.

    The three cases are ranked explicitly instead:

    - never breached, so there was nothing to recover from: best,
    - breached and recovered: ranked by how early,
    - breached and still above the threshold at the end: worst.

    ``recovered_at`` is any increasing measure of when recovery happened - a
    date ordinal here, a day index in the sweep. It is a bare number rather
    than a ``date`` so that this function is the single definition of a
    recovery win for both callers; two rules would eventually disagree.
    """
    if days_above_threshold == 0:
        return -1.0
    if recovered_at is None:
        return math.inf
    return recovered_at


def _compare(arm: ArmResult, base: ArmResult) -> ArmComparison:
    """One head-to-head. Positive deltas always mean ``arm`` did better."""
    peak_delta = base.metrics.peak_wait_days - arm.metrics.peak_wait_days
    base_peak = base.metrics.peak_wait_days
    recovery_saved: float | None = None
    if arm.metrics.recovery_date is not None and base.metrics.recovery_date is not None:
        recovery_saved = float((base.metrics.recovery_date - arm.metrics.recovery_date).days)
    return ArmComparison(
        arm=arm.arm,
        versus=base.arm,
        peak_wait_delta_days=peak_delta,
        peak_wait_reduction_pct=(peak_delta / base_peak * 100.0) if base_peak > 0 else 0.0,
        recovery_days_saved=recovery_saved,
        mean_wait_delta_days=base.metrics.mean_wait_days - arm.metrics.mean_wait_days,
        wait_cost_delta_usd=base.metrics.wait_cost_usd - arm.metrics.wait_cost_usd,
        wins_on_peak=arm.metrics.peak_wait_days < base.metrics.peak_wait_days,
        wins_on_recovery=(
            recovery_rank(arm.metrics.days_above_two_day_wait, _ordinal(arm.metrics.recovery_date))
            < recovery_rank(
                base.metrics.days_above_two_day_wait, _ordinal(base.metrics.recovery_date)
            )
        ),
    )


def _anchor_comparisons(
    truth: GroundTruthFixture, arms: dict[FleetArm, ArmResult]
) -> list[AnchorComparison]:
    """Hold the recorded scalars next to what the baseline arm produced.

    The comparator is REACTIVE_BASELINE throughout, and deliberately so:
    scoring CASCADE against the recorded anchors would reward it for beating a
    number the model never had the information to reach.

    These rows are disclosure, not validation. The recorded congestion was
    driven by vessels arriving off-schedule and by re-handling, neither of
    which appears in the PortWatch series the simulation is fed; the one crisis
    mechanism that does appear - roughly 21% more container volume per call
    across the blind window - is in the fixture and is what makes the simulated
    port congest at all. Expect the peak to be under-predicted and port-stay
    inflation to be over-predicted, and expect the gap to be reported rather
    than closed. Nothing in this module tunes anything to move these rows.
    """
    base = arms.get(COMPARISON_BASE)
    if base is None:
        return []

    simulated: dict[str, float] = {
        "peak_berthing_delay_days": base.metrics.peak_wait_days,
        "recovered_wait_days": base.daily[-1].rolling_wait_days if base.daily else 0.0,
        "port_stay_inflation_pct": base.metrics.port_stay_inflation_pct,
    }
    comparisons = []
    for anchor in truth.anchors:
        tolerance = ANCHOR_TOLERANCES.get(anchor.key)
        if tolerance is None:
            continue
        value = simulated[anchor.key]
        comparisons.append(
            AnchorComparison(
                anchor_key=anchor.key,
                label=anchor.label,
                recorded_value=anchor.value,
                recorded_provenance=anchor.provenance,
                simulated_value=value,
                unit=anchor.unit,
                tolerance=tolerance,
                within_tolerance=abs(value - anchor.value) <= tolerance,
                interpretation=ANCHOR_INTERPRETATIONS[anchor.key],
            )
        )
    return comparisons


#: The knobs the robustness sweep turns, and the value each is held at while
#: the service model is being fitted. Stripping them is not an optimisation, it
#: is the point of the sweep: calibrating a port that has been made 15% slower
#: would simply refit ``efficiency`` upward until the fitted world produced the
#: same throughput again, cancelling the perturbation and leaving a "robustness"
#: run that perturbs nothing. The fit is therefore always the same fit, and the
#: perturbation is applied to the world the arms actually run in.
#:
#: ``seed`` is neutralised for a different reason: calibration runs FCFS over a
#: fixed stream with jitter off, so the seed cannot reach the fitted parameters
#: at all, and letting it into the key would defeat the memo for exactly the
#: multi-seed sweep it exists to serve.
_CALIBRATION_NEUTRAL: dict[str, object] = {
    "seed": 0,
    "service_rate_multiplier": 1.0,
    "arrival_jitter_hours": 0.0,
    "berth_delta": 0,
    "activation_lead_override_days": None,
}


#: Fitted worlds, keyed by everything the fit depends on. Calibration is a
#: coordinate search over a 425-day window and costs tens of seconds, but its
#: inputs are a pinned fixture and a neutralised world, so a sweep of 25 seeds
#: across a parameter grid would otherwise pay for the identical fit hundreds of
#: times. The key includes the fixture hash, so regenerating the fixtures
#: invalidates it rather than silently serving a fit of the old data.
_CALIBRATION_CACHE: dict[tuple[str, str], CalibrationReport] = {}

#: Single-flight guard for the cache. The fit costs tens of seconds of CPU, so
#: a benchmark started while the boot-time warmup is still fitting must wait
#: for that fit rather than race it on a second core.
_CALIBRATION_LOCK = threading.Lock()


def _calibrate_cached(
    slice_: CalibrationSlice, world: FleetWorldConfig, hashes: dict[str, str]
) -> CalibrationReport:
    """``calibrate``, memoised on the fixture hash and the world it fits."""
    base = world.model_copy(update=_CALIBRATION_NEUTRAL)
    key = (hashes.get(f"fixtures/{CRISIS_ARRIVALS_FILE}", ""), base.model_dump_json())
    with _CALIBRATION_LOCK:
        cached = _CALIBRATION_CACHE.get(key)
        if cached is None:
            cached = calibrate(slice_, base)
            _CALIBRATION_CACHE[key] = cached
        return cached


def warm_calibration(world: FleetWorldConfig) -> None:
    """Pay the one-off calibration fit before the first benchmark asks for it."""
    arrivals = load_crisis_arrivals()
    manifest = load_crisis_manifest()
    _calibrate_cached(arrivals.calibration, world, manifest.hashes)


def run_benchmark(config: BenchmarkConfig) -> BenchmarkResult:
    """Run every arm in ``config`` and score them. Pure, deterministic."""
    started = time.perf_counter()
    arrivals = load_crisis_arrivals()
    truth = load_crisis_ground_truth()
    manifest = load_crisis_manifest()
    charter = truth.charter_rate_usd_per_day

    # Calibration happens once, on the calibration slice only. Its type is
    # CalibrationSlice, so the blind days cannot reach it even by mistake.
    report = _calibrate_cached(arrivals.calibration, config.world, manifest.hashes)
    fitted = config.world.model_copy(
        update={
            "seed": config.seed,
            "service": report.fitted,
            # The calibrated effective count, plus whatever the config asked
            # for on top. Adding rather than replacing is what lets a sweep
            # cell run the port one berth short: the calibration owns the
            # fitted part of this number, ``world.berth_delta`` owns the
            # perturbation, and neither can silently overwrite the other.
            "berth_delta": (
                report.effective_berths
                - config.world.berths.active_berths
                + config.world.berth_delta
            ),
        }
    )

    results: dict[FleetArm, ArmResult] = {}
    for arm in config.arms:
        results[arm] = (
            _historical_arm(truth, arrivals.blind.window, charter)
            if arm is FleetArm.HISTORICAL
            else _simulated_arm(arm, config, fitted, arrivals.blind, report, charter)
        )

    base = results.get(COMPARISON_BASE)
    comparisons = (
        [
            _compare(result, base)
            for arm, result in results.items()
            if result.is_simulation and arm is not COMPARISON_BASE
        ]
        if base is not None
        else []
    )

    return BenchmarkResult(
        benchmark_id=f"bench-{config.seed}",
        config=config,
        calibration_window=arrivals.calibration.window,
        blind_window=arrivals.blind.window,
        historical_arm_provenance=truth.historical_curve_provenance,
        arms=[results[arm] for arm in config.arms],
        comparisons=comparisons,
        anchor_comparisons=_anchor_comparisons(truth, results),
        fixture_hashes={
            name: manifest.hashes[name]
            for name in (f"fixtures/{CRISIS_ARRIVALS_FILE}", f"fixtures/{CRISIS_GROUND_TRUTH_FILE}")
            if name in manifest.hashes
        },
        runtime_ms=int((time.perf_counter() - started) * 1000),
        notice=BENCHMARK_NOTICE,
    )
