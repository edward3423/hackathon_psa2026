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
_SURGE_PATTERN = re.compile(r"crane surge allowance\s+of\s+(\d+)", re.IGNORECASE)
_PLUG_PATTERN = re.compile(r"needs (\d+) reefer plugs but (?:has|only) (\d+)", re.IGNORECASE)

# Rush priority when the crane surge budget is scarce: protect pharmaceutical
# reefers first, then time-critical manufacturing, then general dry cargo.
_RUSH_PRIORITY: tuple[CargoType, ...] = (
    CargoType.PHARMA_REEFER,
    CargoType.TIME_CRITICAL_MANUFACTURING,
    CargoType.GENERAL_DRY,
)


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
        """Deterministically repair every rejection type the engine emits.

        The plan is rebuilt group by group from the briefing so that no
        affected group is left without an action:
        - the total rushed count is capped to the crane surge allowance,
          allocating rush slots to the highest-priority cargo first (except
          for AGGRESSIVE_RUSH, whose premise of on-demand handling capacity
          means it never scales its rush volume down and may stay infeasible);
        - rushed powered reefers are additionally capped to the available
          reefer plugs (or an explicit "rush at most N" constraint);
        - everything not rushed is rebooked onto alternative sailings serving
          the same onward vessel with per-sailing capacity tracking;
        - a group with no rush slots and no remaining rebooking capacity is
          explicitly held rather than dropped from the plan.
        """
        reasons_text = " ".join(rejection_reasons)

        ordered_keys: list[tuple[str, CargoType]] = []
        demand: dict[tuple[str, CargoType], int] = {}
        for cargo in _RUSH_PRIORITY:
            for group in _threatened(briefing, cargo):
                key = (group.onward_vessel, group.cargo_type)
                if key not in demand:
                    ordered_keys.append(key)
                    demand[key] = 0
                demand[key] += group.container_count

        currently_rushed: dict[tuple[str, CargoType], int] = {}
        for action in plan.actions:
            if action.action is RecoveryActionType.RUSH:
                key = (action.onward_vessel, action.cargo_type)
                currently_rushed[key] = currently_rushed.get(key, 0) + action.container_count
        desired = {key: min(currently_rushed.get(key, 0), demand[key]) for key in ordered_keys}

        surge = _SURGE_PATTERN.search(reasons_text)
        if surge is not None and plan.archetype is not PlanArchetype.AGGRESSIVE_RUSH:
            rush_budget = int(surge.group(1))
        else:
            # AGGRESSIVE_RUSH is premised on extra handling capacity being
            # available on demand (PRD 9.8); it repairs plug, sailing, and
            # coverage rejections but never concedes total rush volume. If the
            # crane surge allowance still rejects it, it ends infeasible and
            # the fixed-order comparison drops it (PRD 9.9) - by design the
            # hybrid, which does scale down to the allowance, is recommended.
            rush_budget = sum(desired.values())

        pharma_desired = sum(
            count for (_, cargo), count in desired.items() if cargo is CargoType.PHARMA_REEFER
        )
        reefer_budget = pharma_desired
        cap = _constraint_cap(reasons_text)
        if cap is None:
            cap = _constraint_cap(briefing.confirmed_constraint)
        if cap is not None:
            reefer_budget = min(reefer_budget, cap)
        plug_excesses = [
            int(required) - int(available)
            for required, available in _PLUG_PATTERN.findall(reasons_text)
        ]
        if plug_excesses:
            reefer_budget = min(reefer_budget, max(0, pharma_desired - sum(plug_excesses)))

        rush_allocation: dict[tuple[str, CargoType], int] = {}
        rush_remaining = rush_budget
        reefer_remaining = reefer_budget
        for key in ordered_keys:  # ordered by cargo priority, so dry drops first
            _, cargo = key
            want = desired[key]
            if cargo is CargoType.PHARMA_REEFER:
                want = min(want, reefer_remaining)
            take = min(want, rush_remaining)
            rush_allocation[key] = take
            rush_remaining -= take
            if cargo is CargoType.PHARMA_REEFER:
                reefer_remaining -= take

        sailings_for: dict[str, list[str]] = {}
        capacity_left: dict[str, int] = {}
        for sailing in briefing.sailings.sailings:
            sailings_for.setdefault(sailing.replaces_onward_vessel, []).append(sailing.vessel_name)
            capacity_left[sailing.vessel_name] = sailing.available_capacity

        revised: list[PlanAction] = []
        for key in ordered_keys:
            vessel, cargo = key
            rushed = rush_allocation[key]
            if rushed:
                revised.append(_rush(_Group(vessel, cargo, demand[key]), rushed))
            leftover = demand[key] - rushed
            rebooked = 0
            for sailing_name in sailings_for.get(vessel, []):
                if leftover <= 0:
                    break
                room = capacity_left[sailing_name]
                if room <= 0:
                    continue
                moved = min(room, leftover)
                capacity_left[sailing_name] -= moved
                revised.append(
                    PlanAction(
                        action=RecoveryActionType.REBOOK,
                        onward_vessel=vessel,
                        cargo_type=cargo,
                        container_count=moved,
                        target_sailing=sailing_name,
                        rationale=(f"Rebook {moved} containers from {vessel} to {sailing_name}."),
                    )
                )
                leftover -= moved
                rebooked += moved
            if rushed == 0 and rebooked == 0:
                revised.append(
                    PlanAction(
                        action=RecoveryActionType.HOLD,
                        onward_vessel=vessel,
                        cargo_type=cargo,
                        container_count=leftover,
                        target_sailing=None,
                        rationale=(
                            f"Hold {leftover} containers for {vessel}: no rush or "
                            "rebooking capacity remains."
                        ),
                    )
                )
        return plan.model_copy(
            update={
                "actions": revised,
                "assumptions": plan.assumptions
                + [f"Revised after deterministic rejection: {rejection_reasons[0]}"],
            }
        )
