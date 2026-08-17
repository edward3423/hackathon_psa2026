# CASCADE: Deep Judges & PSA Port Operations Critique

## Executive Assessment

CASCADE demonstrates strong software engineering discipline, deterministic calculation guardrails, an explicit state machine, and a human-in-the-loop approval mechanism. However, when evaluated under the rigorous scrutiny of Port of Singapore Authority (PSA) operational standards, Terminal Operating System (TOS) architects, and maritime optimization judges, several structural limitations, domain simplifications, and architectural trade-offs emerge.

---

### Concept worth remembering: Terminal Operating System (TOS)

A Terminal Operating System (TOS) is the master computer brain of a container port. It tracks where every container is placed, tells cranes when to move, assigns berths to incoming ships, and coordinates trucks and robotic vehicles.

---

## 1. Domain Realism and Port Operations (PSA Critique)

### 1.1 Unrealistic Crane Productivity Model
- **Current implementation**: The cost and feasibility engine assumes `1 rushed container = 1.0 extra crane hour` (`EXTRA_CRANE_HOURS_PER_RUSHED_CONTAINER = 1.0` in `src/cascade/engine/costs.py`).
- **PSA Reality**: Quay Cranes (QC - giant shoreline cranes that load and unload container ships) operate at 25 to 35 Gross Moves Per Hour (GMPH - the number of containers a crane moves in one hour). Rushing 20 containers does not take 20 crane hours; it represents approximately 35 to 45 minutes of a single crane gang's time. 
- **The actual constraint**: The real bottleneck is crane allocation split, twin-lift or tandem-lift sequencing, and hatch cover handling on the vessel, not raw single-container crane hours.
- **Improvement required**: Replace the linear crane hour penalty with a realistic Quay Crane Move Rate model (25 to 30 moves/hour) and model crane gang shifts.

### 1.2 Missing Yard Stacking, Digging, and Shifting Physics
- **Current implementation**: Yard capacity is modelled as a scalar occupancy count per block (`peak_occupancy / container_capacity`).
- **PSA Reality**: Container yards stack containers 4 to 5 tiers high. When a container designated for a rush connection is buried under 3 other containers, an Automated Yard Crane (AYC - robotic gantry crane operating in the container storage stacks) must perform "re-handling" or "housekeeping" moves (unstacking other boxes to access the target box). Re-handling consumes significant cycle time and yard tractor capacity.
- **Improvement required**: Incorporate a tier-based re-handling / shuffling factor calculation into the rush feasibility score.

### 1.3 Ignored Horizontal Transport & Automated Guided Vehicle (AGV) Bottlenecks
- **Current implementation**: Rushed containers instantly transfer from yard block to quay.
- **PSA Reality**: In Tuas and Pasir Panjang terminals, containers move between berths and yard blocks via AGVs (Automated Guided Vehicles - battery-powered driverless transport vehicles) and Prime Movers (PM - heavy terminal trucks). During berth congestion, horizontal transport travel time and charging dispatch queues become primary bottlenecks.
- **Improvement required**: Include horizontal travel cycle time and fleet availability checks in the execution timeline.

### 1.4 Carrier Alliances and Commercial Slot Charter Reality
- **Current implementation**: Any alternative sailing with capacity can receive rebooked containers without carrier distinction.
- **PSA Reality**: Ocean carriers operate in rigid alliances (e.g. 2M, Ocean Alliance, Premier Alliance). A carrier will generally not rebook cargo onto a competitor's vessel unless a bilateral slot-charter agreement (commercial contract allowing one carrier to buy container space on another carrier's ship) exists.
- **Improvement required**: Add an alliance / carrier pairing validation step so rebooking suggestions adhere to commercial partnership constraints.

---

### Concept worth remembering: Demurrage and Detention

When a cargo box stays in the port longer than allowed, fees begin. Demurrage is the parking ticket paid to the port for taking up yard space past the agreed free days. Detention is the rental fine paid to the shipping line for holding onto their container box too long.

---

## 2. Multi-Agent Architecture and Optimization Rigidity

### 2.1 Rigid Heuristics vs Mathematical Optimization Solver
- **Current implementation**: Recovery options are hardcoded into exactly three fixed archetypes:
  1. Aggressive Rush (`PlanArchetype.AGGRESSIVE_RUSH`)
  2. Standard Rebook (`PlanArchetype.STANDARD_REBOOK`)
  3. Optimized Hybrid (`PlanArchetype.OPTIMIZED_HYBRID`)
- **Critique**: This is a static heuristic generator rather than an intelligent optimization engine. In real port disruptions with hundreds of transshipment connections, a solver (e.g. Mixed-Integer Linear Programming - MILP or Constraint Programming) should explore a continuous Pareto frontier of cost vs delay vs yard congestion.
- **Improvement required**: Implement a constraint-satisfaction solver (or dynamic solver backend) that outputs Pareto-optimal candidates dynamically based on the current objective weightings.

### 2.2 Scripted vs Autonomous Dispute Resolution
- **Current implementation**: The dispute between the Impact Agent and Yard Agent is statically triggered around a specific pre-set condition (pharma reefers vs reefer plug shortage).
- **Critique**: While great for deterministic presentation, judges will immediately notice that disputes cannot emerge organically for arbitrary novel scenarios or unexpected multi-vessel clashes.
- **Improvement required**: Allow agents to dynamically raise disputes whenever competing threshold constraints (e.g. Berth vs Yard vs Dangerous Goods limits) violate configurable safety margins.

