# CASCADE Product Requirements Document

## 1. Project overview

CASCADE is a decision-support system for port operations controllers. It predicts how a late inbound vessel can cause missed onward sailings, longer container stays, crowded storage yards, and higher operating costs over the next 72 hours.

CASCADE stands for Cognitive Agent for Synchro-modal Cascading Anomaly and Disruption Engine.

The hackathon product uses synthetic data and mocked external systems. It does not control real port equipment or make real carrier bookings.

### Concept worth remembering: transshipment

Transshipment means a container arrives on one ship and leaves on another ship. Think of changing buses during a journey. If the first bus is late, the passenger may miss the next bus. CASCADE finds those problems before they spread.

### Concept worth remembering: cascading disruption

A cascading disruption is one delay causing more delays. A late ship can make containers miss their next ship. Those containers then stay in the yard, take up space, and slow other work.

## 2. Problem

Port controllers receive frequent vessel schedule changes. They must quickly determine:

- which containers will miss their onward connection;
- which cargo needs urgent protection;
- when yard blocks will become too full;
- which recovery plan has the best operational outcome;
- which decisions require human approval.

Manual analysis across alerts, schedules, manifests, and spreadsheets is slow and difficult to repeat. CASCADE combines these inputs into one reproducible forecast and decision brief.

## 3. Goals

- Detect affected container connections from a revised vessel arrival time.
- Simulate container flow and yard occupancy for 72 hours.
- Generate exactly three feasible recovery plans.
- Explain costs, benefits, constraints, and data confidence.
- Require human approval for sensitive operational actions.
- Produce a replayable, deterministic hackathon demonstration.
- Keep calculations separate from language-model recommendations.
- Maintain an auditable record of inputs, outputs, approval, and mocked execution.

## 4. Non-goals

- Connecting to production PSA systems.
- Controlling cranes, berths, gates, or other physical equipment.
- Sending real EDI (Electronic Data Interchange) carrier messages.
- Predicting weather, labor availability, or equipment failures.
- Optimizing an entire port across multiple weeks.
- Claiming verified savings from synthetic demo results.
- Displaying private model reasoning or hidden chain-of-thought.

## 5. Users

### Primary user

The primary user is a port operations controller responsible for vessel connections, yard conditions, and disruption response.

### Secondary user

The secondary user is an operations manager who reviews high-impact decisions, risks, and expected savings.

## 6. Golden demo scenario

The demo starts with normal operations and a yard at 82 percent occupancy. The user injects an 18-hour delay for the synthetic vessel `MV ATLAS STAR`.

The system then:

1. identifies safe, at-risk, and missed container connections;
2. projects yard occupancy for 72 hours;
3. identifies 60 high-priority pharmaceutical reefer containers;
4. creates aggressive, rebooking, and hybrid recovery plans;
5. recommends the hybrid plan with evidence;
6. pauses for human approval;
7. sends approved actions to mocked external systems;
8. shows execution receipts and updated projected outcomes.

A reefer is a refrigerated container. It needs electrical power to keep its cargo cold.

All scenario counts and financial results must come from the simulation engine. They must not be separately hard-coded in the user interface.

## 7. Features and tests

### 7.1 Disruption injection

**FEATURE**

Accept a vessel port call, original ETA (Estimated Time of Arrival), revised ETA, and event timestamp. Calculate the delay from the two ETA values and reject inconsistent input.

**TEST**

Given the seeded `MV ATLAS STAR` port call and a revised ETA 18 hours later, the API creates one disruption with `delay_hours = 18`. Repeating the same request with the same idempotency key creates no duplicate.

### 7.2 Connection impact analysis

**FEATURE**

Calculate when each container will be ready for its onward vessel. Compare that time with the onward vessel's operational cutoff, not only its departure time.

```text
ready_time = inbound_berth_time
           + container_discharge_offset
           + transfer_processing_time

connection_margin = outbound_cutoff_time - ready_time
```

