# CASCADE Hackathon Product Requirements Document

## 1. Project overview

CASCADE is an AI-led, human-governed multi-agent demonstration for PSA port operations. It shows how a delayed incoming vessel can cause missed onward sailings, longer container stays, crowded storage yards, and additional operating costs over the next 72 hours.

CASCADE stands for Cognitive Agent for Synchro-modal Cascading Anomaly and Disruption Engine.

The product is a hackathon demonstration. It uses synthetic operational data and mocked external systems. It will not connect to production PSA systems or control real port operations.

### Transshipment

Transshipment means a container arrives on one ship and leaves on another ship. It is like changing buses. If the first ship is late, the container may miss the next ship.

### Cascading disruption

A cascading disruption is one delay causing more delays. A late ship can make containers miss their next ship. Those containers stay in the yard, use space, and make other work harder.

## 2. Problem

Port controllers need to understand the consequences of a vessel delay quickly. They must identify:

- which containers may miss their next vessel;
- which cargo needs protection first;
- whether the yard may become too full;
- which recovery plan gives the best outcome;
- whether a human should approve the action.

CASCADE demonstrates how a coordinator agent delegates work to specialist agents, reconciles their findings, uses deterministic operational tools, develops recovery options, requests human approval, and shows a clear execution trace.

## 3. Hackathon objective

Demonstrate one polished and repeatable workflow that satisfies the PSA Code Sprint requirements:

1. process an operational alert;
2. identify the issue and objective;
3. choose and invoke relevant tools;
4. determine a recovery plan;
5. handle uncertainty and one tool failure;
6. request human approval;
7. dispatch mocked actions;
8. report decisions, calls, results, approvals, and errors.

The agents independently analyze, delegate, use tools, revise infeasible proposals, and prepare actions. The human sets priorities, resolves exceptional disputes, and approves execution. Human approval is appropriate because the proposed actions affect cargo handling and vessel connections.

## 4. Goals

- Demonstrate a complete alert-to-action agentic workflow.
- Make agent delegation, parallel work, tool use, disagreement, and handoffs clearly visible.
- Produce believable connection and yard-impact results.
- Compare exactly three recovery plans.
- Explain why one plan is recommended.
- Require a visible human approval step.
- Show one controlled tool failure and safe fallback.
- Make the demonstration deterministic and easy to reset.
- Support limited scenario variation without becoming a general simulation platform.
- Deliver a polished single-screen command dashboard.

## 5. Non-goals

- Production deployment.
- Real PSA, terminal, carrier, crane, berth, or customer integration.
- Production authentication, authorization, encryption, or monitoring.
- Accurate prediction of real PSA operations or financial savings.
- Complete port optimization.
- Detailed crane, labor, traffic, weather, or equipment modelling.
- Production-scale performance and reliability.
- Displaying private model reasoning or hidden chain-of-thought.

Removed production features are recorded in `plan/todo.md` as low priority.

## 6. Users

### Primary user

A port operations controller who reviews disruptions and approves recovery actions.

### Demonstration audience

Hackathon judges evaluating relevance, agentic behavior, decision quality, tool orchestration, uncertainty handling, human oversight, impact, and presentation quality.

## 7. Demonstration scope

The synthetic world contains:

- one terminal;
- four yard blocks;
- five to eight vessels;
- 300 to 500 synthetic containers;
- three cargo groups: pharmaceutical reefers, time-critical manufacturing cargo, and general dry cargo;
- three affected outbound vessels;
- three recovery plans;
- two mocked external tools;
- one controlled tool failure.

The user may vary only:

- vessel delay from 6 to 24 hours;
- priority emphasis between cargo protection, congestion reduction, and balanced operation;
- alternative-sailing tool failure on or off.

Arbitrary file uploads and unrestricted scenario editing are outside the demonstration scope.

A reefer is a refrigerated container. It needs electrical power to keep its cargo cold.

The graph may group containers by cargo type and onward vessel. The simulator can still calculate individual container results internally.

## 8. Golden demonstration scenario

The user injects an 18-hour delay for the synthetic vessel `MV ATLAS STAR`.

CASCADE then:

