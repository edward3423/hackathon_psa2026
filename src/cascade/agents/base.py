"""Agent brain seam.

The stage machine computes every figure with deterministic tools; a brain only
provides wording (decision summaries, assumptions) and plan allocations within
the three fixed archetypes. ``ScriptedBrain`` keeps LIVE_STUB offline;
``GeminiBrain`` (agents/live_gemini.py) plugs real gemini-3.5-flash agents into
the same seam.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from cascade.contracts import (
    AlternativeSailingResult,
    ConnectionAnalysis,
    DailyKpi,
    FleetDecision,
    FleetDecisionType,
    FleetPolicyView,
    FleetStrategy,
    PlanningFacts,
    RecoveryPlan,
    ReserveBerthTranche,
)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class WorkflowStep(StrEnum):
    """Narration points in the coordinator-controlled stage sequence."""

    RUN_STARTED = "run_started"
    IMPACT_ASSESSMENT = "impact_assessment"
    YARD_ASSESSMENT = "yard_assessment"
    RECONCILE = "reconcile"
    HUMAN_CONSTRAINT = "human_constraint"
    SAILING_LOOKUP = "sailing_lookup"
    PLAN_PROPOSAL = "plan_proposal"
    PLAN_COMPARISON = "plan_comparison"
    APPROVAL_REQUEST = "approval_request"
    EXECUTION = "execution"
    RUN_COMPLETED = "run_completed"


class AgentSummary(BaseModel):
    """Schema-validated structured output for every agent narration."""

    model_config = ConfigDict(extra="forbid")

    decision_summary: str = Field(min_length=1, max_length=500)
    assumptions: list[str] = Field(default_factory=list, max_length=8)


class PlanProposalSet(BaseModel):
    """Schema-validated structured output for Recovery Agent plan proposals."""

    model_config = ConfigDict(extra="forbid")

    plans: list[RecoveryPlan] = Field(min_length=3, max_length=3)


class PlanRevision(BaseModel):
    """Schema-validated structured output for a single plan revision."""

    model_config = ConfigDict(extra="forbid")

    plan: RecoveryPlan


@dataclass(frozen=True)
class PlanBriefing:
    """Deterministic facts a brain may use when proposing plans."""

    analysis: ConnectionAnalysis
    sailings: AlternativeSailingResult
    confirmed_constraint: str | None
    priority_emphasis: str
    facts: PlanningFacts | None = None


class AgentBrain(Protocol):
    """Wording and plan-allocation seam around the deterministic stage machine."""

    def summarize(self, step: WorkflowStep, facts: dict[str, Any]) -> AgentSummary: ...

    def propose_plans(self, briefing: PlanBriefing) -> list[RecoveryPlan]: ...

    def revise_plan(
        self, plan: RecoveryPlan, rejection_reasons: list[str], briefing: PlanBriefing
    ) -> RecoveryPlan: ...


def summary_message(step: WorkflowStep, facts: dict[str, Any]) -> str:
    """The user message every live brain sends for a step narration."""
    return (
        f"Workflow step: {step.value}. Deterministic facts (the only figures you may "
        f"quote): {json.dumps(facts, default=str)}. Produce the decision summary."
    )


def _feasibility_section(facts: PlanningFacts | None) -> str:
    """Render the deterministic feasibility constraints a live brain must obey.

    Without this a model plans blind: rush counts map onto fixed yard blocks
    it cannot see, so plug rejections become unwinnable guessing (the failure
    mode of 2026-08-17, see docs/notes.md).
    """
    if facts is None:
        return ""
    order_lines = [
        f"  {group}: "
        + ", ".join(f"{slot.yard_block}{'*' if slot.requires_power else ''}" for slot in slots)
        for group, slots in facts.rush_order_by_group.items()
    ]
    return (
        "\nDeterministic feasibility constraints (a plan violating any of these "
        "is rejected):\n"
        "- Total rushed containers across all actions must not exceed the crane "
        f"surge allowance of {facts.crane_surge_allowance}.\n"
        "- Rushing K containers from a group rushes exactly its first K slots in "
        "the fixed order below. Every slot marked * consumes one free reefer plug "
        "in its yard block; per block, plugs consumed must not exceed the free "
        "plugs listed.\n"
        f"- Free reefer plugs by block: {json.dumps(facts.free_plugs_by_block)}\n"
        "- Rush order by group (yard block per slot, * = consumes a plug):\n"
        + "\n".join(order_lines)
        + "\n- Containers not rushed must be rebooked onto a sailing with enough "
        "remaining capacity, or the group stays partly unresolved.\n"
    )


def proposal_message(briefing: PlanBriefing) -> str:
    """The user message every live brain sends to propose the three plans."""
    return (
        "Propose exactly three recovery plans (AGGRESSIVE_RUSH, STANDARD_REBOOK, "
        "OPTIMIZED_HYBRID) for these deterministic facts.\n"
        f"Connection groups: {briefing.analysis.model_dump_json(include={'groups'})}\n"
        f"Alternative sailings: {briefing.sailings.model_dump_json()}\n"
        f"Confirmed human constraint: {briefing.confirmed_constraint or 'none'}\n"
        f"Priority emphasis: {briefing.priority_emphasis}"
        f"{_feasibility_section(briefing.facts)}"
    )


def revision_message(
    plan: RecoveryPlan, rejection_reasons: list[str], briefing: PlanBriefing
) -> str:
    """The user message every live brain sends to revise a rejected plan."""
    return (
        "Deterministic validation rejected this plan. Revise it so every rejection "
        "reason is resolved while keeping the archetype and covering the same cargo.\n"
        f"Plan: {plan.model_dump_json()}\n"
        f"Rejection reasons: {json.dumps(rejection_reasons)}\n"
        f"Alternative sailings: {briefing.sailings.model_dump_json()}\n"
        f"Confirmed human constraint: {briefing.confirmed_constraint or 'none'}"
        f"{_feasibility_section(briefing.facts)}"
    )


def load_prompt(name: str) -> str:
    """Load a versioned agent prompt file by agent short name."""
    path = PROMPTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    if not re.search(r"^version:\s*\d+", text, flags=re.MULTILINE):
        raise ValueError(f"Prompt {name} is missing a version header")
    return text


# ---------------------------------------------------------------------------
# Act 2: the fleet-scale brain seam.
#
# A second, independent seam beside ``AgentBrain``. It does not extend it and
# nothing above changes: the golden single-vessel workflow never calls a
# ``FleetBrain`` and the fleet benchmark never calls an ``AgentBrain``.
#
# The invariant is the same one Act 1 lives by, tightened: a fleet brain may
# only pick entries from an enumerated decision menu and write prose. Every
# numeric effect (berths, service hours, waits, dates) is computed by the
# engine, and every decision is independently re-validated by
# ``validate_fleet_decision`` before it can take effect.
# ---------------------------------------------------------------------------

FLEET_PROMPT_NAME = "fleet_strategy"

# How much recent history a brain is shown. A run is ~150 days; sending all of
# it would bury the signal and grow the prompt without bound. Two weeks covers
# the trailing rolling-wait trend and the last strategy epoch.
FLEET_HISTORY_DAYS = 14


class FleetBrain(Protocol):
    """Weekly strategy seam for the fleet benchmark.

    Implementations return a ``FleetStrategy``: at most four decisions from the
    enumerated menu, plus a summary. They never return a figure the engine then
    uses; the engine reads only ``type`` and the enum/bool/level payload.
    """

    def assess_week(self, view: FleetPolicyView) -> FleetStrategy: ...


def _kpi_line(kpi: DailyKpi) -> str:
    return (
        f"  {kpi.date} (day {kpi.day_index}): arrivals {kpi.arrivals}, "
        f"berthings {kpi.berthings}, queue {kpi.queue_length}, "
        f"rolling 3-day wait {kpi.rolling_wait_days:.2f} d, "
        f"berths {kpi.active_berths}, utilisation {kpi.utilisation:.2f}"
    )


def _reserve_line(tranche: ReserveBerthTranche) -> str:
    window = (
        "" if tranche.available_from is None else f", not available before {tranche.available_from}"
    )
    return (
        f"  {tranche.tranche_id}: {tranche.berths} berths, "
        f"{tranche.activation_lead_days}-day activation lead{window} ({tranche.label})"
    )


def fleet_strategy_message(view: FleetPolicyView) -> str:
    """The user message every live fleet brain sends for one strategy epoch.

    Renders only the deterministic facts in ``view`` - the sole figures a model
    may quote - and restates the menu with its exact bounds. Recent history is
    truncated to ``FLEET_HISTORY_DAYS`` so the prompt stays bounded over a
    150-day run.
    """
    recent = view.history[-FLEET_HISTORY_DAYS:]
    reserves = view.reserves_available
    pending = view.pending_activations
    tranche_ids = ", ".join(tranche.tranche_id for tranche in reserves) or "none"
    return (
        f"Strategy epoch for {view.today} (day index {view.day_index}).\n\n"
        "Deterministic facts - the only figures you may quote:\n"
        f"Recent daily KPIs (last {len(recent)} closed days, oldest first):\n"
        + ("\n".join(_kpi_line(kpi) for kpi in recent) or "  none yet")
        + "\n\nCurrent levers in force:\n"
        f"  active berths: {view.active_berths}\n"
        f"  queue discipline: {view.queue_discipline.value}\n"
        f"  fast connection mode: {'on' if view.fast_connection_mode else 'off'}\n"
        f"  workforce surge level: {view.workforce_surge_level}\n"
        "\nReserve berth tranches you may still activate:\n"
        + ("\n".join(_reserve_line(tranche) for tranche in reserves) or "  none remaining")
        + "\n\nActivations already scheduled (capacity not online yet):\n"
        + (
            "\n".join(
                f"  {item.tranche_id}: {item.berths} berths, effective {item.effective_date}"
                for item in pending
            )
            or "  none"
        )
        + "\n\nDecision menu - you may return at most four decisions, and nothing else:\n"
        f"  ACTIVATE_RESERVE_BERTHS: tranche_id must be one of [{tranche_ids}]. The berths "
        "arrive after that tranche's activation lead, never today.\n"
        "  SET_QUEUE_DISCIPLINE: discipline must be FCFS, CONNECTION_WEIGHTED or "
        "PRIORITY_DISCHARGE, and must differ from the discipline in force.\n"
        "  FAST_CONNECTION_MODE: enabled must be true or false, and must differ from the "
        "mode in force.\n"
        "  WORKFORCE_SURGE: surge_level must be an integer 0, 1 or 2, and must differ from "
        "the level in force.\n"
        "  HOLD: no payload. Return exactly this when no lever should move.\n"
        "\nYou may not state any figure that does not appear above. You choose which levers "
        "to pull; the engine computes every consequence and independently re-validates each "
        "decision, rejecting and logging anything outside these bounds."
    )


def fleet_strategy_is_well_formed(strategy: FleetStrategy) -> bool:
    """Whether every decision carries the payload its type requires.

    The schema alone cannot express "ACTIVATE_RESERVE_BERTHS needs a
    tranche_id", so a model can return a type-valid but empty decision. A live
    adapter treats that as a failed call and falls back rather than shipping a
    decision the engine is certain to reject.
    """
    required: dict[FleetDecisionType, Callable[[FleetDecision], bool]] = {
        FleetDecisionType.ACTIVATE_RESERVE_BERTHS: lambda d: bool(d.tranche_id),
        FleetDecisionType.SET_QUEUE_DISCIPLINE: lambda d: d.discipline is not None,
        FleetDecisionType.FAST_CONNECTION_MODE: lambda d: d.enabled is not None,
        FleetDecisionType.WORKFORCE_SURGE: lambda d: d.surge_level is not None,
        FleetDecisionType.HOLD: lambda d: True,
    }
    return all(required[decision.type](decision) for decision in strategy.decisions)
