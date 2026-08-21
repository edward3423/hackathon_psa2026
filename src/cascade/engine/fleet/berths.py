"""Berth capacity and the admissibility rules for changing it.

The pool holds a number of active berths plus reserve tranches that can be
brought online. Two properties matter for the honesty of the benchmark:

- Capacity never increases retroactively. ``activate`` only schedules an
  effective date; the count changes when ``apply_activation`` is called by
  the ``BERTH_ACTIVATED`` event at that date, never before.
- A rejected lever is reported, not raised. Policies propose; the engine
  decides, records the reason, and carries on.

``validate_fleet_decision`` lives here because most of what it guards is
capacity: tranche existence, availability dates, double activation. It also
covers the non-capacity levers so that every decision passes through one
gate.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta

from cascade.contracts import (
    FleetDecision,
    FleetDecisionType,
    FleetPolicyView,
    FleetWorldConfig,
    PendingActivation,
    ReserveBerthTranche,
)

MAX_SURGE_LEVEL = 2
LEVER_COOLDOWN_DAYS = 1


@dataclass(frozen=True, slots=True)
class ActivationOutcome:
    """Result of proposing an activation: accepted with a date, or a reason."""

    accepted: bool
    reason: str | None = None
    effective_date: date | None = None


@dataclass(slots=True)
class BerthPool:
    """Active berths, in-service occupancy, and scheduled reserve capacity."""

    active: int
    busy: int = 0
    lead_override_days: int | None = None
    _tranches: dict[str, ReserveBerthTranche] = field(default_factory=dict)
    _pending: dict[str, PendingActivation] = field(default_factory=dict)
    _activated: set[str] = field(default_factory=set)
    _order: list[str] = field(default_factory=list)

    @classmethod
    def from_config(cls, world: FleetWorldConfig) -> "BerthPool":
        active = max(1, world.berths.active_berths + world.berth_delta)
        pool = cls(active=active, lead_override_days=world.activation_lead_override_days)
        for tranche in world.berths.reserve_tranches:
            pool._tranches[tranche.tranche_id] = tranche
            pool._order.append(tranche.tranche_id)
        return pool

    # --- occupancy ---------------------------------------------------------

    @property
    def free(self) -> int:
        return max(0, self.active - self.busy)

    def occupy(self) -> None:
        if self.busy >= self.active:
            raise RuntimeError("no free berth to occupy")
        self.busy += 1

    def release(self) -> None:
        if self.busy <= 0:
            raise RuntimeError("no occupied berth to release")
        self.busy -= 1

    # --- reserves ----------------------------------------------------------

    def tranche(self, tranche_id: str) -> ReserveBerthTranche | None:
        return self._tranches.get(tranche_id)

    def available(self) -> list[ReserveBerthTranche]:
        """Tranches that are neither already online nor already scheduled."""
        return [
            self._tranches[key]
            for key in self._order
            if key not in self._activated and key not in self._pending
        ]

    def pending(self) -> list[PendingActivation]:
        return [self._pending[key] for key in self._order if key in self._pending]

    def lead_days(self, tranche: ReserveBerthTranche) -> int:
        override = self.lead_override_days
        return tranche.activation_lead_days if override is None else override

    def effective_date(self, tranche: ReserveBerthTranche, on_date: date) -> date:
        earliest = on_date + timedelta(days=self.lead_days(tranche))
        if tranche.available_from is not None:
            earliest = max(earliest, tranche.available_from)
        return earliest

    def check_activation(self, tranche_id: str, on_date: date) -> str | None:
        """Reason this activation cannot be scheduled, or None if it can."""
        tranche = self._tranches.get(tranche_id)
        if tranche is None:
            return f"unknown reserve tranche {tranche_id!r}"
        if tranche_id in self._activated:
            return f"tranche {tranche_id!r} is already active"
        if tranche_id in self._pending:
            return f"tranche {tranche_id!r} activation is already pending"
        if tranche.available_from is not None and on_date < tranche.available_from:
            return f"tranche {tranche_id!r} is not available before {tranche.available_from}"
        return None

    def activate(self, tranche_id: str, on_date: date) -> ActivationOutcome:
        """Schedule a tranche. Capacity changes later, at the effective date."""
        reason = self.check_activation(tranche_id, on_date)
        if reason is not None:
            return ActivationOutcome(accepted=False, reason=reason)
        tranche = self._tranches[tranche_id]
        effective = self.effective_date(tranche, on_date)
        self._pending[tranche_id] = PendingActivation(
            tranche_id=tranche_id, berths=tranche.berths, effective_date=effective
        )
        return ActivationOutcome(accepted=True, effective_date=effective)

    def apply_activation(self, tranche_id: str) -> int:
        """Bring a scheduled tranche online. Returns the new active count."""
        pending = self._pending.pop(tranche_id, None)
        if pending is None:
            raise RuntimeError(f"tranche {tranche_id!r} has no pending activation")
        self._activated.add(tranche_id)
        self.active += pending.berths
        return self.active


def validate_fleet_decision(
    decision: FleetDecision,
    view: FleetPolicyView,
    world: FleetWorldConfig,
    *,
    last_pulled: Mapping[FleetDecisionType, date] | None = None,
) -> str | None:
    """Reject a proposed lever, or return None if it may be applied today.

    Guards: surge bounds, tranche existence and availability, double or
    pending activation, no retroactive effect (an activation lead is never
    negative), and a one-day cooldown so the same lever cannot be pulled on
    consecutive days.
    """
    pulled = last_pulled or {}
    previous = pulled.get(decision.type)
    if (
        decision.type is not FleetDecisionType.HOLD
        and previous is not None
        and (view.today - previous).days <= LEVER_COOLDOWN_DAYS
    ):
        until = previous + timedelta(days=LEVER_COOLDOWN_DAYS + 1)
        return f"{decision.type} is in cooldown until {until}"

    if decision.type is FleetDecisionType.HOLD:
        return None

    if decision.type is FleetDecisionType.WORKFORCE_SURGE:
        level = decision.surge_level
        if level is None:
            return "WORKFORCE_SURGE requires surge_level"
        if not 0 <= level <= MAX_SURGE_LEVEL:
            return f"surge level {level} outside 0..{MAX_SURGE_LEVEL}"
        if level == view.workforce_surge_level:
            return f"workforce surge is already at level {level}"
        return None

    if decision.type is FleetDecisionType.SET_QUEUE_DISCIPLINE:
        if decision.discipline is None:
            return "SET_QUEUE_DISCIPLINE requires discipline"
        if decision.discipline is view.queue_discipline:
            return f"queue discipline is already {decision.discipline}"
        return None

    if decision.type is FleetDecisionType.FAST_CONNECTION_MODE:
        if decision.enabled is None:
            return "FAST_CONNECTION_MODE requires enabled"
        if decision.enabled is view.fast_connection_mode:
            return f"fast connection mode is already {'on' if decision.enabled else 'off'}"
        return None

    tranche_id = decision.tranche_id
    if tranche_id is None:
        return "ACTIVATE_RESERVE_BERTHS requires tranche_id"
    known = {tranche.tranche_id: tranche for tranche in world.berths.reserve_tranches}
    tranche = known.get(tranche_id)
    if tranche is None:
        return f"unknown reserve tranche {tranche_id!r}"
    if any(pending.tranche_id == tranche_id for pending in view.pending_activations):
        return f"tranche {tranche_id!r} activation is already pending"
    if tranche_id not in {available.tranche_id for available in view.reserves_available}:
        return f"tranche {tranche_id!r} is already active"
    if tranche.available_from is not None and view.today < tranche.available_from:
        return f"tranche {tranche_id!r} is not available before {tranche.available_from}"
    lead = (
        tranche.activation_lead_days
        if world.activation_lead_override_days is None
        else world.activation_lead_override_days
    )
    if lead < 0:
        return "activation lead cannot be negative"
    return None