1. identifies the issue and response objective;
2. delegates connection analysis and yard analysis to specialist agents running concurrently;
3. finds safe, at-risk, and missed connections;
4. identifies 60 pharmaceutical reefers as high priority;
5. forecasts yard occupancy for 72 hours;
6. surfaces a controlled disagreement between cargo protection and reefer plug capacity;
7. opens a transient dispute panel for human resolution;
8. handles an alternative-sailing lookup timeout using a labeled cached fixture;
9. creates, validates, and revises rush, rebook, and hybrid recovery plans;
10. recommends the hybrid plan with medium confidence because cached sailing data was used;
11. pauses for human approval;
12. prepares and validates mocked work orders and carrier notices;
13. shows execution receipts and the improved forecast.

The Impact Agent initially recommends rushing all pharmaceutical reefers. The Yard Agent reports that this would exceed available reefer plugs. The coordinator presents both evidence sets and asks the human to confirm the governing constraint before planning continues.

All figures shown in the interface must come from the same fixture and calculation path. The user interface must not contain separate hard-coded result totals.

The live Gemini workflow is attempted first. If the Gemini API is unavailable, the presenter may explicitly start `DEMO_REPLAY` mode. Replay Mode uses a previously captured valid run and must remain visibly labeled throughout. It must never silently impersonate a live agent run.

## 9. Features and tests

### 9.1 Disruption alert

**FEATURE**

Accept an original ETA (Estimated Time of Arrival), revised ETA, vessel port call, and event time. Calculate the delay and start the workflow.

**TEST**

Given the golden alert, CASCADE reports an 18-hour delay and starts exactly one run. Invalid or incomplete input produces a visible error.

### 9.2 Issue and objective identification

**FEATURE**

State the operational issue and the response objective in plain language.

The golden objective is to protect critical cargo, reduce missed connections, avoid severe yard congestion, and minimize illustrative disruption cost.

**TEST**

The golden alert produces the expected vessel, delay, planning horizon, constraints, and objective without adding facts absent from the fixture.

### 9.3 Connection-impact analysis

**FEATURE**

Compare each container's ready time with its onward vessel cutoff and classify it as:

- `SAFE`: more than 4 hours remain;
- `AT_RISK`: 0 through 4 hours remain;
- `MISSED`: the cutoff has passed.

**TEST**

Fixtures with margins of 5, 4, 0, and -1 hours produce `SAFE`, `AT_RISK`, `AT_RISK`, and `MISSED`.

### 9.4 Cargo priority

**FEATURE**

Prioritize pharmaceutical reefers, then time-critical manufacturing cargo, then general dry cargo. Show the cargo category and connection margin that caused the priority.

**TEST**

Containers with the same connection margin are ranked in the documented order and display the correct reason.

### 9.5 Simplified yard forecast

**FEATURE**

Project hourly yard occupancy for four blocks over 72 hours. Model container arrival, onward loading, missed-connection dwell, and rebooked departure.

Mark 85 percent as congested and 100 percent as full.

**TEST**

The golden fixture always produces the same hourly series. Occupancy never becomes negative, and capacity breaches are shown rather than hidden.

### 9.6 Simplified reefer capacity

**FEATURE**

Compare the number of reefers requiring power with the available plug count in each yard block. Report any shortage as critical.

**TEST**

Eleven reefers entering a block with ten available plugs produces one shortage with a visible start time.

### 9.7 Illustrative cost estimate

**FEATURE**

Calculate a simple illustrative cost from fixed documented rates:

- additional container dwell;
- reefer risk;
- missed-connection penalty;
- extra crane time;
- rebooking.

Show each component and label the result as illustrative.

**TEST**

The total equals the sum of the displayed components. Changing one fixture input changes the corresponding component.

### 9.8 Recovery plans

**FEATURE**

The Recovery Agent generates exactly three plans from fixed archetypes:

1. `AGGRESSIVE_RUSH`: protect current connections using additional handling capacity;
2. `STANDARD_REBOOK`: move affected containers to later synthetic sailings;
3. `OPTIMIZED_HYBRID`: rush high-priority cargo and rebook lower-priority cargo.

The agent chooses cargo allocations, actions, and assumptions. Deterministic tools calculate cost, delay, yard peak, and critical cargo protected. Infeasible proposals are rejected and returned to the agent for revision.

**TEST**

The golden scenario returns three plans. Every affected container group receives one action in each plan.

### 9.9 Plan recommendation

**FEATURE**

Recommend a plan using this fixed order:

1. reject plans that exceed physical capacity;
2. protect critical cargo;
3. reduce missed connections;
4. reduce yard congestion;
5. reduce cost and delay.

