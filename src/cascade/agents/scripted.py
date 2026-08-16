"""Deterministic scripted brain for LIVE_STUB mode.

Wording templates are filled only with figures the stage machine computed from
tool results, so nothing displayed is invented here.
"""

import re
from dataclasses import dataclass
from typing import Any

from cascade.agents.base import AgentSummary, PlanBriefing, WorkflowStep
from cascade.contracts import (
    CargoType,
    ConnectionStatus,
    PlanAction,
    PlanArchetype,
    RecoveryActionType,
    RecoveryPlan,
)

_TEMPLATES: dict[WorkflowStep, tuple[str, list[str]]] = {
    WorkflowStep.RUN_STARTED: (
        "Interpret the {delay_hours}-hour delay of {vessel} and run the Impact and Yard "
        "assessments in parallel with {priority} emphasis.",
        ["Synthetic golden scenario, seed 42"],
    ),
    WorkflowStep.IMPACT_ASSESSMENT: (
        "Prioritize the {pharma_threatened} threatened pharmaceutical reefers; "
        "{at_risk} connections are at risk and {missed} are already missed.",
        [],
    ),
    WorkflowStep.YARD_ASSESSMENT: (
        "Flag the reefer plug shortage as a hard physical constraint: rushing every reefer "
        "needs {required_plugs} plugs but only {available_plugs} exist.",
        [],
    ),
    WorkflowStep.RECONCILE: (
        "Impact and Yard evidence conflict on reefer handling; pause for a human to confirm "
        "the governing constraint before planning.",
        [],
    ),
    WorkflowStep.HUMAN_CONSTRAINT: (
        "Record the confirmed constraint: {constraint}",
        [],
    ),
    WorkflowStep.SAILING_LOOKUP: (
        "Use {sailing_count} synthetic alternative sailings for rebooking options.",
        [],
    ),
    WorkflowStep.PLAN_PROPOSAL: (
        "Propose the three fixed archetypes and submit each to deterministic validation.",
        [],
    ),
    WorkflowStep.PLAN_COMPARISON: (
        "Recommend {recommended}: {rationale}",
        [],
    ),
    WorkflowStep.APPROVAL_REQUEST: (
        "Await mandatory human approval of {recommended} before any mocked dispatch.",
        [],
    ),
    WorkflowStep.EXECUTION: (
        "Translate the approved {plan} plan into allowlisted mocked actions.",
        [],
    ),
    WorkflowStep.RUN_COMPLETED: (
        "{outcome}",
        [],
    ),
}

