import pytest
from pydantic import ValidationError

from cascade.contracts import AgentName, ScenarioControls
from cascade.fixtures import load_fake_events, load_golden_scenario, load_replay_events


def test_golden_fixture_has_expected_delay() -> None:
    scenario = load_golden_scenario()

    assert scenario.alert.delay_hours == 18
    assert scenario.alert.vessel_name == "MV ATLAS STAR"
    assert scenario.controls.delay_hours == 18


@pytest.mark.parametrize("delay", [5, 25])
def test_controls_reject_out_of_scope_delays(delay: int) -> None:
    with pytest.raises(ValidationError):
        ScenarioControls(delay_hours=delay)


def test_recorded_events_are_ordered_and_cover_all_agents() -> None:
    fake_events = load_fake_events()
    replay_events = load_replay_events()

    assert [event.sequence for event in fake_events] == list(range(1, len(fake_events) + 1))
    assert {event.agent for event in replay_events} == set(AgentName)
