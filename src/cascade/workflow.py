"""Coordinator-controlled stage machine for CASCADE runs.

An explicit deterministic sequence (PRD section 10) drives every run:
RUN_STARTED -> parallel Impact + Yard assessment -> reconcile -> golden
dispute pause -> alternative-sailing lookup (optional controlled timeout) ->
Recovery plan proposal, deterministic validation, and revision -> approval
pause -> execution with mocked receipts. Agent brains supply wording and plan
allocations only; every displayed figure flows from ToolBox results into
TraceEvent fields and RunResults.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from cascade.agents.base import AgentBrain, PlanBriefing, WorkflowStep
from cascade.agents.scripted import ScriptedBrain
from cascade.contracts import (
    AgentActivity,
    AgentName,
    AgentStatus,
    ApprovalDecision,
    ApprovalRequest,
    CargoType,
    Confidence,
    ConnectionAnalysis,
    ConnectionStatus,
    Dispute,
    DisputePosition,
    DisputeResolutionRequest,
    EventKind,
    RecoveryPlan,
    RunMode,
    RunResults,
    SailingLookupStatus,
    ScenarioControls,
    ScenarioState,
    TraceEvent,
    WorkflowStage,
    YardForecast,
)
from cascade.fixtures import load_golden_scenario, load_replay_events
from cascade.tools.fake_toolbox import FakeToolBox
from cascade.tools.toolbox import ToolBox, build_toolbox

AGENT_OBJECTIVES: dict[AgentName, str] = {
    AgentName.COORDINATOR: "Interpret the alert and coordinate the recovery workflow.",
    AgentName.IMPACT: "Analyze connection impact and cargo urgency.",
    AgentName.YARD: "Analyze yard occupancy and reefer plug constraints.",
    AgentName.RECOVERY: "Generate and compare validated recovery plans.",
    AgentName.EXECUTION: "Prepare validated mocked actions after approval.",
}

MAX_REVISION_ROUNDS = 3
REPLAY_LABEL = "DEMO REPLAY"

Clock = Callable[[], datetime]


class ConflictError(Exception):
    """A human action does not match the run's current pause state."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _pharma_threatened(analysis: ConnectionAnalysis) -> int:
    return sum(
        group.container_count
        for group in analysis.groups
        if group.cargo_type == CargoType.PHARMA_REEFER
        and group.status in {ConnectionStatus.AT_RISK, ConnectionStatus.MISSED}
    )


def _yard_peak_pct(forecast: YardForecast) -> float:
    return max(100.0 * block.peak_occupancy / block.container_capacity for block in forecast.blocks)