Classify each connection as:

- `SAFE`: margin is greater than 4 hours;
- `AT_RISK`: margin is from 0 through 4 hours;
- `MISSED`: margin is below 0 hours.

**TEST**

Use fixtures with margins of 5, 4, 0, and -1 hours. The expected results are `SAFE`, `AT_RISK`, `AT_RISK`, and `MISSED`.

### 7.3 Cargo priority assessment

**FEATURE**

Prioritize cargo using declared category, temperature requirements, dangerous-goods status, service commitment, and connection margin. The initial priority order is pharmaceutical reefer, dangerous goods, time-critical manufacturing cargo, perishable reefer, then general dry cargo.

Dangerous goods are materials that need special handling because they may burn, react, leak, or harm people and the environment.

**TEST**

Given containers with equal connection margins but different categories, the system ranks them in the documented order and records the fields that caused each priority.

### 7.4 Yard occupancy simulation

**FEATURE**

Simulate each yard block in hourly steps for 72 hours. Model container arrival, discharge, placement, onward loading, missed-connection dwell, and rebooking departure. Convert 20-foot containers to 1 TEU and 40-foot containers to 2 TEU.

TEU means Twenty-foot Equivalent Unit. It is a shared measuring stick: one 20-foot container is 1 TEU and one 40-foot container is 2 TEU.

Occupancy is stored as a fraction from 0 to 1. Congestion overhead is:

```text
overhead(U) = 1.0,                                      when U <= 0.85
overhead(U) = 1.0 + 0.15 * exp(20 * (U - 0.85)),       when U > 0.85
```

**TEST**

The same seed, disruption, and simulation version produce byte-equivalent results. Occupancy never becomes negative. A value above physical capacity is returned as a visible capacity breach, not silently capped.

### 7.5 Reefer plug simulation

**FEATURE**

Track total and occupied electrical plugs in every yard block. Mark reefers without an available plug as critical. Do not treat the stated 36-hour limit as battery life unless the dataset explicitly marks the container as operating without external power.

**TEST**

Given 11 reefers entering a block with 10 available plugs, the result reports one plug shortage with the affected container ID and start time.

### 7.6 Cost calculation

**FEATURE**

Calculate costs in Singapore dollars using versioned rate assumptions. Return every component separately and include its quantity, unit, rate, and duration. Initial components are excess dwell, reefer power, service penalties, crane labor, rebooking, and yard shuffle overhead.

The system must state whether billing rounds partial days up, down, or proportionally. It must prevent the same expense from appearing in more than one component.

**TEST**

A fixture with known quantities and rates produces the expected itemized total. The total equals the exact sum of components, and changing one rate changes only its corresponding component.

### 7.7 Recovery plan generation

**FEATURE**

Generate exactly three feasible plans:

1. `AGGRESSIVE_RUSH`: protect the largest number of current connections using available handling capacity;
2. `STANDARD_REBOOK`: move affected containers to later sailings with confirmed synthetic capacity;
3. `OPTIMIZED_HYBRID`: rush high-priority cargo and rebook lower-priority cargo.

Every plan lists container assignments, required resources, expected cost, delay, yard peak, reefer risk, and constraint violations. An infeasible plan remains visible but cannot be recommended or approved.

**TEST**

For the golden scenario, three plans are returned. Every affected container appears exactly once in each plan. No feasible plan exceeds crane, vessel, yard, or reefer-plug capacity.

### 7.8 Plan scoring and recommendation

**FEATURE**

Rank feasible plans using deterministic normalized metrics. The initial decision order is:

1. reject safety or physical-capacity violations;
2. minimize critical cargo failures;
3. minimize missed connections;
4. minimize yard capacity breaches;
5. minimize total cost and delay.

The language model may summarize results but may not invent inputs, alter calculated values, or override feasibility rules.

**TEST**

