"""Policy arms and the FleetBrain seam (PRD 9.24, 9.25).

Two claims are under test here and they are different claims.

The first is a performance claim: on a synthetic congested window the agentic
arm beats the reactive baseline on peak rolling wait and on time-to-recover.
For that to mean anything, both arms must run the identical engine over the
identical world - so every comparison below builds ONE ``FleetWorldConfig`` and
passes the same object to both runs, and asserts they were equal.

The second is a governance claim: the brain never changes a number. A decision
outside the menu is rejected, recorded with its reason, and changes no state; a
brain that fails hands the epoch to the deterministic scripted brain and the
fallback is visible in the source label.
"""

from datetime import date, timedelta

import pytest
from fleet_world import make_blind_slice, make_tranche, make_world_config

from cascade.agents.base import fleet_strategy_message
from cascade.agents.local_claude import ClaudeBrain
from cascade.agents.scripted import ScriptedFleetBrain
from cascade.contracts import (
    AuditVerdict,
    BlindSlice,
    Confidence,
    DateWindow,
    DecisionSource,
    FleetDecision,
    FleetDecisionType,
    FleetMetrics,
    FleetPolicyView,
    FleetStrategy,
    FleetWorldConfig,
    QueueDiscipline,
)
from cascade.engine.fleet import (
    AgenticFleetPolicy,
    BlindFeed,
    ReactiveBaselinePolicy,
    SimClock,
    SimulationOutcome,
    compute_metrics,
    day_start,
    simulate,
)

START = date(2024, 4, 1)

# The synthetic congested window. A 120-day run at 10 container calls a day on
# nine berths (comfortably inside capacity), with a 16-day surge to 18 a day
# from day 20, which is beyond it. The surge builds a backlog that the port
# then has to drain: the reactive arm is still above a two-day wait more than
# two months later, which is the shape of the recorded 2024 event.
#
# The window is deliberately long enough that BOTH arms fully recover inside
# it. A shorter window flatters whichever arm never clears its backlog, because
# peak wait is measured at berth start and a vessel that never berths never
# contributes to it.
DAY_COUNT = 120
BASE_ARRIVALS_PER_DAY = 10
SURGE_DAYS = range(20, 36)
SURGE_EXTRA_ARRIVALS = 8
ACTIVE_BERTHS = 9

BASELINE_PORT_STAY_HOURS = 24.0
CHARTER_RATE_USD_PER_DAY = 50_000.0


def congested_window() -> BlindSlice:
    return make_blind_slice(
        start=START,
        day_count=DAY_COUNT,
        per_day=BASE_ARRIVALS_PER_DAY,
        surge_days=SURGE_DAYS,
        surge_extra=SURGE_EXTRA_ARRIVALS,
    )


def congested_world() -> FleetWorldConfig:
    return make_world_config(
        active_berths=ACTIVE_BERTHS,
        tranches=[
            make_tranche("keppel-1", berths=2, activation_lead_days=10),
            make_tranche("keppel-2", berths=2, activation_lead_days=14),
        ],
    )


def window() -> DateWindow:
    return DateWindow(
        label="synthetic congested window",
        start=START,
        end=START + timedelta(days=DAY_COUNT - 1),
    )


def run_arm(
    policy: object, world: FleetWorldConfig, blind: BlindSlice
) -> tuple[SimulationOutcome, FleetMetrics]:
    """Run one arm. Every arm in this file goes through this one function."""
    span = window()
    feed = BlindFeed(blind, SimClock(day_start(span.start)))
    outcome = simulate(world, feed, policy, window=span)  # type: ignore[arg-type]
    metrics = compute_metrics(
        outcome.daily,
        outcome.records,
        baseline_port_stay_hours=BASELINE_PORT_STAY_HOURS,
        charter_rate_usd_per_day=CHARTER_RATE_USD_PER_DAY,
    )
    return outcome, metrics


def a_view(today: date = START, **overrides: object) -> FleetPolicyView:
    fields: dict[str, object] = {
        "today": today,
        "day_index": 0,
        "history": [],
        "active_berths": ACTIVE_BERTHS,
        "reserves_available": [make_tranche()],
        "pending_activations": [],
        "queue_discipline": QueueDiscipline.FCFS,
        "fast_connection_mode": False,
        "workforce_surge_level": 0,
    }
    fields.update(overrides)
    return FleetPolicyView.model_validate(fields)


# --- the baseline arm -------------------------------------------------------


