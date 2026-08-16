# Contract change requests from the workflow workstream

Owner: Agent 4 (Workflow). These are proposals for Agent 1; each has a local
workaround already in place, so nothing blocks integration.

## 1. Run-creation request model with a mode field

`POST /api/runs` needs run-mode selection (LIVE_STUB, LIVE_GEMINI,
DEMO_REPLAY). `ScenarioControls` is frozen and has no mode field.

Proposal: add a shared request model to contracts.py:

```python
class RunRequest(ContractModel):
    controls: ScenarioControls
    mode: RunMode = RunMode.LIVE_STUB
```

Workaround: `cascade.api.CreateRunRequest` subclasses `ScenarioControls` with a
`mode` field (flat body, backward compatible with plain ScenarioControls
payloads), plus a `?mode=` query parameter that overrides the body. The
frontend can use either today.

## 2. Evidence pack schema

`retrieve_context` returns `{"query", "facts", "notice"}` where each fact is
`{"fact", "source_title", "source_url"}` (the shape of
fixtures/evidence_pack.json). A typed contract model would let the frontend
render sources safely.

Workaround: the tool returns plain dicts; the workflow only surfaces them in
free-text trace fields.

## 3. Stream-end and mode SSE envelopes

The SSE stream emits `event: trace` (TraceEvent JSON), `event: mode` (replay
label announcement), and `event: stream_end`. Only TraceEvent is in
contracts. If the frontend wants typed envelopes, add:

```python
class StreamEnd(ContractModel):
    run_id: str
    stage: WorkflowStage

class StreamModeLabel(ContractModel):
    run_id: str
    mode: RunMode
    label: str
```

Workaround: both payloads are small stable dicts documented here; the trace
events themselves are fully contract-valid.
