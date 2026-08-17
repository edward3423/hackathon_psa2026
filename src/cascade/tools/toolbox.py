"""ToolBox seam between the workflow stage machine and deterministic tools.

The stage machine only talks to the ``ToolBox`` protocol. ``FakeToolBox``
(in-repo canned contract objects) keeps the workflow fully offline and
deterministic; ``EngineToolBox`` plugs the real engine and golden world in at
integration without any workflow change.
"""

from datetime import datetime
from typing import Protocol

from cascade.contracts import (
    ActionReceipt,
    AlternativeSailingResult,
    Confidence,
    ConnectionAnalysis,
    MockedAction,
    PlanComparison,
    PlanEvaluation,
    PlanningFacts,
    PriorityEmphasis,
    RecoveryPlan,
    YardForecast,
)


class ToolBox(Protocol):
    """Deterministic tool surface used by the workflow stage machine."""

    def analyse_connections(
        self, revised_eta: datetime, emphasis: PriorityEmphasis
    ) -> ConnectionAnalysis: ...

    def simulate_yard(
        self,
        revised_eta: datetime,
        connections: ConnectionAnalysis,
        plan: RecoveryPlan | None,
        horizon_hours: int,
    ) -> YardForecast: ...

    def find_alternative_sailings(self, force_timeout: bool) -> AlternativeSailingResult: ...

    def planning_facts(self, connections: ConnectionAnalysis) -> PlanningFacts: ...

    def evaluate_plan(
        self,
        revised_eta: datetime,
        connections: ConnectionAnalysis,
        plan: RecoveryPlan,
        emphasis: PriorityEmphasis,
    ) -> PlanEvaluation: ...

    def compare_plans(
        self,
        revised_eta: datetime,
        connections: ConnectionAnalysis,
        plans: list[RecoveryPlan],
        emphasis: PriorityEmphasis,
        confidence: Confidence,
    ) -> PlanComparison: ...

    def build_actions(self, plan: RecoveryPlan) -> list[MockedAction]: ...

    def validate_actions(
        self, plan: RecoveryPlan, actions: list[MockedAction]
    ) -> list[ActionReceipt]: ...


def build_toolbox() -> ToolBox:
    """Return the engine-backed toolbox when the engine and world exist.

    Falls back to the deterministic in-repo fake so this workstream runs and
    tests offline before integration.
    """
    try:
        from cascade.tools.engine_toolbox import EngineToolBox

        return EngineToolBox.create()
    except Exception:
        from cascade.tools.fake_toolbox import FakeToolBox

        return FakeToolBox()