def test_the_baseline_arm_never_pulls_a_lever() -> None:
    world = congested_world()
    outcome, metrics = run_arm(ReactiveBaselinePolicy(), world, congested_window())

    assert outcome.decisions == []
    assert {day.active_berths for day in outcome.daily} == {ACTIVE_BERTHS}
    # Discipline, surge and fast connection have no per-day KPI, so they are
    # asserted where they would show: the policy proposes nothing, ever.
    policy = ReactiveBaselinePolicy()
    for day_index in range(DAY_COUNT):
        strategy = policy.decide(a_view(START + timedelta(days=day_index)))
        assert strategy.decisions == []
    assert metrics.vessels_served > 0


# --- the agentic arm --------------------------------------------------------


def test_the_agentic_arm_beats_the_baseline_on_peak_and_recovery() -> None:
    blind = congested_window()
    world = congested_world()

    baseline_outcome, baseline = run_arm(ReactiveBaselinePolicy(), world, blind)
    policy = AgenticFleetPolicy(ScriptedFleetBrain(), world)
    agentic_outcome, agentic = run_arm(policy, world, blind)

    # Same engine, same world object, same seed: only the policy differed.
    assert world == congested_world()
    assert world.seed == congested_world().seed
    assert len(baseline_outcome.daily) == len(agentic_outcome.daily)

    assert baseline.peak_wait_days > 5.0, "the window must actually congest the baseline"
    assert agentic.peak_wait_days < baseline.peak_wait_days
    assert baseline.recovery_date is not None
    assert agentic.recovery_date is not None
    assert agentic.recovery_date < baseline.recovery_date
    assert agentic.mean_wait_days < baseline.mean_wait_days
    assert agentic.days_above_two_day_wait < baseline.days_above_two_day_wait
    assert agentic.vessels_served == baseline.vessels_served

    accepted = [record for record in agentic_outcome.decisions if record.accepted]
    assert accepted, "the agentic arm must actually pull levers"
    assert all(record.rejection_reason is None for record in accepted)
    assert {record.decision.type for record in accepted} >= {
        FleetDecisionType.ACTIVATE_RESERVE_BERTHS,
        FleetDecisionType.WORKFORCE_SURGE,
        FleetDecisionType.SET_QUEUE_DISCIPLINE,
        FleetDecisionType.FAST_CONNECTION_MODE,
    }


def test_reserve_capacity_only_arrives_after_its_activation_lead() -> None:
    blind = congested_window()
    world = congested_world()
    outcome, _ = run_arm(AgenticFleetPolicy(ScriptedFleetBrain(), world), world, blind)

    activations = [
        record
        for record in outcome.decisions
        if record.decision.type is FleetDecisionType.ACTIVATE_RESERVE_BERTHS and record.accepted
    ]
    assert activations, "the scripted brain must reach for capacity on this window"
    berths_on = {day.date: day.active_berths for day in outcome.daily}
    for record in activations:
        assert record.effective_date is not None
        assert record.effective_date > record.date
        assert berths_on[record.date] == ACTIVE_BERTHS
        assert berths_on[record.effective_date] > ACTIVE_BERTHS


def test_the_stress_variant_wins_on_peak_without_any_extra_capacity() -> None:
    blind = congested_window()
    world = congested_world()

    _, baseline = run_arm(ReactiveBaselinePolicy(), world, blind)
    stress_policy = AgenticFleetPolicy(ScriptedFleetBrain(), world, allow_reserve_activation=False)
    stress_outcome, stress = run_arm(stress_policy, world, blind)

    assert not [
        record
        for record in stress_outcome.decisions
        if record.decision.type is FleetDecisionType.ACTIVATE_RESERVE_BERTHS
    ]
    assert {day.active_berths for day in stress_outcome.daily} == {ACTIVE_BERTHS}
    assert stress.peak_wait_days < baseline.peak_wait_days
    assert stress.recovery_date is not None
    assert baseline.recovery_date is not None
    assert stress.recovery_date < baseline.recovery_date


def test_the_stress_variant_is_not_better_than_the_full_agentic_arm() -> None:
    """Withdrawing the capacity lever must not help. It costs, or it is neutral.

    On this window the reserve tranche lands after the peak has passed, so it
    buys nothing on peak wait and only a little on total waiting time. That is
    the honest result and it is asserted as such rather than dressed up.
    """
    blind = congested_window()
    world = congested_world()

    _, full = run_arm(AgenticFleetPolicy(ScriptedFleetBrain(), world), world, blind)
    _, stress = run_arm(
        AgenticFleetPolicy(ScriptedFleetBrain(), world, allow_reserve_activation=False),
        world,
        blind,
    )

    assert stress.peak_wait_days >= full.peak_wait_days
    assert stress.wait_cost_usd >= full.wait_cost_usd