@dataclass
class WorkflowRun:
    """One asynchronous run with an event log, pauses, and results."""

    run_id: str
    mode: RunMode
    controls: ScenarioControls
    scenario: ScenarioState
    toolbox: ToolBox
    brain: AgentBrain
    clock: Clock = _utc_now
    event_delay: float = 0.0
    stage: WorkflowStage = WorkflowStage.READY
    trace: list[TraceEvent] = field(default_factory=list)
    results: RunResults = field(default_factory=RunResults)
    active_dispute: Dispute | None = None
    finished: bool = False

    def __post_init__(self) -> None:
        self._cond = asyncio.Condition()
        self._dispute_event = asyncio.Event()
        self._dispute_resolution: DisputeResolutionRequest | None = None
        self._approval_event = asyncio.Event()
        self._approval: ApprovalRequest | None = None
        self._task: asyncio.Task[None] | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._task = asyncio.create_task(self._run_safely())

    def cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def _run_safely(self) -> None:
        try:
            if self.mode is RunMode.DEMO_REPLAY:
                await self._run_replay()
            else:
                await self._run_stage_machine()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a failed run must surface, not crash the app
            self.stage = WorkflowStage.FAILED
            await self._emit(
                kind=EventKind.ERROR,
                stage=WorkflowStage.FAILED,
                agent=AgentName.COORDINATOR,
                error=str(exc),
                result="Run failed; no further actions will be taken.",
            )
        finally:
            async with self._cond:
                self.finished = True
                self._cond.notify_all()

    # -- event log and subscriptions ----------------------------------------

    async def _emit(self, **fields: Any) -> TraceEvent:
        # Always yield so concurrent agent tasks interleave deterministically.
        await asyncio.sleep(self.event_delay)
        stage = fields.pop("stage")
        self.stage = stage
        event = TraceEvent(
            event_id=f"{self.run_id[:8]}-{len(self.trace) + 1:03d}",
            sequence=len(self.trace) + 1,
            timestamp=self.clock(),
            stage=stage,
            **fields,
        )
        async with self._cond:
            self.trace.append(event)
            self._cond.notify_all()
        return event

    async def wait_events(self, index: int, timeout: float) -> tuple[list[TraceEvent], bool] | None:
        """New events after ``index``, or None on timeout (keep-alive)."""
        async with self._cond:
            if len(self.trace) > index or self.finished:
                return list(self.trace[index:]), self.finished
            try:
                await asyncio.wait_for(self._cond.wait(), timeout)
            except TimeoutError:
                return None
            return list(self.trace[index:]), self.finished

    def activities(self) -> list[AgentActivity]:
        status: dict[AgentName, AgentStatus] = dict.fromkeys(AGENT_OBJECTIVES, AgentStatus.WAITING)
        latest: dict[AgentName, TraceEvent] = {}
        for event in self.trace:
            if event.agent is None:
                continue
            latest[event.agent] = event
            if event.kind == EventKind.AGENT_STARTED:
                status[event.agent] = AgentStatus.RUNNING
            elif event.kind == EventKind.AGENT_COMPLETED:
                status[event.agent] = AgentStatus.COMPLETED
            elif event.kind in {EventKind.DISPUTE_OPENED, EventKind.APPROVAL_REQUIRED}:
                status[event.agent] = AgentStatus.BLOCKED
            elif event.kind == EventKind.ERROR and event.stage == WorkflowStage.FAILED:
                status[event.agent] = AgentStatus.FAILED
            elif event.kind in {EventKind.RUN_STARTED, EventKind.HUMAN_DECISION}:
                status[event.agent] = AgentStatus.RUNNING
            elif event.kind == EventKind.RUN_COMPLETED:
                status[event.agent] = AgentStatus.COMPLETED
        return [
            AgentActivity(
                agent=agent,
                objective=objective,
                status=status[agent],
                confidence=latest[agent].confidence if agent in latest else None,
                last_summary=(
                    (latest[agent].result or latest[agent].decision_summary)
                    if agent in latest
                    else None
                ),
            )
            for agent, objective in AGENT_OBJECTIVES.items()
        ]

    # -- human interaction ---------------------------------------------------

    def resolve_dispute(self, request: DisputeResolutionRequest) -> None:
        if self.active_dispute is None or self.stage is not WorkflowStage.DISPUTE:
            raise ConflictError("No open dispute is awaiting resolution.")
        if request.dispute_id != self.active_dispute.dispute_id:
            raise ConflictError(f"Unknown dispute id {request.dispute_id!r}.")
        if self._dispute_event.is_set():
            raise ConflictError("The dispute has already been resolved.")
        self._dispute_resolution = request
        self._dispute_event.set()

    def decide_approval(self, request: ApprovalRequest) -> None:
        if self.stage is not WorkflowStage.AWAITING_APPROVAL:
            raise ConflictError("The run is not awaiting approval.")
        if self._approval_event.is_set():
            raise ConflictError("An approval decision was already recorded.")
        self._approval = request
        self._approval_event.set()

    # -- stage machine --------------------------------------------------------

    async def _run_stage_machine(self) -> None:
        alert = self.scenario.alert
        emphasis = self.controls.priority_emphasis
        revised_eta = alert.revised_eta
        horizon = self.scenario.planning_horizon_hours
        summarize = self.brain.summarize

        started = summarize(
            WorkflowStep.RUN_STARTED,
            {
                "delay_hours": alert.delay_hours,
                "vessel": alert.vessel_name,
                "priority": emphasis.value,
            },
        )
        await self._emit(
            kind=EventKind.RUN_STARTED,
            stage=WorkflowStage.ASSESSING,
            agent=AgentName.COORDINATOR,
            objective=self.scenario.objective,
            input_summary=(
                f"{alert.vessel_name} revised ETA {revised_eta.isoformat()} "
                f"({alert.delay_hours} hours late); priority {emphasis.value}."
            ),
            decision_summary=started.decision_summary,
            confidence=Confidence.HIGH,
            assumptions=started.assumptions,
            elapsed_ms=180,
            next_handoff=AgentName.IMPACT,
        )

        analysis, baseline = await self._parallel_assessment(revised_eta, emphasis, horizon)
        await self._golden_dispute(analysis, baseline)
        sailings, run_confidence = await self._sailing_lookup()
        comparison_recommended = await self._planning(
            revised_eta, emphasis, horizon, analysis, sailings, run_confidence
        )
        await self._approval_and_execution(comparison_recommended, run_confidence)

    async def _parallel_assessment(
        self, revised_eta: datetime, emphasis: Any, horizon: int
    ) -> tuple[ConnectionAnalysis, YardForecast]:
        group = "assessment-1"

        async def impact_task() -> ConnectionAnalysis:
            await self._emit(
                kind=EventKind.AGENT_STARTED,
                stage=WorkflowStage.ASSESSING,
                agent=AgentName.IMPACT,
                objective=AGENT_OBJECTIVES[AgentName.IMPACT],
                input_summary="Delegated by the Coordinator Agent.",
                parallel_group=group,
            )
            analysis = self.toolbox.analyse_connections(revised_eta, emphasis)
            self.results.connection_analysis = analysis
            pharma = _pharma_threatened(analysis)
            summary = self.brain.summarize(
                WorkflowStep.IMPACT_ASSESSMENT,
                {
                    "pharma_threatened": pharma,
                    "safe": analysis.safe_count,
                    "at_risk": analysis.at_risk_count,
                    "missed": analysis.missed_count,
                },
            )
            await self._emit(
                kind=EventKind.TOOL_CALLED,
                stage=WorkflowStage.ASSESSING,
                agent=AgentName.IMPACT,
                tool="analyse_connections",
                input_summary=f"Revised ETA {revised_eta.isoformat()}",
                result=(
                    f"{analysis.safe_count} safe, {analysis.at_risk_count} at risk, "
                    f"{analysis.missed_count} missed; {pharma} pharmaceutical reefers "
                    "are threatened."
                ),
                decision_summary=summary.decision_summary,
                confidence=Confidence.HIGH,
                assumptions=summary.assumptions,
                elapsed_ms=420,
                parallel_group=group,
            )
            await self._emit(
                kind=EventKind.AGENT_COMPLETED,
                stage=WorkflowStage.ASSESSING,
                agent=AgentName.IMPACT,
                result=f"Connection analysis complete for {len(analysis.groups)} cargo groups.",
                confidence=Confidence.HIGH,
                elapsed_ms=460,
                next_handoff=AgentName.COORDINATOR,
                parallel_group=group,
            )
            return analysis

        async def yard_task() -> YardForecast:
            await self._emit(
                kind=EventKind.AGENT_STARTED,
                stage=WorkflowStage.ASSESSING,
                agent=AgentName.YARD,
                objective=AGENT_OBJECTIVES[AgentName.YARD],
                input_summary="Delegated by the Coordinator Agent.",
                parallel_group=group,
            )
            analysis_for_yard = self.toolbox.analyse_connections(revised_eta, emphasis)
            baseline = self.toolbox.simulate_yard(revised_eta, analysis_for_yard, None, horizon)
            self.results.baseline_yard = baseline
            peak_pct = _yard_peak_pct(baseline)
            shortage = baseline.reefer_shortages[0] if baseline.reefer_shortages else None
            summary = self.brain.summarize(
                WorkflowStep.YARD_ASSESSMENT,
                {
                    "peak_pct": round(peak_pct),
                    "required_plugs": shortage.required_plugs if shortage else 0,
                    "available_plugs": shortage.available_plugs if shortage else 0,
                },
            )
            shortage_text = (
                f"a {shortage.required_plugs - shortage.available_plugs}-plug reefer shortage "
                f"in block {shortage.block_id}"
                if shortage
                else "no reefer plug shortage"
            )
            await self._emit(
                kind=EventKind.TOOL_CALLED,
                stage=WorkflowStage.ASSESSING,
                agent=AgentName.YARD,
                tool="simulate_yard",
                input_summary=f"{len(baseline.blocks)} blocks over {horizon} hours",
                result=(
                    f"Peak yard occupancy reaches {peak_pct:.0f}%; rushing all reefers "
                    f"creates {shortage_text}."
                ),
                decision_summary=summary.decision_summary,
                confidence=Confidence.HIGH,
                assumptions=summary.assumptions,
                elapsed_ms=390,
                parallel_group=group,
            )
            await self._emit(
                kind=EventKind.AGENT_COMPLETED,
                stage=WorkflowStage.ASSESSING,
                agent=AgentName.YARD,
                result=f"Yard forecast complete for {len(baseline.blocks)} blocks.",
                confidence=Confidence.HIGH,
                elapsed_ms=430,
                next_handoff=AgentName.COORDINATOR,
                parallel_group=group,
            )
            return baseline

        analysis, baseline = await asyncio.gather(impact_task(), yard_task())
        return analysis, baseline

    async def _golden_dispute(self, analysis: ConnectionAnalysis, baseline: YardForecast) -> None:
        shortage = baseline.reefer_shortages[0] if baseline.reefer_shortages else None
        if shortage is None:
            return
        pharma = _pharma_threatened(analysis)
        dispute = Dispute(
            dispute_id=f"disp-{self.run_id[:8]}",
            question=(
                "Should all threatened pharmaceutical reefers be rushed, or must the "
                "reefer plug limit govern the plan?"
            ),
            positions=[
                DisputePosition(
                    agent=AgentName.IMPACT,
                    position=f"Rush all {pharma} threatened pharmaceutical reefers.",
                    evidence=[
                        f"{analysis.at_risk_count} connections at risk and "
                        f"{analysis.missed_count} already missed (analyse_connections).",
                        f"{pharma} pharmaceutical reefers hold the highest priority rank.",
                    ],
                ),
                DisputePosition(
                    agent=AgentName.YARD,
                    position="Stay within physical reefer plug capacity.",
                    evidence=[
                        f"Rushing every reefer needs {shortage.required_plugs} plugs but only "
                        f"{shortage.available_plugs} are available (simulate_yard).",
                        f"Shortage starts {shortage.start_time.isoformat()} "
                        f"in block {shortage.block_id}.",
                    ],
                ),
            ],
        )
        self.active_dispute = dispute
        reconcile = self.brain.summarize(WorkflowStep.RECONCILE, {})
        await self._emit(
            kind=EventKind.DISPUTE_OPENED,
            stage=WorkflowStage.DISPUTE,
            agent=AgentName.COORDINATOR,
            objective="Reconcile cargo protection with physical capacity.",
            input_summary=(
                f"Impact wants all {pharma} reefers rushed; Yard reports "
                f"{shortage.required_plugs} plugs needed against {shortage.available_plugs}."
            ),
            decision_summary=reconcile.decision_summary,
            confidence=Confidence.LOW,
            assumptions=reconcile.assumptions,
            result="Planning is paused until a human confirms the governing constraint.",
            elapsed_ms=150,
        )
        await self._dispute_event.wait()
        resolution = self._dispute_resolution
        assert resolution is not None
        dispute.confirmed_constraint = resolution.confirmed_constraint
        dispute.resolved_by_human = True
        decided = self.brain.summarize(
            WorkflowStep.HUMAN_CONSTRAINT, {"constraint": resolution.confirmed_constraint}
        )
        await self._emit(
            kind=EventKind.HUMAN_DECISION,
            stage=WorkflowStage.PLANNING,
            agent=AgentName.COORDINATOR,
            objective="Record the governing constraint confirmed by the controller.",
            input_summary=f"Controller resolved dispute {dispute.dispute_id}.",
            decision_summary=decided.decision_summary,
            result=f"Confirmed constraint: {resolution.confirmed_constraint}",
            confidence=Confidence.HIGH,
            assumptions=decided.assumptions,
            elapsed_ms=90,
            next_handoff=AgentName.RECOVERY,
        )

    async def _sailing_lookup(self) -> tuple[Any, Confidence]:
        force_timeout = self.controls.alternative_sailing_failure
        if force_timeout:
            await self._emit(
                kind=EventKind.ERROR,
                stage=WorkflowStage.PLANNING,
                agent=AgentName.RECOVERY,
                tool="find_alternative_sailings",
                input_summary="Live synthetic sailing lookup.",
                error="find_alternative_sailings timed out after 3000 ms.",
                result="Falling back to the cached synthetic sailing snapshot.",
                confidence=Confidence.MEDIUM,
                elapsed_ms=3000,
            )
        sailings = self.toolbox.find_alternative_sailings(force_timeout)
        self.results.alternative_sailings = sailings
        run_confidence = (
            Confidence.MEDIUM
            if sailings.status is SailingLookupStatus.TIMEOUT_CACHED_FALLBACK
            else Confidence.HIGH
        )
        summary = self.brain.summarize(
            WorkflowStep.SAILING_LOOKUP, {"sailing_count": len(sailings.sailings)}
        )
        assumptions = list(summary.assumptions)
        if sailings.stale_notice:
            assumptions.append(sailings.stale_notice)
        await self._emit(
            kind=EventKind.TOOL_CALLED,
            stage=WorkflowStage.PLANNING,
            agent=AgentName.RECOVERY,
            tool="find_alternative_sailings",
            input_summary="Cached fallback." if force_timeout else "Live synthetic lookup.",
            result=(f"{len(sailings.sailings)} alternative sailings ({sailings.status.value})."),
            decision_summary=summary.decision_summary,
            confidence=run_confidence,
            assumptions=assumptions,
            elapsed_ms=120,
        )
        return sailings, run_confidence

    async def _planning(
        self,
        revised_eta: datetime,
        emphasis: Any,
        horizon: int,
        analysis: ConnectionAnalysis,
        sailings: Any,
        run_confidence: Confidence,
    ) -> Any:
        constraint = self.active_dispute.confirmed_constraint if self.active_dispute else None
        briefing = PlanBriefing(
            analysis=analysis,
            sailings=sailings,
            confirmed_constraint=constraint,
            priority_emphasis=self.controls.priority_emphasis.value,
        )
        proposal = self.brain.summarize(WorkflowStep.PLAN_PROPOSAL, {})
        await self._emit(
            kind=EventKind.AGENT_STARTED,
            stage=WorkflowStage.PLANNING,
            agent=AgentName.RECOVERY,
            objective=AGENT_OBJECTIVES[AgentName.RECOVERY],
            input_summary=(
                "Connection analysis, yard forecast, alternative sailings, and the "
                "confirmed constraint."
            ),
            decision_summary=proposal.decision_summary,
            assumptions=proposal.assumptions,
        )
        plans = self.brain.propose_plans(briefing)
        final_plans: list[RecoveryPlan] = []
        for plan in plans:
            evaluation = self.toolbox.evaluate_plan(revised_eta, analysis, plan, emphasis)
            await self._emit_evaluation(plan, evaluation)
            rounds = 0
            while not evaluation.feasible and rounds < MAX_REVISION_ROUNDS:
                rounds += 1
                await self._emit(
                    kind=EventKind.HANDOFF,
                    stage=WorkflowStage.PLANNING,
                    agent=AgentName.RECOVERY,
                    objective=f"Revise the rejected {plan.archetype.value} proposal.",
                    input_summary="; ".join(evaluation.rejection_reasons),
                    decision_summary=(
                        f"Revision round {rounds}: adjust {plan.archetype.value} to satisfy "
                        "deterministic validation."
                    ),
                    elapsed_ms=200,
                )
                plan = self.brain.revise_plan(plan, evaluation.rejection_reasons, briefing)
                evaluation = self.toolbox.evaluate_plan(revised_eta, analysis, plan, emphasis)
                await self._emit_evaluation(plan, evaluation)
            # A plan that stays infeasible after the revision limit is carried
            # into the comparison as-is: compare_plans never recommends an
            # infeasible plan, and its final REJECTED evaluation stays visible
            # in the trace. Only a fully infeasible slate fails the run below.
            final_plans.append(plan)
        comparison = self.toolbox.compare_plans(
            revised_eta, analysis, final_plans, emphasis, run_confidence
        )
        self.results.plan_comparison = comparison
        compared = self.brain.summarize(
            WorkflowStep.PLAN_COMPARISON,
            {
                "recommended": comparison.recommended.value if comparison.recommended else "none",
                "rationale": comparison.rationale,
            },
        )
        await self._emit(
            kind=EventKind.TOOL_CALLED,
            stage=WorkflowStage.PLANNING,
            agent=AgentName.RECOVERY,
            tool="compare_plans",
            input_summary=f"{len(final_plans)} validated plans.",
            result=comparison.rationale,
            decision_summary=compared.decision_summary,
            confidence=comparison.confidence,
            assumptions=compared.assumptions,
            elapsed_ms=310,
        )
        if comparison.recommended is None:
            raise RuntimeError(
                "All plans stayed infeasible after "
                f"{MAX_REVISION_ROUNDS} revision rounds; nothing can be recommended."
            )
        recommended_plan = None
        if comparison.recommended is not None:
            recommended_plan = next(
                evaluation.plan
                for evaluation in comparison.evaluations
                if evaluation.plan.archetype == comparison.recommended
            )
            planned = self.toolbox.simulate_yard(revised_eta, analysis, recommended_plan, horizon)
            self.results.planned_yard = planned
            await self._emit(
                kind=EventKind.TOOL_CALLED,
                stage=WorkflowStage.PLANNING,
                agent=AgentName.RECOVERY,
                tool="simulate_yard",
                input_summary=f"Recommended plan {comparison.recommended.value}.",
                result=(
                    f"Planned yard peak drops to {_yard_peak_pct(planned):.0f}% "
                    f"with {len(planned.reefer_shortages)} reefer shortages."
                ),
                confidence=comparison.confidence,
                elapsed_ms=280,
            )
        await self._emit(
            kind=EventKind.AGENT_COMPLETED,
            stage=WorkflowStage.PLANNING,
            agent=AgentName.RECOVERY,
            result=(
                f"{sum(1 for e in comparison.evaluations if e.feasible)} feasible plans "
                "ready for approval."
            ),
            confidence=comparison.confidence,
            elapsed_ms=340,
            next_handoff=AgentName.COORDINATOR,
        )
        return comparison

    async def _emit_evaluation(self, plan: RecoveryPlan, evaluation: Any) -> None:
        if evaluation.feasible:
            metrics = evaluation.metrics
            result = (
                f"{plan.archetype.value} feasible: {metrics.missed_connections} missed "
                f"connections, {metrics.critical_cargo_protected_pct:.0f}% critical cargo "
                f"protected, SGD {metrics.cost.total:,.0f} illustrative cost."
            )
        else:
            result = f"{plan.archetype.value} REJECTED: " + "; ".join(evaluation.rejection_reasons)
        await self._emit(
            kind=EventKind.TOOL_CALLED,
            stage=WorkflowStage.PLANNING,
            agent=AgentName.RECOVERY,
            tool="evaluate_plan",
            input_summary=f"{plan.archetype.value}: {len(plan.actions)} actions.",
            result=result,
            confidence=Confidence.HIGH if evaluation.feasible else Confidence.LOW,
            elapsed_ms=260,
        )

    async def _approval_and_execution(self, comparison: Any, run_confidence: Confidence) -> None:
        recommended = comparison.recommended.value if comparison.recommended else "none"
        approval_summary = self.brain.summarize(
            WorkflowStep.APPROVAL_REQUEST, {"recommended": recommended}
        )
        await self._emit(
            kind=EventKind.APPROVAL_REQUIRED,
            stage=WorkflowStage.AWAITING_APPROVAL,
            agent=AgentName.COORDINATOR,
            objective="Obtain mandatory human approval before mocked dispatch.",
            input_summary=f"Recommended plan: {recommended} ({run_confidence.value} confidence).",
            decision_summary=approval_summary.decision_summary,
            confidence=run_confidence,
            assumptions=approval_summary.assumptions,
            result="Execution stays blocked until the controller decides.",
            elapsed_ms=100,
        )
        await self._approval_event.wait()
        approval = self._approval
        assert approval is not None
        if approval.decision is ApprovalDecision.REJECTED:
            await self._emit(
                kind=EventKind.HUMAN_DECISION,
                stage=WorkflowStage.COMPLETE,
                agent=AgentName.COORDINATOR,
                input_summary=f"Controller rejected {approval.plan_archetype.value}.",
                decision_summary="The controller rejected the recommendation.",
                result="No mocked actions will be dispatched.",
                confidence=run_confidence,
                elapsed_ms=80,
            )
            done = self.brain.summarize(
                WorkflowStep.RUN_COMPLETED,
                {"outcome": "Run complete: the plan was rejected and no actions were dispatched."},
            )
            await self._emit(
                kind=EventKind.RUN_COMPLETED,
                stage=WorkflowStage.COMPLETE,
                agent=AgentName.COORDINATOR,
                decision_summary=done.decision_summary,
                result="0 mocked actions dispatched.",
                confidence=run_confidence,
                elapsed_ms=60,
            )
            return

        approved_plan = next(
            evaluation.plan
            for evaluation in comparison.evaluations
            if evaluation.plan.archetype == approval.plan_archetype
        )
        await self._emit(
            kind=EventKind.HUMAN_DECISION,
            stage=WorkflowStage.EXECUTING,
            agent=AgentName.COORDINATOR,
            input_summary=f"Controller approved {approved_plan.archetype.value}.",
            decision_summary=(
                f"Execute the approved {approved_plan.archetype.value} plan with mocked actions."
            ),
            result=f"Approved plan: {approved_plan.archetype.value}.",
            confidence=run_confidence,
            elapsed_ms=80,
            next_handoff=AgentName.EXECUTION,
        )
        execution_summary = self.brain.summarize(
            WorkflowStep.EXECUTION, {"plan": approved_plan.archetype.value}
        )
        await self._emit(
            kind=EventKind.AGENT_STARTED,
            stage=WorkflowStage.EXECUTING,
            agent=AgentName.EXECUTION,
            objective=AGENT_OBJECTIVES[AgentName.EXECUTION],
            input_summary=f"Approved plan {approved_plan.archetype.value}.",
            decision_summary=execution_summary.decision_summary,
            assumptions=execution_summary.assumptions,
        )
        actions = self.toolbox.build_actions(approved_plan)
        receipts = self.toolbox.validate_actions(approved_plan, actions)
        accepted = [
            (action, receipt)
            for action, receipt in zip(actions, receipts, strict=True)
            if receipt.status.value == "ACCEPTED"
        ]
        self.results.receipts = receipts
        self.results.dispatched_actions = [action for action, _ in accepted]
        await self._emit(
            kind=EventKind.TOOL_CALLED,
            stage=WorkflowStage.EXECUTING,
            agent=AgentName.EXECUTION,
            tool="validate_actions",
            input_summary=f"{len(actions)} proposed mocked actions.",
            result=f"{len(accepted)} of {len(actions)} actions accepted by validation.",
            confidence=Confidence.HIGH,
            elapsed_ms=140,
        )
        for action, receipt in accepted:
            await self._emit(
                kind=EventKind.ACTION_DISPATCHED,
                stage=WorkflowStage.EXECUTING,
                agent=AgentName.EXECUTION,
                tool="dispatch_plan",
                input_summary=action.payload_summary,
                decision_summary=action.description,
                result=f"Receipt {receipt.receipt_ref}: {receipt.detail}",
                confidence=Confidence.HIGH,
                elapsed_ms=110,
            )
        await self._emit(
            kind=EventKind.AGENT_COMPLETED,
            stage=WorkflowStage.EXECUTING,
            agent=AgentName.EXECUTION,
            result=f"{len(accepted)} mocked actions dispatched with receipts.",
            confidence=Confidence.HIGH,
            elapsed_ms=160,
            next_handoff=AgentName.COORDINATOR,
        )
        done = self.brain.summarize(
            WorkflowStep.RUN_COMPLETED,
            {
                "outcome": (
                    f"Run complete: {len(accepted)} mocked actions dispatched for "
                    f"{approved_plan.archetype.value}."
                )
            },
        )
        await self._emit(
            kind=EventKind.RUN_COMPLETED,
            stage=WorkflowStage.COMPLETE,
            agent=AgentName.COORDINATOR,
            decision_summary=done.decision_summary,
            result=f"{len(accepted)} mocked actions dispatched.",
            confidence=run_confidence,
            elapsed_ms=90,
        )

    # -- replay mode -----------------------------------------------------------

    async def _run_replay(self) -> None:
        events = load_replay_events()
        toolbox = FakeToolBox()
        brain = ScriptedBrain()
        alert = self.scenario.alert
        emphasis = self.controls.priority_emphasis
        analysis = toolbox.analyse_connections(alert.revised_eta, emphasis)
        self.results.connection_analysis = analysis
        self.results.baseline_yard = toolbox.simulate_yard(
            alert.revised_eta, analysis, None, self.scenario.planning_horizon_hours
        )
        for recorded in events:
            event = recorded.model_copy(deep=True)
            if REPLAY_LABEL not in event.assumptions:
                event.assumptions = [REPLAY_LABEL, *event.assumptions]
            if event.kind == EventKind.HUMAN_DECISION and self._dispute_resolution is not None:
                constraint = self._dispute_resolution.confirmed_constraint
                if event.stage is WorkflowStage.PLANNING:
                    event.decision_summary = f"Record the confirmed constraint: {constraint}"
                    event.result = f"Confirmed constraint: {constraint}"
            await self._replay_emit(event)
            if event.kind == EventKind.DISPUTE_OPENED:
                await self._replay_dispute(analysis)
            elif event.kind == EventKind.APPROVAL_REQUIRED:
                finished = await self._replay_approval(toolbox, brain, analysis, emphasis)
                if finished:
                    return

    async def _replay_emit(self, event: TraceEvent) -> None:
        if self.event_delay:
            await asyncio.sleep(self.event_delay)
        renumbered = event.model_copy(
            update={
                "sequence": len(self.trace) + 1,
                "event_id": f"replay-{len(self.trace) + 1:03d}",
            }
        )
        self.stage = renumbered.stage
        async with self._cond:
            self.trace.append(renumbered)
            self._cond.notify_all()

    async def _replay_dispute(self, analysis: ConnectionAnalysis) -> None:
        baseline = self.results.baseline_yard
        shortage = baseline.reefer_shortages[0] if baseline and baseline.reefer_shortages else None
        pharma = _pharma_threatened(analysis)
        self.active_dispute = Dispute(
            dispute_id=f"disp-{self.run_id[:8]}",
            question=(
                "Should all threatened pharmaceutical reefers be rushed, or must the "
                "reefer plug limit govern the plan?"
            ),
            positions=[
                DisputePosition(
                    agent=AgentName.IMPACT,
                    position=f"Rush all {pharma} threatened pharmaceutical reefers.",
                    evidence=[REPLAY_LABEL],
                ),
                DisputePosition(
                    agent=AgentName.YARD,
                    position="Stay within physical reefer plug capacity.",
                    evidence=[
                        REPLAY_LABEL
                        if shortage is None
                        else f"{shortage.required_plugs} plugs needed, "
                        f"{shortage.available_plugs} available."
                    ],
                ),
            ],
        )
        self.stage = WorkflowStage.DISPUTE
        await self._dispute_event.wait()
        resolution = self._dispute_resolution
        assert resolution is not None
        self.active_dispute.confirmed_constraint = resolution.confirmed_constraint
        self.active_dispute.resolved_by_human = True

    async def _replay_approval(
        self,
        toolbox: FakeToolBox,
        brain: ScriptedBrain,
        analysis: ConnectionAnalysis,
        emphasis: Any,
    ) -> bool:
        alert = self.scenario.alert
        constraint = self.active_dispute.confirmed_constraint if self.active_dispute else None
        sailings = toolbox.find_alternative_sailings(self.controls.alternative_sailing_failure)
        self.results.alternative_sailings = sailings
        run_confidence = (
            Confidence.MEDIUM
            if sailings.status is SailingLookupStatus.TIMEOUT_CACHED_FALLBACK
            else Confidence.HIGH
        )
        briefing = PlanBriefing(
            analysis=analysis,
            sailings=sailings,
            confirmed_constraint=constraint or "rush at most 34 pharmaceutical reefers",
            priority_emphasis=emphasis.value,
        )
        plans = brain.propose_plans(briefing)
        feasible_plans = []
        for plan in plans:
            evaluation = toolbox.evaluate_plan(alert.revised_eta, analysis, plan, emphasis)
            if not evaluation.feasible:
                plan = brain.revise_plan(plan, evaluation.rejection_reasons, briefing)
            feasible_plans.append(plan)
        comparison = toolbox.compare_plans(
            alert.revised_eta, analysis, feasible_plans, emphasis, run_confidence
        )
        self.results.plan_comparison = comparison
        if comparison.recommended is not None:
            recommended_plan = next(
                evaluation.plan
                for evaluation in comparison.evaluations
                if evaluation.plan.archetype == comparison.recommended
            )
            self.results.planned_yard = toolbox.simulate_yard(
                alert.revised_eta,
                analysis,
                recommended_plan,
                self.scenario.planning_horizon_hours,
            )

        await self._approval_event.wait()
        approval = self._approval
        assert approval is not None
        if approval.decision is ApprovalDecision.APPROVED:
            approved_plan = next(
                (
                    evaluation.plan
                    for evaluation in comparison.evaluations
                    if evaluation.plan.archetype == approval.plan_archetype
                ),
                None,
            )
            if approved_plan is not None:
                actions = toolbox.build_actions(approved_plan)
                receipts = toolbox.validate_actions(approved_plan, actions)
                self.results.receipts = receipts
                self.results.dispatched_actions = [
                    action
                    for action, receipt in zip(actions, receipts, strict=True)
                    if receipt.status.value == "ACCEPTED"
                ]
            return False
        await self._replay_emit(
            TraceEvent(
                event_id="replay-reject",
                sequence=1,
                timestamp=self.clock(),
                kind=EventKind.HUMAN_DECISION,
                stage=WorkflowStage.COMPLETE,
                agent=AgentName.COORDINATOR,
                decision_summary="The controller rejected the recommendation.",
                result="No mocked actions will be dispatched.",
                assumptions=[REPLAY_LABEL],
            )
        )
        await self._replay_emit(
            TraceEvent(
                event_id="replay-complete",
                sequence=1,
                timestamp=self.clock(),
                kind=EventKind.RUN_COMPLETED,
                stage=WorkflowStage.COMPLETE,
                agent=AgentName.COORDINATOR,
                decision_summary="Run complete: the plan was rejected.",
                result="0 mocked actions dispatched.",
                assumptions=[REPLAY_LABEL],
            )
        )
        return True


