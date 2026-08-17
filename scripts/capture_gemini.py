"""Capture a live Gemini golden run into fixtures/recorded_gemini/.

Drives the full golden scenario (dispute, timeout fallback, plan revision
cycle, approval) against the real engine with the LIVE_GEMINI capture-profile
brain: decision-critical calls hit gemini-3.5-flash, routine narrations stay
scripted, so the whole run costs about 9 API requests (hard capped at 18,
under the 20-per-day free tier).

Requires GEMINI_API_KEY; if not exported it is read from the gitignored .env.
The recording is written incrementally, then finalized here with the scenario
controls. Review it before committing (see fixtures/recorded_gemini/README.md).

Run: uv run python scripts/capture_gemini.py
"""

import asyncio
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

WAIT_TIMEOUT_SECONDS = 600.0

CONSTRAINT = (
    "Respect the physical reefer plug limit of 150; rush at most 34 pharmaceutical "
    "reefers and rebook the remainder."
)


def load_env_key() -> None:
    if os.environ.get("GEMINI_API_KEY"):
        return
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("GEMINI_API_KEY="):
            os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip().strip('"')
            return


async def _wait_for(predicate: Callable[[], object], label: str) -> None:
    async def poll() -> None:
        while not predicate():
            await asyncio.sleep(0.1)

    try:
        await asyncio.wait_for(poll(), WAIT_TIMEOUT_SECONDS)
    except TimeoutError:
        raise RuntimeError(f"Timed out waiting for {label}") from None


async def capture() -> Path:
    from cascade.agents.live_gemini import RECORDINGS_DIR, build_live_brain
    from cascade.contracts import (
        ApprovalDecision,
        ApprovalRequest,
        DisputeResolutionRequest,
        RunMode,
        ScenarioControls,
        WorkflowStage,
    )
    from cascade.tools.toolbox import build_toolbox
    from cascade.workflow import WorkflowRun, scenario_with_controls

    controls = ScenarioControls()
    run = WorkflowRun(
        run_id="gemini-capture",
        mode=RunMode.LIVE_GEMINI,
        controls=controls,
        scenario=scenario_with_controls(controls),
        toolbox=build_toolbox(),
        brain=build_live_brain(),
    )
    before: set[str] = set()
    if RECORDINGS_DIR.exists():
        before = {path.name for path in RECORDINGS_DIR.glob("*.json")}

    run.start()
    print("Run started; waiting for the reefer-plug dispute...")
    await _wait_for(lambda: run.stage is WorkflowStage.DISPUTE and run.active_dispute, "dispute")
    assert run.active_dispute is not None
    run.resolve_dispute(
        DisputeResolutionRequest(
            dispute_id=run.active_dispute.dispute_id, confirmed_constraint=CONSTRAINT
        )
    )
    print("Dispute resolved; waiting for plan comparison and approval request...")
    await _wait_for(lambda: run.stage is WorkflowStage.AWAITING_APPROVAL, "approval request")
    comparison = run.results.plan_comparison
    assert comparison is not None and comparison.recommended is not None
    print(f"Approving the recommended plan: {comparison.recommended.value}")
    run.decide_approval(
        ApprovalRequest(
            plan_archetype=comparison.recommended,
            decision=ApprovalDecision.APPROVED,
            note="Captured live golden approval.",
        )
    )
    await _wait_for(lambda: run.finished, "run completion")
    if run.stage is not WorkflowStage.COMPLETE:
        raise RuntimeError(f"Run finished in stage {run.stage.value}; recording not finalized.")

    new_files = [
        path for path in RECORDINGS_DIR.glob("*.json") if path.name not in before
    ] or sorted(RECORDINGS_DIR.glob("*.json"), key=lambda path: path.stat().st_mtime)[-1:]
    recording_path = max(new_files, key=lambda path: path.stat().st_mtime)

    payload = json.loads(recording_path.read_text(encoding="utf-8"))
    payload["scenario_controls"] = controls.model_dump(mode="json")
    recording_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded {len(payload['exchanges'])} exchanges to {recording_path}")
    return recording_path


def main() -> int:
    load_env_key()
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY is not set and .env does not provide it; aborting.")
        return 1
    os.environ["CASCADE_RECORD_GEMINI"] = "1"
    asyncio.run(capture())
    return 0


if __name__ == "__main__":
    sys.exit(main())
