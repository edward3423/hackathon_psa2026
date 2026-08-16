"""Regenerate the golden event fixtures from a deterministic LIVE_STUB run.

Rewrites fixtures/fake_agent_events.json and fixtures/replay_events.json with
the complete contract-valid event sequence: parallel assessment, dispute pause,
human constraint, sailing timeout fallback, plan revision cycle, approval, and
mocked dispatch receipts.

Run: uv run python scripts/capture_replay.py
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cascade.agents.scripted import ScriptedBrain
from cascade.contracts import (
    ApprovalDecision,
    ApprovalRequest,
    DisputeResolutionRequest,
    PlanArchetype,
    RunMode,
    ScenarioControls,
    WorkflowStage,
)
from cascade.tools.fake_toolbox import FakeToolBox
from cascade.workflow import WorkflowRun, scenario_with_controls

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

CONSTRAINT = (
    "Respect the physical reefer plug limit of 150; rush at most 34 pharmaceutical "
    "reefers and rebook the remainder."
)


class TickClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 9, 13, 18, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self._now += timedelta(seconds=1)
        return self._now


async def _wait_for(predicate, timeout: float = 5.0) -> None:
    async def poll() -> None:
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(poll(), timeout)


async def capture() -> list[dict]:
    controls = ScenarioControls()
    run = WorkflowRun(
        run_id="golden-capture",
        mode=RunMode.LIVE_STUB,
        controls=controls,
        scenario=scenario_with_controls(controls),
        toolbox=FakeToolBox(),
        brain=ScriptedBrain(),
        clock=TickClock(),
    )
    run.start()
    await _wait_for(lambda: run.stage is WorkflowStage.DISPUTE and run.active_dispute)
    run.resolve_dispute(
        DisputeResolutionRequest(
            dispute_id=run.active_dispute.dispute_id, confirmed_constraint=CONSTRAINT
        )
    )
    await _wait_for(lambda: run.stage is WorkflowStage.AWAITING_APPROVAL)
    run.decide_approval(
        ApprovalRequest(
            plan_archetype=PlanArchetype.OPTIMIZED_HYBRID,
            decision=ApprovalDecision.APPROVED,
            note="Captured golden approval.",
        )
    )
    await _wait_for(lambda: run.finished)
    assert run.stage is WorkflowStage.COMPLETE, run.stage
    return [event.model_dump(mode="json", exclude_none=False) for event in run.trace]


def _write(name: str, events: list[dict]) -> None:
    path = FIXTURES / name
    path.write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(events)} events)")


def main() -> None:
    events = asyncio.run(capture())
    _write("fake_agent_events.json", events)
    replay = []
    for index, event in enumerate(json.loads(json.dumps(events)), start=1):
        event["event_id"] = f"replay-{index:03d}"
        replay.append(event)
    _write("replay_events.json", replay)


if __name__ == "__main__":
    main()
