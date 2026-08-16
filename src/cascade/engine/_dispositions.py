"""Internal helper: map plan actions onto individual containers.

Plan actions are group-level (onward vessel, cargo type, count). This module
assigns them deterministically to concrete containers and derives each
container's outcome and departure time. Shared by yard, cost, and plan
modules so all three agree on the same schedule.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from cascade.contracts import (
    CargoType,
    ConnectionAnalysis,
    ConnectionStatus,
    ContainerConnection,
    PlanAction,
    RecoveryActionType,
    RecoveryPlan,
    WorldFixture,
)


class Outcome(StrEnum):
    DEPARTS_ORIGINAL = "DEPARTS_ORIGINAL"  # makes its planned onward vessel
    RUSHED = "RUSHED"  # makes the original vessel via extra crane handling
    REBOOKED = "REBOOKED"  # departs on an alternative sailing
    UNRESOLVED = "UNRESOLVED"  # dwells in the yard for the whole horizon


@dataclass(frozen=True)
class Disposition:
    connection: ContainerConnection
    requires_power: bool
    yard_block: str
    action: PlanAction | None
    outcome: Outcome
    departure: datetime | None  # None = dwells for the whole horizon
    rebook_delay_hours: float  # extra delay versus the original onward ETD


def assign_plan_actions(
    connections: ConnectionAnalysis, plan: RecoveryPlan | None
) -> dict[str, PlanAction | None]:
    """Assign plan actions to containers, deterministically.

    Within each (onward_vessel, cargo_type) group, containers are ordered by
    priority rank and actions consume containers in plan order, each taking
    ``container_count`` containers. Containers beyond the covered counts keep
    their default behaviour.
    """
    assignment: dict[str, PlanAction | None] = {
        connection.container_id: None for connection in connections.connections
    }
    if plan is None:
        return assignment

    groups: dict[tuple[str, CargoType], list[ContainerConnection]] = {}
    for connection in connections.connections:
        key = (connection.onward_vessel, connection.cargo_type)
        groups.setdefault(key, []).append(connection)
    for members in groups.values():
        members.sort(key=lambda connection: connection.priority_rank)

    cursor: dict[tuple[str, CargoType], int] = dict.fromkeys(groups, 0)
    for action in plan.actions:
        key = (action.onward_vessel, action.cargo_type)
        matched = groups.get(key)
        if matched is None:
            continue
        start = cursor[key]
        for connection in matched[start : start + action.container_count]:
            assignment[connection.container_id] = action
        cursor[key] = min(start + action.container_count, len(matched))

    return assignment


def compute_dispositions(
    world: WorldFixture,
    connections: ConnectionAnalysis,
    plan: RecoveryPlan | None,
) -> list[Disposition]:
    """Derive outcome and departure time for every transshipment container.

    Rules:
    - RUSH: departs at the original onward vessel ETD (extra crane handling
      keeps the connection), even for MISSED containers.
    - REBOOK: departs at the target alternative sailing's departure; a missing
      or unknown target leaves the container unresolved (feasibility checks
      reject such plans).
    - HOLD: dwells for the whole horizon.
    - No action: SAFE and AT_RISK containers depart at the onward ETD; MISSED
      containers dwell for the whole horizon.
    """
    vessels = {vessel.name: vessel for vessel in world.vessels}
    containers = {container.container_id: container for container in world.containers}
    sailings = {sailing.vessel_name: sailing for sailing in world.alternative_sailings}
    assignment = assign_plan_actions(connections, plan)

    dispositions: list[Disposition] = []
    for connection in connections.connections:
        container = containers[connection.container_id]
        onward_etd = vessels[connection.onward_vessel].etd
        action = assignment[connection.container_id]
        outcome = Outcome.DEPARTS_ORIGINAL
        departure: datetime | None = onward_etd
        rebook_delay_hours = 0.0

        if action is None:
            if connection.status is ConnectionStatus.MISSED:
                outcome, departure = Outcome.UNRESOLVED, None
        elif action.action is RecoveryActionType.RUSH:
            outcome = Outcome.RUSHED
        elif action.action is RecoveryActionType.REBOOK:
            sailing = sailings.get(action.target_sailing) if action.target_sailing else None
            if sailing is None:
                outcome, departure = Outcome.UNRESOLVED, None
            else:
                outcome, departure = Outcome.REBOOKED, sailing.departs
                rebook_delay_hours = max(0.0, (sailing.departs - onward_etd).total_seconds() / 3600)
        else:  # HOLD
            outcome, departure = Outcome.UNRESOLVED, None

        dispositions.append(
            Disposition(
                connection=connection,
                requires_power=container.requires_power,
                yard_block=container.yard_block,
                action=action,
                outcome=outcome,
                departure=departure,
                rebook_delay_hours=rebook_delay_hours,
            )
        )
    return dispositions
