# Frontend workstream: contract and endpoint requests

Owner: Agent 5. Requests for Agent 1 (contracts) and Agent 4 (workflow API) so
the dashboard's typed client can drop its hand-written types.

## 1. Add the pause endpoints to the OpenAPI contract

`frontend/src/api/schema.d.ts` has no operations for the two human-in-the-loop
endpoints, so the client currently hand-types them in
`frontend/src/api/types.ts` (`DisputeResolutionRequest`, `ApprovalRequest`).
Please add to the FastAPI app and regenerate:

- `POST /api/runs/{run_id}/dispute-resolution`
  body: `{ dispute_id: string, confirmed_constraint: string }`
  response: `WorkflowState` (or 204; the UI polls `GET /api/runs/{id}` anyway).
- `POST /api/runs/{run_id}/approval`
  body: `{ plan_archetype: PlanArchetype, decision: "APPROVED" | "REJECTED", note?: string }`
  response: `WorkflowState` (or 204).

## 2. Replay mode on run creation

The verification workstream requires a UI control that starts a DEMO_REPLAY
run. `POST /api/runs` takes a `ScenarioControls` body, which has no mode
field. The frontend now sends BOTH of these when the user clicks
"Start demo replay" (either one is enough for the backend to honor):

- query parameter: `POST /api/runs?mode=DEMO_REPLAY`
- extra body field: `{ ...ScenarioControls, "mode": "DEMO_REPLAY" }`

Please pick one, implement it, and add it to the contract; the frontend will
then drop the other. Recommendation: an optional `mode` query parameter keeps
`ScenarioControls` a pure scenario object.

## 3. SSE stream expectations (confirmation, no change requested)

The frontend assumes, per the integration brief:

- event name `trace` with a `TraceEvent` JSON payload, `stream_end` at the end;
- the stream stays open across the DISPUTE and AWAITING_APPROVAL pauses;
- re-connecting with a fresh `EventSource` to the same `events_url` after a
  network drop replays already-sent events (the frontend dedupes by
  `event_id`, so replays are safe; if the backend instead resumes from
  `Last-Event-ID`, that also works).

If any assumption is wrong, tell Agent 5.

## 4. `AgentActivity.parallel_group` (nice to have)

`TraceEvent.parallel_group` exists, but `AgentActivity` has no parallel-group
field, so the parallel-work visualization is derived from trace events only.
Fine for now; add it to `AgentActivity` if the workflow tracks it anyway.
