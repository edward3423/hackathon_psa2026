import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from cascade import __version__
from cascade.contracts import (
    HealthResponse,
    RunCreated,
    ScenarioControls,
    ScenarioState,
    TraceEvent,
    WorkflowStage,
    WorkflowState,
)
from cascade.workflow import DemoRun, DemoRunStore, scenario_with_controls

app = FastAPI(
    title="CASCADE API",
    version=__version__,
    description="Synthetic disruption-recovery demonstration API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
store = DemoRunStore()


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@app.get("/api/scenario", response_model=ScenarioState, tags=["scenario"])
def get_scenario() -> ScenarioState:
    return scenario_with_controls()


@app.post("/api/runs", response_model=RunCreated, status_code=201, tags=["workflow"])
def create_run(controls: ScenarioControls) -> RunCreated:
    run = store.create(controls)
    return RunCreated(
        run_id=run.run_id,
        mode=run.mode,
        stage=WorkflowStage.READY,
        events_url=f"/api/runs/{run.run_id}/events",
    )


def _sse(event_name: str, payload: TraceEvent | dict[str, str]) -> str:
    data = payload.model_dump(mode="json") if isinstance(payload, TraceEvent) else payload
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


async def _stream_run(run: DemoRun) -> AsyncIterator[str]:
    for event in run.events():
        yield _sse("trace", event)
        await asyncio.sleep(0.08)
    yield _sse("stream_end", {"run_id": run.run_id, "stage": run.stage.value})


@app.get("/api/runs/{run_id}/events", tags=["workflow"])
def stream_run(run_id: str) -> StreamingResponse:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return StreamingResponse(
        _stream_run(run),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/runs/{run_id}", response_model=WorkflowState, tags=["workflow"])
def get_run(run_id: str) -> WorkflowState:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return WorkflowState(
        run_id=run.run_id,
        mode=run.mode,
        stage=run.stage,
        scenario=scenario_with_controls(run.controls),
        activities=run.activities(),
        trace=run.trace,
    )


@app.post("/api/reset", response_model=ScenarioState, tags=["scenario"])
def reset_demo() -> ScenarioState:
    store.reset()
    return scenario_with_controls()
