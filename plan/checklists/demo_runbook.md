# CASCADE Demonstration Runbook

Owner: Agent 6 (Verification). Audience: the presenter operating the live demo.

## 1. Reset rehearsal (run before every rehearsal and before judging)

1. Close every stale terminal running uvicorn or vite.
2. From the repository root run `uv run python scripts/preflight.py --live`.
   - Every hard check must PASS. Warnings about optional fixtures are acceptable.
   - If the live Gemini check fails, apply the replay fallback decision (section 4).
3. Start the stack: `npm run dev` (backend on 8000, frontend on 5173).
4. Open http://127.0.0.1:5173 in a maximized browser window at the demonstration
   screen size.
5. Click Reset. Confirm:
   - alert shows MV ATLAS STAR with an 18 hour delay;
   - workflow stage READY, trace empty, all five agent cards WAITING;
   - controls back to defaults (delay 18, priority Balanced).
6. Run one full golden pass end to end (section 2), then click Reset again and
   confirm step 5 holds. The demo is only rehearsed when reset-run-reset works
   twice in a row.

## 2. Golden demo click path

| Step | Action | Expected screen state |
|---|---|---|
| 1 | Show the dashboard before starting | Alert panel with MV ATLAS STAR, 18h delay, objective panel, five WAITING agent cards |
| 2 | Click Start analysis | Stage moves to ASSESSING; live indicator STREAMING; trace begins with Coordinator Agent RUN STARTED |
| 3 | Watch delegation | Impact Agent and Yard Agent cards active at the same time (parallel specialist work) |
| 4 | Wait for the dispute | Dispute panel opens: Impact Agent wants to rush all pharma reefers, Yard Agent reports reefer plug shortage; workflow paused at DISPUTE |
| 5 | Resolve the dispute | Select "reefer plug capacity is the governing constraint" and confirm; panel closes; confirmed constraint appears in the trace |
| 6 | Watch the sailing lookup | With the failure toggle ON: visible timeout error, then a clearly labeled cached fallback with a stale notice; confidence drops to MEDIUM |
| 7 | Wait for plans | Exactly three plan cards (Aggressive rush, Standard rebook, Optimized hybrid); hybrid marked recommended with rationale |
| 8 | Point out the approval gate | Stage AWAITING APPROVAL; approval bar visible; NO work order, notice, or receipt anywhere on screen |
| 9 | Approve the hybrid plan | Execution Agent runs; mocked work orders, reefer checks, and carrier notices appear with ACCEPTED receipts |
| 10 | Close | Stage COMPLETE; improved forecast beside baseline; point at the synthetic-data label |

Narration guardrails: never claim real PSA data, never claim real dispatch,
always say "mocked" for receipts and "illustrative" for costs.

## 3. Failure-path demo (tool timeout)

1. Reset.
2. Confirm the "Simulate sailing lookup timeout" toggle is ON.
3. Click Start analysis and resolve the dispute as in section 2.
4. Show the trace entry where `find_alternative_sailings` times out (visible
   error, not hidden).
5. Show the cached fallback label and the stale-data notice.
6. Show confidence MEDIUM on the recommendation and explain: fallback data
   never removes the human approval requirement.
7. Show that the run still pauses at AWAITING APPROVAL and cannot dispatch on
   its own.

## 4. Replay fallback decision point

Decision rule: if `uv run python scripts/preflight.py --live` fails the
gemini live reachability check (or a live run visibly stalls during the demo),
announce to the audience:

> "The live model API is unavailable right now, so I am switching to our
> captured replay of a valid run. It is labeled DEMO REPLAY on screen."

Then:

1. Reset.
2. Start a DEMO_REPLAY run from the UI.
3. Confirm the persistent DEMO REPLAY label is visible and stays visible.
4. Run the same click path; the approval interaction still works.
5. Never present replay output as live agent reasoning.

## 5. Release acceptance checklist (PRD section 18)

- [ ] The golden workflow succeeds from alert through mocked receipt.
- [ ] Live activity clearly shows all five agents, parallel specialist work, tool calls, and handoffs.
- [ ] The reefer-capacity disagreement pauses for human resolution.
- [ ] Reset restores the original scenario.
- [ ] The same fixture produces the same displayed results.
- [ ] Exactly three plans appear.
- [ ] No action appears before approval.
- [ ] The timeout path visibly reports an error and fallback.
- [ ] Cached sailing data changes confidence to MEDIUM.
- [ ] Replay Mode works offline and remains visibly labeled.
- [ ] Every trace value matches a tool result.
- [ ] Unsupported or unapproved actions fail deterministic validation.
- [ ] The interface has no clipped text, overlapping controls, or unreadable charts.
- [ ] Lint, types, required unit tests, deterministic agent tests, and browser tests pass.
- [ ] The preflight check validates Gemini access, model availability, ports, and fixtures.
- [ ] The demo can replay without internet access.
- [ ] The video is no longer than 10 minutes.
- [ ] The presentation contains no more than 10 slides.
- [ ] No real external action can be triggered.
