# CASCADE Hackathon Product Requirements Document

## 1. Project overview

CASCADE is a human-in-the-loop agentic AI demonstration for PSA port operations. It shows how a delayed incoming vessel can cause missed onward sailings, longer container stays, crowded storage yards, and additional operating costs over the next 72 hours.

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

CASCADE demonstrates how an AI agent can coordinate analysis tools, compare recovery options, request approval, and show a clear execution trace.

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

Higher autonomy is not required. Human approval is appropriate because the proposed actions affect cargo handling and vessel connections.

## 4. Goals

- Demonstrate a complete alert-to-action agentic workflow.
- Produce believable connection and yard-impact results.
- Compare exactly three recovery plans.
- Explain why one plan is recommended.
- Require a visible human approval step.
- Show one controlled tool failure and safe fallback.
- Make the demonstration deterministic and easy to reset.
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

A reefer is a refrigerated container. It needs electrical power to keep its cargo cold.

The graph may group containers by cargo type and onward vessel. The simulator can still calculate individual container results internally.

## 8. Golden demonstration scenario

The user injects an 18-hour delay for the synthetic vessel `MV ATLAS STAR`.

CASCADE then:

1. identifies the issue and response objective;
2. finds safe, at-risk, and missed connections;
3. identifies 60 pharmaceutical reefers as high priority;
4. forecasts yard occupancy for 72 hours;
5. creates rush, rebook, and hybrid recovery plans;
6. recommends the hybrid plan;
7. pauses for human approval;
8. dispatches mocked work orders and carrier notices;
9. shows execution receipts and the improved forecast.

The demonstration also includes a controlled alternative-sailing lookup timeout. CASCADE reports the error, uses a documented fallback fixture, lowers confidence, and requires human review.

All figures shown in the interface must come from the same fixture and calculation path. The user interface must not contain separate hard-coded result totals.

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

Generate exactly three plans:

1. `AGGRESSIVE_RUSH`: protect current connections using additional handling capacity;
2. `STANDARD_REBOOK`: move affected containers to later synthetic sailings;
3. `OPTIMIZED_HYBRID`: rush high-priority cargo and rebook lower-priority cargo.

Each plan shows cost, delay, yard peak, critical cargo protected, and important assumptions.

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

The AI agent explains the calculated recommendation but cannot change simulation values.

**TEST**

Given fixed plan results, repeated runs return the same recommendation. A cheaper plan that exceeds capacity is never recommended.

### 9.10 Human approval

**FEATURE**

Pause before mocked dispatch. Let the controller compare plans, approve one plan, or reject the recommendation.

**TEST**

No mocked work order appears before approval. Approval produces the expected actions, while rejection produces none.

### 9.11 Execution trace

**FEATURE**

Show an ordered trace containing:

- workflow stage;
- tool called;
- short input summary;
- result or error;
- recommendation;
- human decision;
- mocked action and receipt.

Do not display hidden chain-of-thought.

**TEST**

The golden run shows every required stage in order. Every displayed figure matches the corresponding tool result.

### 9.12 Controlled failure and fallback

**FEATURE**

Provide a demo control that makes the alternative-sailing tool time out. Report the failure, load a clearly labeled cached fixture, lower recommendation confidence, and require human approval.

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

Convert the approved plan into mocked terminal work orders and carrier notices. Display a success or failure receipt for each action.

**TEST**

Approving the hybrid plan produces the expected fixed set of mocked actions and visible receipts without contacting an external system.

### 9.16 Demo reset

**FEATURE**

Reset the application to the original golden scenario through one button or command.

**TEST**

After a completed or failed run, reset restores the original alert, fixture, trace, plans, and UI state.

## 10. Agent behavior

The agent coordinates the workflow. Deterministic tools perform calculations.

```text
receive alert
    -> identify issue and objective
    -> call connection analysis
    -> call yard simulation
    -> call alternative-sailing lookup
    -> generate and compare plans
    -> request human approval
    -> dispatch mocked actions
    -> report results
```

The agent may:

- choose the next approved tool;
- summarize structured results;
- compare the three plans;
- request clarification or approval;
- explain failures and fallback behavior.

The agent may not:

- change calculated values;
- invent missing operational data;
- bypass the approval step;
- call unlisted tools;
- execute real operational actions.

## 11. Demonstration tools

| Tool | Purpose | Implementation |
|---|---|---|
| `analyse_connections` | Classify container connections | Deterministic local function |
| `simulate_yard` | Produce the 72-hour yard forecast | Deterministic local function |
| `find_alternative_sailings` | Return later synthetic sailings | Mocked tool with optional timeout |
| `compare_plans` | Calculate and rank three plans | Deterministic local function |
| `dispatch_plan` | Produce work orders and notices | Mocked tool only |

## 12. Architecture

```text
React dashboard
      |
      | REST and SSE
      v
FastAPI backend
      |
      +-- agent workflow
      +-- deterministic analysis tools
      +-- mocked external tools
      +-- in-memory demo state
      |
      v
Seeded JSON fixtures
```

SSE means Server-Sent Events. It lets the server send trace updates to the browser over one open connection.

### Technology choices

- Python 3.12 or later.
- `uv` for all Python package and script commands.
- FastAPI and Pydantic for the backend and typed data.
- A small explicit workflow graph for agent stages and approval.
- React and TypeScript for the frontend.
- React Flow for the cascade graph.
- A lightweight chart library for yard forecasts.
- JSON fixtures and in-memory state for deterministic reset.
- Playwright for the golden end-to-end demonstration test.

