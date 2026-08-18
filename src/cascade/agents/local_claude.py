"""Local Claude headless brain for LIVE_CLAUDE mode.

Runs the same brain seam as GeminiBrain through the locally installed Claude
Code CLI in headless mode (``claude -p``), so live agent wording and plan
allocations work without spending the 20-per-day Gemini free-tier quota. The
stage machine stays deterministic; this brain only produces schema-validated
wording and plan allocations, with the same one-retry policy as the Gemini
path. Creation refuses cleanly when the ``claude`` CLI is not on PATH so the
API never silently impersonates a live run. Only synthetic scenario data is
ever sent (same rule as the Gemini path).

Calls are pinned to Sonnet 5 at low effort (user decision, docs/notes.md);
CASCADE_CLAUDE_MODEL / CASCADE_CLAUDE_EFFORT override. Every call is captured
as a ModelExchange (prompt, raw response, model, effort, duration) which the
stage machine drains into the next trace event and the per-run log file.

Decision record: docs/notes.md ("Local Claude fallback for live agent calls").
"""

import json
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from cascade.agents.base import (
    FLEET_PROMPT_NAME,
    AgentSummary,
    PlanBriefing,
    PlanProposalSet,
    PlanRevision,
    WorkflowStep,
    fleet_strategy_is_well_formed,
    fleet_strategy_message,
    load_prompt,
    proposal_message,
    revision_message,
    summary_message,
)
from cascade.agents.live_gemini import PROMPT_NAMES, STEP_AGENTS
from cascade.agents.scripted import ScriptedFleetBrain
from cascade.contracts import (
    AgentName,
    DecisionSource,
    FleetPolicyView,
    FleetStrategy,
    ModelExchange,
    RecoveryPlan,
)

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_EFFORT = "low"
MODEL_ENV = "CASCADE_CLAUDE_MODEL"
EFFORT_ENV = "CASCADE_CLAUDE_EFFORT"
TIMEOUT_SECONDS = 300.0

ModelT = TypeVar("ModelT", bound=BaseModel)


class MissingClaudeCliError(RuntimeError):
    """Raised when LIVE_CLAUDE is requested without the claude CLI on PATH."""


def claude_cli_path() -> str | None:
    """Absolute path of the Claude Code CLI, or None when not installed."""
    return shutil.which("claude")


def cli_model() -> str:
    return os.environ.get(MODEL_ENV) or DEFAULT_MODEL


def cli_effort() -> str:
    return os.environ.get(EFFORT_ENV) or DEFAULT_EFFORT


def _run_cli(prompt: str) -> str:
    path = claude_cli_path()
    if path is None:
        raise MissingClaudeCliError(
            "The 'claude' CLI is not on PATH. The LIVE_CLAUDE path is unavailable; "
            "explicitly choose LIVE_STUB or DEMO_REPLAY instead."
        )
    command = [
        path,
        "-p",
        "--output-format",
        "json",
        "--model",
        cli_model(),
        "--effort",
        cli_effort(),
    ]
    completed = subprocess.run(
        command,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"claude -p exited with {completed.returncode}: {completed.stderr.strip()[:500]}"
        )
    # --output-format json wraps the reply: {"result": "...", ...}. Fall back
    # to raw stdout if the wrapper shape ever changes.
    try:
        payload = json.loads(completed.stdout)
        result = payload.get("result")
        if isinstance(result, str):
            return result
    except ValueError:
        pass
    return completed.stdout