The coordinator interprets specialist evidence, selects among feasible plans, and explains the recommendation. It cannot change simulation values.

**TEST**

Given fixed plan results, repeated runs return the same recommendation. A cheaper plan that exceeds capacity is never recommended.

### 9.10 Human approval

**FEATURE**

Provide optional human steering after the initial assessment and mandatory approval before mocked dispatch. Let the controller change priorities, compare plans, approve one plan, or reject the recommendation.

**TEST**

No mocked work order appears before approval. Approval produces the expected actions, while rejection produces none.

### 9.11 Execution trace

**FEATURE**

Show an ordered trace containing:

- workflow stage;
- agent name and objective;
- agent handoff;
- tool called;
- short input summary;
- result or error;
- confidence and assumptions;
- elapsed time;
- recommendation;
- human decision;
- mocked action and receipt.

Do not display hidden chain-of-thought.

**TEST**

The golden run shows every required stage in order. Every displayed figure matches the corresponding tool result.

### 9.12 Controlled failure and fallback

**FEATURE**

Provide a demo control that makes the alternative-sailing tool time out. Report the failure, load a clearly labeled cached fixture that may be stale, set confidence to `MEDIUM`, avoid assuming unverified capacity, and require human approval.

**TEST**

When failure mode is enabled, the trace shows the timeout and fallback. The workflow still reaches approval but cannot dispatch automatically.

### 9.13 Cascade graph

**FEATURE**

Display the delayed inbound vessel, three outbound vessels, and grouped container flows. Use labels and colors to distinguish safe, at-risk, missed, and resolved connections.

**TEST**

Graph totals match the analysis results, and every state remains understandable from its text label without color.

### 9.14 Yard and plan comparison

**FEATURE**

Display the baseline yard forecast beside the selected plan forecast. Show three compact plan cards with comparable metrics.

**TEST**

Forecast peaks, times, units, and plan values match the tool results and remain readable on the demonstration screen.

### 9.15 Mocked action dispatch

**FEATURE**

The Execution Agent converts the approved plan into sequenced mocked terminal work orders, reefer checks, and carrier notices. A deterministic validator rejects actions that are not present in the approved plan or allowed tool list. Display a success or failure receipt for each accepted action.

**TEST**

Approving the hybrid plan produces the expected fixed set of mocked actions and visible receipts without contacting an external system.

### 9.16 Demo reset

**FEATURE**

Reset the application to the original golden scenario through one button or command.

**TEST**

After a completed or failed run, reset restores the original alert, fixture, trace, plans, and UI state.

### 9.17 Multi-agent orchestration

**FEATURE**

Run one Coordinator Agent and four specialist agents. Run the Impact Agent and Yard Agent concurrently, then hand their evidence to the Recovery Agent. The Execution Agent runs only after approval.

**TEST**

The trace shows both parallel specialists, their results, the recovery handoff, and the approval-gated execution handoff in the required order.

### 9.18 Transient dispute resolution

**FEATURE**

Open a temporary dispute panel only when agents conflict, inputs are ambiguous, or a human decision is required. Show each position and its tool evidence. Convert the human response into a visible confirmed constraint.

**TEST**

The golden reefer-capacity conflict pauses planning until the human selects a constraint. The confirmed constraint appears in the trace and revised plans respect it.

### 9.19 Scenario controls

**FEATURE**

Allow the user to vary delay, priority emphasis, and alternative-sailing failure. Re-run agent analysis and calculations from those inputs.

**TEST**

Changing any supported control starts a new run whose trace and results reference the selected value. Unsupported input cannot enter the workflow.

### 9.20 Honest Replay Mode

**FEATURE**

Replay one previously captured valid agent run when the Gemini API is unavailable. Display a persistent `DEMO REPLAY` label and preserve the normal approval interaction.

**TEST**

Replay works without network access, matches the captured event sequence, and cannot be mistaken for a live Gemini run.

## 10. Agent behavior

CASCADE is AI-led and human-governed. Gemini agents interpret the disruption, delegate analysis, choose tools, reconcile evidence, propose actions, and revise rejected plans. Deterministic tools remain the source of truth for operational calculations and capacity constraints.

### Agent roles