Given fixed plan metrics, repeated ranking returns the same order. A cheaper plan with a safety violation is never recommended over a safe plan.

### 7.9 Human approval

**FEATURE**

Require human approval when any of these conditions is true:

- projected disruption cost is at least SGD 250,000;
- pharmaceutical reefer cargo is at risk;
- a dangerous-goods handling assignment changes;
- crane or berth allocation changes;
- an external booking or work order would be issued;
- required data is stale, missing, or below the configured confidence threshold.

For the hackathon, every external action is mocked and requires approval.

**TEST**

Create one fixture for every approval condition and verify that execution pauses. Verify that a rejected plan creates no work order and that an approved plan resumes exactly once.

### 7.10 Decision brief

**FEATURE**

Show the recommended plan, alternatives, expected improvement, assumptions, risks, confidence, and the evidence used. Clearly label all data as synthetic.

**TEST**

The brief displays all required fields, matches the simulation response exactly, and contains no value absent from the structured result.

### 7.11 Evidence trace

**FEATURE**

Stream a concise operational trace containing stage, status, timestamp, summary, tool name, input reference, and output reference. Never expose private model reasoning or hidden chain-of-thought.

**TEST**

The user sees ordered events from ingestion through approval. After reconnection with the last event ID, the stream resumes without missing or duplicating events.

### 7.12 Cascade graph

**FEATURE**

Display the delayed inbound vessel, connected outbound vessels, and grouped container flows. Edge width represents TEU count. Color and labels identify `SAFE`, `AT_RISK`, `MISSED`, and `RESOLVED` states. Color is never the only indicator.

**TEST**

Graph totals match the API response. Keyboard users can focus every vessel node, open its details, and identify state without relying on color.

### 7.13 Yard forecast

**FEATURE**

Display hourly occupancy for each yard block and mark 85 percent congestion and 100 percent physical capacity thresholds. Allow baseline and proposed plans to be compared.

**TEST**

Chart values and peak timestamps match the simulation result. Thresholds, axes, units, and comparison labels remain readable at supported screen sizes.

### 7.14 Mocked action dispatch

**FEATURE**

Translate an approved plan into mocked work orders and carrier notices. Store each request and receipt with a correlation ID. Dispatch is idempotent and retry-safe.

**TEST**

Submitting approval twice produces one logical dispatch. A simulated timeout followed by a retry does not create duplicate work orders.

### 7.15 Scenario replay

**FEATURE**

Store the input snapshot, random seed, rate version, simulator version, generated plans, decision, and execution receipts so a completed run can be replayed.

**TEST**

Replaying the golden scenario with the recorded versions produces the same classifications, plan metrics, and recommendation.

### 7.16 Failure and uncertainty handling

**FEATURE**

Show optimistic, expected, and pessimistic scenarios when ETA confidence is uncertain. Mark recommendations as degraded when required data or tools are unavailable. Never silently substitute invented data.

**TEST**

When the schedule lookup times out, the run enters `DEGRADED_AWAITING_REVIEW`, states the missing evidence, and prevents dispatch.

## 8. Functional architecture

```text
React command dashboard
        |
        | REST and SSE
        v
FastAPI application
        |
        +-- disruption service
        +-- deterministic connection engine
        +-- deterministic yard and cost simulator
        +-- plan generator and scorer
        +-- approval workflow
        +-- evidence event stream
        +-- mocked external adapters
        |
        v
SQLite database
```

SSE means Server-Sent Events. It is a simple way for the server to keep sending status updates to the browser over one open connection.

The workflow layer coordinates deterministic services. It does not own shipping calculations. This separation keeps results testable and allows the language model to be replaced without changing business rules.

## 9. Technology plan

### Backend

- Python 3.12 or later.
- `uv` for dependency management and all Python commands.
- FastAPI for REST and SSE endpoints.
- Pydantic for validation and typed contracts.
- SQLAlchemy and SQLite for local persistence.
- A workflow graph for pause, approval, resume, and failure states.
- Deterministic services for connection, yard, cost, and scoring logic.

