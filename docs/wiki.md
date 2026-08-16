# CASCADE Wiki

Audience: AI agents working on this repository. Optimized for accurate
grounding, not for human reading. Facts below are path-anchored; when this
file and the code disagree, the code wins - then update this file.

Last full revision: 2026-08-17, after all five workstreams merged
(fixtures, analysis, verification, workflow, frontend) plus the type
annotation cleanup and regenerated API types.

## 1. Project identity

- CASCADE: AI-led, human-governed multi-agent demo for PSA port disruption
  recovery. Hackathon deliverable (PSA Code Sprint), not production.
- Canonical requirements: plan/prd_main.md (PRD). Deferred items:
  plan/todo.md (all LOW, do not implement before the golden demo works).
- Everything operational is synthetic; all external actions are mocked;
  human approval is mandatory before dispatch; agents may never alter
  calculated values. These four invariants override convenience.
- Demo scenario: inbound vessel MV ATLAS STAR, port call SGSIN-PSA-2042,
  original ETA 2026-09-14T06:00:00Z, default delay 18h. The platform is
  parameterized (delay 6-24h, priority emphasis, failure toggle) but only
  this one scenario ships.

## 2. Repository map and ownership

| Path | Content | Owning workstream |
|---|---|---|
| plan/ | PRD, backlog, checklists, cross-workstream request files | integration (Agent 1) |
| contracts/openapi.json | GENERATED from FastAPI app. Never hand-edit | integration |
| src/cascade/contracts.py | Single source of truth for all shared Pydantic models. Changes only via Agent 1 | integration |
| src/cascade/fixtures.py | Fixture loaders | fixtures (Agent 2) |
| scripts/generate_fixture.py | Deterministic world generator, seed 42 | fixtures |
| fixtures/golden_world.json | Generated world, committed, byte-reproducible | fixtures |
| fixtures/evidence_pack.json | 10 reviewed public facts for retrieve_context | fixtures |
| src/cascade/engine/ | Pure deterministic analysis functions | analysis (Agent 3) |
| src/cascade/workflow.py, api.py, agents/, tools/ | Stage machine, FastAPI, agent brains, ToolBox seam | workflow (Agent 4) |
| fixtures/fake_agent_events.json, replay_events.json, fake_tool_responses.json | Scripted/captured event and tool fixtures | workflow |
| frontend/src/ | React dashboard (components/, hooks/useRunStream.ts, api/client.ts, lib/derive.ts) | frontend (Agent 5) |
| frontend/src/api/schema.d.ts | GENERATED from openapi.json. Never hand-edit | integration |
| e2e/ | Self-contained Playwright project (own package.json, not in npm workspace) | verification (Agent 6) |
| scripts/preflight.py | Demo preflight checks | verification |
| fixtures/recorded_gemini/ | Recorded live-response format spec (recordings TBD) | verification |
| scratch/ | Throwaway probes (gemini_test.py works and is the reference for live Gemini calls) | anyone |

