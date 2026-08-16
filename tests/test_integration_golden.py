"""Golden end-to-end integration: real stage machine + real engine toolbox.

Unlike tests/test_workflow.py (FakeToolBox), this drives the LIVE_STUB stage
machine with build_toolbox(), which must resolve to EngineToolBox over
fixtures/golden_world.json. It covers the full demo path: run start, dispute
resolution, planning with visible revision, approval, and mocked receipts.
"""

import asyncio
from collections.abc import Callable

import pytest

from cascade.agents.scripted import ScriptedBrain
from cascade.contracts import (
    ApprovalDecision,
    ApprovalRequest,
    DisputeResolutionRequest,
    EventKind,
    PlanArchetype,
    RunMode,
    ScenarioControls,
    WorkflowStage,
)
from cascade.tools.engine_toolbox import EngineToolBox
from cascade.tools.toolbox import build_toolbox
from cascade.workflow import WorkflowRun, scenario_with_controls

CONSTRAINT = "Respect physical reefer plug capacity"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_engine_run(alternative_sailing_failure: bool = True) -> WorkflowRun:
    toolbox = build_toolbox()
    # The golden integration must exercise the real engine; a silent fallback
    # to FakeToolBox would make this test meaningless.
    assert isinstance(toolbox, EngineToolBox)
    controls = ScenarioControls(alternative_sailing_failure=alternative_sailing_failure)
    return WorkflowRun(
        run_id="golden-integration-0001",
        mode=RunMode.LIVE_STUB,
        controls=controls,
        scenario=scenario_with_controls(controls),
        toolbox=toolbox,
        brain=ScriptedBrain(),
    )


async def wait_for(predicate: Callable[[], bool], timeout: float = 30.0) -> None:
    async def poll() -> None:
        while not predicate():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(poll(), timeout)


@pytest.mark.anyio
async def test_golden_run_reaches_receipts_with_real_engine() -> None:
    run = make_engine_run()
    run.start()

    await wait_for(lambda: run.stage is WorkflowStage.DISPUTE and run.active_dispute is not None)
    dispute = run.active_dispute
    assert dispute is not None
    run.resolve_dispute(
        DisputeResolutionRequest(dispute_id=dispute.dispute_id, confirmed_constraint=CONSTRAINT)
    )

    await wait_for(lambda: run.stage is WorkflowStage.AWAITING_APPROVAL or run.finished)
    assert run.stage is WorkflowStage.AWAITING_APPROVAL, (
        f"run ended at stage {run.stage}: "
        + "; ".join(event.error or "" for event in run.trace if event.kind == EventKind.ERROR)
    )

    comparison = run.results.plan_comparison
    assert comparison is not None
    assert len(comparison.evaluations) == 3
    # PRD golden scenario item 10: the hybrid plan is the recommendation.
    assert comparison.recommended is PlanArchetype.OPTIMIZED_HYBRID
    recommended = next(
        evaluation
        for evaluation in comparison.evaluations
        if evaluation.plan.archetype == comparison.recommended
    )
    assert recommended.feasible

    # The revision cycle is visible in the trace (PRD 9.8).
    revisions = [
        event
        for event in run.trace
        if event.kind == EventKind.HANDOFF and "Revise" in (event.objective or "")
    ]
    assert revisions, "at least one plan revision must be visible in the trace"

    # Nothing dispatch-like exists before approval (PRD 9.10).
    assert not any(event.kind == EventKind.ACTION_DISPATCHED for event in run.trace)

    run.decide_approval(
        ApprovalRequest(plan_archetype=comparison.recommended, decision=ApprovalDecision.APPROVED)
    )
    await wait_for(lambda: run.finished)

    final_stage: WorkflowStage = run.stage
    assert final_stage is WorkflowStage.COMPLETE
    assert run.trace[-1].kind == EventKind.RUN_COMPLETED
    assert run.results.dispatched_actions
    assert run.results.receipts
    assert all(receipt.status.value == "ACCEPTED" for receipt in run.results.receipts)
    dispatched = [event for event in run.trace if event.kind == EventKind.ACTION_DISPATCHED]
    assert len(dispatched) == len(run.results.dispatched_actions)


@pytest.mark.anyio
async def test_infeasible_plan_is_carried_into_comparison_not_fatal() -> None:
    """A plan that stays infeasible must reach compare_plans as infeasible.

    The run only fails when all three plans end infeasible; otherwise every
    evaluation (feasible or not) appears in the comparison.
    """
    run = make_engine_run()
    run.start()
    await wait_for(lambda: run.stage is WorkflowStage.DISPUTE and run.active_dispute is not None)
    assert run.active_dispute is not None
    run.resolve_dispute(
        DisputeResolutionRequest(
            dispute_id=run.active_dispute.dispute_id, confirmed_constraint=CONSTRAINT
        )
    )
    await wait_for(lambda: run.stage is WorkflowStage.AWAITING_APPROVAL or run.finished)
    assert run.stage is WorkflowStage.AWAITING_APPROVAL
    comparison = run.results.plan_comparison
    assert comparison is not None
    # All three archetypes are present in the comparison regardless of
    # feasibility, and infeasible ones carry their rejection reasons.
    assert len(comparison.evaluations) == 3
    for evaluation in comparison.evaluations:
        if not evaluation.feasible:
            assert evaluation.rejection_reasons
            assert evaluation.plan.archetype != comparison.recommended
    run.cancel()
