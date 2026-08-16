import pytest

from cascade.agents import build_agent_shell
from cascade.agents.base import PROMPTS_DIR, AgentSummary, load_prompt
from cascade.agents.live_gemini import (
    HIGH_THINKING_BUDGET,
    LOW_THINKING_BUDGET,
    STEP_AGENTS,
    THINKING_BUDGETS,
    GeminiBrain,
    MissingGeminiKeyError,
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


def test_scripted_brain_summaries_are_schema_valid() -> None:
    brain = ScriptedBrain()
    from cascade.agents.base import WorkflowStep

    summary = brain.summarize(
        WorkflowStep.RUN_STARTED,
        {"delay_hours": 18, "vessel": "MV ATLAS STAR", "priority": "BALANCED"},
    )
    assert isinstance(summary, AgentSummary)
    assert "18" in summary.decision_summary
