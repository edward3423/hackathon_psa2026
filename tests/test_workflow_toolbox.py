from datetime import UTC, datetime

from cascade.agents.base import PlanBriefing
from cascade.agents.scripted import ScriptedBrain
from cascade.contracts import (
    ActionReceiptStatus,
    CargoType,
    Confidence,
    PlanArchetype,
    PriorityEmphasis,
    RecoveryActionType,
)
from cascade.tools.evidence import retrieve_context
from cascade.tools.fake_toolbox import RUSH_REEFER_CAP, FakeToolBox

REVISED_ETA = datetime(2026, 9, 15, 0, 0, tzinfo=UTC)
EMPHASIS = PriorityEmphasis.BALANCED


def briefing(constraint: str | None = None) -> PlanBriefing:
    toolbox = FakeToolBox()
    return PlanBriefing(
        analysis=toolbox.analyse_connections(REVISED_ETA, EMPHASIS),
        sailings=toolbox.find_alternative_sailings(force_timeout=True),
        confirmed_constraint=constraint,
        priority_emphasis=EMPHASIS.value,
    )


def test_cost_totals_equal_component_sums() -> None:
    toolbox = FakeToolBox()
    plans = ScriptedBrain().propose_plans(briefing())
    for plan in plans:
        evaluation = toolbox.evaluate_plan(REVISED_ETA, briefing().analysis, plan, EMPHASIS)
        cost = evaluation.metrics.cost
        assert cost.total == sum(component.amount for component in cost.components)
        assert cost.illustrative is True


def test_rushing_all_reefers_is_rejected_and_revision_becomes_feasible() -> None:
    toolbox = FakeToolBox()
    brain = ScriptedBrain()
    context = briefing()
    plans = brain.propose_plans(context)
    aggressive = next(plan for plan in plans if plan.archetype == PlanArchetype.AGGRESSIVE_RUSH)
    evaluation = toolbox.evaluate_plan(REVISED_ETA, context.analysis, aggressive, EMPHASIS)
    assert evaluation.feasible is False
    assert evaluation.rejection_reasons

    revised = brain.revise_plan(aggressive, evaluation.rejection_reasons, context)
    revised_eval = toolbox.evaluate_plan(REVISED_ETA, context.analysis, revised, EMPHASIS)
    assert revised_eval.feasible is True
    rushed = sum(
        action.container_count
        for action in revised.actions
        if action.action == RecoveryActionType.RUSH and action.cargo_type == CargoType.PHARMA_REEFER
    )
    assert rushed <= RUSH_REEFER_CAP
    # Every affected cargo group still receives an action.
    total = sum(action.container_count for action in revised.actions)
    original_total = sum(action.container_count for action in aggressive.actions)
    assert total == original_total


def test_constraint_cap_flows_into_hybrid_plan() -> None:
    context = briefing(f"Physical plugs govern; rush at most {RUSH_REEFER_CAP} reefers.")
    plans = ScriptedBrain().propose_plans(context)
    hybrid = next(plan for plan in plans if plan.archetype == PlanArchetype.OPTIMIZED_HYBRID)
    rushed = sum(
        action.container_count
        for action in hybrid.actions
        if action.action == RecoveryActionType.RUSH and action.cargo_type == CargoType.PHARMA_REEFER
    )
    assert rushed <= RUSH_REEFER_CAP
    assert any("Confirmed constraint" in assumption for assumption in hybrid.assumptions)


def test_compare_plans_never_recommends_infeasible_plan() -> None:
    toolbox = FakeToolBox()
    context = briefing()
    plans = ScriptedBrain().propose_plans(context)  # aggressive is infeasible here
    comparison = toolbox.compare_plans(
        REVISED_ETA, context.analysis, plans, EMPHASIS, Confidence.MEDIUM
    )
    infeasible = {
        evaluation.plan.archetype
        for evaluation in comparison.evaluations
        if not evaluation.feasible
    }
    assert PlanArchetype.AGGRESSIVE_RUSH in infeasible
    assert comparison.recommended not in infeasible
    assert comparison.confidence is Confidence.MEDIUM


def test_actions_validate_against_the_approved_plan() -> None:
    toolbox = FakeToolBox()
    brain = ScriptedBrain()
    context = briefing(f"rush at most {RUSH_REEFER_CAP}")
    plans = brain.propose_plans(context)
    hybrid = next(plan for plan in plans if plan.archetype == PlanArchetype.OPTIMIZED_HYBRID)
    rebook = next(plan for plan in plans if plan.archetype == PlanArchetype.STANDARD_REBOOK)

    actions = toolbox.build_actions(hybrid)
    receipts = toolbox.validate_actions(hybrid, actions)
    assert all(receipt.status is ActionReceiptStatus.ACCEPTED for receipt in receipts)
    assert all(receipt.receipt_ref for receipt in receipts)

    foreign = toolbox.build_actions(rebook)
    mixed = toolbox.validate_actions(hybrid, foreign)
    assert all(receipt.status is ActionReceiptStatus.REJECTED for receipt in mixed)


def test_retrieve_context_returns_sourced_facts() -> None:
    response = retrieve_context("transshipment hub Singapore")
    assert response["facts"]
    for fact in response["facts"]:
        assert fact.get("fact")
    assert "evidence" in response["notice"].lower() or response["notice"]
