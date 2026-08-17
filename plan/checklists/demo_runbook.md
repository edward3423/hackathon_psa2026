# CASCADE Demonstration Runbook

Owner: Agent 6 (Verification). Audience: the presenter operating the live demo.

## 1. Reset rehearsal (run before every rehearsal and before judging)

1. Close every stale terminal running uvicorn or vite.
2. From the repository root run `uv run python scripts/preflight.py --live`.
   - Every hard check must PASS. Warnings about optional fixtures are acceptable.
   - If the live Gemini check fails, apply the replay fallback decision (section 4).
3. Start the stack: `npm run dev` (backend on 8620, frontend on 5620).
4. Open http://127.0.0.1:5620 in a maximized browser window at the demonstration
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
| 2 | Click Start run | Stage moves to ASSESSING; live indicator STREAMING; the trace drawer counter climbs (click EXECUTION TRACE / Expand to watch events, first is Coordinator Agent RUN STARTED) |
| 3 | Watch delegation | Impact Agent and Yard Agent cards active at the same time (parallel specialist work) |
| 4 | Wait for the dispute | Dispute panel opens: Impact Agent wants to rush all pharma reefers, Yard Agent reports reefer plug shortage; workflow paused at DISPUTE |
| 5 | Resolve the dispute | Click the preset "Respect physical reefer plug capacity", then "Confirm constraint"; panel closes; confirmed constraint appears in the trace. The top-bar controls (including Reset) stay usable while the panel is open |
| 6 | Watch the sailing lookup | With the failure toggle ON: visible timeout error, then a clearly labeled cached fallback with a stale notice; confidence drops to MEDIUM |
| 7 | Wait for plans | Exactly three plan cards under RECOVERY PLANS (Aggressive Rush, Standard Rebook, Optimized Hybrid); hybrid carries the Recommended badge and a WHY RECOMMENDED rationale. Aggressive Rush is marked INFEASIBLE after its visible revision attempts - it never concedes rush volume, so the crane surge allowance keeps rejecting it |
| 8 | Point out the approval gate | Stage AWAITING APPROVAL; approval bar visible with plan switcher, Approve, and Reject; NO work order, notice, or receipt anywhere on screen |
| 9 | Approve the hybrid plan | Keep Optimized Hybrid in the approval-bar plan switcher and click Approve; Execution Agent runs; EXECUTION RECEIPTS (MOCKED) lists ACCEPTED receipts |
| 10 | Close | Stage COMPLETE; improved forecast beside baseline; point at the synthetic-data label |

Narration guardrails: never claim real PSA data, never claim real dispatch,
always say "mocked" for receipts and "illustrative" for costs.

## 3. Failure-path demo (tool timeout)

1. Reset.
2. Confirm the "Simulate sailing lookup timeout" toggle is ON.
3. Click Start run and resolve the dispute as in section 2.
4. Show the trace entry where `find_alternative_sailings` times out (visible
   error, not hidden; expand the trace drawer).
5. Show the SAILING LOOKUP TIMEOUT - CACHED FALLBACK callout and the
   stale-data notice in the metrics panel.
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
2. Click "Start demo replay".
3. Confirm the persistent DEMO REPLAY label is visible and stays visible.
4. Run the same click path; the dispute and approval interactions still work.
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
