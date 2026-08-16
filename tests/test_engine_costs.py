from datetime import timedelta

from engine_world import (
    BASE,
    REVISED_ETA,
    inbound_vessel_fixture,
    make_container,
    make_world,
    outbound_vessel,
)

from cascade.contracts import (
    AlternativeSailing,
    CargoType,
    CostRates,
    PlanAction,
    PlanArchetype,
    PriorityEmphasis,
    RecoveryActionType,
    RecoveryPlan,
)
from cascade.engine import analyse_connections, estimate_cost, simulate_yard

EMPHASIS = PriorityEmphasis.BALANCED

RATES = CostRates(
    dwell_per_container_hour=2.0,
    reefer_risk_per_hour=5.0,
    missed_connection_penalty=100.0,
    crane_hour=50.0,
    rebooking_fee=25.0,
)


def hybrid_scenario(rates: CostRates = RATES):
    vessels = [
        inbound_vessel_fixture(),
        outbound_vessel("MV GONE", REVISED_ETA - timedelta(hours=2)),
    ]
    containers = [
        make_container(
            "R001",
            cargo_type=CargoType.PHARMA_REEFER,
            requires_power=True,
            onward_vessel="MV GONE",
        ),
        make_container("D001", onward_vessel="MV GONE"),
        make_container("D002", onward_vessel="MV GONE"),
    ]
    sailing = AlternativeSailing(
        vessel_name="ALT ONE",
        replaces_onward_vessel="MV GONE",
        departs=BASE + timedelta(hours=40),
        connection_cutoff=BASE + timedelta(hours=36),
        available_capacity=5,
    )
    world = make_world(
        containers,
        vessels=vessels,
        alternative_sailings=[sailing],
        cost_rates=rates,
    )
    plan = RecoveryPlan(
        archetype=PlanArchetype.OPTIMIZED_HYBRID,
        title="Hybrid",
        actions=[
            PlanAction(
                action=RecoveryActionType.RUSH,
                onward_vessel="MV GONE",
                cargo_type=CargoType.PHARMA_REEFER,
                container_count=1,
                target_sailing=None,
                rationale="protect pharma",
            ),
            PlanAction(
                action=RecoveryActionType.REBOOK,
                onward_vessel="MV GONE",
                cargo_type=CargoType.GENERAL_DRY,
                container_count=1,
                target_sailing="ALT ONE",
                rationale="rebook dry cargo",
            ),
        ],
    )
    return world, plan


def compute(world, plan):
    connections = analyse_connections(world, REVISED_ETA, EMPHASIS)
    yard = simulate_yard(world, REVISED_ETA, connections, plan)
    return estimate_cost(world, connections, plan, yard)


def test_total_equals_sum_of_components_and_all_five_present():
    world, plan = hybrid_scenario()
    estimate = compute(world, plan)
    assert estimate.illustrative is True
    assert [component.name for component in estimate.components] == [
        "additional dwell",
        "reefer risk",
        "missed-connection penalty",
        "extra crane time",
        "rebooking",
    ]
    assert estimate.total == round(sum(component.amount for component in estimate.components), 2)
    for component in estimate.components:
        assert component.basis


def test_component_values_follow_documented_formulas():
    world, plan = hybrid_scenario()
    estimate = compute(world, plan)
    by_name = {component.name: component for component in estimate.components}
    # rushed reefer: 18h dwell; rebooked dry: 18h + (departs 40h - ETD 20h) = 38h;
    # unresolved dry: 72h horizon dwell
    assert by_name["additional dwell"].amount == (18 + 38 + 72) * 2.0
    # one exposed reefer x 18h delay x 5.0 (no plug shortage in this world)
    assert by_name["reefer risk"].amount == 18 * 5.0
    assert by_name["missed-connection penalty"].amount == 1 * 100.0
    assert by_name["extra crane time"].amount == 1 * 1.0 * 50.0
    assert by_name["rebooking"].amount == 1 * 25.0


def test_changing_one_rate_changes_only_the_matching_component():
    world, plan = hybrid_scenario()
    baseline = {c.name: c.amount for c in compute(world, plan).components}
    bumped_rates = RATES.model_copy(update={"rebooking_fee": 75.0})
    world_bumped, plan_bumped = hybrid_scenario(bumped_rates)
    bumped = {c.name: c.amount for c in compute(world_bumped, plan_bumped).components}
    assert bumped["rebooking"] == baseline["rebooking"] + 50.0
    for name in (
        "additional dwell",
        "reefer risk",
        "missed-connection penalty",
        "extra crane time",
    ):
        assert bumped[name] == baseline[name]
