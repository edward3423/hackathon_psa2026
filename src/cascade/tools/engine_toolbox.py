"""Engine-backed ToolBox.

Thin adapter over the deterministic engine functions and the golden world
fixture delivered by the sibling workstreams. Imports are lazy so this module
can exist before the engine lands; ``build_toolbox`` falls back to the fake
when construction fails.
"""

from datetime import datetime
from typing import Any

from cascade.contracts import (
    ActionReceipt,
    AlternativeSailingResult,
    Confidence,
    ConnectionAnalysis,
    MockedAction,
    PlanComparison,
    PlanEvaluation,
    PriorityEmphasis,
    RecoveryPlan,
    SailingLookupStatus,
    WorldFixture,
    YardForecast,
)


class EngineToolBox:
    """Calls the real engine with the golden world loaded once."""

    def __init__(self, world: WorldFixture, engine: Any) -> None:
        self._world = world
        self._engine = engine

    @classmethod
    def create(cls) -> "EngineToolBox":
        import importlib
        from types import SimpleNamespace

        import cascade.fixtures as fixtures

        engine = SimpleNamespace(
            connections=importlib.import_module("cascade.engine.connections"),
            yard=importlib.import_module("cascade.engine.yard"),
            plans=importlib.import_module("cascade.engine.plans"),
            actions=importlib.import_module("cascade.engine.actions"),
        )
        load_golden_world = getattr(fixtures, "load_golden_world")  # noqa: B009
        return cls(world=load_golden_world(), engine=engine)

    def analyse_connections(
        self, revised_eta: datetime, emphasis: PriorityEmphasis
    ) -> ConnectionAnalysis:
        return self._engine.connections.analyse_connections(self._world, revised_eta, emphasis)

    def simulate_yard(
        self,
        revised_eta: datetime,
        connections: ConnectionAnalysis,
        plan: RecoveryPlan | None,
        horizon_hours: int,
    ) -> YardForecast:
        return self._engine.yard.simulate_yard(
            self._world, revised_eta, connections, plan, horizon_hours
        )

    def find_alternative_sailings(self, force_timeout: bool) -> AlternativeSailingResult:
        sailings = [sailing.model_copy(deep=True) for sailing in self._world.alternative_sailings]
        if force_timeout:
            return AlternativeSailingResult(
                status=SailingLookupStatus.TIMEOUT_CACHED_FALLBACK,
                sailings=sailings,
                stale_notice=(
                    "Live sailing lookup timed out; using the cached synthetic snapshot, "
                    "which may be stale."
                ),
            )
        return AlternativeSailingResult(
            status=SailingLookupStatus.MOCK_SUCCESS, sailings=sailings, stale_notice=None
        )

    def evaluate_plan(
        self,
        revised_eta: datetime,
        connections: ConnectionAnalysis,
        plan: RecoveryPlan,
        emphasis: PriorityEmphasis,
    ) -> PlanEvaluation:
        return self._engine.plans.evaluate_plan(
            self._world, revised_eta, connections, plan, emphasis
        )

    def compare_plans(
        self,
        revised_eta: datetime,
        connections: ConnectionAnalysis,
        plans: list[RecoveryPlan],
        emphasis: PriorityEmphasis,
        confidence: Confidence,
    ) -> PlanComparison:
        return self._engine.plans.compare_plans(
            self._world, revised_eta, connections, plans, emphasis, confidence
        )

    def build_actions(self, plan: RecoveryPlan) -> list[MockedAction]:
        return self._engine.actions.build_actions(plan)

    def validate_actions(
        self, plan: RecoveryPlan, actions: list[MockedAction]
    ) -> list[ActionReceipt]:
        return self._engine.actions.validate_actions(plan, actions)
