"""Fit the service model on the pre-crisis window, and only on that window.

The calibrator's parameter type is ``CalibrationSlice``. ``BlindSlice`` is a
separate contract with no inheritance relationship to it, so handing the
calibrator crisis data is a type error at check time and a ``TypeError`` at
run time. That is the whole point: a model tuned on the days it is later
asked to predict would make the benchmark meaningless.

Fitting is a deterministic coordinate search - a coarse grid over effective
berth count and efficiency, then a refinement of efficiency, then a sweep of
``congestion_alpha``. No optimiser library, no randomness, no early exit on a
system clock. Three criteria decide ``passed``:

- simulated mean daily port calls within ``THROUGHPUT_TOLERANCE_PCT`` of the
  observed count (the port keeps up with its own arrivals),
- simulated mean rolling wait below ``HEALTHY_WAIT_DAYS`` (a healthy port),
- utilisation inside ``[MIN_UTILISATION, MAX_UTILISATION]`` (neither a ghost
  port nor a saturated one).

An Erlang-C M/M/c expectation at the fitted utilisation is reported next to
the simulated wait as an independent cross-check on the queueing behaviour.
"""

import math
from dataclasses import dataclass
from datetime import datetime, time

from cascade.contracts import (
    BlindSlice,
    CalibrationReport,
    CalibrationSlice,
    FleetWorldConfig,
    ServiceModelConfig,
)
from cascade.engine.fleet.events import FcfsPolicy
from cascade.engine.fleet.feed import BlindFeed, SimClock
from cascade.engine.fleet.metrics import HOURS_PER_DAY
from cascade.engine.fleet.simulate import simulate

THROUGHPUT_TOLERANCE_PCT = 5.0
HEALTHY_WAIT_DAYS = 1.0
MIN_UTILISATION = 0.3
MAX_UTILISATION = 0.92
TARGET_WAIT_DAYS = 0.25

EFFICIENCY_GRID = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]
BERTH_DELTAS = [-1, 0, 1, 2]
ALPHA_GRID = [0.0, 0.1, 0.2, 0.3]
REFINE_OFFSETS = [-0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06]


def erlang_c_wait_days(arrival_rate: float, service_days: float, servers: int) -> float:
    """Expected M/M/c queueing delay in days. Infinite when the queue is unstable."""
    if servers <= 0 or service_days <= 0 or arrival_rate <= 0:
        return 0.0
    offered = arrival_rate * service_days
    utilisation = offered / servers
    if utilisation >= 1.0:
        return math.inf
    terms = [offered**k / math.factorial(k) for k in range(servers)]
    busy = offered**servers / math.factorial(servers) / (1.0 - utilisation)
    probability = busy / (sum(terms) + busy)
    return probability / (servers / service_days - arrival_rate)


@dataclass(frozen=True, slots=True)
class _Trial:
    """One simulated candidate, scored for the search."""

    berths: int
    service: ServiceModelConfig
    throughput_error_pct: float
    mean_wait_days: float
    mean_rolling_wait_days: float
    mean_port_stay_hours: float
    utilisation: float

    @property
    def score(self) -> float:
        """Lower is better: throughput first, then a healthy-but-busy port."""
        wait_penalty = max(0.0, self.mean_rolling_wait_days - TARGET_WAIT_DAYS) * 10.0
        idle_penalty = max(0.0, MIN_UTILISATION - self.utilisation) * 20.0
        strain_penalty = max(0.0, self.utilisation - MAX_UTILISATION) * 40.0
        return abs(self.throughput_error_pct) + wait_penalty + idle_penalty + strain_penalty


