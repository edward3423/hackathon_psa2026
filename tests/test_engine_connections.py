from datetime import timedelta

from engine_world import (
    REVISED_ETA,
    inbound_vessel_fixture,
    make_container,
    make_world,
    outbound_vessel,
)

from cascade.contracts import CargoType, ConnectionStatus, PriorityEmphasis, WorldFixture
from cascade.engine import analyse_connections


def margin_world(margins_hours: list[float]) -> WorldFixture:
    vessels = [inbound_vessel_fixture()]
    containers = []
    for index, margin in enumerate(margins_hours):
        name = f"MV M{index}"
        vessels.append(outbound_vessel(name, REVISED_ETA + timedelta(hours=margin)))
        containers.append(make_container(f"C{index:03d}", onward_vessel=name))
    return make_world(containers, vessels=vessels)


def test_margin_classification_boundaries() -> None:
    world = margin_world([5, 4, 0, -1])
    analysis = analyse_connections(world, REVISED_ETA, PriorityEmphasis.BALANCED)
    by_id = {c.container_id: c for c in analysis.connections}
    assert by_id["C000"].status is ConnectionStatus.SAFE
    assert by_id["C001"].status is ConnectionStatus.AT_RISK
    assert by_id["C002"].status is ConnectionStatus.AT_RISK
    assert by_id["C003"].status is ConnectionStatus.MISSED
    assert analysis.safe_count == 1
    assert analysis.at_risk_count == 2
    assert analysis.missed_count == 1
    assert analysis.delay_hours == 18


def test_ready_time_and_margin_use_handling_hours() -> None:
    vessels = [
        inbound_vessel_fixture(),
        outbound_vessel("MV OUT", REVISED_ETA + timedelta(hours=6)),
    ]
    world = make_world([make_container("C001", handling_hours=2.0)], vessels=vessels)
    analysis = analyse_connections(world, REVISED_ETA, PriorityEmphasis.BALANCED)
    connection = analysis.connections[0]
    assert connection.ready_time == REVISED_ETA + timedelta(hours=2)
    assert connection.margin_hours == 4.0
    assert connection.status is ConnectionStatus.AT_RISK


def test_equal_margin_containers_rank_in_cargo_order_with_reason() -> None:
    containers = [
        make_container("C-DRY", cargo_type=CargoType.GENERAL_DRY),
        make_container("C-PHARMA", cargo_type=CargoType.PHARMA_REEFER, requires_power=True),
        make_container("C-MFG", cargo_type=CargoType.TIME_CRITICAL_MANUFACTURING),
    ]
    world = make_world(containers)
    analysis = analyse_connections(world, REVISED_ETA, PriorityEmphasis.BALANCED)
    ordered = sorted(analysis.connections, key=lambda c: c.priority_rank)
    assert [c.container_id for c in ordered] == ["C-PHARMA", "C-MFG", "C-DRY"]
    assert [c.priority_rank for c in ordered] == [1, 2, 3]
    assert "pharma reefer" in ordered[0].priority_reason
    assert "time-critical manufacturing" in ordered[1].priority_reason
    assert "general dry" in ordered[2].priority_reason
    for connection in ordered:
        assert f"{connection.margin_hours:.1f}h margin" in connection.priority_reason


def test_smaller_margin_ranks_higher_within_cargo_type() -> None:
    vessels = [
        inbound_vessel_fixture(),
        outbound_vessel("MV TIGHT", REVISED_ETA + timedelta(hours=1)),
        outbound_vessel("MV LOOSE", REVISED_ETA + timedelta(hours=8)),
    ]
    containers = [
        make_container("C-LOOSE", onward_vessel="MV LOOSE"),
        make_container("C-TIGHT", onward_vessel="MV TIGHT"),
    ]
    world = make_world(containers, vessels=vessels)
    analysis = analyse_connections(world, REVISED_ETA, PriorityEmphasis.BALANCED)
    ordered = sorted(analysis.connections, key=lambda c: c.priority_rank)
    assert [c.container_id for c in ordered] == ["C-TIGHT", "C-LOOSE"]


def test_containers_without_onward_vessel_are_excluded() -> None:
    world = make_world([make_container("C001"), make_container("C-STAY", onward_vessel=None)])
    analysis = analyse_connections(world, REVISED_ETA, PriorityEmphasis.BALANCED)
    assert [c.container_id for c in analysis.connections] == ["C001"]


def test_group_summaries_count_per_vessel_cargo_status() -> None:
    containers = [
        make_container("C001"),
        make_container("C002"),
        make_container("C003", cargo_type=CargoType.PHARMA_REEFER, requires_power=True),
    ]
    world = make_world(containers)
    analysis = analyse_connections(world, REVISED_ETA, PriorityEmphasis.BALANCED)
    assert sum(group.container_count for group in analysis.groups) == 3
    dry = next(g for g in analysis.groups if g.cargo_type is CargoType.GENERAL_DRY)
    assert dry.onward_vessel == "MV OUT"
    assert dry.container_count == 2
