"""Illustrative cost estimate (PRD 9.7).

Five fixed components computed from world.cost_rates. The result is labelled
illustrative; the numbers demonstrate relative plan economics only.
"""

from cascade.contracts import (
    ConnectionAnalysis,
    ConnectionStatus,
    CostComponent,
    CostEstimate,
    RecoveryPlan,
    WorldFixture,
    YardForecast,
)
from cascade.engine._dispositions import Outcome, compute_dispositions

EXTRA_CRANE_HOURS_PER_RUSHED_CONTAINER = 1.0

COMPONENT_ADDITIONAL_DWELL = "additional dwell"
COMPONENT_REEFER_RISK = "reefer risk"
COMPONENT_MISSED_PENALTY = "missed-connection penalty"
COMPONENT_EXTRA_CRANE = "extra crane time"
COMPONENT_REBOOKING = "rebooking"


def estimate_cost(
    world: WorldFixture,
    connections: ConnectionAnalysis,
    plan: RecoveryPlan | None,
    yard: YardForecast,
) -> CostEstimate:
    """Sum five fixed illustrative components from world.cost_rates.

    - additional dwell: every connection container accrues the vessel delay
      as extra dwell; rebooked containers add their rebooking delay; containers
      left unresolved dwell for the whole forecast horizon.
    - reefer risk: powered reefers that are not SAFE are exposed for the delay
      duration; each reefer plug shortage adds shortfall x remaining horizon
      hours of exposure.
    - missed-connection penalty: one penalty per container that still misses
      its connection under the plan.
    - extra crane time: one extra crane hour per rushed container.
    - rebooking: one fee per rebooked container.
    """
    rates = world.cost_rates
    delay = float(connections.delay_hours)
    dispositions = compute_dispositions(world, connections, plan)

    dwell_hours = 0.0
    unresolved = 0
    rushed = 0
    rebooked = 0
    for disposition in dispositions:
        if disposition.outcome is Outcome.UNRESOLVED:
            dwell_hours += yard.horizon_hours
            unresolved += 1
        elif disposition.outcome is Outcome.REBOOKED:
            dwell_hours += delay + disposition.rebook_delay_hours
            rebooked += 1
        else:
            dwell_hours += delay
            if disposition.outcome is Outcome.RUSHED:
                rushed += 1

    exposed_reefers = sum(
        1
        for disposition in dispositions
        if disposition.requires_power and disposition.connection.status is not ConnectionStatus.SAFE
    )
    reefer_exposure_hours = exposed_reefers * delay
    series_starts = {block.block_id: block.series[0].time for block in yard.blocks}
    for shortage in yard.reefer_shortages:
        elapsed = (shortage.start_time - series_starts[shortage.block_id]).total_seconds() / 3600
        remaining = max(0.0, yard.horizon_hours - elapsed)
        reefer_exposure_hours += (shortage.required_plugs - shortage.available_plugs) * remaining

    components = [
        CostComponent(
            name=COMPONENT_ADDITIONAL_DWELL,
            amount=round(dwell_hours * rates.dwell_per_container_hour, 2),
            basis=(
                f"{dwell_hours:.0f} extra container-hours "
                f"x {rates.dwell_per_container_hour} per container-hour"
            ),
        ),
        CostComponent(
            name=COMPONENT_REEFER_RISK,
            amount=round(reefer_exposure_hours * rates.reefer_risk_per_hour, 2),
            basis=(
                f"{exposed_reefers} exposed reefers over {delay:.0f}h delay plus "
                f"plug shortfalls, {reefer_exposure_hours:.0f} reefer-hours "
                f"x {rates.reefer_risk_per_hour} per hour"
            ),
        ),
        CostComponent(
            name=COMPONENT_MISSED_PENALTY,
            amount=round(unresolved * rates.missed_connection_penalty, 2),
            basis=(
                f"{unresolved} unresolved missed connections "
                f"x {rates.missed_connection_penalty} per connection"
            ),
        ),
        CostComponent(
            name=COMPONENT_EXTRA_CRANE,
            amount=round(rushed * EXTRA_CRANE_HOURS_PER_RUSHED_CONTAINER * rates.crane_hour, 2),
            basis=(
                f"{rushed} rushed containers "
                f"x {EXTRA_CRANE_HOURS_PER_RUSHED_CONTAINER} crane hours "
                f"x {rates.crane_hour} per crane hour"
            ),
        ),
        CostComponent(
            name=COMPONENT_REBOOKING,
            amount=round(rebooked * rates.rebooking_fee, 2),
            basis=f"{rebooked} rebooked containers x {rates.rebooking_fee} per rebooking",
        ),
    ]
    total = round(sum(component.amount for component in components), 2)
    return CostEstimate(components=components, total=total, illustrative=True)
