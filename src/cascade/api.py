import json
import os
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from cascade import __version__
from cascade.ais import configured_bounding_boxes, live_positions
from cascade.contracts import (
    ApprovalRequest,
    DisputeResolutionRequest,
    HealthResponse,
    RunCreated,
    RunMode,
    ScenarioControls,
    ScenarioState,
    WorkflowStage,
    WorkflowState,
)
from cascade.workflow import ConflictError, RunStore, WorkflowRun, scenario_with_controls

KEEPALIVE_SECONDS = 15.0

load_dotenv()

app = FastAPI(
    title="CASCADE API",
    version=__version__,
    description="Synthetic disruption-recovery demonstration API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5620",
        "http://127.0.0.1:5620",
        "http://localhost:5621",
        "http://127.0.0.1:5621",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
store = RunStore(event_delay=0.05)


class CreateRunRequest(ScenarioControls):
    """Scenario controls plus explicit run-mode selection."""

    mode: RunMode = RunMode.LIVE_STUB


def _get_run_or_404(run_id: str) -> WorkflowRun:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@app.get("/api/scenario", response_model=ScenarioState, tags=["scenario"])
def get_scenario() -> ScenarioState:
    return scenario_with_controls()


@app.get("/api/ais/status", tags=["vessel-traffic"])
def ais_status() -> dict[str, object]:
    available = bool(os.environ.get("AISSTREAM_API_KEY"))
    return {
        "available": available,
        "provider": "AISStream" if available else None,
        "coverage": "Red Sea and Singapore approaches",
        "bounding_boxes": configured_bounding_boxes(),
    }


_MODE_QUERY = Query(default=None, description="Overrides the body mode field.")


@app.post("/api/runs", response_model=RunCreated, status_code=201, tags=["workflow"])
async def create_run(
    request: CreateRunRequest,
    mode: RunMode | None = _MODE_QUERY,
) -> RunCreated:
    selected_mode = mode or request.mode
    if selected_mode is RunMode.LIVE_GEMINI and not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(
            status_code=409,
            detail=(
                "LIVE_GEMINI requires a GEMINI_API_KEY. The live path is unavailable; "
                "explicitly choose DEMO_REPLAY to replay the captured run instead."
            ),
        )
    if selected_mode is RunMode.LIVE_CLAUDE:
        from cascade.agents.local_claude import claude_cli_path

        if claude_cli_path() is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "LIVE_CLAUDE requires the Claude Code CLI ('claude') on PATH. The "
                    "local live path is unavailable; choose LIVE_STUB or DEMO_REPLAY."
                ),
            )
    controls = ScenarioControls(
        delay_hours=request.delay_hours,
        priority_emphasis=request.priority_emphasis,
        alternative_sailing_failure=request.alternative_sailing_failure,
    )
    try:
        run = store.create(controls, selected_mode)
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return RunCreated(
        run_id=run.run_id,
        mode=run.mode,
        stage=WorkflowStage.READY,
        events_url=f"/api/runs/{run.run_id}/events",
    )


def _sse(event_name: str, payload: BaseModel | dict[str, object]) -> str:
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


async def _stream_ais(api_key: str) -> AsyncIterator[str]:
    try:
        async for position in live_positions(api_key):
            yield _sse("position", position)
    except Exception as error:
        yield _sse("provider_error", {"detail": f"AIS provider disconnected: {error}"})


@app.get("/api/ais/stream", tags=["vessel-traffic"])
def stream_ais() -> StreamingResponse:
    api_key = os.environ.get("AISSTREAM_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AISSTREAM_API_KEY is not configured")
    return StreamingResponse(
        _stream_ais(api_key),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_run(run: WorkflowRun) -> AsyncIterator[str]:
    if run.mode is RunMode.DEMO_REPLAY:
        yield _sse("mode", {"run_id": run.run_id, "mode": run.mode.value, "label": "DEMO REPLAY"})
    index = 0
    while True:
        update = await run.wait_events(index, timeout=KEEPALIVE_SECONDS)
        if update is None:
            yield ": keep-alive\n\n"
            continue
        events, finished = update
        for event in events:
            index += 1
            yield _sse("trace", event)
        if finished and index == len(run.trace):
            yield _sse("stream_end", {"run_id": run.run_id, "stage": run.stage.value})
            return


@app.get("/api/runs/{run_id}/events", tags=["workflow"])
def stream_run(run_id: str) -> StreamingResponse:
    run = _get_run_or_404(run_id)
    return StreamingResponse(
        _stream_run(run),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/runs/{run_id}", response_model=WorkflowState, tags=["workflow"])
def get_run(run_id: str) -> WorkflowState:
    run = _get_run_or_404(run_id)
    return WorkflowState(
        run_id=run.run_id,
        mode=run.mode,
        stage=run.stage,
        scenario=run.scenario,
        activities=run.activities(),
        trace=run.trace,
        active_dispute=run.active_dispute,
        results=run.results,
    )


@app.post("/api/runs/{run_id}/dispute-resolution", response_model=WorkflowState, tags=["workflow"])
async def resolve_dispute(run_id: str, request: DisputeResolutionRequest) -> WorkflowState:
    run = _get_run_or_404(run_id)
    try:
        run.resolve_dispute(request)
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return get_run(run_id)


@app.post("/api/runs/{run_id}/approval", response_model=WorkflowState, tags=["workflow"])
async def decide_approval(run_id: str, request: ApprovalRequest) -> WorkflowState:
    run = _get_run_or_404(run_id)
    try:
        run.decide_approval(request)
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return get_run(run_id)


@app.post("/api/reset", response_model=ScenarioState, tags=["scenario"])
def reset_demo() -> ScenarioState:
    store.reset()
    return scenario_with_controls()
