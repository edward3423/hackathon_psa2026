from datetime import datetime, timedelta

from engine_world import (
    BASE,
    REVISED_ETA,
    inbound_vessel_fixture,
    make_block,
    make_container,
    make_world,
    outbound_vessel,
)

from cascade.contracts import (
    CargoType,
    ConnectionAnalysis,
    PlanAction,
    PlanArchetype,
    PriorityEmphasis,
    RecoveryActionType,
    RecoveryPlan,
    WorldFixture,
    YardForecast,
)
from cascade.engine import analyse_connections, simulate_yard

EMPHASIS = PriorityEmphasis.BALANCED


def analyse(world: WorldFixture) -> ConnectionAnalysis:
    return analyse_connections(world, REVISED_ETA, EMPHASIS)


def occupancy_at(forecast: YardForecast, block_id: str, moment: datetime) -> int:
    block = next(b for b in forecast.blocks if b.block_id == block_id)
    point = next(p for p in block.series if p.time == moment)
    return point.occupancy


def test_series_starts_at_inbound_eta_floor_and_spans_horizon() -> None:
    world = make_world([make_container("C001")])
    forecast = simulate_yard(world, REVISED_ETA, analyse(world))
    assert forecast.horizon_hours == 72
    block = forecast.blocks[0]
    assert len(block.series) == 72
    assert block.series[0].time == BASE
    assert block.series[-1].time == BASE + timedelta(hours=71)


def test_series_is_identical_across_repeated_runs_and_never_negative() -> None:
    containers = [make_container(f"C{i:03d}") for i in range(6)]
    world = make_world(containers)
    connections = analyse(world)
    first = simulate_yard(world, REVISED_ETA, connections)
    second = simulate_yard(world, REVISED_ETA, connections)
    assert first == second
    for block in first.blocks:
        for point in block.series:
            assert point.occupancy >= 0


def test_arrival_and_departure_shape() -> None:
    world = make_world([make_container("C001")])
    forecast = simulate_yard(world, REVISED_ETA, analyse(world))
    # arrives at revised ETA (hour 18), departs at MV OUT ETD (hour 30)
    assert occupancy_at(forecast, "B1", BASE + timedelta(hours=17)) == 0
    assert occupancy_at(forecast, "B1", REVISED_ETA) == 1
    assert occupancy_at(forecast, "B1", BASE + timedelta(hours=29)) == 1
    assert occupancy_at(forecast, "B1", BASE + timedelta(hours=30)) == 0


def test_capacity_breaches_are_visible_not_hidden() -> None:
    vessels = [
        inbound_vessel_fixture(),
        outbound_vessel("MV GONE", REVISED_ETA - timedelta(hours=2)),
    ]
    containers = [make_container(f"C{i:03d}", onward_vessel="MV GONE") for i in range(6)]
    world = make_world(containers, vessels=vessels, yard_blocks=[make_block(container_capacity=5)])
    forecast = simulate_yard(world, REVISED_ETA, analyse(world))
    block = forecast.blocks[0]
    late_points = [p for p in block.series if p.time >= REVISED_ETA]
    assert all(p.occupancy == 6 for p in late_points)
    assert all(p.congested and p.full for p in late_points)
    assert block.peak_occupancy == 6


def test_unresolved_missed_containers_dwell_for_whole_horizon() -> None:
    vessels = [
        inbound_vessel_fixture(),
        outbound_vessel("MV GONE", REVISED_ETA - timedelta(hours=2)),
    ]
    world = make_world([make_container("C001", onward_vessel="MV GONE")], vessels=vessels)
    forecast = simulate_yard(world, REVISED_ETA, analyse(world))
    block = forecast.blocks[0]
    assert block.series[-1].occupancy == 1


def test_rebooked_missed_containers_depart_at_alternative_sailing() -> None:
    from cascade.contracts import AlternativeSailing

    vessels = [
        inbound_vessel_fixture(),
        outbound_vessel("MV GONE", REVISED_ETA - timedelta(hours=2)),
    ]
    sailing = AlternativeSailing(
        vessel_name="ALT ONE",
        replaces_onward_vessel="MV GONE",
        departs=BASE + timedelta(hours=40),
        connection_cutoff=BASE + timedelta(hours=36),
        available_capacity=10,
    )
    world = make_world(
        [make_container("C001", onward_vessel="MV GONE")],
        vessels=vessels,
        alternative_sailings=[sailing],
    )
    plan = RecoveryPlan(
        archetype=PlanArchetype.STANDARD_REBOOK,
        title="Rebook",
        actions=[
            PlanAction(
                action=RecoveryActionType.REBOOK,
                onward_vessel="MV GONE",
                cargo_type=CargoType.GENERAL_DRY,
                container_count=1,
                target_sailing="ALT ONE",
                rationale="move to next sailing",
            )
        ],
    )
    forecast = simulate_yard(world, REVISED_ETA, analyse(world), plan)
    assert occupancy_at(forecast, "B1", BASE + timedelta(hours=39)) == 1
    assert occupancy_at(forecast, "B1", BASE + timedelta(hours=40)) == 0


def test_eleven_reefers_with_ten_plugs_produce_one_shortage_with_start_time() -> None:
    containers = [
        make_container(f"R{i:03d}", cargo_type=CargoType.PHARMA_REEFER, requires_power=True)
        for i in range(11)
    ]
    world = make_world(containers, yard_blocks=[make_block(reefer_plugs=10)])
    forecast = simulate_yard(world, REVISED_ETA, analyse(world))
    assert len(forecast.reefer_shortages) == 1
    shortage = forecast.reefer_shortages[0]
    assert shortage.block_id == "B1"
    assert shortage.start_time == REVISED_ETA
    assert shortage.required_plugs == 11
    assert shortage.available_plugs == 10


def test_ten_reefers_with_ten_plugs_produce_no_shortage() -> None:
    containers = [
        make_container(f"R{i:03d}", cargo_type=CargoType.PHARMA_REEFER, requires_power=True)
        for i in range(10)
    ]
    world = make_world(containers, yard_blocks=[make_block(reefer_plugs=10)])
    forecast = simulate_yard(world, REVISED_ETA, analyse(world))
    assert forecast.reefer_shortages == []


def test_rushed_reefers_still_consume_plugs() -> None:
    # Missed reefer rushed onto a vessel whose ETD is already past: it must
    # still appear in plug demand for at least one hour.
    vessels = [
        inbound_vessel_fixture(),
        outbound_vessel(
            "MV GONE",
            REVISED_ETA - timedelta(hours=6),
            etd=REVISED_ETA - timedelta(hours=2),
        ),
    ]
    containers = [
        make_container(
            f"R{i:03d}",
            cargo_type=CargoType.PHARMA_REEFER,
            requires_power=True,
            onward_vessel="MV GONE",
        )
        for i in range(11)
    ]
    world = make_world(containers, vessels=vessels, yard_blocks=[make_block(reefer_plugs=10)])
    plan = RecoveryPlan(
        archetype=PlanArchetype.AGGRESSIVE_RUSH,
        title="Rush",
        actions=[
            PlanAction(
                action=RecoveryActionType.RUSH,
                onward_vessel="MV GONE",
                cargo_type=CargoType.PHARMA_REEFER,
                container_count=11,
                target_sailing=None,
                rationale="surge cranes",
            )
        ],
    )
    forecast = simulate_yard(world, REVISED_ETA, analyse(world), plan)
    assert len(forecast.reefer_shortages) == 1
    assert forecast.reefer_shortages[0].start_time == REVISED_ETA