Branch layout: all five workstream branches (cascade/data-fixtures,
cascade/simulation-engine, cascade/workflow-api,
cascade/frontend-dashboard, cascade/verification-delivery) are merged
into main; the D:/Projects/cascade-wt/* worktrees are historical. After
changing contracts or API endpoints run `npm run generate:types` and
commit the regenerated files. Cross-workstream asks live in
plan/contract_requests_*.md (verification, frontend, workflow) - some
remain open; reconcile through Agent 1 before acting on them.

## 3. Commands (Windows; always uv for Python)

| Command | Effect |
|---|---|
| uv sync | Install Python deps into .venv |
| npm install | Install workspace deps (root + frontend) |
| npm run generate:types | Export openapi.json from the app, then regenerate frontend/src/api/schema.d.ts |
| npm run dev | uvicorn on 8000 + vite on 5173, concurrently |
| npm run check | ruff lint+format check, pytest, frontend vitest, tsc build - the full gate |
| uv run pytest | Backend tests only |
| uv run python scripts/generate_fixture.py | Regenerate fixtures/golden_world.json (must be byte-identical) |
| uv run python scripts/preflight.py [--live] | Demo readiness checks; --live does one real Gemini call if key present |
| cd e2e && npx playwright test | Browser specs (needs `npm install` + `npx playwright install chromium` inside e2e/ once) |

Environment quirks:
- Filesystem is D:\Projects (capital P); sessions may see D:\projects. Git
  resolves to the capitalized form; case-sensitive path comparisons break
  (this is why built-in worktree isolation failed; use manual worktrees).
- Port 5173 is sometimes occupied by an unrelated app on this machine; e2e
  uses 5174 --strictPort. Never let app logic depend on the frontend port.
- uv invocations in npm scripts use `--cache-dir .uv-cache`.
- GEMINI_API_KEY lives in D:\projects\hackathon_psa2026\.env (gitignored).
  Never commit it; never make tests depend on it.

## 4. Contracts (src/cascade/contracts.py)

All models extend ContractModel (extra="forbid"): unknown fields are
rejected everywhere. All shared types live in this one file; other modules
import from it and never redefine shapes.

Workflow layer: RunMode (LIVE_STUB | LIVE_GEMINI | DEMO_REPLAY),
WorkflowStage (READY, ASSESSING, DISPUTE, PLANNING, AWAITING_APPROVAL,
EXECUTING, COMPLETE, FAILED), EventKind (RUN_STARTED, AGENT_STARTED,
TOOL_CALLED, AGENT_COMPLETED, HANDOFF, DISPUTE_OPENED, HUMAN_DECISION,
APPROVAL_REQUIRED, ACTION_DISPATCHED, ERROR, RUN_COMPLETED), AgentName
(five display names, e.g. "Coordinator Agent"), AgentStatus, Confidence
(HIGH | MEDIUM | LOW - categorical only, never percentages),
DisruptionAlert (delay_hours is a computed field), ScenarioControls
(delay_hours 6..24 default 18, priority_emphasis, alternative_sailing
_failure default true), ScenarioState, AgentActivity, TraceEvent (the SSE
payload; parallel_group marks concurrent specialists), DisputePosition,
Dispute, WorkflowState (carries results: RunResults | None), RunCreated,
HealthResponse.

Domain layer: CargoType (PHARMA_REEFER | TIME_CRITICAL_MANUFACTURING |
GENERAL_DRY), ConnectionStatus (SAFE | AT_RISK | MISSED | RESOLVED),
VesselRole, PlanArchetype (AGGRESSIVE_RUSH | STANDARD_REBOOK |
OPTIMIZED_HYBRID), RecoveryActionType (RUSH | REBOOK | HOLD),
MockedActionType (TERMINAL_WORK_ORDER | REEFER_CHECK | CARRIER_NOTICE),
SailingLookupStatus (MOCK_SUCCESS | TIMEOUT_CACHED_FALLBACK), Vessel,
YardBlock, Container (handling_hours = hours from revised ETA until ready
in yard), AlternativeSailing (replaces_onward_vessel links it to an
affected outbound vessel), CostRates, WorldFixture, ContainerConnection,
ConnectionGroupSummary, ConnectionAnalysis, YardOccupancyPoint,
BlockForecast, ReeferShortage, YardForecast, CostComponent, CostEstimate
(illustrative flag), PlanAction, RecoveryPlan, PlanMetrics, PlanEvaluation,
PlanComparison, AlternativeSailingResult, MockedAction, ActionReceipt
(ACCEPTED | REJECTED), RunResults, DisputeResolutionRequest,
ApprovalRequest (ApprovalDecision APPROVED | REJECTED).

Classification rule (fixed): margin_hours = connection_cutoff -
(revised_eta + handling_hours), in hours. SAFE if margin > 4; AT_RISK if
0 <= margin <= 4; MISSED if margin < 0. Congested = occupancy >= 85% of
block capacity; full = >= 100%.

Priority rule (fixed): PHARMA_REEFER before TIME_CRITICAL_MANUFACTURING
before GENERAL_DRY; within a cargo type, smaller margin first.

Recommendation order (fixed, PRD 9.9): drop infeasible plans; maximize
critical cargo protected; minimize missed connections; minimize yard peak;
minimize cost then delay. Ties: archetype order AGGRESSIVE_RUSH,
STANDARD_REBOOK, OPTIMIZED_HYBRID. A cheaper infeasible plan must never
win.

Confidence semantics: HIGH = all inputs complete, tools succeeded. MEDIUM
= fallback/stale cached data used (planning continues, approval still
required). LOW = conflicting/missing critical inputs (forces dispute
before planning).

## 5. Golden world (fixtures/golden_world.json)

Generated by scripts/generate_fixture.py with random.Random(42) only; no
clock reads; regeneration is byte-identical (tests enforce committed ==
regenerated). Key facts:

- 400 containers: 60 PHARMA_REEFER (all requires_power=true, all bound for
  affected outbound vessels), 130 TIME_CRITICAL_MANUFACTURING, 210
  GENERAL_DRY (40 of which have onward_vessel=null, i.e. import cargo).
- 6 vessels: inbound MV ATLAS STAR; affected outbound MV MERIDIAN WAVE
  (cutoff original ETA +22h), MV CORAL EMPRESS (+30h), MV PACIFIC HARRIER
  (+34h); unaffected MV JADE HORIZON (+60h), MV AURORA BREEZE (+78h).
- 4 yard blocks. Reefer plugs YB1 18, YB2 14, YB3 12, YB4 0; total 44 < 60
  reefers, and 24 plugs already occupied initially - rushing all 60 reefers
  is infeasible. This is the designed trigger for the golden dispute.
- Occupancy tuned so YB1 peaks ~85.4% and YB2 ~85.8% if missed cargo
  dwells (crosses the 85% congestion line); YB3 ~83.9%, YB4 ~79.8%.
- Connection mix by delay: 6h -> 334 SAFE / 26 AT_RISK / 0 MISSED; 18h ->
  188 / 70 / 102; 24h -> 87 / 89 / 184.
- 4 alternative sailings (one per affected vessel plus a second for
  MERIDIAN WAVE), capacities 70/40/60/55 - deliberately below demand so
  rebooking requires allocation choices.
- cost_rates: dwell 4 per container-hour, reefer risk 25 per hour, missed
  connection 1200, crane hour 600, rebooking 350 (illustrative).

Loaders: cascade.fixtures.load_golden_world() -> WorldFixture,
load_evidence_pack() -> dict, plus load_golden_scenario(),
load_fake_events(), load_replay_events(), load_fake_tool_responses().

## 5b. Engine (src/cascade/engine/)

Pure deterministic functions; no I/O, randomness, or clock reads. Public
surface (also exported from engine/__init__.py):

- connections.analyse_connections(world, revised_eta, emphasis) ->
  ConnectionAnalysis; helpers classify_margin(margin_hours),
  inbound_vessel(world).
- yard.simulate_yard(world, revised_eta, connections, plan=None,
  horizon_hours=72) -> YardForecast.
- costs.estimate_cost(world, connections, plan, yard) -> CostEstimate.
- plans.evaluate_plan(world, revised_eta, connections, plan, emphasis) ->
  PlanEvaluation; plans.compare_plans(..., confidence=HIGH) ->
  PlanComparison.
- actions.build_actions(plan) -> list[MockedAction];
  actions.validate_actions(plan, actions) -> list[ActionReceipt].
- _dispositions.py (internal): single deterministic action-to-container
  assignment shared by yard, costs, and plans so all three agree on one
  schedule. Do not bypass it.

Fixed modelling decisions (change only with a PRD-level reason):
- Yard series starts at the inbound vessel's original ETA floored to the
  hour; exactly horizon_hours points (hours 0..71); presence rule is
  arrival <= t < departure; occupancy clamped at zero.
- Crane surge allowance: 40 rushed containers per plan
  (CRANE_SURGE_ALLOWANCE_CONTAINERS, roughly one crane-shift of extra
  moves); extra crane cost = 1.0 crane hour per rushed container.
- Group PlanActions map to containers by priority rank in plan-action
  order, each consuming container_count containers; leftovers keep default
  behavior (SAFE/AT_RISK depart at onward ETD, MISSED dwell full horizon).
- Rushed containers occupy the yard at least one hour, so rushed reefers
  always register plug demand; initial_containers are a non-departing
  background load.
- Reefer shortage = first hour where initial_reefers_on_power + powered
  arrivals exceed reefer_plugs; at most one shortage reported per block.
- Priority ranking ignores emphasis (emphasis steers agents upstream, not
  deterministic ordering) - keeps outputs replay-stable.
- Feasibility rejects: sailing over-capacity or unknown target sailing,
  rushed powered reefers above a block's free plugs (reefer_plugs minus
  initial_reefers_on_power; yard-wide plug pressure from waiting cargo is
  surfaced by the yard forecast, not as a plan rejection), rush count
  above surge allowance, any AT_RISK/MISSED group left without an action.
- Ids: sequential per type WO-/RC-/CN- with 3-digit counters; receipts
  RCPT-<action_id>; validation accepts only exact plan-derived actions and
  rejects unknown ids, tampered content, and duplicates.

## 6. Feature matrix (PRD 9.x -> implementation)

Status letters: M = merged on main; F = in flight on the named branch.

| PRD | Feature | Where | Status |
|---|---|---|---|
| 9.1 | Disruption alert intake, delay computed | contracts.DisruptionAlert (computed delay_hours); POST /api/runs | M (basic) |
| 9.2 | Issue and objective identification | golden_scenario.json objective; coordinator stage machine emits it | F workflow |
| 9.3 | Connection classification SAFE/AT_RISK/MISSED | engine/connections.py analyse_connections | M |
| 9.4 | Cargo priority ranking with reason | same module, priority_rank/priority_reason | M |
| 9.5 | 72h hourly yard forecast, 85/100% thresholds | engine/yard.py simulate_yard | M |
| 9.6 | Reefer plug shortage detection | engine/yard.py (ReeferShortage in YardForecast) | M |
| 9.7 | Illustrative cost, total = sum of 5 components | engine/costs.py estimate_cost | M |
| 9.8 | Exactly three plan archetypes, revision on rejection | engine/plans.py + workflow revision loop | M engine / F workflow |
| 9.9 | Fixed-order recommendation | engine/plans.py compare_plans | M |
| 9.10 | Mandatory human approval | POST /api/runs/{id}/approval; no ACTION_DISPATCHED before it | F workflow |
| 9.11 | Full execution trace | TraceEvent over SSE; all displayed figures flow from tool results | M (shape) / F (real flow) |
| 9.12 | Controlled tool failure + labeled cached fallback + MEDIUM | ScenarioControls.alternative_sailing_failure; SailingLookupStatus | F workflow |
| 9.13 | Cascade graph, color + text labels | frontend @xyflow/react graph fed by ConnectionAnalysis.groups | F frontend |
| 9.14 | Yard baseline vs plan charts, 3 plan cards | frontend recharts + plan cards from PlanComparison | F frontend |
| 9.15 | Mocked dispatch with deterministic validation | engine/actions.py build_actions/validate_actions + Execution stage | M engine / F workflow |
| 9.16 | One-step demo reset | POST /api/reset | M (basic) / F (full state) |
| 9.17 | 5 agents, parallel Impact+Yard, gated Execution | stage machine + TraceEvent.parallel_group | F workflow |
| 9.18 | Transient dispute panel, confirmed constraint | Dispute contract; dispute-resolution endpoint; overlay UI | F workflow+frontend |
| 9.19 | Scenario controls re-run | ScenarioControls on POST /api/runs | M (accepted) / F (honored) |
| 9.20 | Honest Replay Mode, always labeled | RunMode.DEMO_REPLAY; replay_events.json; exact-text "DEMO REPLAY" label | F workflow+frontend |

## 7. Runtime architecture

React dashboard (vite, port 5173) -> REST + SSE -> FastAPI (uvicorn, port
8000, src/cascade/api.py) -> coordinator-controlled stage machine wrapping
Google ADK agents (gemini-3.5-flash) -> deterministic engine functions ->
JSON fixtures + in-memory state. No database. Only live network dependency
is the Gemini API.

Stage sequence (PRD 10): RUN_STARTED -> identify issue/objective ->
parallel Impact + Yard (same parallel_group) -> reconcile or DISPUTE_OPENED
(pause; human posts DisputeResolutionRequest; constraint recorded as
HUMAN_DECISION and enforced on plans) -> alternative-sailing lookup (times
out when toggled; cached fallback labeled stale; confidence -> MEDIUM) ->
Recovery proposes 3 plans -> deterministic validation rejects infeasible ->
revision cycle (at least one visible in trace; ScriptedBrain.revise_plan
repairs surge, plug, sailing-capacity, and coverage rejections, but
AGGRESSIVE_RUSH never concedes rush volume, stays infeasible in the golden
world, and is carried into compare_plans as infeasible - the run fails only
if all three plans end infeasible) -> APPROVAL_REQUIRED (pause)
-> APPROVED: Execution builds actions -> validate_actions -> dispatch
receipts -> RUN_COMPLETED; REJECTED: complete with zero actions.

Run modes: LIVE_STUB = offline deterministic scripted run (default, CI).
LIVE_GEMINI = real ADK agents; refused cleanly when GEMINI_API_KEY absent;
higher thinking budget for Coordinator and Recovery. DEMO_REPLAY = replays
fixtures/replay_events.json offline; approval interaction preserved; UI
shows persistent exact-text "DEMO REPLAY".

Hard behavioral rules for agents (enforced by structure, restated in
prompts): may not change calculated values, invent operational data,
bypass approval, call unlisted tools, or trigger real actions. Tools
allowlist (PRD 11): analyse_connections, simulate_yard,
find_alternative_sailings, compare_plans, retrieve_context,
validate_actions, dispatch_plan.

## 8. API surface

On main today: GET /api/health; GET /api/scenario; POST /api/runs
(ScenarioControls -> RunCreated with events_url); GET /api/runs/{id}/events
(SSE, event name "trace" with TraceEvent JSON, terminal event
"stream_end"); GET /api/runs/{id} (WorkflowState); POST /api/reset.

Landing with cascade/workflow-api: POST /api/runs gains a mode field
(DEMO_REPLAY selectable, LIVE_GEMINI guarded); SSE becomes a live queue
that pauses at DISPUTE_OPENED / APPROVAL_REQUIRED and resumes after the
matching POST; POST /api/runs/{id}/dispute-resolution
(DisputeResolutionRequest); POST /api/runs/{id}/approval (ApprovalRequest);
WorkflowState.results populated (ConnectionAnalysis, baseline_yard,
planned_yard, AlternativeSailingResult, PlanComparison, dispatched_actions,
receipts).

## 9. Testing map

- tests/test_contracts.py, test_api.py, test_adk_shell.py - foundation.
- tests/test_fixtures.py - 9 tests: world validity, byte-determinism,
  counts, 60 reefers, 18h margin mix has all three classes, plugs < 60,
  referential integrity, sailing sanity.
- tests/test_engine_*.py (5 files, 33 tests) plus tests/engine_world.py
  hand-written world builders - PRD acceptance: margins 5/4/0/-1 ->
  SAFE/AT_RISK/AT_RISK/MISSED; 11 reefers vs 10 plugs -> one shortage;
  cost total = component sum; infeasible-cheaper never recommended;
  determinism; validate_actions rejects out-of-plan actions.
- frontend vitest (landing) - alert render, graph totals = group sums,
  dispute overlay, approval gating, receipts, DEMO REPLAY label.
- e2e/specs/ Playwright: stub-smoke.spec.ts passes today (run from UI,
  trace renders, stream end); golden-run, timeout-fallback, demo-replay
  are test.fixme() until workflow + frontend merge. UI selector contract:
  dispute dialog role=dialog name contains "dispute" with a "reefer plug
  capacity" constraint button; exactly three role=article plan cards, one
  visible "Recommended"; Approve/Reject buttons; no "work order"/
  "receipt"/"dispatched"/"carrier notice" text pre-approval; literal
  "ACCEPTED" on receipts; "DEMO REPLAY" exact text in replay.
- scripts/preflight.py - ports, fixture validation, key presence,
  optional --live Gemini round trip. Exit nonzero only on hard failures.

Definition of done for the build: PRD section 18 checklist, mirrored as
checkboxes in plan/checklists/demo_runbook.md.

## 10. Working agreements

- Style: no emojis anywhere; no em dashes (plain dash); terse prose;
  commit messages without agent co-author lines.
- Python only through uv. Windows PowerShell is the primary shell.
- Never hand-edit generated files (contracts/openapi.json,
  frontend/src/api/schema.d.ts); regenerate via npm run generate:types.
- Contract changes go through Agent 1 (integration) only; other
  workstreams file requests in plan/contract_requests_<name>.md.
- Determinism everywhere: seed 42, no wall-clock reads in generators or
  engine, categorical confidence only, deterministic ids (WO-001 style,
  no uuids in engine outputs).
- Honesty rules: replay is always labeled; cached data is always labeled;
  synthetic/illustrative labels on all values; no hidden chain-of-thought
  in any UI or trace.
- Stop adding features once the golden end-to-end flow passes (PRD 15.5).
