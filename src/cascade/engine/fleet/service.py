"""Vessel service time at the berth.

One pure function. Given a call's size and the state of the port when it
berths, it returns how many hours the berth is occupied.

    handling = teu / (cranes_per_berth * moves_per_crane_hour
                      * teu_per_move * efficiency)
    hours    = (base_hours + handling) * congestion
    congestion = 1 + alpha * min(queue_length / queue_ref, cap)

The congestion factor is the feedback loop that turns a queue into a crisis:
a longer queue slows every call down, which lengthens the queue further. It
saturates at ``congestion_cap`` so the model cannot run away.

Levers, all applied to the parameters rather than to the answer, so a lever's
effect is visible in the model and not bolted on afterwards:

- ``WORKFORCE_SURGE`` at level L scales ``congestion_alpha`` by
  ``surge_alpha_factor ** L`` (extra crews absorb congestion) and
  ``efficiency`` by ``(1 + surge_efficiency_gain) ** L``.
- ``FAST_CONNECTION_MODE`` speeds up only the connection-heavy share of the
  call: the fraction ``connection_teu / teu`` of the work is multiplied by
  ``fast_connection_speedup``, the rest is untouched.
- ``service_rate_multiplier`` from ``FleetWorldConfig`` scales the final
  duration, and exists so the robustness sweep can perturb the whole port
  without disturbing the fitted parameters.
"""

from cascade.contracts import ServiceModelConfig


def service_hours(
    *,
    teu: float,
    connection_teu: float,
    queue_length: int,
    service: ServiceModelConfig,
    surge_level: int = 0,
    fast_connection: bool = False,
    rate_multiplier: float = 1.0,
) -> float:
    """Berth occupancy in hours for one call. Pure: no state, no clock."""
    efficiency = service.efficiency * (1.0 + service.surge_efficiency_gain) ** surge_level
    alpha = service.congestion_alpha * service.surge_alpha_factor**surge_level

    moves_per_hour = service.cranes_per_berth * service.moves_per_crane_hour
    handling = teu / (moves_per_hour * service.teu_per_move * efficiency)
    congestion = 1.0 + alpha * min(
        queue_length / service.congestion_queue_ref, service.congestion_cap
    )
    hours = (service.base_hours + handling) * congestion

    if fast_connection and teu > 0.0:
        share = min(1.0, max(0.0, connection_teu / teu))
        hours *= 1.0 - share + share * service.fast_connection_speedup

    return hours * rate_multiplier
