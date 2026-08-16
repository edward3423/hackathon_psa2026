"""Connection-impact analysis (PRD 9.3, 9.4).

Deterministic classification of every transshipment container against its
onward vessel cutoff, plus a priority ranking across all connections.
"""

from collections import Counter
from datetime import datetime, timedelta

from cascade.contracts import (
    CargoType,
    ConnectionAnalysis,
    ConnectionGroupSummary,
    ConnectionStatus,
    ContainerConnection,
    PriorityEmphasis,
    Vessel,
    VesselRole,
    WorldFixture,
)

SAFE_MARGIN_THRESHOLD_HOURS = 4.0

CARGO_PRIORITY_ORDER: tuple[CargoType, ...] = (
    CargoType.PHARMA_REEFER,
    CargoType.TIME_CRITICAL_MANUFACTURING,
    CargoType.GENERAL_DRY,
)

CARGO_LABELS: dict[CargoType, str] = {
    CargoType.PHARMA_REEFER: "pharma reefer",
    CargoType.TIME_CRITICAL_MANUFACTURING: "time-critical manufacturing",
    CargoType.GENERAL_DRY: "general dry",
}

_STATUS_ORDER: tuple[ConnectionStatus, ...] = (
    ConnectionStatus.MISSED,
    ConnectionStatus.AT_RISK,
    ConnectionStatus.SAFE,
    ConnectionStatus.RESOLVED,
)


def classify_margin(margin_hours: float) -> ConnectionStatus:
    """SAFE above 4 hours, AT_RISK between 0 and 4 inclusive, MISSED below 0."""
    if margin_hours > SAFE_MARGIN_THRESHOLD_HOURS:
        return ConnectionStatus.SAFE
    if margin_hours >= 0:
        return ConnectionStatus.AT_RISK
    return ConnectionStatus.MISSED


def inbound_vessel(world: WorldFixture) -> Vessel:
    for vessel in world.vessels:
        if vessel.role is VesselRole.INBOUND:
            return vessel
    raise ValueError("world fixture has no inbound vessel")


def analyse_connections(
    world: WorldFixture,
    revised_eta: datetime,
    emphasis: PriorityEmphasis,
) -> ConnectionAnalysis:
    """Classify every transshipment container and rank it by priority.

    ready_time = revised_eta + handling_hours.
    margin_hours = onward connection cutoff - ready_time, in hours.

    Priority ranking is fixed regardless of ``emphasis`` (PRD 9.4): pharma
    reefers first, then time-critical manufacturing, then general dry; within
    a cargo type a smaller margin ranks higher. ``emphasis`` steers the agents
    upstream, never this deterministic ordering, so equal inputs always
    produce equal ranks. Containers with no onward vessel are excluded.
    """
    del emphasis  # documented as non-influencing; kept for a stable tool signature
    vessels = {vessel.name: vessel for vessel in world.vessels}
    delay_hours = round((revised_eta - inbound_vessel(world).eta).total_seconds() / 3600)

    staged: list[tuple[int, float, str, ContainerConnection]] = []
    for container in world.containers:
        if container.onward_vessel is None:
            continue
        onward = vessels[container.onward_vessel]
        cutoff = onward.connection_cutoff or onward.etd
        ready_time = revised_eta + timedelta(hours=container.handling_hours)
        margin_hours = (cutoff - ready_time).total_seconds() / 3600
        status = classify_margin(margin_hours)
        reason = (
            f"{CARGO_LABELS[container.cargo_type]} cargo with "
            f"{margin_hours:.1f}h margin to {onward.name} cutoff"
        )
        connection = ContainerConnection(
            container_id=container.container_id,
            cargo_type=container.cargo_type,
            onward_vessel=onward.name,
            ready_time=ready_time,
            connection_cutoff=cutoff,
            margin_hours=round(margin_hours, 2),
            status=status,
            priority_rank=1,  # provisional; assigned after sorting
            priority_reason=reason,
        )
        staged.append(
            (
                CARGO_PRIORITY_ORDER.index(container.cargo_type),
                margin_hours,
                container.container_id,
                connection,
            )
        )

    staged.sort(key=lambda item: (item[0], item[1], item[2]))
    connections = [
        entry[3].model_copy(update={"priority_rank": rank})
        for rank, entry in enumerate(staged, start=1)
    ]

    counts = Counter(connection.status for connection in connections)
    group_counts: Counter[tuple[str, CargoType, ConnectionStatus]] = Counter(
        (connection.onward_vessel, connection.cargo_type, connection.status)
        for connection in connections
    )
    groups = [
        ConnectionGroupSummary(
            onward_vessel=vessel_name,
            cargo_type=cargo_type,
            status=status,
            container_count=count,
        )
        for (vessel_name, cargo_type, status), count in sorted(
            group_counts.items(),
            key=lambda item: (
                item[0][0],
                CARGO_PRIORITY_ORDER.index(item[0][1]),
                _STATUS_ORDER.index(item[0][2]),
            ),
        )
    ]

    return ConnectionAnalysis(
        delay_hours=delay_hours,
        safe_count=counts[ConnectionStatus.SAFE],
        at_risk_count=counts[ConnectionStatus.AT_RISK],
        missed_count=counts[ConnectionStatus.MISSED],
        groups=groups,
        connections=connections,
    )
