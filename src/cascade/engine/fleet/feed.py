"""Blind arrival feed and the simulation clock that gates it.

The benchmark claims the simulated arms never see the crisis before it
happens. That claim is enforced here by construction rather than by
convention:

- ``SimClock`` is the single source of simulated time. It is monotonic and
  only the simulation loop advances it. Nothing reads a system clock.
- ``BlindFeed`` wraps a ``BlindSlice`` behind exactly two read methods,
  ``arrivals_between`` and ``history_until``. Any read whose upper bound is
  later than ``clock.now`` raises ``FutureReadError``. There is no accessor
  that hands back the slice, no length, and iteration is refused, so a caller
  cannot route around the gate.
- Every read - accepted or refused - is appended to an audit log that ships
  inside the benchmark result.

Clock resolution. The operating day is the unit of information in this model:
a port knows the manifest of the day it has entered, and nothing beyond it.
The loop therefore advances the clock to the *end* of day ``d`` when it
reaches day ``d`` and then reveals day ``d``. ``clock.now`` is the revealed
horizon, and ``lookahead_seconds`` measures reads beyond that horizon. A clean
run reads nothing past the day it is currently simulating, so every entry has
``lookahead_seconds == 0.0``.
"""

from bisect import bisect_right
from datetime import date, datetime, timedelta
from typing import Never

from cascade.contracts import (
    ArrivalDay,
    AuditVerdict,
    BlindAuditEntry,
    BlindAuditSummary,
    BlindSlice,
    DateWindow,
    VesselArrival,
)


class FutureReadError(Exception):
    """Raised when a caller asks the feed for data past the clock."""


class SimClock:
    """Monotonic simulated time. Only the simulation loop advances it."""

    def __init__(self, start: datetime) -> None:
        self._start = start
        self._now = start

    @property
    def start(self) -> datetime:
        return self._start

    @property
    def now(self) -> datetime:
        return self._now

    @property
    def day_index(self) -> int:
        """Whole days elapsed since the start of the run."""
        return max(0, (self._now - self._start).days)

    def advance_to(self, moment: datetime) -> None:
        """Move time forward. Moving backwards is a programming error."""
        if moment < self._now:
            raise ValueError(f"clock cannot move backwards: {moment} < {self._now}")
        self._now = moment


class BlindFeed:
    """The only door onto the crisis arrival stream."""

    def __init__(self, slice_: BlindSlice, clock: SimClock) -> None:
        ordered = sorted(slice_.days, key=lambda day: day.date)
        self.__days: tuple[ArrivalDay, ...] = tuple(ordered)
        self.__dates: tuple[date, ...] = tuple(day.date for day in ordered)
        self.__by_date: dict[date, ArrivalDay] = {day.date: day for day in ordered}
        self.__window = slice_.window
        self._clock = clock
        self._entries: list[BlindAuditEntry] = []
        self._violations = 0

    @property
    def clock(self) -> SimClock:
        """The clock this feed is gated by. The simulation loop owns advancing it."""
        return self._clock

    @property
    def window(self) -> DateWindow:
        """The blind window's label and bounds. Carries no arrival data."""
        return self.__window

    def arrivals_between(self, t0: datetime, t1: datetime) -> list[VesselArrival]:
        """Arrivals with ``t0 <= arrival < t1``, ordered by time then vessel id."""
        self._record(t1)
        found: list[VesselArrival] = []
        cursor = t0.date()
        while cursor <= t1.date():
            day = self.__by_date.get(cursor)
            if day is not None:
                found.extend(a for a in day.arrivals if t0 <= a.arrival < t1)
            cursor += timedelta(days=1)
        found.sort(key=lambda arrival: (arrival.arrival, arrival.vessel_id))
        return found

    def history_until(self, now: datetime) -> list[ArrivalDay]:
        """Every arrival day that has fully elapsed at ``now``."""
        self._record(now)
        cutoff = (now - timedelta(days=1)).date()
        return list(self.__days[: bisect_right(self.__dates, cutoff)])

    def audit(self) -> BlindAuditSummary:
        """Summarise every read attempted against this feed."""
        worst = max(self._entries, key=lambda e: e.lookahead_seconds, default=None)
        return BlindAuditSummary(
            total_reads=len(self._entries),
            max_lookahead_seconds=worst.lookahead_seconds if worst is not None else 0.0,
            violations=self._violations,
            verdict=AuditVerdict.FAIL if self._violations else AuditVerdict.PASS,
            worst_entry=worst,
        )

    def _record(self, requested_until: datetime) -> None:
        now = self._clock.now
        lookahead = max(0.0, (requested_until - now).total_seconds())
        self._entries.append(
            BlindAuditEntry(
                day_index=self._clock.day_index,
                clock=now,
                requested_until=requested_until,
                lookahead_seconds=lookahead,
            )
        )
        if lookahead > 0.0:
            self._violations += 1
            raise FutureReadError(
                f"read until {requested_until} is {lookahead:.0f}s past the clock at {now}"
            )

    def __iter__(self) -> Never:
        raise TypeError("BlindFeed is not iterable: use arrivals_between or history_until")
