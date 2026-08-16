from datetime import timedelta

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
    AlternativeSailing,
    CargoType,
    Confidence,
    ConnectionAnalysis,
    CostRates,
    PlanAction,
    PlanArchetype,
    PriorityEmphasis,
    RecoveryActionType,
    RecoveryPlan,
    WorldFixture,
)
from cascade.engine import analyse_connections, compare_plans, evaluate_plan
from cascade.engine.plans import CRANE_SURGE_ALLOWANCE_CONTAINERS

EMPHASIS = PriorityEmphasis.BALANCED


def missed_dry_world(container_count: int = 5, sailing_capacity: int = 3) -> WorldFixture:
    """A world where all dry containers miss MV GONE; rebooking is cheap but
    the only alternative sailing is too small to carry them all."""
    vessels = [
        inbound_vessel_fixture(),
        outbound_vessel("MV GONE", REVISED_ETA - timedelta(hours=2)),
    ]
    containers = [
        make_container(f"D{i:03d}", onward_vessel="MV GONE") for i in range(container_count)
    ]
    sailing = AlternativeSailing(
        vessel_name="ALT ONE",
        replaces_onward_vessel="MV GONE",
        departs=BASE + timedelta(hours=40),
        connection_cutoff=BASE + timedelta(hours=36),
        available_capacity=sailing_capacity,
    )
    rates = CostRates(
        dwell_per_container_hour=0.1,
        reefer_risk_per_hour=1.0,
        missed_connection_penalty=10.0,
        crane_hour=1000.0,  # rushing is expensive
        rebooking_fee=1.0,  # rebooking is cheap
    )
    return make_world(
        containers,
        vessels=vessels,
        yard_blocks=[make_block(container_capacity=100)],
        alternative_sailings=[sailing],
        cost_rates=rates,
    )


def rush_plan(count: int = 5) -> RecoveryPlan:
    return RecoveryPlan(
        archetype=PlanArchetype.AGGRESSIVE_RUSH,
        title="Rush everything",
        actions=[
            PlanAction(
                action=RecoveryActionType.RUSH,
                onward_vessel="MV GONE",
                cargo_type=CargoType.GENERAL_DRY,
                container_count=count,
                target_sailing=None,
                rationale="surge cranes",
            )
        ],
    )


def rebook_plan(count: int = 5) -> RecoveryPlan:
    return RecoveryPlan(
        archetype=PlanArchetype.STANDARD_REBOOK,
        title="Rebook everything",
        actions=[
            PlanAction(
                action=RecoveryActionType.REBOOK,
                onward_vessel="MV GONE",
                cargo_type=CargoType.GENERAL_DRY,
                container_count=count,
                target_sailing="ALT ONE",
                rationale="move to next sailing",
            )
        ],
    )


def analyse(world: WorldFixture) -> ConnectionAnalysis:
    return analyse_connections(world, REVISED_ETA, EMPHASIS)


def test_plan_exceeding_sailing_capacity_is_infeasible() -> None:
    world = missed_dry_world()
    evaluation = evaluate_plan(world, REVISED_ETA, analyse(world), rebook_plan(5), EMPHASIS)
    assert not evaluation.feasible
    assert any("capacity" in reason for reason in evaluation.rejection_reasons)


def test_plan_exceeding_crane_surge_allowance_is_infeasible() -> None:
    count = CRANE_SURGE_ALLOWANCE_CONTAINERS + 1
    world = missed_dry_world(container_count=count)
    evaluation = evaluate_plan(world, REVISED_ETA, analyse(world), rush_plan(count), EMPHASIS)
    assert not evaluation.feasible
    assert any("crane surge" in reason for reason in evaluation.rejection_reasons)


def test_plan_leaving_affected_group_without_action_is_infeasible() -> None:
    world = missed_dry_world()
    empty_plan = RecoveryPlan(
        archetype=PlanArchetype.STANDARD_REBOOK, title="Do nothing", actions=[]
    )
    evaluation = evaluate_plan(world, REVISED_ETA, analyse(world), empty_plan, EMPHASIS)
    assert not evaluation.feasible
    assert any("no action" in reason for reason in evaluation.rejection_reasons)


def test_plan_exceeding_reefer_plugs_is_infeasible() -> None:
    vessels = [
        inbound_vessel_fixture(),
        outbound_vessel("MV GONE", REVISED_ETA - timedelta(hours=2)),
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
        title="Rush reefers",
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
    evaluation = evaluate_plan(world, REVISED_ETA, analyse(world), plan, EMPHASIS)
    assert not evaluation.feasible
    assert any("reefer plugs" in reason for reason in evaluation.rejection_reasons)


def test_cheaper_plan_exceeding_capacity_is_never_recommended() -> None:
    world = missed_dry_world()
    connections = analyse(world)
    comparison = compare_plans(
        world, REVISED_ETA, connections, [rush_plan(5), rebook_plan(5)], EMPHASIS
    )
    by_archetype = {e.plan.archetype: e for e in comparison.evaluations}
    rush_cost = by_archetype[PlanArchetype.AGGRESSIVE_RUSH].metrics.cost.total
    rebook_cost = by_archetype[PlanArchetype.STANDARD_REBOOK].metrics.cost.total
    assert rebook_cost < rush_cost  # the infeasible plan is cheaper
    assert not by_archetype[PlanArchetype.STANDARD_REBOOK].feasible
    assert comparison.recommended is PlanArchetype.AGGRESSIVE_RUSH
    assert "AGGRESSIVE_RUSH" in comparison.rationale


def test_repeated_compare_plans_return_the_same_recommendation() -> None:
    world = missed_dry_world()
    connections = analyse(world)
    plans = [rush_plan(5), rebook_plan(5)]
    first = compare_plans(world, REVISED_ETA, connections, plans, EMPHASIS)
    second = compare_plans(world, REVISED_ETA, connections, plans, EMPHASIS)
    assert first == second


def test_fewest_missed_connections_wins_among_feasible_plans() -> None:
    world = missed_dry_world(container_count=5, sailing_capacity=5)
    connections = analyse(world)
    partial_rebook = RecoveryPlan(
        archetype=PlanArchetype.STANDARD_REBOOK,
        title="Rebook some",
        actions=[
            PlanAction(
                action=RecoveryActionType.REBOOK,
                onward_vessel="MV GONE",
                cargo_type=CargoType.GENERAL_DRY,
                container_count=3,
                target_sailing="ALT ONE",
                rationale="partial rebook",
            )
        ],
    )
    comparison = compare_plans(
        world, REVISED_ETA, connections, [partial_rebook, rush_plan(5)], EMPHASIS
    )
    # partial rebooking leaves 2 containers missed; rushing all 5 leaves none,
    # so the rush plan wins despite its far higher cost.
    assert comparison.recommended is PlanArchetype.AGGRESSIVE_RUSH


def test_no_feasible_plan_yields_no_recommendation() -> None:
    world = missed_dry_world()
    comparison = compare_plans(
        world,
        REVISED_ETA,
        analyse(world),
        [rebook_plan(5)],
        EMPHASIS,
        confidence=Confidence.MEDIUM,
    )
    assert comparison.recommended is None
    assert comparison.confidence is Confidence.MEDIUM
    assert "No plan is feasible" in comparison.rationale
