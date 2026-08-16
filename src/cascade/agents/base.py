"""Agent brain seam.

The stage machine computes every figure with deterministic tools; a brain only
provides wording (decision summaries, assumptions) and plan allocations within
the three fixed archetypes. ``ScriptedBrain`` keeps LIVE_STUB offline;
``GeminiBrain`` (agents/live_gemini.py) plugs real gemini-3.5-flash agents into
the same seam.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from cascade.contracts import (
    AlternativeSailingResult,
    ConnectionAnalysis,
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


class AgentBrain(Protocol):
    """Wording and plan-allocation seam around the deterministic stage machine."""

    def summarize(self, step: WorkflowStep, facts: dict[str, Any]) -> AgentSummary: ...

    def propose_plans(self, briefing: PlanBriefing) -> list[RecoveryPlan]: ...

    def revise_plan(
        self, plan: RecoveryPlan, rejection_reasons: list[str], briefing: PlanBriefing
    ) -> RecoveryPlan: ...


def load_prompt(name: str) -> str:
    """Load a versioned agent prompt file by agent short name."""
    path = PROMPTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    if not re.search(r"^version:\s*\d+", text, flags=re.MULTILINE):
        raise ValueError(f"Prompt {name} is missing a version header")
    return text
