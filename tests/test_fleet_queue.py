"""Queueing correctness for the fleet discrete-event engine (PRD 9.22)."""

from datetime import date, timedelta
from random import Random

import pytest
from fleet_world import (
    make_arrival_day,
    make_blind_slice,
    make_service_config,
    make_tranche,
    make_world_config,
    poisson_arrival_slice,
)

from cascade.contracts import (
    ArrivalDay,
    BlindSlice,
    Confidence,
    DateWindow,
    FleetDecision,
    FleetDecisionType,
    FleetPolicyView,
    FleetStrategy,
    FleetWorldConfig,
    QueueDiscipline,
    VesselArrival,
)
from cascade.engine.fleet import (
    BlindFeed,
    DayCounters,
    FcfsPolicy,
    SimClock,
    SimulationOutcome,
    VesselRecord,
    build_daily_kpis,
    compute_metrics,
    day_start,
    erlang_c_wait_days,
    service_hours,
    simulate,
    validate_fleet_decision,
)

START = date(2024, 4, 1)


class OnDayPolicy:
    """Emits a fixed set of decisions on one day and holds on every other."""

    def __init__(self, day: date, decisions: list[FleetDecision]) -> None:
        self._day = day
        self._decisions = decisions
        self.views: list[FleetPolicyView] = []

    def decide(self, view: FleetPolicyView) -> FleetStrategy:
        self.views.append(view)
        return FleetStrategy(
            decisions=self._decisions if view.today == self._day else [],
            summary="scripted test policy",
            confidence=Confidence.MEDIUM,
        )


def run(blind: BlindSlice, world: FleetWorldConfig, policy: object = None) -> SimulationOutcome:
    feed = BlindFeed(blind, SimClock(day_start(blind.window.start)))
    chosen = FcfsPolicy() if policy is None else policy
    return simulate(world, feed, chosen, window=blind.window)  # type: ignore[arg-type]


def one_day_slice(sizes: list[tuple[float, float]], *, spacing_minutes: int = 5) -> BlindSlice:
    """A single day whose calls arrive minutes apart, so they all queue up."""
    midnight = day_start(START)
    arrivals = [
        VesselArrival(
            vessel_id=f"S-{index:02d}",
            arrival=midnight + timedelta(minutes=spacing_minutes * index),
            teu=teu,
            connection_teu=connection,
        )
        for index, (teu, connection) in enumerate(sizes)
    ]
    return BlindSlice(
        window=DateWindow(label="one day", start=START, end=START),
        days=[ArrivalDay(date=START, portcalls_container=len(arrivals), arrivals=arrivals)],
    )


def test_fcfs_serves_vessels_in_arrival_order() -> None:
    blind = one_day_slice([(1200.0, 300.0), (900.0, 800.0), (2400.0, 100.0), (600.0, 50.0)])
    outcome = run(blind, make_world_config(active_berths=1, tranches=[]))

    by_start = sorted(outcome.records, key=lambda record: record.berth_start)
    assert [record.vessel_id for record in by_start] == ["S-00", "S-01", "S-02", "S-03"]
    assert [record.arrival for record in by_start] == sorted(
        record.arrival for record in outcome.records
    )


def test_connection_weighted_serves_the_largest_connection_load_first() -> None:
    blind = one_day_slice([(1200.0, 300.0), (900.0, 800.0), (2400.0, 100.0), (600.0, 500.0)])
    world = make_world_config(active_berths=1, tranches=[])
    policy = OnDayPolicy(
        START,
        [
            FleetDecision(
                type=FleetDecisionType.SET_QUEUE_DISCIPLINE,
                discipline=QueueDiscipline.CONNECTION_WEIGHTED,
                rationale="drain transhipment backlog first",
            )
        ],
    )
    outcome = run(blind, world, policy)

    order = [record.vessel_id for record in sorted(outcome.records, key=lambda r: r.berth_start)]
    # S-00 berths on arrival with an empty queue; the rest are ranked by
    # connection TEU descending: 800, 500, 100.
    assert order == ["S-00", "S-01", "S-03", "S-02"]


