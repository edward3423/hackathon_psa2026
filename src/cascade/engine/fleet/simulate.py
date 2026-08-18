"""The fleet discrete-event simulation loop.

One arm of the benchmark is one call to :func:`simulate`. The loop owns the
clock, the berth pool, the waiting queue and the event heap; the policy owns
nothing but its opinion, delivered once a day through a ``FleetPolicyView``
that contains no future.

Day structure, all at 00:00 of day d (see ``events.FleetEventKind`` for the
tie-break order):

1. ``DAY_BOUNDARY`` closes day d-1 into a ``DayCounters`` snapshot, checks
   conservation, then advances the clock into day d and pulls exactly that
   day's arrivals from the blind feed.
2. ``POLICY_EPOCH`` shows the policy the closed history and applies whatever
   survives ``validate_fleet_decision``.

Everything else is driven by the vessels themselves. After the last day the
loop keeps running until the queue drains, so every arrival is accounted for.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from random import Random

from cascade.contracts import (
    BlindAuditSummary,
    DailyKpi,
    DateWindow,
    DecisionSource,
    FleetDecision,
    FleetDecisionType,
    FleetPolicyView,
    FleetWorldConfig,
    QueueDiscipline,
    RecordedDecision,
    VesselArrival,
)
from cascade.engine.fleet.berths import BerthPool, validate_fleet_decision
from cascade.engine.fleet.events import (
    DECISION_AGENTS,
    EventQueue,
    FleetEvent,
    FleetEventKind,
    FleetPolicy,
    WaitingVessel,
    queue_key,
)
from cascade.engine.fleet.feed import BlindFeed
from cascade.engine.fleet.metrics import DailyKpiBuilder, DayCounters, VesselRecord
from cascade.engine.fleet.service import service_hours

MIDNIGHT = time.min


@dataclass(frozen=True, slots=True)
class SimulationOutcome:
    """Everything one arm produced. Metrics are computed from it, not in it."""

    daily: list[DailyKpi]
    records: list[VesselRecord]
    counters: list[DayCounters]
    decisions: list[RecordedDecision]
    blind_audit: BlindAuditSummary


@dataclass(slots=True)
class _Run:
    """Mutable state of one simulation. Created and discarded per arm."""

    world: FleetWorldConfig
    feed: BlindFeed
    policy: FleetPolicy
    window: DateWindow
    source: DecisionSource
    pool: BerthPool
    rng: Random
    builder: DailyKpiBuilder = field(default_factory=DailyKpiBuilder)
    events: EventQueue = field(default_factory=EventQueue)
    queue: list[WaitingVessel] = field(default_factory=list)
    pending: dict[str, VesselArrival] = field(default_factory=dict)
    daily: list[DailyKpi] = field(default_factory=list)
    waits_today: list[float] = field(default_factory=list)
    in_service: dict[str, tuple[WaitingVessel, datetime]] = field(default_factory=dict)
    live: list[tuple[datetime, datetime]] = field(default_factory=list)
    records: list[VesselRecord] = field(default_factory=list)
    counters: list[DayCounters] = field(default_factory=list)
    decisions: list[RecordedDecision] = field(default_factory=list)
    last_pulled: dict[FleetDecisionType, date] = field(default_factory=dict)
    discipline: QueueDiscipline = QueueDiscipline.FCFS
    fast_connection: bool = False
    surge_level: int = 0
    day: date | None = None
    day_index: int = 0
    arrivals_today: int = 0
    berthings_today: int = 0
    departures_today: int = 0
    total_arrived: int = 0
    total_departed: int = 0

    # --- day boundaries ----------------------------------------------------

    def close_day(self, boundary: datetime) -> None:
        if self.day is None:
            return
        day_start = datetime.combine(self.day, MIDNIGHT)
        busy_hours = 0.0
        remaining: list[tuple[datetime, datetime]] = []
        for start, end in self.live:
            overlap = min(end, boundary) - max(start, day_start)
            busy_hours += max(0.0, overlap.total_seconds() / 3600.0)
            if end > boundary:
                remaining.append((start, end))
        self.live = remaining
        if self.total_arrived != self.total_departed + len(self.in_service) + len(self.queue):
            raise RuntimeError(f"conservation violated at {boundary}")
        counter = DayCounters(
            date=self.day,
            day_index=self.day_index,
            arrivals=self.arrivals_today,
            berthings=self.berthings_today,
            departures=self.departures_today,
            queue_length=len(self.queue),
            in_service=len(self.in_service),
            active_berths=self.pool.active,
            teu_waiting=sum(vessel.teu for vessel in self.queue),
            busy_berth_hours=busy_hours,
        )
        self.counters.append(counter)
        self.daily.append(self.builder.add(counter, self.waits_today))
        self.arrivals_today = 0
        self.berthings_today = 0
        self.departures_today = 0
        self.waits_today = []

    def open_day(self, day: date, day_index: int) -> None:
        self.day = day
        self.day_index = day_index
        if day > self.window.end:
            return
        day_start = datetime.combine(day, MIDNIGHT)
        horizon = day_start + timedelta(days=1)
        self.feed.clock.advance_to(horizon)
        for arrival in self.feed.arrivals_between(day_start, horizon):
            self.events.push(
                self.jitter(arrival, day_start),
                FleetEventKind.ARRIVAL,
                vessel_id=arrival.vessel_id,
            )
            self.pending[arrival.vessel_id] = arrival

    def jitter(self, arrival: VesselArrival, floor: datetime) -> datetime:
        hours = self.world.arrival_jitter_hours
        if hours <= 0.0:
            return arrival.arrival
        shifted = arrival.arrival + timedelta(hours=self.rng.uniform(-hours, hours))
        return max(shifted, floor)

    # --- vessel lifecycle --------------------------------------------------

    def on_arrival(self, event: FleetEvent) -> None:
        arrival = self.pending.pop(str(event.vessel_id))
        self.queue.append(
            WaitingVessel(
                vessel_id=arrival.vessel_id,
                arrival=event.time,
                teu=arrival.teu,
                connection_teu=arrival.connection_teu,
            )
        )
        self.arrivals_today += 1
        self.total_arrived += 1

    def dispatch(self, now: datetime) -> None:
        while self.queue and self.pool.free > 0:
            index = min(
                range(len(self.queue)),
                key=lambda i: queue_key(self.discipline, self.queue[i]),
            )
            vessel = self.queue.pop(index)
            hours = service_hours(
                teu=vessel.teu,
                connection_teu=vessel.connection_teu,
                queue_length=len(self.queue),
                service=self.world.service,
                surge_level=self.surge_level,
                fast_connection=self.fast_connection,
                rate_multiplier=self.world.service_rate_multiplier,
            )
            end = now + timedelta(hours=hours)
            self.pool.occupy()
            self.in_service[vessel.vessel_id] = (vessel, now)
            self.live.append((now, end))
            self.berthings_today += 1
            self.waits_today.append((now - vessel.arrival).total_seconds() / 86400.0)
            self.events.push(end, FleetEventKind.BERTH_END, vessel_id=vessel.vessel_id)

    def on_berth_end(self, event: FleetEvent) -> None:
        vessel, started = self.in_service.pop(str(event.vessel_id))
        self.pool.release()
        self.records.append(
            VesselRecord(
                vessel_id=vessel.vessel_id,
                arrival=vessel.arrival,
                berth_start=started,
                berth_end=event.time,
                teu=vessel.teu,
                connection_teu=vessel.connection_teu,
            )
        )
        self.departures_today += 1
        self.total_departed += 1

    # --- policy ------------------------------------------------------------

    def view(self, today: date, daily: list[DailyKpi]) -> FleetPolicyView:
        # model_construct: every field is engine-built and already typed, and
        # a run can hold thousands of days of history to re-validate daily.
        return FleetPolicyView.model_construct(
            today=today,
            day_index=self.day_index,
            history=daily,
            active_berths=self.pool.active,
            reserves_available=self.pool.available(),
            pending_activations=self.pool.pending(),
            queue_discipline=self.discipline,
            fast_connection_mode=self.fast_connection,
            workforce_surge_level=self.surge_level,
        )

    def apply(self, decision: FleetDecision, view: FleetPolicyView) -> RecordedDecision:
        today = view.today
        reason = validate_fleet_decision(decision, view, self.world, last_pulled=self.last_pulled)
        effective: date | None = None
        if reason is None:
            effective = today
            if decision.type is FleetDecisionType.ACTIVATE_RESERVE_BERTHS:
                outcome = self.pool.activate(str(decision.tranche_id), today)
                reason, effective = outcome.reason, outcome.effective_date
                if outcome.accepted and outcome.effective_date is not None:
                    self.events.push(
                        datetime.combine(outcome.effective_date, MIDNIGHT),
                        FleetEventKind.BERTH_ACTIVATED,
                        tranche_id=decision.tranche_id,
                    )
            elif decision.type is FleetDecisionType.SET_QUEUE_DISCIPLINE and (
                decision.discipline is not None
            ):
                self.discipline = decision.discipline
            elif decision.type is FleetDecisionType.FAST_CONNECTION_MODE:
                self.fast_connection = bool(decision.enabled)
            elif decision.type is FleetDecisionType.WORKFORCE_SURGE:
                self.surge_level = int(decision.surge_level or 0)
            if reason is None and decision.type is not FleetDecisionType.HOLD:
                self.last_pulled[decision.type] = today
        return RecordedDecision(
            date=today,
            day_index=self.day_index,
            agent=DECISION_AGENTS[decision.type],
            decision=decision,
            accepted=reason is None,
            rejection_reason=reason,
            source=self.source,
            effective_date=effective if reason is None else None,
        )

    def on_policy_epoch(self, today: date) -> None:
        view = self.view(today, self.daily)
        for decision in self.policy.decide(view).decisions:
            self.decisions.append(self.apply(decision, view))


def simulate(
    world: FleetWorldConfig,
    feed: BlindFeed,
    policy: FleetPolicy,
    *,
    window: DateWindow,
    rolling_window_days: int = 3,
    decision_source: DecisionSource = DecisionSource.SCRIPTED,
) -> SimulationOutcome:
    """Run one arm over ``window`` and return everything it produced."""
    run = _Run(
        world=world,
        feed=feed,
        policy=policy,
        window=window,
        source=decision_source,
        pool=BerthPool.from_config(world),
        rng=Random(world.seed),
        builder=DailyKpiBuilder(rolling_window_days),
    )
    days = (window.end - window.start).days + 1
    for offset in range(days + 1):
        moment = datetime.combine(window.start + timedelta(days=offset), MIDNIGHT)
        run.events.push(moment, FleetEventKind.DAY_BOUNDARY)
        if offset < days:
            run.events.push(moment, FleetEventKind.POLICY_EPOCH)

    while run.events:
        event = run.events.pop()
        if event.kind is FleetEventKind.DAY_BOUNDARY:
            run.close_day(event.time)
            run.open_day(event.time.date(), (event.time.date() - window.start).days)
        elif event.kind is FleetEventKind.POLICY_EPOCH:
            run.on_policy_epoch(event.time.date())
        elif event.kind is FleetEventKind.BERTH_END:
            run.on_berth_end(event)
        elif event.kind is FleetEventKind.BERTH_ACTIVATED:
            run.pool.apply_activation(str(event.tranche_id))
        elif event.kind is FleetEventKind.ARRIVAL:
            run.on_arrival(event)
        if event.kind is not FleetEventKind.DAY_BOUNDARY:
            run.dispatch(event.time)

    return SimulationOutcome(
        daily=run.daily,
        records=run.records,
        counters=run.counters,
        decisions=run.decisions,
        blind_audit=feed.audit(),
    )