_CAP_PATTERN = re.compile(r"rush at most (\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class _Group:
    onward_vessel: str
    cargo_type: CargoType
    container_count: int


def _constraint_cap(text: str | None) -> int | None:
    if not text:
        return None
    match = _CAP_PATTERN.search(text)
    return int(match.group(1)) if match else None


def _threatened(briefing: PlanBriefing, cargo: CargoType) -> list[_Group]:
    return [
        _Group(group.onward_vessel, group.cargo_type, group.container_count)
        for group in briefing.analysis.groups
        if group.cargo_type == cargo
        and group.status in {ConnectionStatus.AT_RISK, ConnectionStatus.MISSED}
    ]


def _rush(group: _Group, count: int | None = None) -> PlanAction:
    containers = group.container_count if count is None else count
    return PlanAction(
        action=RecoveryActionType.RUSH,
        onward_vessel=group.onward_vessel,
        cargo_type=group.cargo_type,
        container_count=containers,
        target_sailing=None,
        rationale=f"Rush {containers} containers to still meet {group.onward_vessel}.",
    )


def _rebook(group: _Group, targets: dict[str, str], count: int | None = None) -> PlanAction:
    containers = group.container_count if count is None else count
    target = targets.get(group.onward_vessel)
    return PlanAction(
        action=RecoveryActionType.REBOOK,
        onward_vessel=group.onward_vessel,
        cargo_type=group.cargo_type,
        container_count=containers,
        target_sailing=target,
        rationale=(
            f"Rebook {containers} containers from {group.onward_vessel} to "
            f"{target or 'a later synthetic sailing'}."
        ),
    )


class ScriptedBrain:
    """Offline deterministic wording and plan allocations."""

    def summarize(self, step: WorkflowStep, facts: dict[str, Any]) -> AgentSummary:
        template, assumptions = _TEMPLATES[step]
        return AgentSummary(
            decision_summary=template.format(**facts), assumptions=list(assumptions)
        )

    def propose_plans(self, briefing: PlanBriefing) -> list[RecoveryPlan]:
        pharma = _threatened(briefing, CargoType.PHARMA_REEFER)
        manufacturing = _threatened(briefing, CargoType.TIME_CRITICAL_MANUFACTURING)
        dry = _threatened(briefing, CargoType.GENERAL_DRY)
        targets = {
            sailing.replaces_onward_vessel: sailing.vessel_name
            for sailing in briefing.sailings.sailings
        }
        assumptions = ["Deterministic tools remain the source of truth for all figures."]
        if briefing.confirmed_constraint:
            assumptions.append(f"Confirmed constraint: {briefing.confirmed_constraint}")

        aggressive = RecoveryPlan(
            archetype=PlanArchetype.AGGRESSIVE_RUSH,
            title="Rush every threatened connection",
            actions=[_rush(group) for group in pharma + manufacturing + dry],
            assumptions=assumptions + ["Additional handling capacity is available on demand."],
        )
        rebook = RecoveryPlan(
            archetype=PlanArchetype.STANDARD_REBOOK,
            title="Rebook affected cargo onto later sailings",
            actions=[_rebook(group, targets) for group in pharma + manufacturing + dry],
            assumptions=assumptions + ["Later synthetic sailings accept the rebooked volume."],
        )
        cap = _constraint_cap(briefing.confirmed_constraint)
        hybrid_actions: list[PlanAction] = []
        for group in pharma:
            if cap is not None and group.container_count > cap:
                hybrid_actions.append(_rush(group, cap))
                hybrid_actions.append(_rebook(group, targets, group.container_count - cap))
            else:
                hybrid_actions.append(_rush(group))
        hybrid_actions.extend(_rush(group) for group in manufacturing)
        hybrid_actions.extend(_rebook(group, targets) for group in dry)
        hybrid = RecoveryPlan(
            archetype=PlanArchetype.OPTIMIZED_HYBRID,
            title="Rush critical cargo and rebook the rest",
            actions=hybrid_actions,
            assumptions=assumptions,
        )
        return [aggressive, rebook, hybrid]

    def revise_plan(
        self, plan: RecoveryPlan, rejection_reasons: list[str], briefing: PlanBriefing
    ) -> RecoveryPlan:
        cap = _constraint_cap(" ".join(rejection_reasons))
        if cap is None:
            cap = _constraint_cap(briefing.confirmed_constraint)
        targets = {
            sailing.replaces_onward_vessel: sailing.vessel_name
            for sailing in briefing.sailings.sailings
        }
        revised: list[PlanAction] = []
        budget = cap
        for action in plan.actions:
            rushes_reefers = (
                action.action == RecoveryActionType.RUSH
                and action.cargo_type == CargoType.PHARMA_REEFER
            )
            if not rushes_reefers:
                revised.append(action)
                continue
            group = _Group(action.onward_vessel, action.cargo_type, action.container_count)
            if budget is None:
                revised.append(_rebook(group, targets))
                continue
            keep = min(action.container_count, budget)
            budget -= keep
            if keep:
                revised.append(_rush(group, keep))
            overflow = action.container_count - keep
            if overflow:
                revised.append(_rebook(group, targets, overflow))
        return plan.model_copy(
            update={
                "actions": revised,
                "assumptions": plan.assumptions
                + [f"Revised after deterministic rejection: {rejection_reasons[0]}"],
            }
        )