# --- brain cadence ----------------------------------------------------------


class CountingBrain:
    """Counts consultations while behaving exactly like the scripted brain."""

    def __init__(self) -> None:
        self.inner = ScriptedFleetBrain()
        self.calls: list[date] = []

    def assess_week(self, view: FleetPolicyView) -> FleetStrategy:
        self.calls.append(view.today)
        return self.inner.assess_week(view)


def test_the_brain_is_consulted_weekly_not_daily() -> None:
    blind = congested_window()
    world = congested_world()
    brain = CountingBrain()
    policy = AgenticFleetPolicy(brain, world)
    run_arm(policy, world, blind)

    scheduled = DAY_COUNT // 7 + 1
    assert len(brain.calls) == policy.brain_calls
    assert scheduled <= policy.brain_calls <= scheduled + 6, (
        "weekly epochs plus a handful of threshold exceptions, not a daily model call"
    )
    triggers = [epoch.trigger for epoch in policy.epochs]
    assert triggers.count("scheduled") == scheduled
    assert 1 <= triggers.count("threshold") <= 6
    assert len(set(brain.calls)) == len(brain.calls), "at most one consultation per day"
    assert policy.decision_source is DecisionSource.SCRIPTED


def test_the_daily_controller_keeps_executing_between_epochs() -> None:
    """A non-epoch day still runs, and it never invents a decision."""
    world = congested_world()
    brain = CountingBrain()
    policy = AgenticFleetPolicy(brain, world)

    day_zero = policy.decide(a_view(START, day_index=0))
    assert brain.calls == [START]
    day_one = policy.decide(a_view(START + timedelta(days=1), day_index=1))
    assert brain.calls == [START], "day 1 is not an epoch"
    assert day_zero.decisions and day_zero.decisions[0].type is FleetDecisionType.HOLD
    assert day_one.decisions == [], "HOLD is stated once, not repeated daily"


# --- governance: rejection and fallback -------------------------------------


class OneShotBrain:
    """Returns a fixed strategy at the first epoch and HOLDs at every later one."""

    def __init__(self, decisions: list[FleetDecision]) -> None:
        self._decisions = decisions
        self.epochs = 0

    def assess_week(self, view: FleetPolicyView) -> FleetStrategy:
        self.epochs += 1
        decisions = (
            self._decisions
            if self.epochs == 1
            else [FleetDecision(type=FleetDecisionType.HOLD, rationale="steady state")]
        )
        return FleetStrategy(decisions=decisions, summary="test brain", confidence=Confidence.LOW)


def test_an_out_of_menu_decision_is_rejected_recorded_and_changes_nothing() -> None:
    blind = congested_window()
    world = congested_world()
    brain = OneShotBrain(
        [
            FleetDecision(
                type=FleetDecisionType.ACTIVATE_RESERVE_BERTHS,
                tranche_id="tuas-phantom",
                rationale="a tranche that does not exist in this world",
            )
        ]
    )
    outcome, _ = run_arm(AgenticFleetPolicy(brain, world), world, blind)

    activations = [
        record
        for record in outcome.decisions
        if record.decision.type is FleetDecisionType.ACTIVATE_RESERVE_BERTHS
    ]
    assert activations, "the invalid decision must reach the engine, not be swallowed"
    for record in activations:
        assert record.accepted is False
        assert record.rejection_reason is not None
        assert "tuas-phantom" in record.rejection_reason
        assert record.effective_date is None
    # The run continued and nothing about the world moved.
    assert {day.active_berths for day in outcome.daily} == {ACTIVE_BERTHS}
    assert len(outcome.daily) == DAY_COUNT
    assert all(
        record.accepted
        for record in outcome.decisions
        if record.decision.type is not FleetDecisionType.ACTIVATE_RESERVE_BERTHS
    )


def test_the_controller_stops_re_offering_a_decision_the_engine_keeps_refusing() -> None:
    world = congested_world()
    brain = OneShotBrain(
        [
            FleetDecision(
                type=FleetDecisionType.ACTIVATE_RESERVE_BERTHS,
                tranche_id="tuas-phantom",
                rationale="never valid",
            )
        ]
    )
    policy = AgenticFleetPolicy(brain, world)
    emitted = 0
    for day_index in range(7):
        strategy = policy.decide(a_view(START + timedelta(days=day_index), day_index=day_index))
        emitted += sum(
            1
            for decision in strategy.decisions
            if decision.type is FleetDecisionType.ACTIVATE_RESERVE_BERTHS
        )
    assert 1 <= emitted <= 3, "re-offered a bounded number of times, then dropped"