def test_priority_discharge_clears_the_smallest_calls_first() -> None:
    blind = one_day_slice([(1200.0, 300.0), (900.0, 800.0), (2400.0, 100.0), (600.0, 500.0)])
    policy = OnDayPolicy(
        START,
        [
            FleetDecision(
                type=FleetDecisionType.SET_QUEUE_DISCIPLINE,
                discipline=QueueDiscipline.PRIORITY_DISCHARGE,
                rationale="clear small calls to drain the queue",
            )
        ],
    )
    outcome = run(blind, make_world_config(active_berths=1, tranches=[]), policy)

    order = [record.vessel_id for record in sorted(outcome.records, key=lambda r: r.berth_start)]
    assert order == ["S-00", "S-03", "S-01", "S-02"]


def test_conservation_holds_at_every_day_boundary() -> None:
    blind = make_blind_slice(day_count=45, surge_days=range(8, 22), surge_extra=6)
    outcome = run(blind, make_world_config())

    arrived = departed = 0
    for counter in outcome.counters:
        arrived += counter.arrivals
        departed += counter.departures
        assert arrived == departed + counter.in_service + counter.queue_length
    assert arrived == sum(len(day.arrivals) for day in blind.days)


def test_waits_are_never_negative() -> None:
    blind = make_blind_slice(day_count=45, surge_days=range(8, 22), surge_extra=6)
    outcome = run(blind, make_world_config())

    assert outcome.records
    for record in outcome.records:
        assert record.wait_days >= 0.0
        assert record.berth_end >= record.berth_start >= record.arrival
    assert all(day.rolling_wait_days >= 0.0 for day in outcome.daily)


def test_mmc_mean_wait_matches_erlang_c() -> None:
    """Poisson arrivals plus exponential service must reproduce Erlang-C.

    60,000 vessels at 70 percent utilisation. The M/M/c queue is strongly
    autocorrelated, so the sample mean converges slowly; 10 percent is the
    tolerance that batch holds comfortably at this sample size (the measured
    error for this seed is about 5 percent, and it falls below 2 percent at
    200,000 vessels).
    """
    rate, servers, mean_service_days = 11.2, 4, 0.25
    blind = poisson_arrival_slice(vessels=60_000, arrival_rate_per_day=rate, mean_teu=6.0, seed=3)
    service = make_service_config(
        base_hours=0.0,
        cranes_per_berth=1.0,
        moves_per_crane_hour=1.0,
        teu_per_move=1.0,
        efficiency=1.0,
        congestion_alpha=0.0,
    )
    outcome = run(blind, make_world_config(active_berths=servers, service=service, tranches=[]))

    simulated = sum(record.wait_days for record in outcome.records) / len(outcome.records)
    predicted = erlang_c_wait_days(rate, mean_service_days, servers)
    assert len(outcome.records) == 60_000
    assert abs(simulated / predicted - 1.0) < 0.10


def test_reserve_activation_respects_the_lead_time_to_the_day() -> None:
    blind = make_blind_slice(day_count=30)
    tranche = make_tranche("keppel-1", berths=2, activation_lead_days=10)
    world = make_world_config(active_berths=8, tranches=[tranche])
    decision_day = START + timedelta(days=2)
    policy = OnDayPolicy(
        decision_day,
        [
            FleetDecision(
                type=FleetDecisionType.ACTIVATE_RESERVE_BERTHS,
                tranche_id="keppel-1",
                rationale="reactivate reserve capacity",
            )
        ],
    )
    outcome = run(blind, world, policy)

    recorded = outcome.decisions[0]
    assert recorded.accepted
    assert recorded.effective_date == decision_day + timedelta(days=10)
    before = [day for day in outcome.daily if day.date < recorded.effective_date]
    after = [day for day in outcome.daily if day.date >= recorded.effective_date]
    assert {day.active_berths for day in before} == {8}
    assert {day.active_berths for day in after} == {10}


def test_activation_before_available_from_is_rejected() -> None:
    blind = make_blind_slice(day_count=10)
    tranche = make_tranche(
        "tuas-2", berths=3, activation_lead_days=0, available_from=START + timedelta(days=30)
    )
    policy = OnDayPolicy(
        START,
        [
            FleetDecision(
                type=FleetDecisionType.ACTIVATE_RESERVE_BERTHS,
                tranche_id="tuas-2",
                rationale="too early",
            )
        ],
    )
    outcome = run(blind, make_world_config(tranches=[tranche]), policy)

    assert outcome.decisions[0].accepted is False
    assert "not available before" in str(outcome.decisions[0].rejection_reason)
    assert {day.active_berths for day in outcome.daily} == {8}


