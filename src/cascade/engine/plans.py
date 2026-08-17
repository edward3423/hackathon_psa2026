"""Plan evaluation and recommendation (PRD 9.8, 9.9).

Deterministic feasibility checks, metrics, and a fixed-order recommendation.
The coordinator agent explains and presents; it cannot change these numbers.
"""

from collections import Counter
from datetime import datetime

from cascade.contracts import (
    CargoType,
    Confidence,
    ConnectionAnalysis,
    ConnectionStatus,
    ContainerConnection,
    PlanArchetype,
    PlanComparison,
    PlanEvaluation,
    PlanMetrics,
    PlanningFacts,
    PriorityEmphasis,
    RecoveryActionType,
    RecoveryPlan,
    RushSlot,
    WorldFixture,
)
from cascade.engine._dispositions import Outcome, compute_dispositions
from cascade.engine.costs import estimate_cost
from cascade.engine.yard import simulate_yard

# Documented crane surge allowance: the terminal can rush at most this many
# containers within the planning horizon before crane capacity is exceeded.
# Basis: illustrative surge capacity of roughly one crane-shift of extra moves.
CRANE_SURGE_ALLOWANCE_CONTAINERS = 40

ARCHETYPE_ORDER: tuple[PlanArchetype, ...] = (
    PlanArchetype.AGGRESSIVE_RUSH,
    PlanArchetype.STANDARD_REBOOK,
    PlanArchetype.OPTIMIZED_HYBRID,
)

_CRITICAL_CARGO = (CargoType.PHARMA_REEFER, CargoType.TIME_CRITICAL_MANUFACTURING)
_AFFECTED = (ConnectionStatus.AT_RISK, ConnectionStatus.MISSED)


def planning_facts(world: WorldFixture, connections: ConnectionAnalysis) -> PlanningFacts:
    """Deterministic feasibility facts for plan proposal and revision.

    Mirrors the exact semantics ``evaluate_plan`` enforces: rush actions
    consume a group's containers in priority order (assign_plan_actions), and
    each rushed powered container occupies one free plug in its own block.
    Covers every group with at least one affected connection - the groups a
    plan must act on.
    """
    containers = {container.container_id: container for container in world.containers}
    groups: dict[tuple[str, CargoType], list[ContainerConnection]] = {}
    affected_keys: set[tuple[str, CargoType]] = set()
    for connection in connections.connections:
        key = (connection.onward_vessel, connection.cargo_type)
        groups.setdefault(key, []).append(connection)
        if connection.status in _AFFECTED:
            affected_keys.add(key)

    rush_order: dict[str, list[RushSlot]] = {}
    for key in sorted(affected_keys):
        members = sorted(groups[key], key=lambda connection: connection.priority_rank)
        rush_order[f"{key[0]}/{key[1].value}"] = [
            RushSlot(
                yard_block=containers[connection.container_id].yard_block,
                requires_power=containers[connection.container_id].requires_power,
            )
            for connection in members
        ]

    free_plugs = {
        block.block_id: max(0, block.reefer_plugs - block.initial_reefers_on_power)
        for block in world.yard_blocks
    }
    return PlanningFacts(
        crane_surge_allowance=CRANE_SURGE_ALLOWANCE_CONTAINERS,
        free_plugs_by_block=free_plugs,
        rush_order_by_group=rush_order,
    )


