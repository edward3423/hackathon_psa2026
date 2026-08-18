"""Discrete-event scaffolding for the fleet simulation.

A heap of events ordered by ``(time, kind rank, sequence)``. The kind rank
fixes what happens when several events land on the same instant, which is
common because day boundaries, policy epochs and berth completions all fall
on round times:

1. ``DAY_BOUNDARY`` - close yesterday's counters, reveal today's arrivals.
2. ``POLICY_EPOCH`` - the policy decides using yesterday's closed history.
3. ``BERTH_END`` - free a berth before anything competes for it.
4. ``BERTH_ACTIVATED`` - reserve capacity comes online.
5. ``ARRIVAL`` - a vessel joins the queue.
6. ``BERTH_START`` - dispatch pump: fill every free berth from the queue.

The sequence number is a per-queue counter, so equal-time equal-kind events
run in insertion order. Nothing in the loop depends on dict or set iteration
order, so a run is reproducible from its seed alone.
"""

import heapq
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Protocol

from cascade.contracts import (
    AgentName,
    Confidence,
    FleetDecisionType,
    FleetPolicyView,
    FleetStrategy,
    QueueDiscipline,
)

DECISION_AGENTS: dict[FleetDecisionType, AgentName] = {
    FleetDecisionType.ACTIVATE_RESERVE_BERTHS: AgentName.YARD,
    FleetDecisionType.SET_QUEUE_DISCIPLINE: AgentName.RECOVERY,
    FleetDecisionType.FAST_CONNECTION_MODE: AgentName.EXECUTION,
    FleetDecisionType.WORKFORCE_SURGE: AgentName.IMPACT,
    FleetDecisionType.HOLD: AgentName.COORDINATOR,
}


class FleetEventKind(IntEnum):
    """Event kinds, valued by their same-instant priority (lower runs first)."""

    DAY_BOUNDARY = 0
    POLICY_EPOCH = 1
    BERTH_END = 2
    BERTH_ACTIVATED = 3
    ARRIVAL = 4
    BERTH_START = 5


@dataclass(frozen=True, slots=True)
class FleetEvent:
    """One scheduled happening. Payload fields are kind-specific and optional."""

    time: datetime
    kind: FleetEventKind
    sequence: int
    vessel_id: str | None = None
    tranche_id: str | None = None


@dataclass(slots=True)
class EventQueue:
    """Minimal deterministic priority queue over ``heapq``."""

    _heap: list[tuple[datetime, int, int, FleetEvent]] = field(default_factory=list)
    _next_sequence: int = 0

    def push(
        self,
        time: datetime,
        kind: FleetEventKind,
        *,
        vessel_id: str | None = None,
        tranche_id: str | None = None,
    ) -> FleetEvent:
        event = FleetEvent(
            time=time,
            kind=kind,
            sequence=self._next_sequence,
            vessel_id=vessel_id,
            tranche_id=tranche_id,
        )
        self._next_sequence += 1
        heapq.heappush(self._heap, (event.time, int(event.kind), event.sequence, event))
        return event

    def pop(self) -> FleetEvent:
        return heapq.heappop(self._heap)[3]

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)


@dataclass(slots=True)
class WaitingVessel:
    """A call sitting in the queue, waiting for a berth."""

    vessel_id: str
    arrival: datetime
    teu: float
    connection_teu: float


def queue_key(discipline: QueueDiscipline, vessel: WaitingVessel) -> tuple[float, float, str]:
    """Ordering within the queue. Always ends in arrival time then vessel id.

    - FCFS: arrival time.
    - CONNECTION_WEIGHTED: most connection TEU first, so transhipment boxes
      make their onward sailings.
    - PRIORITY_DISCHARGE: smallest call first, clearing short calls quickly to
      drain the queue.
    """
    stamp = vessel.arrival.timestamp()
    if discipline is QueueDiscipline.CONNECTION_WEIGHTED:
        return (-vessel.connection_teu, stamp, vessel.vessel_id)
    if discipline is QueueDiscipline.PRIORITY_DISCHARGE:
        return (vessel.teu, stamp, vessel.vessel_id)
    return (stamp, stamp, vessel.vessel_id)


class FleetPolicy(Protocol):
    """Anything that can be asked, once a day, what to do next."""

    def decide(self, view: FleetPolicyView) -> FleetStrategy: ...


class FcfsPolicy:
    """The do-nothing policy: first come, first served, no levers, ever."""

    def decide(self, view: FleetPolicyView) -> FleetStrategy:
        return FleetStrategy(
            decisions=[],
            summary="First come, first served. No capacity or prioritisation levers.",
            confidence=Confidence.HIGH,
        )