def _view(today: date, **overrides: object) -> FleetPolicyView:
    fields: dict[str, object] = {
        "today": today,
        "day_index": 0,
        "history": [],
        "active_berths": 8,
        "reserves_available": [make_tranche()],
        "pending_activations": [],
        "queue_discipline": QueueDiscipline.FCFS,
        "fast_connection_mode": False,
        "workforce_surge_level": 0,
    }
    fields.update(overrides)
    return FleetPolicyView(**fields)


def test_validate_rejects_out_of_bounds_surge() -> None:
    world = make_world_config()
    decision = FleetDecision(
        type=FleetDecisionType.WORKFORCE_SURGE, surge_level=None, rationale="no level"
    )
    assert validate_fleet_decision(decision, _view(START), world) == (
        "WORKFORCE_SURGE requires surge_level"
    )
    valid = decision.model_copy(update={"surge_level": 2})
    assert validate_fleet_decision(valid, _view(START), world) is None
    too_high = FleetDecision.model_construct(
        type=FleetDecisionType.WORKFORCE_SURGE, surge_level=5, rationale="above the cap"
    )
    assert "outside 0..2" in str(validate_fleet_decision(too_high, _view(START), world))


def test_validate_rejects_unknown_and_already_active_tranches() -> None:
    world = make_world_config()
    unknown = FleetDecision(
        type=FleetDecisionType.ACTIVATE_RESERVE_BERTHS,
        tranche_id="nope",
        rationale="unknown tranche",
    )
    assert "unknown reserve tranche" in str(validate_fleet_decision(unknown, _view(START), world))

    known = unknown.model_copy(update={"tranche_id": "keppel-1"})
    assert validate_fleet_decision(known, _view(START), world) is None
    assert "already active" in str(
        validate_fleet_decision(known, _view(START, reserves_available=[]), world)
    )


def test_validate_rejects_double_activation_and_cooldown() -> None:
    blind = make_blind_slice(day_count=12)
    activate = FleetDecision(
        type=FleetDecisionType.ACTIVATE_RESERVE_BERTHS,
        tranche_id="keppel-1",
        rationale="twice in one epoch",
    )

    class RepeatPolicy:
        def decide(self, view: FleetPolicyView) -> FleetStrategy:
            decisions = [activate] if view.day_index in (0, 1, 3) else []
            return FleetStrategy(
                decisions=decisions, summary="repeat pull", confidence=Confidence.LOW
            )

    outcome = run(blind, make_world_config(), RepeatPolicy())
    reasons = [decision.rejection_reason for decision in outcome.decisions]
    assert [decision.accepted for decision in outcome.decisions] == [True, False, False]
    assert "cooldown" in str(reasons[1])
    assert "already pending" in str(reasons[2])


def test_determinism_for_a_fixed_seed() -> None:
    blind = make_blind_slice(day_count=40, surge_days=range(5, 20), surge_extra=5)
    world = make_world_config(arrival_jitter_hours=2.0)

    first = run(blind, world)
    second = run(blind, world)
    assert [day.model_dump() for day in first.daily] == [day.model_dump() for day in second.daily]


def test_full_length_run_is_fast() -> None:
    """A 150-day, ~2,000-vessel arm is the benchmark's unit of work."""
    from time import perf_counter

    blind = make_blind_slice(day_count=150, per_day=13, surge_days=range(30, 60), surge_extra=4)
    assert sum(len(day.arrivals) for day in blind.days) >= 1_900
    world = make_world_config(active_berths=9)

    started = perf_counter()
    outcome = run(blind, world)
    elapsed = perf_counter() - started

    assert len(outcome.daily) == 150
    assert elapsed < 2.0


def test_arrival_days_are_only_revealed_as_the_clock_reaches_them() -> None:
    rng = Random(5)
    days = [make_arrival_day(START + timedelta(days=offset), 6, rng) for offset in range(5)]
    blind = BlindSlice(
        window=DateWindow(label="reveal", start=START, end=START + timedelta(days=4)), days=days
    )
    outcome = run(blind, make_world_config())

    assert outcome.blind_audit.total_reads == 5
    assert outcome.blind_audit.max_lookahead_seconds == 0.0
    assert outcome.blind_audit.violations == 0