def _extract_json(text: str) -> str:
    """Slice the first top-level JSON object out of possibly chatty output."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"No JSON object found in CLI output: {text.strip()[:200]!r}")
    return text[start : end + 1]


class ClaudeBrain:
    """Schema-validated live wording and plan allocations via ``claude -p``."""

    def __init__(self, runner: Callable[[str], str] | None = None) -> None:
        self._runner = runner if runner is not None else _run_cli
        self.exchanges: list[ModelExchange] = []
        # Act 2 only: the deterministic brain this adapter falls back to, and
        # the source label of the most recent fleet strategy epoch.
        self._fleet_fallback = ScriptedFleetBrain()
        self.last_decision_source: DecisionSource = DecisionSource.SCRIPTED

    @classmethod
    def create(cls) -> "ClaudeBrain":
        if claude_cli_path() is None:
            raise MissingClaudeCliError(
                "The 'claude' CLI is not on PATH. The LIVE_CLAUDE path is unavailable; "
                "explicitly choose LIVE_STUB or DEMO_REPLAY instead."
            )
        return cls()

    # -- AgentBrain interface -------------------------------------------------

    def summarize(self, step: WorkflowStep, facts: dict[str, object]) -> AgentSummary:
        return self._generate(STEP_AGENTS[step], summary_message(step, facts), AgentSummary)

    def propose_plans(self, briefing: PlanBriefing) -> list[RecoveryPlan]:
        message = proposal_message(briefing)
        return self._generate(AgentName.RECOVERY, message, PlanProposalSet).plans

    def revise_plan(
        self, plan: RecoveryPlan, rejection_reasons: list[str], briefing: PlanBriefing
    ) -> RecoveryPlan:
        message = revision_message(plan, rejection_reasons, briefing)
        return self._generate(AgentName.RECOVERY, message, PlanRevision).plan

    # -- FleetBrain interface (Act 2) ------------------------------------------

    def assess_week(self, view: FleetPolicyView) -> FleetStrategy:
        """One fleet strategy epoch, with a visible scripted fallback.

        Same contract as the Gemini adapter: any failure - CLI error, timeout,
        unparseable output, schema violation, or a decision missing the payload
        its menu entry requires - hands the epoch to ``ScriptedFleetBrain`` and
        sets ``last_decision_source`` to ``SCRIPTED_FALLBACK``.
        """
        try:
            strategy = self._generate(
                AgentName.COORDINATOR,
                fleet_strategy_message(view),
                FleetStrategy,
                prompt_name=FLEET_PROMPT_NAME,
            )
            if not fleet_strategy_is_well_formed(strategy):
                raise ValueError("fleet strategy contains a decision without its required payload")
        except Exception:
            self.last_decision_source = DecisionSource.SCRIPTED_FALLBACK
            return self._fleet_fallback.assess_week(view)
        self.last_decision_source = DecisionSource.MODEL
        return strategy

    # -- plumbing ---------------------------------------------------------------

    def _call(self, agent: AgentName, prompt: str) -> str:
        started = time.monotonic()
        response = self._runner(prompt)
        self.exchanges.append(
            ModelExchange(
                provider="claude-cli",
                model=cli_model(),
                effort=cli_effort(),
                agent=agent,
                prompt=prompt,
                response=response,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )
        return response

    def _generate(
        self,
        agent: AgentName,
        message: str,
        schema: type[ModelT],
        *,
        prompt_name: str | None = None,
    ) -> ModelT:
        # The CLI has no JSON response mode, so the target schema is stated
        # explicitly and the reply is sliced to its JSON object before the
        # same local pydantic validation the Gemini path uses, with one retry
        # that feeds the validation error back.
        #
        # `prompt_name` overrides the per-agent Act 1 prompt; it exists so the
        # Act 2 fleet strategy epoch can reuse this whole call path with its own
        # versioned prompt. Omitted, behaviour is exactly as before.
        system_instruction = load_prompt(prompt_name or PROMPT_NAMES[agent])
        schema_json = json.dumps(schema.model_json_schema(), default=str)
        prompt = (
            f"{system_instruction}\n\n{message}\n\n"
            "Respond with exactly one JSON object matching this JSON Schema. "
            f"No markdown fences, no commentary:\n{schema_json}"
        )
        last_error: Exception | None = None
        contents = prompt
        for _ in range(2):
            text = self._call(agent, contents)
            try:
                return schema.model_validate_json(_extract_json(text))
            except ValueError as error:
                last_error = error
                contents = (
                    f"{prompt}\n\nYour previous response failed schema validation with: "
                    f"{error}\nRespond again with only the corrected JSON object."
                )
        raise RuntimeError(f"Claude CLI output failed schema validation twice: {last_error}")
