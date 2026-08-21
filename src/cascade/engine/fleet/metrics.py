"""The single calculation path for every displayed fleet figure.

Nothing else in the benchmark is allowed to compute a headline number. The
definitions, once, here:

- wait = berth start - arrival. This is what Linerlytica reported as
  "berthing delays".
- port stay = berth end - arrival. This is what PSA reported as "+22%".
- ``rolling_wait_days`` for a day = mean wait of the vessels that *berthed*
  in the trailing ``rolling_window_days`` (that day inclusive). A day with no
  berthings carries the previous value forward rather than dropping to zero,
  so the series measures the port's condition, not its sample size.
- ``peak_wait_days`` / ``peak_wait_date`` are the maximum of that rolling
  series and the first date attaining it.
- ``recovery_date`` is the first date strictly after the peak whose rolling
  wait is at or below ``recovery_threshold_days`` and stays there for
  ``recovery_sustain_days`` consecutive days; None if that never happens.
- ``port_stay_inflation_pct`` compares mean port stay against a baseline the
  caller supplies (the calibration figure). This module never reads a
  fixture.
- ``missed_connection_proxy`` is a PROXY, not a count of real missed boxes:
  the number of vessels carrying connection TEU whose wait exceeded
  ``CONNECTION_BUFFER_DAYS``, the slack a transhipment box is assumed to have
  before its onward sailing leaves without it.
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from cascade.contracts import DailyKpi, FleetMetrics

TWO_DAY_WAIT_THRESHOLD = 2.0
CONNECTION_BUFFER_DAYS = 1.0
HOURS_PER_DAY = 24.0


@dataclass(frozen=True, slots=True)
class VesselRecord:
    """One completed call. Waits are derived, never stored twice."""

    vessel_id: str
    arrival: datetime
    berth_start: datetime
    berth_end: datetime
    teu: float
    connection_teu: float

    @property
    def wait_days(self) -> float:
        return (self.berth_start - self.arrival).total_seconds() / 86400.0

    @property
    def port_stay_hours(self) -> float:
        return (self.berth_end - self.arrival).total_seconds() / 3600.0


@dataclass(frozen=True, slots=True)
class DayCounters:
    """End-of-day snapshot the simulation loop hands to this module."""

    date: date
    day_index: int
    arrivals: int
    berthings: int
    departures: int
    queue_length: int
    in_service: int
    active_berths: int
    teu_waiting: float
    busy_berth_hours: float


class DailyKpiBuilder:
    """Streams counters into ``DailyKpi`` rows, one day at a time.

    The simulation appends a day as it closes it, so the rolling mean is
    maintained incrementally rather than recomputed for every policy epoch.
    """

    def __init__(self, rolling_window_days: int = 3) -> None:
        if rolling_window_days < 1:
            raise ValueError("rolling_window_days must be at least 1")
        self._span = rolling_window_days
        self._window: deque[tuple[float, int]] = deque()
        self._sum = 0.0
        self._count = 0
        self._previous = 0.0

    def add(self, counter: DayCounters, waits: Sequence[float]) -> DailyKpi:
        day_sum = sum(waits)
        self._window.append((day_sum, len(waits)))
        self._sum += day_sum
        self._count += len(waits)
        while len(self._window) > self._span:
            old_sum, old_count = self._window.popleft()
            self._sum -= old_sum
            self._count -= old_count
        rolling = self._sum / self._count if self._count else self._previous
        self._previous = rolling
        capacity_hours = counter.active_berths * HOURS_PER_DAY
        return DailyKpi(
            date=counter.date,
            day_index=counter.day_index,
            arrivals=counter.arrivals,
            berthings=counter.berthings,
            departures=counter.departures,
            queue_length=counter.queue_length,
            mean_wait_days=(day_sum / len(waits)) if waits else 0.0,
            rolling_wait_days=max(0.0, rolling),
            active_berths=counter.active_berths,
            teu_waiting=counter.teu_waiting,
            utilisation=(
                min(1.0, counter.busy_berth_hours / capacity_hours) if capacity_hours > 0 else 0.0
            ),
        )


def build_daily_kpis(
    counters: list[DayCounters],
    records: list[VesselRecord],
    *,
    rolling_window_days: int = 3,
) -> list[DailyKpi]:
    """Turn engine counters plus completed calls into the daily KPI series."""
    waits_by_date: dict[date, list[float]] = {}
    for record in records:
        waits_by_date.setdefault(record.berth_start.date(), []).append(record.wait_days)
    builder = DailyKpiBuilder(rolling_window_days)
    return [builder.add(counter, waits_by_date.get(counter.date, [])) for counter in counters]


def _recovery_date(
    daily: list[DailyKpi], peak_index: int, threshold: float, sustain_days: int
) -> date | None:
    for start in range(peak_index + 1, len(daily)):
        window = daily[start : start + sustain_days]
        if len(window) < sustain_days:
            return None
        if all(day.rolling_wait_days <= threshold for day in window):
            return window[0].date
    return None


def compute_metrics(
    daily: list[DailyKpi],
    records: list[VesselRecord],
    *,
    baseline_port_stay_hours: float,
    charter_rate_usd_per_day: float,
    recovery_threshold_days: float = 2.0,
    recovery_sustain_days: int = 5,
) -> FleetMetrics:
    """Every headline figure for one arm, from one place."""
    if not daily:
        raise ValueError("cannot compute metrics without a daily series")

    peak_index = max(range(len(daily)), key=lambda i: (daily[i].rolling_wait_days, -i))
    peak = daily[peak_index]
    waits = [record.wait_days for record in records]
    stays = [record.port_stay_hours for record in records]
    mean_stay = sum(stays) / len(stays) if stays else 0.0
    inflation = (
        (mean_stay / baseline_port_stay_hours - 1.0) * 100.0
        if baseline_port_stay_hours > 0
        else 0.0
    )
    return FleetMetrics(
        peak_wait_days=max(0.0, peak.rolling_wait_days),
        peak_wait_date=peak.date,
        recovery_date=_recovery_date(
            daily, peak_index, recovery_threshold_days, recovery_sustain_days
        ),
        days_above_two_day_wait=sum(
            1 for day in daily if day.rolling_wait_days > TWO_DAY_WAIT_THRESHOLD
        ),
        mean_wait_days=max(0.0, sum(waits) / len(waits)) if waits else 0.0,
        mean_port_stay_hours=max(0.0, mean_stay),
        port_stay_inflation_pct=inflation,
        vessels_served=len(records),
        teu_served=sum(record.teu for record in records),
        missed_connection_proxy=sum(
            1
            for record in records
            if record.connection_teu > 0.0 and record.wait_days > CONNECTION_BUFFER_DAYS
        ),
        wait_cost_usd=max(0.0, sum(waits) * charter_rate_usd_per_day),
    )