def test_a_brain_that_raises_falls_back_to_the_scripted_decision_and_says_so() -> None:
    def explode(prompt: str) -> str:
        raise RuntimeError("the CLI is not there")

    brain = ClaudeBrain(runner=explode)
    view = a_view(day_index=0)

    strategy = brain.assess_week(view)

    assert brain.last_decision_source is DecisionSource.SCRIPTED_FALLBACK
    assert strategy == ScriptedFleetBrain().assess_week(view)

    world = congested_world()
    policy = AgenticFleetPolicy(brain, world)
    policy.decide(view)
    assert policy.decision_source is DecisionSource.SCRIPTED_FALLBACK
    assert policy.epochs[-1].source is DecisionSource.SCRIPTED_FALLBACK


def test_a_brain_returning_unparseable_output_falls_back_visibly() -> None:
    brain = ClaudeBrain(runner=lambda prompt: "I would suggest adding three berths.")
    strategy = brain.assess_week(a_view())
    assert brain.last_decision_source is DecisionSource.SCRIPTED_FALLBACK
    assert strategy.decisions


def test_a_menu_decision_without_its_payload_is_treated_as_a_failed_call() -> None:
    reply = (
        '{"decisions": [{"type": "ACTIVATE_RESERVE_BERTHS", "rationale": "more berths"}], '
        '"summary": "act", "confidence": "HIGH"}'
    )
    brain = ClaudeBrain(runner=lambda prompt: reply)
    brain.assess_week(a_view())
    assert brain.last_decision_source is DecisionSource.SCRIPTED_FALLBACK


def test_a_well_formed_model_answer_is_labelled_as_a_model_decision() -> None:
    reply = (
        '{"decisions": [{"type": "WORKFORCE_SURGE", "surge_level": 1, '
        '"rationale": "rolling wait is climbing"}], '
        '"summary": "surge", "confidence": "MEDIUM"}'
    )
    brain = ClaudeBrain(runner=lambda prompt: reply)
    strategy = brain.assess_week(a_view())
    assert brain.last_decision_source is DecisionSource.MODEL
    assert strategy.decisions[0].surge_level == 1


# --- the prompt facts -------------------------------------------------------


def test_the_strategy_message_carries_only_facts_from_the_view() -> None:
    view = a_view(
        today=date(2024, 5, 10),
        day_index=39,
        workforce_surge_level=1,
        reserves_available=[make_tranche("keppel-1", berths=2, activation_lead_days=10)],
    )
    message = fleet_strategy_message(view)

    assert "2024-05-10" in message
    assert "keppel-1" in message
    assert "10-day activation lead" in message
    assert "workforce surge level: 1" in message
    assert "may not state any figure" in message
    for entry in FleetDecisionType:
        assert entry.value in message


def test_the_strategy_message_history_is_bounded() -> None:
    blind = congested_window()
    world = congested_world()
    outcome, _ = run_arm(ReactiveBaselinePolicy(), world, blind)
    long_view = a_view(
        today=outcome.daily[-1].date + timedelta(days=1),
        day_index=DAY_COUNT - 1,
        history=outcome.daily,
    )

    message = fleet_strategy_message(long_view)
    rendered_days = sum(1 for line in message.splitlines() if "rolling 3-day wait" in line)
    assert rendered_days == 14
    assert str(outcome.daily[0].date) not in message


# --- determinism and blindness ----------------------------------------------


def test_two_identical_agentic_runs_are_identical() -> None:
    world = congested_world()
    first, first_metrics = run_arm(
        AgenticFleetPolicy(ScriptedFleetBrain(), world), world, congested_window()
    )
    second, second_metrics = run_arm(
        AgenticFleetPolicy(ScriptedFleetBrain(), world), world, congested_window()
    )

    assert first.decisions == second.decisions
    assert first.daily == second.daily
    assert first_metrics == second_metrics


@pytest.mark.parametrize("agentic", [False, True])
def test_the_blind_audit_passes_with_zero_lookahead_for_both_arms(agentic: bool) -> None:
    world = congested_world()
    policy: object = (
        AgenticFleetPolicy(ScriptedFleetBrain(), world) if agentic else ReactiveBaselinePolicy()
    )
    outcome, _ = run_arm(policy, world, congested_window())

    audit = outcome.blind_audit
    assert audit.verdict is AuditVerdict.PASS
    assert audit.violations == 0
    assert audit.max_lookahead_seconds == 0.0
    assert audit.total_reads == DAY_COUNT