No database is required for the hackathon build.

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

### Synthetic operational data

Generate the complete demo fixture with seed `42`. Clearly label all vessels, containers, yard values, costs, plans, and results as synthetic or illustrative.

Store one reviewed fixture in the repository so the judged demonstration does not depend on network access.

## 14. Safety, security, and scalability statement

These topics are documentation deliverables, not production implementation work.

### Safety

- All actions are mocked.
- Human approval is always required.
- Capacity rules are deterministic.
- Missing or failed data lowers confidence and prevents automatic action.
- The interface labels synthetic and illustrative values.

### Security

A production version would require authentication, role-based approval, secret management, restricted tool permissions, protected audit records, input validation, and prompt-injection controls. The hackathon build contains no real credentials or production connections.

Prompt injection is when untrusted text tries to command the agent. The demonstration uses controlled synthetic fixtures, while the production design would treat all external text as untrusted data.

### Scalability

A production version could replace JSON and in-memory state with a relational database, event bus, and independent simulation workers. The hackathon build only needs to support one local demonstration user and one scenario at a time.

An event bus is a shared delivery system for updates between services.

## 15. Multi-agent implementation plan

### 15.1 Blocking foundation

Agent 1 completes the shared foundation before parallel implementation begins:

- repository structure;
- Python and frontend package configuration;
- root lint, test, type-check, and build commands;
- shared Pydantic and OpenAPI schemas;
- generated TypeScript API types;
- workflow-state and trace-event schemas;
- golden input fixture;
- fake tool responses;
- minimal backend and frontend shells.

The foundation passes when a clean worktree installs successfully, validates the golden fixture, generates frontend types, renders a fake alert, and passes all initial checks.

### 15.2 Parallel worktrees

After the foundation passes, six agents work simultaneously:

| Agent | Branch | Ownership |
|---|---|---|
| 1: Integration | `codex/integration-foundation` | contracts, root configuration, integration, shared checks |
| 2: Fixtures | `codex/data-fixtures` | synthetic generator and reviewed golden fixture |
| 3: Analysis | `codex/simulation-engine` | connections, yard, reefer, cost, plans, unit tests |
| 4: Workflow | `codex/workflow-api` | agent stages, API, SSE, approval, mock dispatch |
| 5: Frontend | `codex/frontend-dashboard` | dashboard, graph, chart, cards, trace, approval UI |
| 6: Verification | `codex/verification-delivery` | end-to-end test, failure test, reset script, slides, video |

Each agent owns separate paths. Shared contract changes go through Agent 1.

### 15.3 Merge order

Merge small working slices in this order:

1. contracts, fixtures, and fake responses;
2. alert and objective display;
3. connection analysis and cascade graph;
4. yard simulation and forecast;
5. three plans and recommendation;
6. approval and mocked dispatch;
7. controlled failure and fallback;
8. golden end-to-end test and UI polish.

A vertical slice is one small path that works from user input to visible result.

### 15.4 Seven-day schedule

| Day | Target |
|---|---|
| 1 | Foundation contracts and fake vertical path pass |
| 2 | Six worktrees build fixtures, tools, API, UI, and tests in parallel |
| 3 | Alert, connection analysis, and cascade graph integrate |
| 4 | Yard forecast, plans, and recommendation integrate |
| 5 | Approval, mocked dispatch, and golden end-to-end flow pass |
| 6 | Failure path, visual polish, slides, and video rehearsal |
| 7 | Final checks, reset rehearsal, recording, and backup video |

### 15.5 Coordination rules

- Use `contracts/` as the shared interface source.
- Do not manually edit generated API types.
- Keep commits small and merge working slices daily.
- Run Python commands through `uv`.
- Do not add live external service dependencies.
- Route cross-owned defects to the owning agent with a reproduction.
- Stop adding features after the golden end-to-end flow passes.

## 16. Quality plan

Required automated checks:

- unit tests for classification, yard, costs, and plan ranking;
- contract tests for API and trace shapes;
- one golden browser test from alert through mocked receipt;
- one browser test for the tool timeout and fallback;
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
| 2:00 to 7:00 | Golden workflow from alert to mocked receipt |
| 7:00 to 8:00 | Controlled tool failure and fallback |
| 8:00 to 9:00 | Architecture, safety, security, and scalability |
| 9:00 to 10:00 | Illustrative impact, limitations, and closing |

### Presentation

The presentation must contain no more than 10 slides:

1. title and value proposition;
2. PSA problem;
3. cascading disruption example;
4. solution and autonomy choice;
5. agent tools and execution flow;
6. demonstration results;
7. architecture;
8. uncertainty, safety, and security;
9. illustrative impact, limitations, and scalability;
10. team and next steps.

All synthetic values and illustrative savings must be labeled.

## 18. Release acceptance criteria

The demonstration is ready when:

- the golden workflow succeeds from alert through mocked receipt;
- reset restores the original scenario;
- the same fixture produces the same displayed results;
- exactly three plans appear;
- no action appears before approval;
- the timeout path visibly reports an error and fallback;
- every trace value matches a tool result;
- the interface has no clipped text, overlapping controls, or unreadable charts;
- lint, types, required unit tests, and both browser tests pass;
- the demo runs without internet access;
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
- Security and scalability are described but not implemented.