### 2.3 Single-Vessel vs Multi-Berth Network Cascades
- **Current implementation**: Focuses exclusively on a single inbound vessel (MV ATLAS STAR) and its immediate outbound connections.
- **PSA Reality**: PSA handles dozens of mega-vessels simultaneously across interconnected berths. An 18-hour delay on one vessel creates a berth clash: the berth is either occupied by another vessel or another vessel is forced to idle at anchorage (the designated parking area at sea outside the port), burning fuel and missing subsequent tides.
- **Improvement required**: Expand the simulation scope to include adjacent berth schedule clashes and anchorage waiting queues.

---

## 3. UI/UX and Port Controller Operational Workflow

### 3.1 Lack of Berth Gantt Chart Visualization
- **Current implementation**: Visualizes connections as an abstract node/flow graph and line metrics.
- **Controller Reality**: Port controllers live in Berth Planning Gantt charts (a timeline bar chart showing when ships arrive, tie up at berths, and depart). Showing vessel arrival shifts on a visual berth timeline makes delay impact immediately intuitive.
- **Improvement required**: Add a dynamic Berth Schedule Gantt component showing berth occupation overlaps and revised departure windows.

### 3.2 Abstract Yard Metrics vs Spatial Block Heatmap
- **Current implementation**: Yard occupancy is plotted as an aggregated 72-hour line chart.
- **Controller Reality**: Yard controllers need to see which specific yard blocks (e.g., Block 01 vs Block 04) are turning red, where reefer plug rows are situated, and which crane tracks are overloaded.
- **Improvement required**: Provide a top-down 2D spatial yard block heatmap showing block-by-block density and reefer plug saturation.

### 3.3 Work Order Granularity and Integration Readiness
- **Current implementation**: Generates high-level mock action receipts (e.g. `RUSH_CONTAINERS`, `REBOOK_CONTAINERS`).
- **TOS Reality**: Real dispatch orders require EDI (Electronic Data Interchange - standardized electronic document format for shipping) or API messages containing ISO container codes, bay-row-tier target locations, and equipment assignment tags (e.g. BAPLIE, MOVINS, COARRI).
- **Improvement required**: Enhance mock execution receipts to display standardized EDI/JSON work order payloads ready for TOS ingestion.

---

## 4. Comprehensive List of Major and Minor Improvements

### Major Improvements (High Impact)
1. **Berth Gantt & Allocation Window Model**: Integrate a visual berth schedule timeline to show how the late vessel impacts downstream berthing windows and port anchorage queues.
2. **Realistic Crane Productivity & Re-handling Calculator**: Replace `1 container = 1 crane hour` with realistic Gross Moves Per Hour (25-30 GMPH) and add a tier re-handling penalty for stacked containers.
3. **Dynamic Multi-Plan Optimizer (Pareto Frontier)**: Replace hardcoded 3-archetype generation with a dynamic multi-objective solver that balances cost, connection preservation, and yard pressure.
4. **Spatial 2D Yard Heatmap**: Replace abstract line charts with an interactive terminal map displaying block layout, reefer zones, and crane work queues.
5. **Carrier Alliance & Free-Time Logic**: Incorporate commercial alliance validations on rebooking and separate demurrage, detention, and shifting fees.

### Minor Improvements (Polish & Robustness)
1. **ISO Container Number Realism**: Validate all synthetic container IDs against standard ISO 6346 checksum formatting (4 letters + 7 numbers, e.g., `MSKU9021438`).
2. **Reefer Cold-Chain Telematics**: Display target setpoint temperature and cold-chain integrity countdown timers for pharma and perishable reefers.
3. **Export to Standard EDI / TOS Payload**: Add a "View TOS Dispatch Payload" button in the Execution phase showing the generated EDI/JSON instructions.
4. **Scenario Import / Custom Parameter Injector**: Enable uploading custom vessel delay scenarios (JSON or CSV) beyond the single ATLAS STAR fixture.
5. **Confidence Score Breakdown**: Provide a tooltip on confidence badges explaining specifically which data sources (e.g. AIS vessel tracking vs carrier schedule feed) contributed to a `MEDIUM` or `LOW` rating.

---

### Concept worth remembering: ISO 6346 Container Number

Every shipping container in the world has a unique nameplate made of 4 letters and 7 numbers. The fourth letter is always 'U' for standard freight containers, and the last number is a math check digit to ensure no one mistypes it.

---

## 5. Summary Evaluation Scorecard

| Evaluation Dimension | Rating | Judge / PSA Perspective |
|---|---|---|
| **Human-in-the-Loop Governance** | **9.5 / 10** | Exceptional. The explicit approval gate and dispute resolution ensure complete human authority. |
| **Deterministic Guardrails** | **9.0 / 10** | Excellent separation of LLM narration from deterministic mathematical calculations. |
| **Auditability & Traceability** | **9.0 / 10** | Clear structured event trace logging with model exchange tracking. |
| **Domain Realism & Physics** | **6.5 / 10** | Oversimplified crane hours, missing yard re-handling/stacking physics, and basic single-vessel scope. |
| **Optimization Sophistication** | **6.0 / 10** | Relies on 3 fixed static archetypes rather than a true dynamic solver searching the Pareto frontier. |
| **Controller UI / Experience** | **8.0 / 10** | Clean, fast, and structured, but lacks standard berth Gantt timelines and spatial 2D yard heatmaps. |
