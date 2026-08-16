import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import TypeAdapter

from cascade.contracts import ScenarioState, TraceEvent

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"
T = TypeVar("T")


def _read_json(name: str) -> Any:
    with (FIXTURES / name).open(encoding="utf-8") as fixture:
        return json.load(fixture)


def load_golden_scenario() -> ScenarioState:
    return ScenarioState.model_validate(_read_json("golden_scenario.json"))


def load_fake_events() -> list[TraceEvent]:
    return TypeAdapter(list[TraceEvent]).validate_python(_read_json("fake_agent_events.json"))


def load_replay_events() -> list[TraceEvent]:
    return TypeAdapter(list[TraceEvent]).validate_python(_read_json("replay_events.json"))


def load_fake_tool_responses() -> dict[str, Any]:
    return dict(_read_json("fake_tool_responses.json"))
