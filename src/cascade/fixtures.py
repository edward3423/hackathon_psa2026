import hashlib
import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import TypeAdapter

from cascade.contracts import (
    ArrivalStreamFixture,
    FixtureManifest,
    GroundTruthFixture,
    ScenarioState,
    TraceEvent,
    WorldFixture,
)

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


def load_golden_world() -> WorldFixture:
    return WorldFixture.model_validate(_read_json("golden_world.json"))


def load_evidence_pack() -> dict[str, Any]:
    return dict(_read_json("evidence_pack.json"))


# --- Act 2 crisis benchmark fixtures ---------------------------------------
#
# Runtime code reads only these validated fixtures. It never touches the
# network or the raw PortWatch CSV under data/raw; scripts/fetch_portwatch.py
# is the only thing that does, and it is never invoked by tests or the API.

CRISIS_ARRIVALS_FILE = "crisis_arrivals.json"
CRISIS_GROUND_TRUTH_FILE = "crisis_ground_truth.json"
CRISIS_MANIFEST_FILE = "crisis_manifest.json"


def load_crisis_arrivals() -> ArrivalStreamFixture:
    return ArrivalStreamFixture.model_validate(_read_json(CRISIS_ARRIVALS_FILE))


def load_crisis_ground_truth() -> GroundTruthFixture:
    return GroundTruthFixture.model_validate(_read_json(CRISIS_GROUND_TRUTH_FILE))


def load_crisis_manifest() -> FixtureManifest:
    return FixtureManifest.model_validate(_read_json(CRISIS_MANIFEST_FILE))


def sha256_of(name: str) -> str:
    """Hash a fixture exactly as written on disk, so the manifest is checkable."""
    return hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