def _run_trial(
    slice_: CalibrationSlice, base: FleetWorldConfig, berths: int, service: ServiceModelConfig
) -> _Trial:
    world = base.model_copy(
        update={
            "berths": base.berths.model_copy(update={"active_berths": berths}),
            "service": service,
            "berth_delta": 0,
        }
    )
    clock = SimClock(start=datetime.combine(slice_.window.start, time.min))
    feed = BlindFeed(BlindSlice(window=slice_.window, days=slice_.days), clock)
    outcome = simulate(world, feed, FcfsPolicy(), window=slice_.window)
    days = len(outcome.daily) or 1
    observed = sum(day.portcalls_container for day in slice_.days) / (len(slice_.days) or 1)
    simulated = sum(day.departures for day in outcome.daily) / days
    stays = [record.port_stay_hours for record in outcome.records]
    waits = [record.wait_days for record in outcome.records]
    return _Trial(
        berths=berths,
        service=service,
        throughput_error_pct=(simulated / observed - 1.0) * 100.0 if observed else 100.0,
        mean_wait_days=sum(waits) / len(waits) if waits else 0.0,
        mean_rolling_wait_days=sum(day.rolling_wait_days for day in outcome.daily) / days,
        mean_port_stay_hours=sum(stays) / len(stays) if stays else 0.0,
        utilisation=sum(day.utilisation for day in outcome.daily) / days,
    )


def calibrate(slice_: CalibrationSlice, base: FleetWorldConfig) -> CalibrationReport:
    """Fit efficiency, berth count and congestion alpha on the pre-crisis days."""
    if not isinstance(slice_, CalibrationSlice):
        raise TypeError(
            "calibrate accepts only a CalibrationSlice; crisis days are never fitted on"
        )
    if not slice_.days:
        raise ValueError("cannot calibrate on an empty window")

    best = min(
        (
            _run_trial(
                slice_,
                base,
                berths,
                base.service.model_copy(update={"efficiency": efficiency}),
            )
            for berths in sorted({max(1, base.berths.active_berths + d) for d in BERTH_DELTAS})
            for efficiency in EFFICIENCY_GRID
        ),
        key=lambda trial: (trial.score, trial.berths, trial.service.efficiency),
    )
    best = min(
        (
            _run_trial(
                slice_,
                base,
                best.berths,
                best.service.model_copy(
                    update={"efficiency": round(best.service.efficiency + offset, 4)}
                ),
            )
            for offset in REFINE_OFFSETS
            if best.service.efficiency + offset > 0.0
        ),
        key=lambda trial: (trial.score, trial.service.efficiency),
    )
    best = min(
        (
            _run_trial(
                slice_,
                base,
                best.berths,
                best.service.model_copy(update={"congestion_alpha": alpha}),
            )
            for alpha in ALPHA_GRID
        ),
        key=lambda trial: (trial.score, trial.service.congestion_alpha),
    )

    notes: list[str] = []
    if abs(best.throughput_error_pct) > THROUGHPUT_TOLERANCE_PCT:
        notes.append(
            f"throughput error {best.throughput_error_pct:+.1f}% exceeds "
            f"+-{THROUGHPUT_TOLERANCE_PCT:.0f}%"
        )
    if best.mean_rolling_wait_days >= HEALTHY_WAIT_DAYS:
        notes.append(
            f"pre-crisis rolling wait {best.mean_rolling_wait_days:.2f} d is not a healthy port"
        )
    if not MIN_UTILISATION <= best.utilisation <= MAX_UTILISATION:
        notes.append(
            f"utilisation {best.utilisation:.2f} outside "
            f"[{MIN_UTILISATION:.2f}, {MAX_UTILISATION:.2f}]"
        )
    if not notes:
        notes.append("all calibration criteria met on the pre-crisis window")

    arrivals = sum(len(day.arrivals) for day in slice_.days) / (len(slice_.days) or 1)
    service_days = best.mean_port_stay_hours / HOURS_PER_DAY - best.mean_wait_days
    erlang = erlang_c_wait_days(arrivals, max(service_days, 1e-9), best.berths)
    observed = sum(day.portcalls_container for day in slice_.days) / (len(slice_.days) or 1)
    return CalibrationReport(
        window=slice_.window,
        fitted=best.service,
        effective_berths=best.berths,
        observed_mean_daily_portcalls=observed,
        simulated_mean_daily_portcalls=observed * (1.0 + best.throughput_error_pct / 100.0),
        throughput_error_pct=best.throughput_error_pct,
        simulated_mean_wait_days=best.mean_wait_days,
        simulated_mean_port_stay_hours=best.mean_port_stay_hours,
        erlang_c_wait_days=erlang if math.isfinite(erlang) else 999.0,
        utilisation=best.utilisation,
        passed=len(notes) == 1 and notes[0].startswith("all calibration"),
        notes=notes,
    )
