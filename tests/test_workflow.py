import asyncio
from collections.abc import Callable

import pytest

from cascade.agents.scripted import ScriptedBrain
from cascade.contracts import (
    ApprovalDecision,
    ApprovalRequest,
    Confidence,
    DisputeResolutionRequest,
    EventKind,
    PlanArchetype,
    RunMode,
    ScenarioControls,
    WorkflowStage,
)
from cascade.tools.fake_toolbox import FakeToolBox
from cascade.workflow import ConflictError, WorkflowRun, scenario_with_controls

CONSTRAINT = "Respect the reefer plug limit; rush at most 34 pharmaceutical reefers."


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_run(
    mode: RunMode = RunMode.LIVE_STUB,
    alternative_sailing_failure: bool = True,
) -> WorkflowRun:
    controls = ScenarioControls(alternative_sailing_failure=alternative_sailing_failure)
    return WorkflowRun(
        run_id="test-run-0001",
        mode=mode,
        controls=controls,
        scenario=scenario_with_controls(controls),
        toolbox=FakeToolBox(),
        brain=ScriptedBrain(),
    )


async def wait_for(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    async def poll() -> None:
        while not predicate():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(poll(), timeout)


async def drive_to_approval(run: WorkflowRun) -> None:
    run.start()
    await wait_for(lambda: run.stage is WorkflowStage.DISPUTE and run.active_dispute is not None)
    assert run.active_dispute is not None
    run.resolve_dispute(
        DisputeResolutionRequest(
            dispute_id=run.active_dispute.dispute_id, confirmed_constraint=CONSTRAINT
        )
    )
    await wait_for(lambda: run.stage is WorkflowStage.AWAITING_APPROVAL)


@pytest.mark.anyio
async def test_happy_path_reaches_receipts_through_approval() -> None:
    run = make_run()
    await drive_to_approval(run)
    run.decide_approval(
        ApprovalRequest(
            plan_archetype=PlanArchetype.OPTIMIZED_HYBRID, decision=ApprovalDecision.APPROVED
        )
    )
    await wait_for(lambda: run.finished)

    assert run.stage is WorkflowStage.COMPLETE
    kinds = [event.kind for event in run.trace]
    assert kinds[0] == EventKind.RUN_STARTED
    assert kinds[-1] == EventKind.RUN_COMPLETED
    assert EventKind.DISPUTE_OPENED in kinds
    assert EventKind.HUMAN_DECISION in kinds
    assert EventKind.APPROVAL_REQUIRED in kinds
    assert EventKind.ACTION_DISPATCHED in kinds

    # Parallel delegation is visible via a shared parallel group.
    parallel = [event for event in run.trace if event.parallel_group == "assessment-1"]
    parallel_agents: set[str] = set()
    for event in parallel:
        assert event.agent is not None
        parallel_agents.add(event.agent.value)
    assert parallel_agents == {"Impact Agent", "Yard Agent"}

    # Results are populated and dispatched actions carry accepted receipts.
    results = run.results
    assert results.connection_analysis is not None
    assert results.baseline_yard is not None
    assert results.planned_yard is not None
    assert results.alternative_sailings is not None
    assert results.plan_comparison is not None
    assert len(results.plan_comparison.evaluations) == 3
    assert results.dispatched_actions
    assert len(results.receipts) >= len(results.dispatched_actions)

    # Displayed figures flow from tool results, not hard-coded strings.
    analysis = results.connection_analysis
    impact_event = next(event for event in run.trace if event.tool == "analyse_connections")
    assert impact_event.result is not None
    assert str(analysis.safe_count) in impact_event.result
    assert str(analysis.at_risk_count) in impact_event.result
    assert str(analysis.missed_count) in impact_event.result
    dispatched = [event for event in run.trace if event.kind == EventKind.ACTION_DISPATCHED]
    assert len(dispatched) == len(results.dispatched_actions)


@pytest.mark.anyio
async def test_no_action_dispatched_before_approval() -> None:
    run = make_run()
    await drive_to_approval(run)
    approval_seq = next(
        event.sequence for event in run.trace if event.kind == EventKind.APPROVAL_REQUIRED
    )
    assert not any(event.kind == EventKind.ACTION_DISPATCHED for event in run.trace)
    run.decide_approval(
        ApprovalRequest(
            plan_archetype=PlanArchetype.OPTIMIZED_HYBRID, decision=ApprovalDecision.APPROVED
        )
    )
    await wait_for(lambda: run.finished)
    for event in run.trace:
        if event.kind == EventKind.ACTION_DISPATCHED:
            assert event.sequence > approval_seq


@pytest.mark.anyio
async def test_rejection_produces_zero_actions() -> None:
    run = make_run()
    await drive_to_approval(run)
    run.decide_approval(
        ApprovalRequest(
            plan_archetype=PlanArchetype.OPTIMIZED_HYBRID, decision=ApprovalDecision.REJECTED
        )
    )
    await wait_for(lambda: run.finished)
    assert run.stage is WorkflowStage.COMPLETE
    assert not any(event.kind == EventKind.ACTION_DISPATCHED for event in run.trace)
    assert run.results.dispatched_actions == []
    assert run.results.receipts == []
    assert run.trace[-1].kind == EventKind.RUN_COMPLETED


@pytest.mark.anyio
async def test_dispute_pauses_and_constraint_enters_trace() -> None:
    run = make_run()
    run.start()
    await wait_for(lambda: run.stage is WorkflowStage.DISPUTE)

    # The run stays paused while no resolution is posted.
    await asyncio.sleep(0.05)
    assert run.stage is WorkflowStage.DISPUTE
    assert run.trace[-1].kind == EventKind.DISPUTE_OPENED
    assert not run.finished

    dispute = run.active_dispute
    assert dispute is not None
    assert len(dispute.positions) == 2
    with pytest.raises(ConflictError):
        run.resolve_dispute(
            DisputeResolutionRequest(dispute_id="disp-wrong", confirmed_constraint=CONSTRAINT)
        )
    run.resolve_dispute(
        DisputeResolutionRequest(dispute_id=dispute.dispute_id, confirmed_constraint=CONSTRAINT)
    )
    await wait_for(lambda: run.stage is WorkflowStage.AWAITING_APPROVAL)
    decision = next(event for event in run.trace if event.kind == EventKind.HUMAN_DECISION)
    assert CONSTRAINT in (decision.result or "")
    assert dispute.resolved_by_human is True
    assert dispute.confirmed_constraint == CONSTRAINT

    # Revised planning respects the confirmed constraint.
    comparison = run.results.plan_comparison
    assert comparison is not None
    for evaluation in comparison.evaluations:
        assert evaluation.feasible
        assert any(CONSTRAINT in assumption for assumption in evaluation.plan.assumptions)


@pytest.mark.anyio
async def test_revision_cycle_is_visible_in_trace() -> None:
    run = make_run()
    await drive_to_approval(run)
    evaluations = [event for event in run.trace if event.tool == "evaluate_plan"]
    rejected = [event for event in evaluations if "REJECTED" in (event.result or "")]
    assert rejected, "at least one proposal must be rejected and revised"
    handoffs = [
        event
        for event in run.trace
        if event.kind == EventKind.HANDOFF and "Revise" in (event.objective or "")
    ]
    assert handoffs
    assert handoffs[0].sequence > rejected[0].sequence
    feasible_after = [
        event
        for event in evaluations
        if event.sequence > handoffs[0].sequence and "feasible" in (event.result or "")
    ]
    assert feasible_after
    run.decide_approval(
        ApprovalRequest(
            plan_archetype=PlanArchetype.OPTIMIZED_HYBRID, decision=ApprovalDecision.REJECTED
        )
    )
    await wait_for(lambda: run.finished)


@pytest.mark.anyio
async def test_timeout_sets_medium_confidence_and_still_requires_approval() -> None:
    run = make_run(alternative_sailing_failure=True)
    await drive_to_approval(run)
    error = next(event for event in run.trace if event.kind == EventKind.ERROR)
    assert error.tool == "find_alternative_sailings"
    fallback = next(
        event
        for event in run.trace
        if event.tool == "find_alternative_sailings" and event.kind == EventKind.TOOL_CALLED
    )
    assert "TIMEOUT_CACHED_FALLBACK" in (fallback.result or "")
    assert fallback.confidence is Confidence.MEDIUM
    assert any("stale" in assumption.lower() for assumption in fallback.assumptions)
    approval = next(event for event in run.trace if event.kind == EventKind.APPROVAL_REQUIRED)
    assert approval.confidence is Confidence.MEDIUM
    assert run.results.plan_comparison is not None
    assert run.results.plan_comparison.confidence is Confidence.MEDIUM
    run.decide_approval(
        ApprovalRequest(
            plan_archetype=PlanArchetype.OPTIMIZED_HYBRID, decision=ApprovalDecision.REJECTED
        )
    )
    await wait_for(lambda: run.finished)


@pytest.mark.anyio
async def test_success_lookup_keeps_high_confidence() -> None:
    run = make_run(alternative_sailing_failure=False)
    await drive_to_approval(run)
    assert not any(event.kind == EventKind.ERROR for event in run.trace)
    approval = next(event for event in run.trace if event.kind == EventKind.APPROVAL_REQUIRED)
    assert approval.confidence is Confidence.HIGH
    run.decide_approval(
        ApprovalRequest(
            plan_archetype=PlanArchetype.OPTIMIZED_HYBRID, decision=ApprovalDecision.REJECTED
        )
    )
    await wait_for(lambda: run.finished)


@pytest.mark.anyio
async def test_approval_rejected_when_not_awaiting() -> None:
    run = make_run()
    run.start()
    await wait_for(lambda: run.stage is WorkflowStage.DISPUTE)
    with pytest.raises(ConflictError):
        run.decide_approval(
            ApprovalRequest(
                plan_archetype=PlanArchetype.OPTIMIZED_HYBRID, decision=ApprovalDecision.APPROVED
            )
        )
    run.cancel()


@pytest.mark.anyio
async def test_replay_mode_streams_captured_sequence_offline() -> None:
    run = make_run(mode=RunMode.DEMO_REPLAY)
    run.start()
    await wait_for(lambda: run.stage is WorkflowStage.DISPUTE)
    assert all("DEMO REPLAY" in event.assumptions for event in run.trace)
    assert run.active_dispute is not None
    run.resolve_dispute(
        DisputeResolutionRequest(
            dispute_id=run.active_dispute.dispute_id, confirmed_constraint=CONSTRAINT
        )
    )
    await wait_for(lambda: run.stage is WorkflowStage.AWAITING_APPROVAL)
    assert not any(event.kind == EventKind.ACTION_DISPATCHED for event in run.trace)
    run.decide_approval(
        ApprovalRequest(
            plan_archetype=PlanArchetype.OPTIMIZED_HYBRID, decision=ApprovalDecision.APPROVED
        )
    )
    await wait_for(lambda: run.finished)
    assert run.stage is WorkflowStage.COMPLETE
    assert run.trace[-1].kind == EventKind.RUN_COMPLETED
    assert all("DEMO REPLAY" in event.assumptions for event in run.trace)
    constraint_event = next(
        event
        for event in run.trace
        if event.kind == EventKind.HUMAN_DECISION and event.stage is WorkflowStage.PLANNING
    )
    assert CONSTRAINT in (constraint_event.result or "")
    assert run.results.dispatched_actions
    assert run.results.plan_comparison is not None
