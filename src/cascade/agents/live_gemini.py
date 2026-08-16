"""Live gemini-3.5-flash brain for LIVE_GEMINI mode.

The stage machine stays deterministic: this brain only produces schema-validated
wording and plan allocations. Higher thinking budgets go to the Coordinator and
Recovery agents, lower budgets to the specialists. Guarded by GEMINI_API_KEY;
creation refuses cleanly without a key so the API never silently impersonates a
live run. Exchanges can be recorded to fixtures/recorded_gemini/ in the format
documented there (verbatim responses, hashed prompts, no secrets).
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from cascade.agents.base import (
    AgentSummary,
    PlanBriefing,
    PlanProposalSet,
    PlanRevision,
    WorkflowStep,
    load_prompt,
)
from cascade.contracts import AgentName, RecoveryPlan

MODEL = "gemini-3.5-flash"
HIGH_THINKING_BUDGET = 2048
LOW_THINKING_BUDGET = 256

_PROMPT_NAMES: dict[AgentName, str] = {
    AgentName.COORDINATOR: "coordinator",
    AgentName.IMPACT: "impact",
    AgentName.YARD: "yard",
    AgentName.RECOVERY: "recovery",
    AgentName.EXECUTION: "execution",
}

THINKING_BUDGETS: dict[AgentName, int] = {
    AgentName.COORDINATOR: HIGH_THINKING_BUDGET,
    AgentName.RECOVERY: HIGH_THINKING_BUDGET,
    AgentName.IMPACT: LOW_THINKING_BUDGET,
    AgentName.YARD: LOW_THINKING_BUDGET,
    AgentName.EXECUTION: LOW_THINKING_BUDGET,
}

STEP_AGENTS: dict[WorkflowStep, AgentName] = {
    WorkflowStep.RUN_STARTED: AgentName.COORDINATOR,
    WorkflowStep.IMPACT_ASSESSMENT: AgentName.IMPACT,
    WorkflowStep.YARD_ASSESSMENT: AgentName.YARD,
    WorkflowStep.RECONCILE: AgentName.COORDINATOR,
    WorkflowStep.HUMAN_CONSTRAINT: AgentName.COORDINATOR,
    WorkflowStep.SAILING_LOOKUP: AgentName.RECOVERY,
    WorkflowStep.PLAN_PROPOSAL: AgentName.RECOVERY,
    WorkflowStep.PLAN_COMPARISON: AgentName.RECOVERY,
    WorkflowStep.APPROVAL_REQUEST: AgentName.COORDINATOR,
    WorkflowStep.EXECUTION: AgentName.EXECUTION,
    WorkflowStep.RUN_COMPLETED: AgentName.COORDINATOR,
}

RECORDINGS_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "recorded_gemini"

ModelT = TypeVar("ModelT", bound=BaseModel)


class MissingGeminiKeyError(RuntimeError):
    """Raised when LIVE_GEMINI is requested without a GEMINI_API_KEY."""


class GeminiRecorder:
    """Records live exchanges in the fixtures/recorded_gemini README format."""

    def __init__(self, recording_id: str) -> None:
        self.recording_id = recording_id
        self.exchanges: list[dict[str, Any]] = []
        self._path = RECORDINGS_DIR / f"{recording_id}.json"

    def record(
        self,
        agent: AgentName,
        system_instruction: str,
        contents_summary: str,
        response_text: str,
    ) -> None:
        self.exchanges.append(
            {
                "sequence": len(self.exchanges) + 1,
                "agent": agent.value,
                "request": {
                    "system_instruction_sha256": hashlib.sha256(
                        system_instruction.encode("utf-8")
                    ).hexdigest(),
                    "contents_summary": contents_summary[:200],
                    "tools_offered": [],
                },
                "response": {
                    "text": response_text,
                    "function_calls": [],
                    "finish_reason": "STOP",
                },
            }
        )
        self._flush()

    def _flush(self) -> None:
        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "recording_id": self.recording_id,
            "captured_at": datetime.now(UTC).isoformat(),
            "model": MODEL,
            "notes": "Automated capture of a live golden run; review before committing.",
            "exchanges": self.exchanges,
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class GeminiBrain:
    """Schema-validated live wording and plan allocations via gemini-3.5-flash."""

    def __init__(self, api_key: str, recorder: GeminiRecorder | None = None) -> None:
        if not api_key:
            raise MissingGeminiKeyError(
                "LIVE_GEMINI requires a GEMINI_API_KEY; refuse rather than impersonate."
            )
        self._api_key = api_key
        self._recorder = recorder
        self._client: Any = None

    @classmethod
    def create(cls) -> "GeminiBrain":
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise MissingGeminiKeyError(
                "GEMINI_API_KEY is not set. The live Gemini path is unavailable; "
                "explicitly choose DEMO_REPLAY instead."
            )
        recorder = None
        if os.environ.get("CASCADE_RECORD_GEMINI"):
            stamp = datetime.now(UTC).strftime("%Y%m%d")
            recorder = GeminiRecorder(f"golden__full-workflow__{stamp}")
        return cls(api_key=api_key, recorder=recorder)

    # -- AgentBrain interface -------------------------------------------------

    def summarize(self, step: WorkflowStep, facts: dict[str, Any]) -> AgentSummary:
        agent = STEP_AGENTS[step]
        message = (
            f"Workflow step: {step.value}. Deterministic facts (the only figures you may "
            f"quote): {json.dumps(facts, default=str)}. Produce the decision summary."
        )
        return self._generate(agent, message, AgentSummary)

    def propose_plans(self, briefing: PlanBriefing) -> list[RecoveryPlan]:
        message = (
            "Propose exactly three recovery plans (AGGRESSIVE_RUSH, STANDARD_REBOOK, "
            "OPTIMIZED_HYBRID) for these deterministic facts.\n"
            f"Connection groups: {briefing.analysis.model_dump_json(include={'groups'})}\n"
            f"Alternative sailings: {briefing.sailings.model_dump_json()}\n"
            f"Confirmed human constraint: {briefing.confirmed_constraint or 'none'}\n"
            f"Priority emphasis: {briefing.priority_emphasis}"
        )
        return self._generate(AgentName.RECOVERY, message, PlanProposalSet).plans

    def revise_plan(
        self, plan: RecoveryPlan, rejection_reasons: list[str], briefing: PlanBriefing
    ) -> RecoveryPlan:
        message = (
            "Deterministic validation rejected this plan. Revise it so every rejection "
            "reason is resolved while keeping the archetype and covering the same cargo.\n"
            f"Plan: {plan.model_dump_json()}\n"
            f"Rejection reasons: {json.dumps(rejection_reasons)}\n"
            f"Alternative sailings: {briefing.sailings.model_dump_json()}\n"
            f"Confirmed human constraint: {briefing.confirmed_constraint or 'none'}"
        )
        return self._generate(AgentName.RECOVERY, message, PlanRevision).plan

    # -- plumbing ---------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def _generate(self, agent: AgentName, message: str, schema: type[ModelT]) -> ModelT:
        from google.genai import types

        system_instruction = load_prompt(_PROMPT_NAMES[agent])
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGETS[agent]),
        )
        response = self._get_client().models.generate_content(
            model=MODEL, contents=message, config=config
        )
        text = response.text or ""
        if self._recorder is not None:
            self._recorder.record(agent, system_instruction, message, text)
        return schema.model_validate_json(text)