@pytest.mark.parametrize("discipline", list(QueueDiscipline))
def test_every_discipline_serves_every_vessel(discipline: QueueDiscipline) -> None:
    blind = make_blind_slice(day_count=20, surge_days=range(4, 10), surge_extra=4)
    policy = OnDayPolicy(
        START,
        [
            FleetDecision(
                type=FleetDecisionType.SET_QUEUE_DISCIPLINE,
                discipline=discipline,
                rationale="exercise the discipline",
            )
        ],
    )
    outcome = run(blind, make_world_config(), policy)
    assert len(outcome.records) == sum(len(day.arrivals) for day in blind.days)


# --- service model and metrics ----------------------------------------------


def test_levers_shorten_service_time() -> None:
    service = make_service_config()
    plain = service_hours(teu=1400.0, connection_teu=700.0, queue_length=20, service=service)
    surged = service_hours(
        teu=1400.0, connection_teu=700.0, queue_length=20, service=service, surge_level=2
    )
    fast = service_hours(
        teu=1400.0, connection_teu=700.0, queue_length=20, service=service, fast_connection=True
    )
    quiet = service_hours(teu=1400.0, connection_teu=700.0, queue_length=0, service=service)

    assert quiet < plain, "congestion feedback must lengthen calls"
    assert surged < plain, "workforce surge absorbs congestion and lifts efficiency"
    assert fast == pytest.approx(plain * (0.5 + 0.5 * service.fast_connection_speedup))
    capped = service_hours(teu=1400.0, connection_teu=0.0, queue_length=10_000, service=service)
    assert capped == pytest.approx(quiet * (1 + service.congestion_alpha * service.congestion_cap))


def make_counters(waits: list[float]) -> tuple[list[DayCounters], list[VesselRecord]]:
    """One vessel a day, with the given wait in days."""
    counters: list[DayCounters] = []
    records: list[VesselRecord] = []
    for index, wait in enumerate(waits):
        day = START + timedelta(days=index)
        counters.append(
            DayCounters(
                date=day,
                day_index=index,
                arrivals=1,
                berthings=1,
                departures=1,
                queue_length=0,
                in_service=0,
                active_berths=4,
                teu_waiting=0.0,
                busy_berth_hours=48.0,
            )
        )
        arrival = day_start(day) - timedelta(days=wait)
        records.append(
            VesselRecord(
                vessel_id=f"M-{index:02d}",
                arrival=arrival,
                berth_start=day_start(day),
                berth_end=day_start(day) + timedelta(hours=12),
                teu=1000.0,
                connection_teu=400.0,
            )
        )
    return counters, records


def test_rolling_wait_averages_the_trailing_window() -> None:
    counters, records = make_counters([0.0, 3.0, 6.0, 9.0])
    daily = build_daily_kpis(counters, records, rolling_window_days=3)
    assert [day.rolling_wait_days for day in daily] == [0.0, 1.5, 3.0, 6.0]


def test_recovery_needs_a_sustained_return_below_the_threshold() -> None:
    counters, records = make_counters([0.5, 6.0, 6.0, 1.0, 5.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    daily = build_daily_kpis(counters, records, rolling_window_days=1)
    metrics = compute_metrics(
        daily,
        records,
        baseline_port_stay_hours=12.0,
        charter_rate_usd_per_day=10_000.0,
        recovery_threshold_days=2.0,
        recovery_sustain_days=5,
    )

    assert metrics.peak_wait_days == 6.0
    assert metrics.peak_wait_date == START + timedelta(days=1)
    # Day 3 dips below the threshold but day 4 spikes again, so recovery only
    # starts at day 5, the first of five sustained days.
    assert metrics.recovery_date == START + timedelta(days=5)
    assert metrics.days_above_two_day_wait == 3
    assert metrics.vessels_served == 10
    # Three vessels waited longer than the one-day connection buffer.
    assert metrics.missed_connection_proxy == 3
    assert metrics.wait_cost_usd == pytest.approx(sum([0.5, 6, 6, 1, 5, 1, 1, 1, 1, 1]) * 10_000)
    assert metrics.port_stay_inflation_pct > 0.0


def test_metrics_need_a_daily_series() -> None:
    with pytest.raises(ValueError, match="daily series"):
        compute_metrics([], [], baseline_port_stay_hours=12.0, charter_rate_usd_per_day=1.0)
