"""In-memory arrival streams and world configs for the fleet engine tests.

Deliberately independent of ``fixtures/crisis_arrivals.json``: the engine tests
must run before, and without, the data pipeline. Everything is seeded, so two
calls with the same arguments produce equal objects.
"""

from datetime import date, timedelta
from random import Random

from cascade.contracts import (
    ArrivalDay,
    BerthPoolConfig,
    BlindSlice,
    CalibrationSlice,
    DateWindow,
    FleetWorldConfig,
    ReserveBerthTranche,
    ServiceModelConfig,
    VesselArrival,
)
from cascade.engine.fleet.feed import day_start

START = date(2024, 4, 1)


def make_service_config(**overrides: float) -> ServiceModelConfig:
    """A service model that berths a 1,400 TEU call in roughly 12 hours."""
    fields: dict[str, float] = {
        "base_hours": 2.0,
        "cranes_per_berth": 3.0,
        "moves_per_crane_hour": 28.0,
        "teu_per_move": 1.6,
        "efficiency": 1.0,
        "congestion_alpha": 0.15,
        "congestion_queue_ref": 10.0,
        "congestion_cap": 3.0,
        "surge_alpha_factor": 0.6,
        "surge_efficiency_gain": 0.08,
        "fast_connection_speedup": 0.75,
    }
    fields.update(overrides)
    return ServiceModelConfig(**fields)


def make_tranche(
    tranche_id: str = "keppel-1",
    berths: int = 2,
    activation_lead_days: int = 10,
    available_from: date | None = None,
) -> ReserveBerthTranche:
    return ReserveBerthTranche(
        tranche_id=tranche_id,
        label=f"Reserve tranche {tranche_id}",
        berths=berths,
        activation_lead_days=activation_lead_days,
        available_from=available_from,
        basis="test fixture",
    )


def make_world_config(
    *,
    seed: int = 42,
    active_berths: int = 8,
    tranches: list[ReserveBerthTranche] | None = None,
    service: ServiceModelConfig | None = None,
    **overrides: float | int | None,
) -> FleetWorldConfig:
    return FleetWorldConfig(
        seed=seed,
        berths=BerthPoolConfig(
            active_berths=active_berths, reserve_tranches=tranches or [make_tranche()]
        ),
        service=service or make_service_config(),
        **overrides,
    )


def make_arrival_day(
    day: date,
    count: int,
    rng: Random,
    *,
    teu_mean: float = 1400.0,
    connection_share: float = 0.4,
    prefix: str = "V",
) -> ArrivalDay:
    """One day of calls spread uniformly over 24 hours, seeded sizes."""
    arrivals: list[VesselArrival] = []
    midnight = day_start(day)
    for index in range(count):
        teu = max(150.0, rng.lognormvariate(0.0, 0.45) * teu_mean)
        arrivals.append(
            VesselArrival(
                vessel_id=f"{prefix}-{day.isoformat()}-{index:03d}",
                arrival=midnight + timedelta(hours=rng.uniform(0.0, 24.0)),
                teu=round(teu, 2),
                connection_teu=round(teu * connection_share, 2),
            )
        )
    arrivals.sort(key=lambda arrival: (arrival.arrival, arrival.vessel_id))
    return ArrivalDay(date=day, portcalls_container=count, arrivals=arrivals)


def _days(
    start: date, day_count: int, per_day: int, seed: int, teu_mean: float, prefix: str
) -> list[ArrivalDay]:
    rng = Random(seed)
    return [
        make_arrival_day(
            start + timedelta(days=offset), per_day, rng, teu_mean=teu_mean, prefix=prefix
        )
        for offset in range(day_count)
    ]


def make_calibration_slice(
    *,
    start: date = date(2023, 1, 1),
    day_count: int = 60,
    per_day: int = 12,
    seed: int = 7,
    teu_mean: float = 1400.0,
) -> CalibrationSlice:
    window = DateWindow(
        label="test calibration", start=start, end=start + timedelta(days=day_count - 1)
    )
    return CalibrationSlice(
        window=window, days=_days(start, day_count, per_day, seed, teu_mean, "C")
    )


def make_blind_slice(
    *,
    start: date = START,
    day_count: int = 30,
    per_day: int = 12,
    seed: int = 11,
    teu_mean: float = 1400.0,
    surge_days: range | None = None,
    surge_extra: int = 6,
) -> BlindSlice:
    """A blind window, optionally with a congestion hump over ``surge_days``."""
    rng = Random(seed)
    days: list[ArrivalDay] = []
    for offset in range(day_count):
        count = per_day + (surge_extra if surge_days and offset in surge_days else 0)
        days.append(
            make_arrival_day(
                start + timedelta(days=offset), count, rng, teu_mean=teu_mean, prefix="B"
            )
        )
    window = DateWindow(label="test blind", start=start, end=start + timedelta(days=day_count - 1))
    return BlindSlice(window=window, days=days)


def poisson_arrival_slice(
    *,
    vessels: int,
    arrival_rate_per_day: float,
    mean_teu: float,
    seed: int = 3,
    start: date = date(2024, 1, 1),
) -> BlindSlice:
    """Poisson arrivals with exponential call sizes, for the M/M/c check.

    Interarrival gaps are exponential and TEU is exponential, so with
    ``base_hours = 0`` and ``congestion_alpha = 0`` the service time is
    exponential too and the queue is a textbook M/M/c.
    """
    rng = Random(seed)
    midnight = day_start(start)
    by_date: dict[date, list[VesselArrival]] = {}
    offset_days = 0.0
    for index in range(vessels):
        offset_days += rng.expovariate(arrival_rate_per_day)
        moment = midnight + timedelta(days=offset_days)
        by_date.setdefault(moment.date(), []).append(
            VesselArrival(
                vessel_id=f"P-{index:06d}",
                arrival=moment,
                teu=rng.expovariate(1.0 / mean_teu),
                connection_teu=0.0,
            )
        )
    last = midnight + timedelta(days=offset_days)
    days = [
        ArrivalDay(
            date=start + timedelta(days=offset),
            portcalls_container=len(by_date.get(start + timedelta(days=offset), [])),
            arrivals=by_date.get(start + timedelta(days=offset), []),
        )
        for offset in range((last.date() - start).days + 1)
    ]
    window = DateWindow(label="poisson", start=start, end=last.date())
    return BlindSlice(window=window, days=days)
