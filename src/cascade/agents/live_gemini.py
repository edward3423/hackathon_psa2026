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
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from cascade.agents.base import (
    AgentBrain,
    AgentSummary,
    PlanBriefing,
    PlanProposalSet,
    PlanRevision,
    WorkflowStep,
    load_prompt,
    proposal_message,
    revision_message,
    summary_message,
)
from cascade.agents.scripted import ScriptedBrain
from cascade.contracts import AgentName, ModelExchange, RecoveryPlan

MODEL = "gemini-3.5-flash"

# Free-tier gemini-3.5-flash allows only 20 requests per day, so a recording
# run is hard-capped below that: better to abort loudly than to burn the whole
# daily quota into 429s and leave a partial recording.
CAPTURE_CALL_BUDGET = 18

# Steps whose wording goes to the live model while recording. Everything else
# is routine narration that the scripted brain words identically well; keeping
# it local is what fits a full golden run inside the daily quota.
LIVE_CAPTURE_STEPS: frozenset[WorkflowStep] = frozenset(
    {
        WorkflowStep.RECONCILE,
        WorkflowStep.HUMAN_CONSTRAINT,
        WorkflowStep.PLAN_COMPARISON,
        WorkflowStep.APPROVAL_REQUEST,
    }
)
HIGH_THINKING_BUDGET = 2048
LOW_THINKING_BUDGET = 256

PROMPT_NAMES: dict[AgentName, str] = {
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


class GeminiCallBudgetError(RuntimeError):
    """Raised before an API request would exceed the configured call budget."""


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
            "notes": (
                "Automated capture-profile recording: decision-critical calls are live, "
                "routine narrations scripted (free-tier quota). Review before committing."
            ),
            "exchanges": self.exchanges,
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class GeminiBrain:
    """Schema-validated live wording and plan allocations via gemini-3.5-flash."""

    def __init__(
        self,
        api_key: str,
        recorder: GeminiRecorder | None = None,
        call_budget: int | None = None,
    ) -> None:
        if not api_key:
            raise MissingGeminiKeyError(
                "LIVE_GEMINI requires a GEMINI_API_KEY; refuse rather than impersonate."
            )
        self._api_key = api_key
        self._recorder = recorder
        self._call_budget = call_budget
        self.api_calls = 0
        self.exchanges: list[ModelExchange] = []
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
        call_budget = None
        if os.environ.get("CASCADE_RECORD_GEMINI"):
            stamp = datetime.now(UTC).strftime("%Y%m%d")
            recorder = GeminiRecorder(f"golden__capture-profile__{stamp}")
            call_budget = CAPTURE_CALL_BUDGET
        return cls(api_key=api_key, recorder=recorder, call_budget=call_budget)

    # -- AgentBrain interface -------------------------------------------------

    def summarize(self, step: WorkflowStep, facts: dict[str, Any]) -> AgentSummary:
        return self._generate(STEP_AGENTS[step], summary_message(step, facts), AgentSummary)

    def propose_plans(self, briefing: PlanBriefing) -> list[RecoveryPlan]:
        message = proposal_message(briefing)
        return self._generate(AgentName.RECOVERY, message, PlanProposalSet).plans

    def revise_plan(
        self, plan: RecoveryPlan, rejection_reasons: list[str], briefing: PlanBriefing
    ) -> RecoveryPlan:
        message = revision_message(plan, rejection_reasons, briefing)
        return self._generate(AgentName.RECOVERY, message, PlanRevision).plan

    # -- plumbing ---------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def _generate(self, agent: AgentName, message: str, schema: type[ModelT]) -> ModelT:
        # JSON mode plus local pydantic validation: the API's schema enforcement
        # rejects the strict (extra=forbid) contract schemas, so the schema is
        # stated in the versioned prompt and validated here, with one retry that
        # feeds the validation error back to the agent.
        from google.genai import types

        system_instruction = load_prompt(PROMPT_NAMES[agent])
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGETS[agent]),
        )
        client = self._get_client()
        last_error: Exception | None = None
        contents = message
        for _ in range(2):
            if self._call_budget is not None and self.api_calls >= self._call_budget:
                raise GeminiCallBudgetError(
                    f"Gemini call budget of {self._call_budget} reached; aborting "
                    "before another API request is spent."
                )
            self.api_calls += 1
            started = time.monotonic()
            response = client.models.generate_content(model=MODEL, contents=contents, config=config)
            text = response.text or ""
            self.exchanges.append(
                ModelExchange(
                    provider="gemini",
                    model=MODEL,
                    effort=f"thinking_budget={THINKING_BUDGETS[agent]}",
                    agent=agent,
                    prompt=contents,
                    response=text,
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
            )
            if self._recorder is not None:
                self._recorder.record(agent, system_instruction, contents, text)
            try:
                return schema.model_validate_json(text)
            except ValueError as error:
                last_error = error
                contents = (
                    f"{message}\n\nYour previous response failed schema validation with: "
                    f"{error}\nRespond again with only the corrected JSON object."
                )
        raise RuntimeError(f"Gemini output failed schema validation twice: {last_error}")


class CaptureProfileBrain:
    """Quota-saving hybrid brain used only while recording live exchanges.

    Decision-critical calls (dispute reconciliation, human constraint, plan
    proposal, revisions, comparison, approval request) go to the live model;
    routine step narrations use the scripted wording. A golden run then costs
    about 9 Gemini requests instead of 15-21, fitting the 20-per-day free tier
    with retry headroom.
    """

    def __init__(self, live: GeminiBrain, scripted: AgentBrain | None = None) -> None:
        self.live = live
        self.scripted: AgentBrain = scripted if scripted is not None else ScriptedBrain()

    @property
    def exchanges(self) -> list[ModelExchange]:
        return self.live.exchanges

    def summarize(self, step: WorkflowStep, facts: dict[str, Any]) -> AgentSummary:
        brain = self.live if step in LIVE_CAPTURE_STEPS else self.scripted
        return brain.summarize(step, facts)

    def propose_plans(self, briefing: PlanBriefing) -> list[RecoveryPlan]:
        return self.live.propose_plans(briefing)

    def revise_plan(
        self, plan: RecoveryPlan, rejection_reasons: list[str], briefing: PlanBriefing
    ) -> RecoveryPlan:
        return self.live.revise_plan(plan, rejection_reasons, briefing)


def build_live_brain() -> AgentBrain:
    """The LIVE_GEMINI brain: fully live, or the capture profile when recording."""
    brain = GeminiBrain.create()
    if os.environ.get("CASCADE_RECORD_GEMINI"):
        return CaptureProfileBrain(brain)
    return brain
