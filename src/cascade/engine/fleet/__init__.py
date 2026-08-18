"""Fleet-scale discrete-event simulation for the Red Sea 2024 blind benchmark.

A parallel vertical to the single-vessel engine: same values (deterministic,
no clock reads, no hidden state), different scale. Nothing here imports the
golden fixtures, and nothing here can see past the simulation clock.
"""

from cascade.engine.fleet.berths import (
    ActivationOutcome,
    BerthPool,
    validate_fleet_decision,
)
from cascade.engine.fleet.calibrate import calibrate, erlang_c_wait_days
from cascade.engine.fleet.events import (
    EventQueue,
    FcfsPolicy,
    FleetEvent,
    FleetEventKind,
    FleetPolicy,
    WaitingVessel,
)
from cascade.engine.fleet.feed import BlindFeed, FutureReadError, SimClock
from cascade.engine.fleet.metrics import (
    DailyKpiBuilder,
    DayCounters,
    VesselRecord,
    build_daily_kpis,
    compute_metrics,
)
from cascade.engine.fleet.service import service_hours
from cascade.engine.fleet.simulate import SimulationOutcome, simulate

__all__ = [
    "ActivationOutcome",
    "BerthPool",
    "BlindFeed",
    "DailyKpiBuilder",
    "DayCounters",
    "EventQueue",
    "FcfsPolicy",
    "FleetEvent",
    "FleetEventKind",
    "FleetPolicy",
    "FutureReadError",
    "SimClock",
    "SimulationOutcome",
    "VesselRecord",
    "WaitingVessel",
    "build_daily_kpis",
    "calibrate",
    "compute_metrics",
    "erlang_c_wait_days",
    "service_hours",
    "simulate",
    "validate_fleet_decision",
]
