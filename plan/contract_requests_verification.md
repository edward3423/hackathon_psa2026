# Verification workstream: selector and contract requests

Owner: Agent 6. Requests for other workstreams so the browser tests in `e2e/`
can flip from `test.fixme()` to passing without selector churn. Tests select
by role and accessible name wherever possible; these are the elements the
final acceptance specs assume.

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
