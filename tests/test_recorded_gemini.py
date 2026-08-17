"""Deterministic agent tests over recorded live Gemini responses.

Replays every committed recording in fixtures/recorded_gemini/ without any
network access: each recorded response must validate against the same schema
the live brain enforces (AgentSummary, PlanProposalSet, PlanRevision), with a
failed attempt allowed only when the very next exchange is its retry and that
retry validates - exactly the one-retry policy in GeminiBrain._generate.
"""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from cascade.agents.base import AgentSummary, PlanProposalSet, PlanRevision
from cascade.agents.live_gemini import MODEL

RECORDINGS_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "recorded_gemini"
RECORDINGS = sorted(RECORDINGS_DIR.glob("*.json"))


def _expected_schema(contents_summary: str) -> type[BaseModel]:
    if contents_summary.startswith("Workflow step:"):
        return AgentSummary
    if contents_summary.startswith("Propose exactly three recovery plans"):
        return PlanProposalSet
    if contents_summary.startswith("Deterministic validation rejected"):
        return PlanRevision
    raise AssertionError(f"Unrecognized recorded request: {contents_summary[:80]}")


@pytest.mark.parametrize("path", RECORDINGS, ids=[p.stem for p in RECORDINGS])
def test_recording_metadata_is_complete(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["model"] == MODEL
    assert payload["recording_id"] == path.stem
    assert payload["scenario_controls"]["delay_hours"] == 18
    sequences = [exchange["sequence"] for exchange in payload["exchanges"]]
    assert sequences == list(range(1, len(sequences) + 1))
    for exchange in payload["exchanges"]:
        request = exchange["request"]
        # Prompts stay versioned in code; recordings hold only a hash.
        assert len(request["system_instruction_sha256"]) == 64
        assert len(request["contents_summary"]) <= 200


@pytest.mark.parametrize("path", RECORDINGS, ids=[p.stem for p in RECORDINGS])
def test_recorded_responses_replay_through_the_live_schemas(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    exchanges = payload["exchanges"]
    index = 0
    while index < len(exchanges):
        exchange = exchanges[index]
        schema = _expected_schema(exchange["request"]["contents_summary"])
        try:
            schema.model_validate_json(exchange["response"]["text"])
            index += 1
            continue
        except ValueError:
            pass
        # One retry is allowed: the next exchange must be the same agent and
        # schema, and its response must validate.
        retry = exchanges[index + 1] if index + 1 < len(exchanges) else None
        assert retry is not None, f"Exchange {exchange['sequence']} failed with no retry"
        assert retry["agent"] == exchange["agent"]
        assert _expected_schema(retry["request"]["contents_summary"]) is schema
        schema.model_validate_json(retry["response"]["text"])
        index += 2


def test_at_least_one_recording_is_committed() -> None:
    assert RECORDINGS, "fixtures/recorded_gemini/ must hold at least one reviewed recording"
