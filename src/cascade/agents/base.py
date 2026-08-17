"""Agent brain seam.

The stage machine computes every figure with deterministic tools; a brain only
provides wording (decision summaries, assumptions) and plan allocations within
the three fixed archetypes. ``ScriptedBrain`` keeps LIVE_STUB offline;
``GeminiBrain`` (agents/live_gemini.py) plugs real gemini-3.5-flash agents into
the same seam.
"""

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from cascade.contracts import (
    AlternativeSailingResult,
    ConnectionAnalysis,
    PlanningFacts,
    RecoveryPlan,
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
