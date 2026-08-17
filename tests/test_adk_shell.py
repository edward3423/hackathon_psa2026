import pytest

from cascade.agents import build_agent_shell
from cascade.agents.base import PROMPTS_DIR, AgentSummary, load_prompt
from cascade.agents.live_gemini import (
    CAPTURE_CALL_BUDGET,
    HIGH_THINKING_BUDGET,
    LIVE_CAPTURE_STEPS,
    LOW_THINKING_BUDGET,
    STEP_AGENTS,
    THINKING_BUDGETS,
    CaptureProfileBrain,
    GeminiBrain,
    GeminiCallBudgetError,
    MissingGeminiKeyError,
    build_live_brain,
)
from cascade.agents.scripted import ScriptedBrain
from cascade.contracts import AgentName

PROMPT_NAMES = ["coordinator", "impact", "yard", "recovery", "execution"]


def test_adk_shell_contains_five_named_agents() -> None:
    shell = build_agent_shell()

    assert shell.coordinator.name == "coordinator_agent"
    assert shell.impact.name == "impact_agent"
    assert shell.yard.name == "yard_agent"
    assert shell.recovery.name == "recovery_agent"
    assert shell.execution.name == "execution_agent"
    assert shell.parallel_assessment.graph is not None
    graph_agents = {node.name for node in shell.parallel_assessment.graph.nodes}
    assert {"impact_agent", "yard_agent"}.issubset(graph_agents)


def test_prompt_files_are_versioned_and_wired_into_the_shell() -> None:
    for name in PROMPT_NAMES:
        prompt = load_prompt(name)
        assert prompt.startswith("version:"), name
        assert "chain-of-thought" in prompt, name
        assert (PROMPTS_DIR / f"{name}.md").exists()
    shell = build_agent_shell()
    assert shell.impact.instruction == load_prompt("impact")
    assert shell.coordinator.instruction == load_prompt("coordinator")


def test_prompts_forbid_the_prd_agent_misbehaviors() -> None:
    for name in PROMPT_NAMES:
        prompt = load_prompt(name).lower()
        assert "never" in prompt, name
        assert "allowlisted tool" in prompt or "allowlisted" in prompt, name


def test_gemini_brain_refuses_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(MissingGeminiKeyError):
        GeminiBrain.create()
    with pytest.raises(MissingGeminiKeyError):
        GeminiBrain(api_key="")


def test_gemini_brain_constructs_with_key_and_never_calls_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    brain = GeminiBrain.create()
    assert brain._client is None  # lazily created; construction is offline


def test_thinking_budgets_follow_prd_reasoning_levels() -> None:
    assert THINKING_BUDGETS[AgentName.COORDINATOR] == HIGH_THINKING_BUDGET
    assert THINKING_BUDGETS[AgentName.RECOVERY] == HIGH_THINKING_BUDGET
    for agent in (AgentName.IMPACT, AgentName.YARD, AgentName.EXECUTION):
        assert THINKING_BUDGETS[agent] == LOW_THINKING_BUDGET
    # Every narration step maps to a named agent with a prompt file.
    for agent in STEP_AGENTS.values():
        assert agent in THINKING_BUDGETS


def test_capture_profile_routes_only_decision_steps_to_the_live_brain() -> None:
    from cascade.agents.base import WorkflowStep

    class RecordingBrain:
        def __init__(self, label: str) -> None:
            self.label = label
            self.summarized: list[WorkflowStep] = []

        def summarize(self, step: WorkflowStep, facts: dict[str, object]) -> AgentSummary:
            self.summarized.append(step)
            return AgentSummary(decision_summary=self.label)

    live = RecordingBrain("live")
    scripted = RecordingBrain("scripted")
    brain = CaptureProfileBrain(live, scripted=scripted)  # type: ignore[arg-type]

    for step in WorkflowStep:
        brain.summarize(step, {"delay_hours": 18, "vessel": "MV ATLAS STAR"})
    assert set(scripted.summarized) == set(WorkflowStep) - set(LIVE_CAPTURE_STEPS)
    assert set(live.summarized) == set(LIVE_CAPTURE_STEPS)
    # Routine narration must not spend quota; decision steps must be live.
    assert WorkflowStep.RUN_STARTED not in live.summarized
    assert WorkflowStep.RECONCILE in live.summarized


def test_gemini_call_budget_stops_before_spending_another_request() -> None:
    brain = GeminiBrain(api_key="test-key-not-real", call_budget=0)
    with pytest.raises(GeminiCallBudgetError):
        brain._generate(AgentName.COORDINATOR, "message", AgentSummary)
    assert brain.api_calls == 0


def test_build_live_brain_uses_the_capture_profile_only_when_recording(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.delenv("CASCADE_RECORD_GEMINI", raising=False)
    assert isinstance(build_live_brain(), GeminiBrain)

    monkeypatch.setenv("CASCADE_RECORD_GEMINI", "1")
    brain = build_live_brain()
    assert isinstance(brain, CaptureProfileBrain)
    assert brain.live._recorder is not None
    assert brain.live._call_budget == CAPTURE_CALL_BUDGET
    assert CAPTURE_CALL_BUDGET < 20  # the free-tier daily request limit


def test_scripted_brain_summaries_are_schema_valid() -> None:
    brain = ScriptedBrain()
    from cascade.agents.base import WorkflowStep

    summary = brain.summarize(
        WorkflowStep.RUN_STARTED,
        {"delay_hours": 18, "vessel": "MV ATLAS STAR", "priority": "BALANCED"},
    )
    assert isinstance(summary, AgentSummary)
    assert "18" in summary.decision_summary
