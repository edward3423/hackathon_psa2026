"""``fixtures/agent_status_golden.json`` must keep describing a real run.

The fixture is the contract the frontend status machine is tested against (see
``frontend/src/lib/derive.test.ts``). If the workflow starts emitting a
different sequence of events, or ``WorkflowRun.activities()`` starts reading
them differently, this fails and the fixture has to be regenerated with::

    uv run python scripts/export_agent_status_golden.py

which forces the frontend test to be re-run against the new contract rather
than letting the two machines drift apart unnoticed.
"""

import json
from pathlib import Path

import pytest

from scripts.export_agent_status_golden import GOLDEN_PATH, record_golden_run


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_golden_fixture_is_committed() -> None:
    assert GOLDEN_PATH.exists(), "run scripts/export_agent_status_golden.py"


@pytest.mark.anyio
async def test_golden_fixture_matches_a_fresh_run() -> None:
    recorded = json.loads(Path(GOLDEN_PATH).read_text(encoding="utf-8"))
    assert await record_golden_run() == recorded


def test_every_agent_completes_at_the_end_of_the_run() -> None:
    """The state the QA report caught the UI contradicting: nothing is left RUNNING."""
    recorded = json.loads(Path(GOLDEN_PATH).read_text(encoding="utf-8"))
    assert recorded["final_stage"] == "COMPLETE"
    assert [activity["status"] for activity in recorded["activities"]] == ["COMPLETED"] * 5
