"""Blind-mode enforcement and its audit trail (PRD 9.23).

The point of these tests is that blindness is structural. A future read is
impossible to perform accidentally, there is no back door onto the stream,
and every read that did happen is on the record.
"""

import ast
import importlib.util
from collections.abc import Iterable
from datetime import datetime, time, timedelta

import pytest
from fleet_world import make_blind_slice

from cascade.contracts import ArrivalDay, AuditVerdict, VesselArrival
from cascade.engine.fleet import BlindFeed, FutureReadError, SimClock

FIXTURE_MODULE = "cascade.fixtures"


def make_feed(day_count: int = 5) -> tuple[BlindFeed, SimClock, datetime]:
    blind = make_blind_slice(day_count=day_count)
    start = datetime.combine(blind.window.start, time.min)
    clock = SimClock(start)
    return BlindFeed(blind, clock), clock, start


def test_reading_past_the_clock_raises() -> None:
    feed, clock, start = make_feed()
    clock.advance_to(start + timedelta(days=1))

    assert feed.arrivals_between(start, start + timedelta(days=1))
    with pytest.raises(FutureReadError):
        feed.arrivals_between(start, start + timedelta(days=2))
    with pytest.raises(FutureReadError):
        feed.history_until(start + timedelta(days=3))

    audit = feed.audit()
    assert audit.total_reads == 3
    assert audit.violations == 2
    assert audit.verdict is AuditVerdict.FAIL
    assert audit.max_lookahead_seconds == 2 * 86400.0


def test_clock_is_monotonic_and_owned_by_the_loop() -> None:
    _, clock, start = make_feed()
    clock.advance_to(start + timedelta(days=2))
    assert clock.day_index == 2
    with pytest.raises(ValueError, match="backwards"):
        clock.advance_to(start + timedelta(days=1))


def test_no_public_member_hands_back_the_stream() -> None:
    feed, clock, start = make_feed()
    clock.advance_to(start + timedelta(days=5))

    def holds_arrivals(value: object) -> bool:
        return isinstance(value, ArrivalDay | VesselArrival) or (
            isinstance(value, Iterable)
            and not isinstance(value, str)
            and any(isinstance(item, ArrivalDay | VesselArrival) for item in value)
        )

    public = [name for name in dir(feed) if not name.startswith("_")]
    assert sorted(public) == ["arrivals_between", "audit", "clock", "history_until", "window"]
    for name in public:
        member = getattr(feed, name)
        assert not holds_arrivals(member), f"{name} exposes the stream"

    with pytest.raises(TypeError):
        iter(feed)
    with pytest.raises(TypeError):
        len(feed)  # type: ignore[arg-type]


def test_a_clean_run_audits_every_read_with_zero_lookahead() -> None:
    feed, clock, start = make_feed(day_count=4)
    for offset in range(4):
        clock.advance_to(start + timedelta(days=offset + 1))
        feed.arrivals_between(start + timedelta(days=offset), clock.now)

    audit = feed.audit()
    assert audit.total_reads == 4
    assert audit.violations == 0
    assert audit.max_lookahead_seconds == 0.0
    assert audit.verdict is AuditVerdict.PASS
    assert audit.worst_entry is not None
    assert audit.worst_entry.lookahead_seconds == 0.0


def test_history_only_returns_fully_elapsed_days() -> None:
    feed, clock, start = make_feed(day_count=6)
    clock.advance_to(start + timedelta(days=3))
    history = feed.history_until(clock.now)
    assert [day.date for day in history] == [
        (start + timedelta(days=offset)).date() for offset in range(3)
    ]


# --- import hygiene ---------------------------------------------------------


def module_imports(module_name: str) -> set[str]:
    """First-party imports declared by a module, read from its AST."""
    spec = importlib.util.find_spec(module_name)
    assert spec is not None and spec.origin is not None, module_name
    with open(spec.origin, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=spec.origin)
    found: set[str] = set()
    package = module_name.rsplit(".", 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = f"{package}.{base}" if base else package
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return {name for name in found if name.split(".")[0] == "cascade"}


def reachable_modules(root: str) -> set[str]:
    """Every first-party module reachable from ``root`` by import edges."""
    seen: set[str] = set()
    frontier = [root]
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            spec = importlib.util.find_spec(current)
        except (ImportError, ModuleNotFoundError):
            continue
        if spec is None or spec.origin is None or not spec.origin.endswith(".py"):
            continue
        frontier.extend(module_imports(current) - seen)
    return seen


def test_the_feed_cannot_reach_the_fixture_loader() -> None:
    reachable = reachable_modules("cascade.engine.fleet.feed")
    assert "cascade.contracts" in reachable, "sanity: the walk does follow import edges"
    assert FIXTURE_MODULE not in reachable


def test_policies_module_cannot_reach_the_fixture_loader() -> None:
    module = "cascade.engine.fleet.policies"
    if importlib.util.find_spec(module) is None:
        pytest.skip("policies module not written yet")
    assert FIXTURE_MODULE not in reachable_modules(module)
