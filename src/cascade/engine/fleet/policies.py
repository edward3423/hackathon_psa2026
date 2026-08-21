"""The two simulated benchmark arms.

Both arms are run by the SAME :func:`cascade.engine.fleet.simulate` over the
SAME ``FleetWorldConfig`` object. The only difference between
``REACTIVE_BASELINE`` and ``CASCADE_AGENTIC`` is which object is passed as the
``policy`` argument. Nothing in this module reads a config, a fixture or a
clock, and nothing here can widen a berth pool or shorten a service time: a
policy's entire vocabulary is the enumerated ``FleetDecision`` menu, and every
decision it emits is independently re-validated by ``validate_fleet_decision``
before the engine will act on it.

The agentic arm has two layers, deliberately separated:

- A **daily deterministic controller** (:meth:`AgenticFleetPolicy.decide` on a
  non-epoch day) that makes no brain call. It only reconciles the strategy
  currently in force against the state the engine reports: a decision that the
  view shows already satisfied is dropped, a decision still outstanding is
  re-offered, and a decision whose lever is inside the engine's cooldown is
  held back rather than emitted as noise. It also watches the rolling wait and
  calls an exception epoch when it breaches ``exception_wait_days``.
- A **strategy epoch** (every ``epoch_days``-th day index, plus those
  threshold-triggered exceptions) that consults a ``FleetBrain``. Over the
  ~150-day blind window that is about 22 weekly calls plus a handful of
  exception calls.

The controller never invents a decision. Every ``FleetDecision`` it emits came
verbatim from a brain; the controller only decides *whether* and *when* to
re-offer one. The brain in turn may only pick menu entries. So no number
anywhere on this path originates outside the engine.

This module deliberately has no import path to ``cascade.fixtures`` (asserted
by ``tests/test_blind_feed.py``) and no runtime import of ``cascade.agents``:
the brain seam is structural, imported for typing only, so the engine never
depends on the agent layer.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from cascade.contracts import (
    Confidence,
    DecisionSource,
    FleetDecision,
    FleetDecisionType,
    FleetPolicyView,
    FleetStrategy,
    FleetWorldConfig,
)
from cascade.engine.fleet.berths import LEVER_COOLDOWN_DAYS
from cascade.engine.fleet.events import FcfsPolicy

if TYPE_CHECKING:  # pragma: no cover - typing only, see module docstring
    from cascade.agents.base import FleetBrain

# --- tuning defaults --------------------------------------------------------

#: Cadence of the scheduled strategy epochs, in whole days of the run.
STRATEGY_EPOCH_DAYS = 7

#: Rolling 3-day wait (days) at which the controller stops waiting for the next
#: scheduled epoch and calls an exception epoch. Chosen at the level where the
#: port is visibly past normal operation but a 10-14 day berth activation can
#: still land before the peak.
EXCEPTION_WAIT_DAYS = 4.0

#: Minimum whole days between brain calls. Without it a sustained breach would
#: call the brain every day, which is exactly the daily-LLM design this
#: workstream avoids.
EXCEPTION_MIN_GAP_DAYS = 3

#: How long the controller keeps re-offering an outstanding decision before
#: dropping it. A decision the engine keeps refusing (an unknown tranche, say)
#: must not be re-offered for the rest of the run.
INTENT_TTL_DAYS = 4

MAX_DECISIONS_PER_EPOCH = 4


def decision_is_satisfied(decision: FleetDecision, view: FleetPolicyView) -> bool:
    """Whether the state the engine reports already reflects this decision.

    Used by the controller to stop re-offering a decision that has landed, and
    by ``ScriptedFleetBrain`` to avoid proposing a lever that is already where
    it wants it (which the engine would reject as a no-op).
    """
    if decision.type is FleetDecisionType.WORKFORCE_SURGE:
        return decision.surge_level == view.workforce_surge_level
    if decision.type is FleetDecisionType.SET_QUEUE_DISCIPLINE:
        return decision.discipline is view.queue_discipline
    if decision.type is FleetDecisionType.FAST_CONNECTION_MODE:
        return decision.enabled is view.fast_connection_mode
    if decision.type is FleetDecisionType.ACTIVATE_RESERVE_BERTHS:
        # Satisfied once the tranche is scheduled, which is what acceptance
        # looks like from outside: the berths are booked and dated, they just
        # have not landed yet. Deliberately NOT "absent from reserves_available"
        # - a tranche that does not exist in this world is absent too, and that
        # decision must reach the engine to be rejected and recorded rather than
        # be quietly dropped here.
        return any(
            pending.tranche_id == decision.tranche_id for pending in view.pending_activations
        )
    return False


def brain_decision_source(brain: object) -> DecisionSource:
    """Where the last strategy actually came from.

    A brain may advertise ``last_decision_source`` (the live adapters do, so a
    scripted fallback after a transport or schema failure stays visible). A
    brain that says nothing is treated as scripted, which is the honest default
    for the deterministic scored configuration.
    """
    source = getattr(brain, "last_decision_source", None)
    return source if isinstance(source, DecisionSource) else DecisionSource.SCRIPTED


class ReactiveBaselinePolicy(FcfsPolicy):
    """The ``REACTIVE_BASELINE`` arm: what the port does with no coordination.

    It works the queue in arrival order with the capacity it already has. It
    never activates a reserve tranche, never changes queue discipline, never
    surges the workforce and never enables fast connection mode - it returns an
    empty decision list on every one of its daily epochs.

    Behaviourally this is exactly ``FcfsPolicy``, and it subclasses it rather
    than restating it so that the two can never drift apart. The separate name
    exists because an arm of the benchmark deserves one.
    """


@dataclass(slots=True)
class StrategyEpoch:
    """One brain consultation. Recorded so the benchmark can report cadence."""

    date: date
    day_index: int
    trigger: str
    source: DecisionSource
    decisions: int


@dataclass(slots=True)
class _Intent:
    """A brain decision the controller is still trying to get applied."""

    decision: FleetDecision
    expires_on: date


class AgenticFleetPolicy:
    """The ``CASCADE_AGENTIC`` arm: weekly strategy, daily execution.

    Parameters
    ----------
    brain:
        Supplies a ``FleetStrategy`` at each strategy epoch. ``ScriptedFleetBrain``
        is the default and the scored configuration; the live adapters are
        narrative.
    world:
        The same ``FleetWorldConfig`` object the engine runs on. Held so the
        policy can be reported alongside its world; the policy reads nothing
        from it that would let it act outside the menu.
    epoch_days:
        Scheduled strategy cadence. Default ``STRATEGY_EPOCH_DAYS`` (7).
    exception_wait_days:
        Rolling wait that triggers an off-cycle epoch. Default
        ``EXCEPTION_WAIT_DAYS`` (4.0 days).
    exception_min_gap_days:
        Floor on the gap between brain calls. Default ``EXCEPTION_MIN_GAP_DAYS``
        (3 days).
    intent_ttl_days:
        How long an outstanding decision is re-offered. Default
        ``INTENT_TTL_DAYS`` (4 days).
    allow_reserve_activation:
        ``False`` produces the ``CASCADE_NO_EXTRA_CAPACITY`` stress variant: the
        capacity lever is withdrawn, so the arm has to cope with prioritisation
        and surge alone. The reserve tranches are hidden from the brain as well
        as filtered out of its answer, so the brain is never invited to propose
        a lever this arm does not have.
    """

    def __init__(
        self,
        brain: "FleetBrain",
        world: FleetWorldConfig,
        *,
        epoch_days: int = STRATEGY_EPOCH_DAYS,
        exception_wait_days: float = EXCEPTION_WAIT_DAYS,
        exception_min_gap_days: int = EXCEPTION_MIN_GAP_DAYS,
        intent_ttl_days: int = INTENT_TTL_DAYS,
        allow_reserve_activation: bool = True,
    ) -> None:
        if epoch_days < 1:
            raise ValueError("epoch_days must be at least 1")
        self._brain = brain
        self._world = world
        self._epoch_days = epoch_days
        self._exception_wait_days = exception_wait_days
        self._exception_min_gap_days = exception_min_gap_days
        self._intent_ttl_days = intent_ttl_days
        self._allow_reserve_activation = allow_reserve_activation

        self.epochs: list[StrategyEpoch] = []
        self._intents: list[_Intent] = []
        self._last_emitted: dict[FleetDecisionType, date] = {}
        self._last_epoch_day: int | None = None
        self._epoch_summary = "No strategy set yet."
        self._confidence = Confidence.MEDIUM

    # --- reporting ---------------------------------------------------------

    @property
    def brain_calls(self) -> int:
        """How many times a brain was consulted over the run."""
        return len(self.epochs)

    @property
    def decision_source(self) -> DecisionSource:
        """The honest source label for the whole run.

        ``SCRIPTED_FALLBACK`` if any epoch fell back, otherwise ``MODEL`` if any
        epoch came from a model, otherwise ``SCRIPTED``. The pessimistic order
        is deliberate: one silent fallback must not let a run be labelled as a
        pure model run.
        """
        sources = {epoch.source for epoch in self.epochs}
        if DecisionSource.SCRIPTED_FALLBACK in sources:
            return DecisionSource.SCRIPTED_FALLBACK
        if DecisionSource.MODEL in sources:
            return DecisionSource.MODEL
        return DecisionSource.SCRIPTED

    # --- FleetPolicy -------------------------------------------------------

    def decide(self, view: FleetPolicyView) -> FleetStrategy:
        trigger = self._epoch_trigger(view)
        if trigger is not None:
            self._open_epoch(view, trigger)
        return self._apply_strategy_in_force(view)

    # --- strategy epochs ---------------------------------------------------

    def _rolling_wait(self, view: FleetPolicyView) -> float:
        return view.history[-1].rolling_wait_days if view.history else 0.0

    def _epoch_trigger(self, view: FleetPolicyView) -> str | None:
        if self._last_epoch_day is None or view.day_index % self._epoch_days == 0:
            return "scheduled"
        elapsed = view.day_index - self._last_epoch_day
        if (
            self._rolling_wait(view) >= self._exception_wait_days
            and elapsed >= self._exception_min_gap_days
        ):
            return "threshold"
        return None

    def _brain_view(self, view: FleetPolicyView) -> FleetPolicyView:
        if self._allow_reserve_activation:
            return view
        return view.model_copy(update={"reserves_available": [], "pending_activations": []})

    def _open_epoch(self, view: FleetPolicyView, trigger: str) -> None:
        strategy = self._brain.assess_week(self._brain_view(view))
        allowed = [
            decision
            for decision in strategy.decisions
            if self._allow_reserve_activation
            or decision.type is not FleetDecisionType.ACTIVATE_RESERVE_BERTHS
        ][:MAX_DECISIONS_PER_EPOCH]
        # HOLD is a statement, not a lever: it is recorded on the epoch day and
        # never re-offered, so it expires the same day it is made.
        self._intents = [
            _Intent(
                decision=decision,
                expires_on=view.today
                + timedelta(
                    days=0 if decision.type is FleetDecisionType.HOLD else self._intent_ttl_days
                ),
            )
            for decision in allowed
        ]
        self._epoch_summary = strategy.summary
        self._confidence = strategy.confidence
        self._last_epoch_day = view.day_index
        self.epochs.append(
            StrategyEpoch(
                date=view.today,
                day_index=view.day_index,
                trigger=trigger,
                source=brain_decision_source(self._brain),
                decisions=len(allowed),
            )
        )

    # --- daily controller --------------------------------------------------

    def _in_cooldown(self, decision: FleetDecision, today: date) -> bool:
        if decision.type is FleetDecisionType.HOLD:
            return False
        previous = self._last_emitted.get(decision.type)
        return previous is not None and (today - previous).days <= LEVER_COOLDOWN_DAYS

    def _apply_strategy_in_force(self, view: FleetPolicyView) -> FleetStrategy:
        outstanding: list[_Intent] = []
        emit: list[FleetDecision] = []
        for intent in self._intents:
            if decision_is_satisfied(intent.decision, view) or view.today > intent.expires_on:
                continue
            outstanding.append(intent)
            if self._in_cooldown(intent.decision, view.today):
                continue
            emit.append(intent.decision)
            if intent.decision.type is not FleetDecisionType.HOLD:
                self._last_emitted[intent.decision.type] = view.today
        self._intents = outstanding
        return FleetStrategy(
            decisions=emit,
            summary=self._summary(view, emit, outstanding),
            confidence=self._confidence,
        )

    def _summary(
        self, view: FleetPolicyView, emit: list[FleetDecision], outstanding: list[_Intent]
    ) -> str:
        if self._last_epoch_day == view.day_index:
            return self._epoch_summary
        if emit:
            return (
                f"Executing {len(emit)} outstanding decision(s) from the strategy set on "
                f"day {self._last_epoch_day}; no new assessment today."
            )
        if outstanding:
            return (
                f"{len(outstanding)} decision(s) from the current strategy are held back "
                "inside the engine's lever cooldown."
            )
        return "Current strategy is fully in force; no lever to move today."


def make_agentic_policy(
    brain: "FleetBrain", world: FleetWorldConfig, *, allow_reserve_activation: bool = True
) -> AgenticFleetPolicy:
    """Build the agentic arm, or its no-extra-capacity stress variant.

    A single constructor for both so the stress arm can never be a divergent
    copy of the policy it is meant to stress.
    """
    return AgenticFleetPolicy(brain, world, allow_reserve_activation=allow_reserve_activation)