| Agent | Responsibility | Reasoning level |
|---|---|---|
| Coordinator Agent | Interpret the alert, set objectives, delegate work, reconcile results, manage disputes, and recommend the next step | Higher |
| Impact Agent | Analyze connections, cargo urgency, and disruption consequences | Lower |
| Yard Agent | Analyze yard occupancy, reefer plugs, and physical constraints | Lower |
| Recovery Agent | Generate, validate, revise, and compare recovery plans | Higher |
| Execution Agent | Translate an approved plan into validated mocked actions | Lower |

```text
receive alert
    -> identify issue and objective
    -> delegate in parallel
        -> Impact Agent calls connection analysis
        -> Yard Agent calls yard simulation
    -> reconcile evidence or open dispute panel
    -> call alternative-sailing lookup
    -> Recovery Agent generates plans
    -> deterministic tools validate and score plans
    -> Recovery Agent revises rejected plans
    -> request human approval
    -> Execution Agent prepares actions
    -> deterministic action validation
    -> dispatch mocked actions
    -> report results
```

Agents may:

- choose the next approved tool;
- delegate work to the named specialist agents;
- summarize structured results;
- generate allocations and actions within the three plan archetypes;
- revise a proposal rejected by deterministic validation;
- compare feasible plans and explain trade-offs;
- request clarification or approval;
- explain failures and fallback behavior.

Agents may not:

- change calculated values;
- invent missing operational data;
- bypass the approval step;
- call unlisted tools;
- execute real operational actions.

### Confidence

Use categorical confidence only:

- `HIGH`: all required inputs are complete and required tools succeeded;
- `MEDIUM`: a fallback or potentially stale cached result was used;
- `LOW`: critical inputs conflict or remain missing.

Low confidence forces dispute resolution before planning continues. Medium confidence permits planning but never removes approval. Do not display invented confidence percentages.

## 11. Demonstration tools

| Tool | Purpose | Implementation |
|---|---|---|
| `analyse_connections` | Classify container connections | Deterministic local function |
| `simulate_yard` | Produce the 72-hour yard forecast | Deterministic local function |
| `find_alternative_sailings` | Return later synthetic sailings | Mocked tool with optional timeout |
| `compare_plans` | Calculate and rank three plans | Deterministic local function |
| `retrieve_context` | Retrieve selected PSA and port context with source links | Local evidence-pack lookup |
| `validate_actions` | Ensure proposed actions match the approved plan and allowlist | Deterministic local function |
| `dispatch_plan` | Produce work orders and notices | Mocked tool only |

## 12. Architecture

```text
React dashboard
      |
      | REST and SSE
      v
FastAPI backend
      |
      +-- Google ADK multi-agent workflow
      +-- deterministic analysis tools
      +-- mocked external tools
      +-- in-memory demo state
      +-- captured Replay Mode events
      |
      v
Seeded JSON fixtures and local evidence pack
```

SSE means Server-Sent Events. It lets the server send trace updates to the browser over one open connection.

### Technology choices

- Python 3.12 or later.
- `uv` for all Python package and script commands.
- FastAPI and Pydantic for the backend and typed data.
- Google Agent Development Kit (ADK) for multi-agent delegation, tools, sessions, and events.
- Gemini API using `gemini-3.5-flash` for all five agents.
- Higher reasoning effort for the Coordinator and Recovery agents, and lower effort for the other specialists.
- An explicit coordinator-controlled stage sequence around ADK for repeatability and approval gates.
- React and TypeScript for the frontend.
- React Flow for the cascade graph.
- A lightweight chart library for yard forecasts.
- JSON fixtures and in-memory state for deterministic reset.
- Playwright for the golden end-to-end demonstration test.

No database is required for the hackathon build.

The system runs locally on one laptop. Gemini is the only live network dependency. Google Cloud deployment, Agent-to-Agent networking, and a second model provider are outside scope.

## 13. Data plan

### Official context sources