def evaluate_plan(
    world: WorldFixture,
    revised_eta: datetime,
    connections: ConnectionAnalysis,
    plan: RecoveryPlan,
    emphasis: PriorityEmphasis,
) -> PlanEvaluation:
    """Check feasibility and compute deterministic metrics for one plan.

    A plan is rejected when it exceeds alternative-sailing capacity, rushes
    more powered reefers into a yard block than that block has free reefer
    plugs, rushes more containers than the crane surge allowance, or leaves an
    affected (AT_RISK or MISSED) container group with no action. ``emphasis`` does not
    alter feasibility or metrics; the recommendation order is fixed (PRD 9.9).
    """
    del emphasis
    reasons: list[str] = []

    sailings = {sailing.vessel_name: sailing for sailing in world.alternative_sailings}
    rebooked_per_sailing: Counter[str] = Counter()
    for action in plan.actions:
        if action.action is not RecoveryActionType.REBOOK:
            continue
        if action.target_sailing is None:
            reasons.append(
                f"rebook action for {action.onward_vessel}/{action.cargo_type} "
                "names no target sailing"
            )
        elif action.target_sailing not in sailings:
            reasons.append(f"unknown alternative sailing {action.target_sailing}")
        else:
            rebooked_per_sailing[action.target_sailing] += action.container_count
    for sailing_name, count in sorted(rebooked_per_sailing.items()):
        capacity = sailings[sailing_name].available_capacity
        if count > capacity:
            reasons.append(
                f"rebooks {count} containers onto {sailing_name} which has capacity {capacity}"
            )

    rushed_total = sum(
        action.container_count
        for action in plan.actions
        if action.action is RecoveryActionType.RUSH
    )
    if rushed_total > CRANE_SURGE_ALLOWANCE_CONTAINERS:
        reasons.append(
            f"rushes {rushed_total} containers, above the crane surge allowance "
            f"of {CRANE_SURGE_ALLOWANCE_CONTAINERS}"
        )

    affected_groups = {
        (connection.onward_vessel, connection.cargo_type)
        for connection in connections.connections
        if connection.status in _AFFECTED
    }
    plan_groups = {(action.onward_vessel, action.cargo_type) for action in plan.actions}
    for vessel_name, cargo_type in sorted(
        affected_groups - plan_groups, key=lambda group: (group[0], group[1])
    ):
        reasons.append(f"affected group {vessel_name}/{cargo_type} receives no action")

    yard = simulate_yard(world, revised_eta, connections, plan)
    dispositions = compute_dispositions(world, connections, plan)

    # Reefer plug feasibility covers what a plan controls: the powered reefers
    # it rushes must fit the plugs their block has free of the initial
    # background load. Yard-wide plug pressure from cargo that waits in the
    # yard regardless of the plan is a scenario condition surfaced by the yard
    # forecast (PRD 9.6), not a plan defect.
    blocks = {block.block_id: block for block in world.yard_blocks}
    rushed_powered: Counter[str] = Counter()
    for disposition in dispositions:
        if disposition.outcome is Outcome.RUSHED and disposition.requires_power:
            rushed_powered[disposition.yard_block] += 1
    for block_id, count in sorted(rushed_powered.items()):
        block = blocks[block_id]
        free_plugs = max(0, block.reefer_plugs - block.initial_reefers_on_power)
        if count > free_plugs:
            reasons.append(f"block {block_id} needs {count} reefer plugs but has {free_plugs}")
    unresolved = sum(1 for d in dispositions if d.outcome is Outcome.UNRESOLVED)
    critical_affected = [
        d
        for d in dispositions
        if d.connection.cargo_type in _CRITICAL_CARGO and d.connection.status in _AFFECTED
    ]
    if critical_affected:
        protected = sum(1 for d in critical_affected if d.outcome is not Outcome.UNRESOLVED)
        critical_pct = round(protected * 100 / len(critical_affected), 1)
    else:
        critical_pct = 100.0
    peak_pct = max(
        (round(block.peak_occupancy * 100 / block.container_capacity, 1) for block in yard.blocks),
        default=0.0,
    )
    delays = [d.rebook_delay_hours for d in dispositions]
    if unresolved:
        delays.append(float(yard.horizon_hours))
    max_delay = round(max(delays, default=0.0), 1)

    metrics = PlanMetrics(
        cost=estimate_cost(world, connections, plan, yard),
        missed_connections=unresolved,
        critical_cargo_protected_pct=critical_pct,
        yard_peak_occupancy_pct=peak_pct,
        max_additional_delay_hours=max_delay,
    )
    return PlanEvaluation(
        plan=plan,
        metrics=metrics,
        feasible=not reasons,
        rejection_reasons=reasons,
    )


def _ranking_key(evaluation: PlanEvaluation) -> tuple[float, int, float, float, float, int]:
    metrics = evaluation.metrics
    return (
        -metrics.critical_cargo_protected_pct,
        metrics.missed_connections,
        metrics.yard_peak_occupancy_pct,
        metrics.cost.total,
        metrics.max_additional_delay_hours,
        ARCHETYPE_ORDER.index(evaluation.plan.archetype),
    )


def compare_plans(
    world: WorldFixture,
    revised_eta: datetime,
    connections: ConnectionAnalysis,
    plans: list[RecoveryPlan],
    emphasis: PriorityEmphasis,
    confidence: Confidence = Confidence.HIGH,
) -> PlanComparison:
    """Evaluate all plans and recommend one in the fixed PRD 9.9 order.

    Infeasible plans are never recommended. Among feasible plans the order is:
    most critical cargo protected, fewest missed connections, lowest yard peak
    percent, lowest cost, lowest additional delay; ties broken by archetype
    order AGGRESSIVE_RUSH, STANDARD_REBOOK, OPTIMIZED_HYBRID.
    """
    evaluations = [evaluate_plan(world, revised_eta, connections, plan, emphasis) for plan in plans]
    feasible = [evaluation for evaluation in evaluations if evaluation.feasible]
    if not feasible:
        return PlanComparison(
            evaluations=evaluations,
            recommended=None,
            rationale=(
                "No plan is feasible: every candidate violates at least one "
                "physical constraint, so none can be recommended."
            ),
            confidence=confidence,
        )

    best = min(feasible, key=_ranking_key)
    metrics = best.metrics
    rejected = len(evaluations) - len(feasible)
    rationale = (
        f"{best.plan.archetype.value} is recommended: it protects "
        f"{metrics.critical_cargo_protected_pct:.0f} percent of critical cargo, "
        f"leaves {metrics.missed_connections} missed connections, peaks the yard "
        f"at {metrics.yard_peak_occupancy_pct:.0f} percent, and costs "
        f"{metrics.cost.total:.0f} (illustrative)."
    )
    if rejected:
        rationale += f" {rejected} plan(s) were rejected as infeasible."
    return PlanComparison(
        evaluations=evaluations,
        recommended=best.plan.archetype,
        rationale=rationale,
        confidence=confidence,
    )
