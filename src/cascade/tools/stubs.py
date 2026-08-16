from typing import Any

from cascade.fixtures import load_fake_tool_responses


def _response(tool_name: str) -> dict[str, Any]:
    """Return an isolated copy of a recorded synthetic tool response."""
    return dict(load_fake_tool_responses()[tool_name])


def analyse_connections(vessel_name: str) -> dict[str, Any]:
    """Classify synthetic container connections for a delayed inbound vessel."""
    return {"vessel_name": vessel_name, **_response("analyse_connections")}


def simulate_yard(planning_horizon_hours: int = 72) -> dict[str, Any]:
    """Return a recorded synthetic yard and reefer capacity forecast."""
    return {"planning_horizon_hours": planning_horizon_hours, **_response("simulate_yard")}


def find_alternative_sailings(force_timeout: bool = True) -> dict[str, Any]:
    """Return cached synthetic sailings or a controlled timeout result."""
    response = _response("find_alternative_sailings")
    if force_timeout:
        return {"live_lookup": "TIMEOUT", **response}
    return {"live_lookup": "MOCK_SUCCESS", **response}


def compare_plans() -> dict[str, Any]:
    """Return recorded results for three synthetic recovery-plan archetypes."""
    return _response("compare_plans")


def retrieve_context(query: str) -> dict[str, Any]:
    """Return short reviewed facts with source links from the local evidence pack."""
    from cascade.tools.evidence import retrieve_context as _retrieve

    return _retrieve(query)


def validate_actions(plan_id: str) -> dict[str, Any]:
    """Return a placeholder deterministic validation result for a synthetic plan."""
    return {"plan_id": plan_id, "valid": True, "status": "FOUNDATION_STUB"}


def dispatch_plan(plan_id: str) -> dict[str, Any]:
    """Create a mocked receipt without contacting an operational system."""
    return {
        "plan_id": plan_id,
        "status": "MOCKED",
        "receipt": f"synthetic-receipt-{plan_id.lower()}",
    }