- [PSA International Annual and Sustainability Report 2025](https://annualreport.globalpsa.com/)
- [PSA Singapore Sustainability Report 2025](https://www.singaporepsa.com/wp-content/uploads/2026/06/PSA-SG-Sustainability-Report-2025.pdf)
- [MPA Port Statistics](https://www.mpa.gov.sg/who-we-are/newsroom-resources/research-and-statistics/port-statistics)
- [MPA Vessel Arrivals, Monthly](https://data.gov.sg/collections/394/view)
- [UN/LOCODE](https://unlocode.unece.org/publications/)

MPA means Maritime and Port Authority of Singapore.

UN/LOCODE means United Nations Code for Trade and Transport Locations. It provides standard codes for ports and other transport places.

These sources provide context and rough calibration only. They do not provide container connections, yard occupancy, crane availability, customer costs, or alternative-sailing capacity.

Extract a small reviewed evidence pack from these sources. The `retrieve_context` tool returns short facts with source links. Agents must not browse the internet during the live workflow.

### Synthetic operational data

Generate the complete demo fixture with seed `42`. Clearly label all vessels, containers, yard values, costs, plans, and results as synthetic or illustrative.

Store one reviewed fixture in the repository so the judged demonstration does not depend on network access.

### Dashboard layout

- Top: alert, objective, scenario controls, and current workflow stage.
- Left: cascade graph of vessels and affected cargo.
- Center: live agent activity, parallel work, and handoffs.
- Right: operational metrics and three recovery-plan cards.
- Bottom drawer: expandable execution trace.
- Temporary overlay: dispute evidence and human resolution.
- Fixed approval bar: selected plan, consequences, approve, and reject.

Chat is not a persistent assistant interface. It appears only inside the transient dispute panel. Completed agent activity cards remain expandable and show objectives, inputs, tools, evidence summaries, assumptions, confidence, result, elapsed time, and next handoff. They never expose private chain-of-thought.

## 14. Safety, security, and scalability statement

These topics are documentation deliverables, not production implementation work.

### Safety

- All actions are mocked.
- Human approval is always required.
- Capacity rules are deterministic.
- Missing or failed data lowers confidence and prevents automatic action.
- The interface labels synthetic and illustrative values.
- Replay Mode is always visibly labeled and never presented as live agent execution.

### Security

A production version would require authentication, role-based approval, secret management, restricted tool permissions, protected audit records, input validation, and prompt-injection controls. The hackathon build contains no real credentials or production connections.

Prompt injection is when untrusted text tries to command the agent. The demonstration uses controlled synthetic fixtures, while the production design would treat all external text as untrusted data.

### Scalability

A production version could replace JSON and in-memory state with a relational database, event bus, and independent simulation workers. The hackathon build only needs to support one local demonstration user and one scenario at a time.

Free-tier Gemini prompts and responses may be used by Google to improve its products. Only synthetic data and the public evidence pack may be sent to Gemini.

An event bus is a shared delivery system for updates between services.

## 15. Multi-agent implementation plan

### 15.1 Blocking foundation

Agent 1 completes the shared foundation before parallel implementation begins:

- repository structure;
- Python and frontend package configuration;
- root lint, test, type-check, and build commands;
- shared Pydantic and OpenAPI schemas;
- generated TypeScript API types;
- workflow-state, agent-event, dispute, confidence, and trace-event schemas;
- Google ADK shell with five stub agents and stub tools;
- golden input fixture;
- fake tool responses;
- captured Replay Mode event fixture;
- minimal backend and frontend shells.

The foundation passes when a clean worktree installs successfully, validates the golden fixture, generates frontend types, streams a fake multi-agent run to the dashboard, renders the alert, and passes all initial checks.

### 15.2 Parallel worktrees

After the foundation passes, six agents work simultaneously:

| Agent | Branch | Ownership |
|---|---|---|
| 1: Integration | `codex/integration-foundation` | contracts, root configuration, integration, shared checks |
| 2: Fixtures | `codex/data-fixtures` | synthetic generator and reviewed golden fixture |
| 3: Analysis | `codex/simulation-engine` | deterministic connections, yard, reefer, cost, validation, and unit tests |
| 4: Workflow | `codex/workflow-api` | Gemini and ADK agents, API, SSE, disputes, approval, and mock dispatch |
| 5: Frontend | `codex/frontend-dashboard` | dashboard, agent activity, dispute panel, graph, chart, plans, trace, and approval UI |
| 6: Verification | `codex/verification-delivery` | recorded responses, live evaluation, browser tests, reset, preflight, slides, and video |

Each agent owns separate paths. Shared contract changes go through Agent 1.

### 15.3 Merge order

Merge small working slices in this order:

1. contracts, fixtures, and fake responses;
2. alert and objective display;
3. visible parallel agent delegation with recorded responses;
4. connection analysis, yard simulation, and visual results;
5. dispute resolution and confirmed constraints;
6. agent-generated plans, deterministic validation, and recommendation;
7. approval, validated mocked dispatch, and receipts;
8. live Gemini path, tool failure, Replay Mode, end-to-end tests, and UI polish.

A vertical slice is one small path that works from user input to visible result.

### 15.4 Seven-day schedule

| Day | Target |
|---|---|
| 1 | Foundation contracts and fake vertical path pass |
| 2 | Six worktrees build fixtures, tools, API, UI, and tests in parallel |
| 3 | Parallel agents, alert, connection analysis, yard analysis, and visual results integrate |
| 4 | Dispute resolution, plans, validation, and recommendation integrate |
| 5 | Approval, mocked dispatch, Replay Mode, and golden end-to-end flow pass |
| 6 | Live Gemini evaluation, failure path, visual polish, slides, and video rehearsal |
| 7 | Final checks, reset rehearsal, recording, and backup video |

### 15.5 Coordination rules

- Use `contracts/` as the shared interface source.
- Do not manually edit generated API types.
- Keep commits small and merge working slices daily.
- Run Python commands through `uv`.
- Do not add live external service dependencies other than the Gemini API.
- Keep all prompts and agent outputs versioned and schema-validated.
- Route cross-owned defects to the owning agent with a reproduction.
- Stop adding features after the golden end-to-end flow passes.

## 16. Quality plan

Required automated checks:

- unit tests for classification, yard, costs, and plan ranking;
- contract tests for API and trace shapes;
- deterministic agent tests using recorded Gemini responses;
- one golden browser test from alert through dispute, approval, and mocked receipt;
- one browser test for the tool timeout, cached sailing fallback, and medium confidence;
- one browser test for visibly labeled Replay Mode;
- one optional live Gemini evaluation for valid delegation, tool selection, evidence use, constraint compliance, and approval gating;
- lint and type checks for backend and frontend;
- one visual review at the demonstration screen size.

Production-scale, exhaustive, and cross-browser testing is not required.

## 17. Submission deliverables

### Demonstration video

The video must be no longer than 10 minutes:

| Time | Content |
|---|---|
| 0:00 to 1:00 | PSA problem, user, and objective |
| 1:00 to 2:00 | CASCADE and human-in-the-loop design |
| 2:00 to 7:00 | Live multi-agent workflow, parallel analysis, dispute, plans, approval, and mocked receipt |
| 7:00 to 8:00 | Tool timeout, cached fallback, and confidence handling |
| 8:00 to 9:00 | Architecture, safety, security, and scalability |
| 9:00 to 10:00 | Illustrative impact, limitations, and closing |

### Presentation

The presentation must contain no more than 10 slides:

1. title and value proposition;
2. PSA problem;
3. cascading disruption example;
4. solution and autonomy choice;
5. agent tools and execution flow;
6. visible agent collaboration and demonstration results;
7. architecture;
8. uncertainty, safety, and security;
9. illustrative impact, limitations, and scalability;
10. team and next steps.

All synthetic values and illustrative savings must be labeled.

## 18. Release acceptance criteria

The demonstration is ready when:

- the golden workflow succeeds from alert through mocked receipt;
- live activity clearly shows all five agents, parallel specialist work, tool calls, and handoffs;
- the reefer-capacity disagreement pauses for human resolution;
- reset restores the original scenario;
- the same fixture produces the same displayed results;
- exactly three plans appear;
- no action appears before approval;
- the timeout path visibly reports an error and fallback;
- cached sailing data changes confidence to `MEDIUM`;
- Replay Mode works offline and remains visibly labeled;
- every trace value matches a tool result;
- unsupported or unapproved actions fail deterministic validation;
- the interface has no clipped text, overlapping controls, or unreadable charts;
- lint, types, required unit tests, deterministic agent tests, and browser tests pass;
- the preflight check validates Gemini access, model availability, ports, and fixtures;
- the demo can replay without internet access;
- the video is no longer than 10 minutes;
- the presentation contains no more than 10 slides;
- no real external action can be triggered.

## 19. Limitations

- All operational records and costs are synthetic.
- The result is a demonstration of a decision process, not a prediction of real PSA outcomes.
- The yard model omits many real operational constraints.
- Alternative sailings and action receipts are mocked.
- Fixed ETA scenarios do not represent a full probability forecast.
- The application supports one scenario and one local user at a time.
- Live agent wording and tool sequence may vary between runs even when calculated results remain fixed.
- Gemini free-tier availability and limits are not guaranteed during judging.
- Replay Mode demonstrates a captured run rather than live AI reasoning.
- Security and scalability are described but not implemented.