def default_brain_factory(mode: RunMode) -> AgentBrain:
    if mode is RunMode.LIVE_GEMINI:
        from cascade.agents.live_gemini import build_live_brain

        return build_live_brain()
    if mode is RunMode.LIVE_CLAUDE:
        from cascade.agents.local_claude import ClaudeBrain

        return ClaudeBrain.create()
    return ScriptedBrain()


class RunStore:
    """In-memory run registry with pluggable toolbox and brain seams."""

    def __init__(
        self,
        toolbox_factory: Callable[[], ToolBox] = build_toolbox,
        brain_factory: Callable[[RunMode], AgentBrain] = default_brain_factory,
        event_delay: float = 0.0,
    ) -> None:
        self._runs: dict[str, WorkflowRun] = {}
        self.toolbox_factory = toolbox_factory
        self.brain_factory = brain_factory
        self.event_delay = event_delay

    def create(self, controls: ScenarioControls, mode: RunMode) -> WorkflowRun:
        brain = self.brain_factory(mode)
        toolbox = FakeToolBox() if mode is RunMode.DEMO_REPLAY else self.toolbox_factory()
        run = WorkflowRun(
            run_id=str(uuid4()),
            mode=mode,
            controls=controls,
            scenario=scenario_with_controls(controls),
            toolbox=toolbox,
            brain=brain,
            event_delay=self.event_delay,
        )
        self._runs[run.run_id] = run
        run.start()
        return run

    def get(self, run_id: str) -> WorkflowRun | None:
        return self._runs.get(run_id)

    def reset(self) -> None:
        for run in self._runs.values():
            run.cancel()
        self._runs.clear()


def scenario_with_controls(controls: ScenarioControls | None = None) -> ScenarioState:
    scenario = load_golden_scenario()
    if controls is None:
        return scenario
    alert = scenario.alert.model_copy(
        update={"revised_eta": scenario.alert.original_eta + timedelta(hours=controls.delay_hours)}
    )
    return scenario.model_copy(update={"alert": alert, "controls": controls})
