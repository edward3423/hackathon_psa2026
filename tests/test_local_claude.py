import json

import pytest
from fastapi.testclient import TestClient

from cascade.agents.base import AgentSummary, WorkflowStep
from cascade.agents.local_claude import (
    ClaudeBrain,
    MissingClaudeCliError,
    _extract_json,
)


def test_extract_json_slices_fences_and_commentary() -> None:
    wrapped = 'Here you go:\n```json\n{"decision_summary": "ok", "assumptions": []}\n```\n'
    assert json.loads(_extract_json(wrapped)) == {"decision_summary": "ok", "assumptions": []}
    with pytest.raises(ValueError):
        _extract_json("no json here")


def test_claude_brain_validates_and_retries_once() -> None:
    responses = iter(
        [
            "not even json",
            '{"decision_summary": "Recovered on retry.", "assumptions": []}',
        ]
    )
    prompts: list[str] = []

    def runner(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    brain = ClaudeBrain(runner=runner)
    summary = brain.summarize(WorkflowStep.RECONCILE, {"detail": "synthetic"})
    assert isinstance(summary, AgentSummary)
    assert summary.decision_summary == "Recovered on retry."
    assert len(prompts) == 2
    assert "failed schema validation" in prompts[1]
    # The versioned prompt and the deterministic facts both reach the CLI.
    assert "Workflow step: reconcile" in prompts[0]
    assert "JSON Schema" in prompts[0]


def test_claude_brain_fails_after_two_invalid_responses() -> None:
    brain = ClaudeBrain(runner=lambda _prompt: '{"wrong_field": true}')
    with pytest.raises(RuntimeError, match="failed schema validation twice"):
        brain.summarize(WorkflowStep.RECONCILE, {})


def test_create_refuses_without_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cascade.agents.local_claude.shutil.which", lambda _name: None)
    with pytest.raises(MissingClaudeCliError):
        ClaudeBrain.create()


def test_api_guards_live_claude_when_cli_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from cascade import api

    monkeypatch.setattr("cascade.agents.local_claude.shutil.which", lambda _name: None)
    client = TestClient(api.app)
    response = client.post("/api/runs?mode=LIVE_CLAUDE", json={})
    assert response.status_code == 409
    assert "claude" in response.json()["detail"].lower()
