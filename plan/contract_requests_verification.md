# Verification workstream: selector and contract requests

Owner: Agent 6. Requests for other workstreams so the browser tests in `e2e/`
can flip from `test.fixme()` to passing without selector churn. Tests select
by role and accessible name wherever possible; these are the elements the
final acceptance specs assume.

## Open product defects (found by e2e verification, 2026-08-17)

### 1. LIVE_STUB planning always fails: run ends FAILED instead of AWAITING_APPROVAL

Blocks: `e2e/specs/golden-run.spec.ts`, `e2e/specs/timeout-fallback.spec.ts`
(both left `test.fixme` referencing this entry). DEMO_REPLAY is unaffected and
its browser test passes, so the plan/approval/receipt UI itself works.

Repro (no browser needed):
1. `uv run uvicorn cascade.api:app --port 8000`
2. `POST /api/runs` with default controls (LIVE_STUB, delay 18, BALANCED,
   failure toggle on or off - both reproduce).
3. Wait for stage DISPUTE, then `POST /api/runs/{id}/dispute-resolution` with
   any constraint offered by the UI, e.g. "Respect physical reefer plug
   capacity".
4. Expected: three evaluated plans, stage AWAITING_APPROVAL.
5. Actual: stage FAILED; trace ERROR "Plan AGGRESSIVE_RUSH stayed infeasible
   after 3 revision rounds."; result "Run failed; no further actions will be
   taken."

Root cause (two owners, pick either fix):
- Engine (Agent 3): `CRANE_SURGE_ALLOWANCE_CONTAINERS = 12` in
  `src/cascade/engine/plans.py`, while the golden world has 172 threatened
  containers (23 pharma reefer, 68 manufacturing, 81 dry). Any archetype that
  rushes whole groups exceeds 12 by an order of magnitude.
- Scripted brain (Agent 4): `ScriptedBrain.revise_plan` in
  `src/cascade/agents/scripted.py` only revises PHARMA_REEFER rush actions
  (and only caps them when the text contains "rush at most N"). Rush actions
  for manufacturing and dry cargo are never converted to rebooks, so
  AGGRESSIVE_RUSH (172 rushed) and OPTIMIZED_HYBRID (rushes all 68
  manufacturing) can never satisfy the 12-container allowance, and the
  workflow raises after MAX_REVISION_ROUNDS.

Why the unit suite is green anyway: `tests/test_api.py` and
`tests/test_workflow.py` replace the toolbox with `FakeToolBox`, so the real
`EngineToolBox` planning path is never exercised end to end. Suggest one
integration test that runs `RunStore` with `build_toolbox()`.

### 2. Minor UX: the dispute overlay blocks the Reset button

`DisputeOverlay` renders a full-screen backdrop, so while the workflow is
paused at the dispute the Reset button (and trace drawer toggle) cannot be
clicked. PRD 9.16 expects one-button reset; during a live demo a stuck
dispute would strand the presenter. Suggest allowing Reset above the
backdrop or a cancel affordance in the overlay. The e2e specs work around it
(they resolve the dispute before resetting).

## For Agent 5 (frontend dashboard)

1. Dispute panel: render as `role="dialog"` with an accessible name containing
   "dispute". Include the literal agent names "Impact Agent" and "Yard Agent"
   and the word "reefer" in the panel body. Constraint choices as buttons; the
   reefer option's accessible name must contain "reefer plug capacity".
2. Plan cards: exactly three `role="article"` elements with accessible names
   containing "plan". The recommended card must contain the visible word
   "Recommended" and the archetype text (OPTIMIZED_HYBRID or "Optimized
   hybrid").
3. Approval bar: an approve control reachable via
   `getByRole('button', { name: /approve/i })` and a matching reject button.
4. Dispatch artifacts: before approval, no element may contain the text
   "work order", "carrier notice", "receipt", or "dispatched"
   (case-insensitive). After approval, receipts must show the literal status
   text "ACCEPTED".
5. Stage display: keep the current exact-text stage strings ("AWAITING
   APPROVAL", "COMPLETE") and the "STREAMING"/"IDLE" live indicator.
6. Timeout path: visible text matching /timeout|timed out/i, a "cached" label,
   and a "stale" notice; confidence rendered as the exact text "MEDIUM".
7. Replay mode: a UI control to start a DEMO_REPLAY run with accessible name
   containing "demo replay", and a persistent label with the exact text
   "DEMO REPLAY" visible from run start through completion.
8. Keep `.trace-list li` (or provide `role="listitem"` inside a named trace
   list) for trace entries; entries for tool failures should include the tool
   name `find_alternative_sailings`.

## For Agent 4 (workflow API)

1. Pause the SSE stream at DISPUTE_OPENED until
   `POST /api/runs/{id}/dispute-resolution` and at APPROVAL_REQUIRED until
   `POST /api/runs/{id}/approval`, as contracted.
2. A way to create a DEMO_REPLAY run (e.g. `mode` on POST /api/runs) so the
   replay spec can start one from the UI.
3. Recording hook for live Gemini exchanges in the format described in
   `fixtures/recorded_gemini/README.md`.

## For Agent 2 (fixtures)

1. `fixtures/golden_world.json` validating against `WorldFixture` - preflight
   currently skips it with a warning until it exists.
2. `fixtures/evidence_pack.json` (any valid JSON; tell Agent 6 if it gets a
   contract model so preflight can bind it).