### Frontend

- React and TypeScript.
- React Flow for the cascade graph.
- A chart library for the 72-hour yard forecast.
- Generated TypeScript types from the OpenAPI schema.
- Accessible components with keyboard and screen-reader support.

### Quality

- Unit tests for formulas and boundary values.
- Contract tests for API schemas.
- Integration tests for workflow persistence and idempotency.
- End-to-end tests for the golden scenario and approval flow.
- Visual regression tests for the command dashboard.
- Formatting, type checks, linting, and tests enforced in continuous integration.

## 10. API contract

Base path: `/api/v1`

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/overview` | Current synthetic port summary |
| `POST` | `/disruptions` | Create a disruption and start analysis |
| `GET` | `/disruptions/{id}` | Read status and summary |
| `GET` | `/disruptions/{id}/events` | Stream evidence events using SSE |
| `GET` | `/disruptions/{id}/cascade` | Read graph nodes and container-flow edges |
| `GET` | `/disruptions/{id}/simulation` | Read baseline and scenario forecasts |
| `GET` | `/disruptions/{id}/plans` | Read the three recovery plans |
| `POST` | `/disruptions/{id}/decision` | Approve or reject one plan |
| `GET` | `/disruptions/{id}/actions` | Read mocked dispatch requests and receipts |

All timestamps use ISO 8601 with timezone offsets. All money fields include currency. All percentages use fractions from 0 to 1 in the API and are formatted as percentages only in the user interface.

Write requests require an idempotency key. Errors use a shared structure containing code, message, retryability, correlation ID, and field details.

## 11. Core data model

- `Vessel`: stable ship identity and physical characteristics.
- `PortCall`: one visit by a vessel, including terminal, berth, ETA, ETD (Estimated Time of Departure), and operational cutoffs.
- `Container`: size, weight, category, requirements, and current state.
- `Connection`: inbound port call, outbound port call, booked capacity, and processing requirements.
- `YardBlock`: TEU capacity, reefer plugs, allowed cargo, and current inventory.
- `YardEvent`: time-stamped arrival, placement, move, load, or departure.
- `Disruption`: original and revised schedule facts.
- `SimulationRun`: immutable input snapshot, versions, seed, and results.
- `Plan`: calculated metrics and feasibility.
- `PlanAction`: one proposed operational change.
- `Decision`: approver, selected plan, reason, and timestamp.
- `ExecutionReceipt`: mocked external result and correlation ID.

A port call is one ship visit. A vessel may visit many times, so connections must use port-call IDs rather than only vessel IDs.

## 12. Data assumptions

The seeded dataset contains:

- 25 large mainline vessels;
- 40 smaller regional feeder vessels;
- 5,000 transshipping containers;
- enough port calls before and after the disruption to simulate 72 hours;
- yard blocks with cargo restrictions and reefer-plug limits;
- alternative sailings with explicit available capacity.

A feeder vessel is a smaller ship that carries containers between a large hub and nearby ports.

The generator uses seed `42`. Data is synthetic and must be labeled as such in the dashboard, presentation, and video.

## 13. Workflow states

```text
RECEIVED
ANALYZING
SIMULATING
GENERATING_PLANS
AWAITING_APPROVAL
APPROVED
REJECTED
DISPATCHING
COMPLETED
DEGRADED_AWAITING_REVIEW
FAILED
```

Every transition is persisted. A process restart must not lose an approval pause or duplicate execution.

## 14. Non-functional requirements

- First evidence event appears within 500 milliseconds of a successful request.
- The seeded 5,000-container simulation completes within 3 seconds on the demo machine.
- The dashboard becomes interactive within 2 seconds after local application load.
- All write operations are idempotent.
- Every calculated value is traceable to an input snapshot and formula version.
- No secret, private prompt, or chain-of-thought appears in logs or the UI.
- The interface supports keyboard navigation and readable contrast.
- The supported desktop layout has no clipped text, overlapping controls, or unreadable chart labels.
- A failed dependency cannot cause silent autonomous execution.

## 15. Implementation plan

### Day 1: contracts and foundations

- Freeze terminology, schemas, API routes, workflow states, and rate assumptions.
- Create repository structure, quality checks, migrations, and generated API types.
- Define the golden scenario and its expected outputs.

### Day 2: data and deterministic domain logic

- Build the seeded synthetic data generator.
- Implement port calls, connection readiness, TEU conversion, and classification.
- Add boundary-focused unit and property tests.

### Day 3: simulation and planning

- Implement yard events, reefer plugs, congestion, and itemized cost calculations.
- Implement plan feasibility, generation, and deterministic scoring.
- Lock golden-scenario snapshots after review.

### Day 4: workflow and API

- Implement disruption creation, persisted workflow states, approval, replay, and SSE.
- Add idempotency, correlation IDs, mocked adapters, and contract tests.

### Day 5: user interface and end-to-end tests

- Build the overview, cascade graph, yard forecast, plan comparison, evidence trace, and approval flow.
- Test the complete golden scenario from the user's perspective.
- Add visual regression and accessibility checks.

### Day 6: resilience and polish

- Add uncertainty scenarios, stale-data handling, timeouts, retries, and degraded states.
- Fix UI defects, test failures, lint failures, and flaky tests.
- Validate every displayed value against API data.

### Day 7: delivery

- Run the full quality pipeline on the demo machine.
- Record a deterministic demonstration with a reset procedure and backup recording.
- Finalize slides with synthetic-data and illustrative-savings labels.

## 16. Release acceptance criteria

The hackathon release is ready when:

- the golden scenario succeeds from disruption injection through mocked dispatch;
- the same inputs produce the same outputs across five clean runs;
- all plan totals reconcile with their itemized calculations;
- every approval rule has an automated test;
- duplicate requests and retries create no duplicate actions;
- failure and degraded states are visible and safe;
- the UI passes end-to-end, visual, accessibility, type, lint, and unit checks;
- the demo can be reset without editing the database manually;
- all displayed claims are produced by the system or labeled illustrative;
- no real external action can be triggered.

## 17. Limitations

- Results depend on synthetic schedules, manifests, capacities, and rates.
- The simulator simplifies crane sequencing, traffic, labor, weather, and equipment behavior.
- Three scenario bands do not represent a complete probability forecast.
- Mocked carrier capacity is not proof that a real booking is available.
- Cost outputs demonstrate the product method and are not verified PSA savings.
- SQLite is suitable for the local demo, not a multi-site production deployment.
- The model recommends from supplied options and cannot discover every possible recovery strategy.

## 18. Risks and controls

| Risk | Control |
|---|---|
| Invented schedule or capacity | Recommendations use structured tool results only |
| Wrong cost total | Versioned rates, itemized output, and reconciliation tests |
| Duplicate work order | Idempotency keys and persisted execution receipts |
| Unsafe recommendation | Hard feasibility rules and human approval |
| Misleading confidence | Visible scenario assumptions and degraded states |
| Demo instability | Seeded data, replay, reset command, and backup recording |
| UI hides important detail | Labels, keyboard access, visible units, and visual tests |

## 19. Future direction

- Replace synthetic data with approved, read-only operational feeds.
- Add calibrated ETA probability models and historical validation.
- Expand the simulator to crane, berth, labor, gate, rail, and truck constraints.
- Use a production database and event bus.
- Add role-based access, signed approvals, and full security review.
- Run recommendations in shadow mode before any controlled operational pilot.

Shadow mode means the system makes suggestions but cannot act. People compare its suggestions with real outcomes to learn whether it is safe and useful.
