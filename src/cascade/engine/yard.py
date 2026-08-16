"""Simplified yard forecast (PRD 9.5, 9.6).

Hourly occupancy series per yard block plus reefer plug shortages, driven
entirely by the world fixture, the connection analysis, and an optional
recovery plan. Deterministic: no clock reads, no randomness.
"""

from datetime import datetime, timedelta

from cascade.contracts import (
    BlockForecast,
    ConnectionAnalysis,
    RecoveryPlan,
    ReeferShortage,
    WorldFixture,
    YardForecast,
    YardOccupancyPoint,
)
from cascade.engine._dispositions import Outcome, compute_dispositions
from cascade.engine.connections import inbound_vessel

CONGESTION_THRESHOLD_PCT = 85
MINIMUM_RUSH_PRESENCE = timedelta(hours=1)


def _floor_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def simulate_yard(
    world: WorldFixture,
    revised_eta: datetime,
    connections: ConnectionAnalysis,
    plan: RecoveryPlan | None = None,
    horizon_hours: int = 72,
) -> YardForecast:
    """Project hourly occupancy per block and detect reefer plug shortages.

    Modelling decisions (documented for repeatability):
    - The series starts at the inbound vessel's original ETA floored to the
      hour and contains ``horizon_hours`` points (hours 0..horizon_hours-1).
    - Every world container arrives at ready_time = revised_eta +
      handling_hours into its yard block; block ``initial_containers`` are a
      constant background that never departs within the horizon.
    - SAFE and AT_RISK containers depart at their onward vessel ETD. MISSED
      containers depart only if the plan rebooks them (at the alternative
      sailing departure) or rushes them (at the original ETD); otherwise they
      dwell for the whole horizon. Containers with no onward vessel dwell for
      the whole horizon.
    - A rushed container stays in the yard for at least one hour so it always
      consumes a slot, and a powered rushed reefer always consumes a plug.
    - A container is present at sample time t if arrival <= t < departure.
    - congested = occupancy >= 85 percent of capacity; full = occupancy >=
      capacity. Occupancy is clamped at zero, never negative.
    - Reefer plug demand per block per hour = initial_reefers_on_power plus
      powered containers present; the first hour where demand exceeds
      ``reefer_plugs`` is reported as that block's shortage.
    """
    start = _floor_hour(inbound_vessel(world).eta)
    dispositions = {
        disposition.connection.container_id: disposition
        for disposition in compute_dispositions(world, connections, plan)
    }

    presence: dict[str, list[tuple[datetime, datetime | None, bool]]] = {
        block.block_id: [] for block in world.yard_blocks
    }
    for container in world.containers:
        arrival = revised_eta + timedelta(hours=container.handling_hours)
        disposition = dispositions.get(container.container_id)
        departure = disposition.departure if disposition else None
        if departure is not None:
            floor = arrival + (
                MINIMUM_RUSH_PRESENCE
                if disposition and disposition.outcome is Outcome.RUSHED
                else timedelta(0)
            )
            departure = max(departure, floor)
        presence[container.yard_block].append((arrival, departure, container.requires_power))

    blocks: list[BlockForecast] = []
    shortages: list[ReeferShortage] = []
    for block in world.yard_blocks:
        intervals = presence[block.block_id]
        series: list[YardOccupancyPoint] = []
        peak_occupancy = -1
        peak_time = start
        shortage: ReeferShortage | None = None
        for hour in range(horizon_hours):
            moment = start + timedelta(hours=hour)
            present = [
                (arrival, departure, powered)
                for arrival, departure, powered in intervals
                if arrival <= moment and (departure is None or departure > moment)
            ]
            occupancy = max(0, block.initial_containers + len(present))
            series.append(
                YardOccupancyPoint(
                    time=moment,
                    occupancy=occupancy,
                    congested=occupancy * 100
                    >= block.container_capacity * CONGESTION_THRESHOLD_PCT,
                    full=occupancy >= block.container_capacity,
                )
            )
            if occupancy > peak_occupancy:
                peak_occupancy = occupancy
                peak_time = moment
            powered_demand = block.initial_reefers_on_power + sum(
                1 for _, _, powered in present if powered
            )
            if shortage is None and powered_demand > block.reefer_plugs:
                shortage = ReeferShortage(
                    block_id=block.block_id,
                    start_time=moment,
                    required_plugs=powered_demand,
                    available_plugs=block.reefer_plugs,
                )
        blocks.append(
            BlockForecast(
                block_id=block.block_id,
                container_capacity=block.container_capacity,
                series=series,
                peak_occupancy=peak_occupancy,
                peak_time=peak_time,
            )
        )
        if shortage is not None:
            shortages.append(shortage)

    return YardForecast(
        horizon_hours=horizon_hours,
        blocks=blocks,
        reefer_shortages=shortages,
    )
