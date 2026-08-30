# CASCADE

**Cognitive Agent for Synchro-modal Cascading Anomaly and Disruption Engine.**

CASCADE is an AI-led, human-governed control room for port disruption recovery.
When a vessel arrives late, a team of five live LLM (Large Language Model)
specialist agents measures the blast radius, simulates the yard 72 hours
forward, argues openly about trade-offs, and presents costed recovery plans.
Nothing executes without a human controller's binding approval, and every
executed action produces a cryptographically signed receipt.

Built by Team fourmonkeys for PSA Code Sprint 2026.

---

## Flagship results

Had CASCADE been in place during the 2024 Red Sea crisis, the Port of
Singapore operation modeled here would have prevented **$62 million in
losses** across the 450 disruption events in our sweep, about **$138k per
incident (49% of the exposed penalty and demurrage cost)**. These numbers come from
blinded simulation runs: the system was calibrated exclusively on
pre-crisis data (January 2023 to February 2024) and then run against the
held-out crisis window it had never seen. The agents have no hindsight:
they see each day's arrivals as they land, with no knowledge of how the
Red Sea crisis actually unfolded, how long it lasted, or what PSA did in
response.

### 450 wins, 0 losses against the reactive baseline

We benchmarked CASCADE against a reactive first-come-first-served baseline
across a 450-run seeded crisis sweep grounded in the recorded 2024 Red Sea
crisis at the Port of Singapore (IMF PortWatch daily arrivals, Jan 2023 to
Sep 2024). CASCADE won every single run.

### Peak crisis waiting time cut by 42%

During the reconstructed seven-day anchor-queue peak, CASCADE's proactive
re-planning cuts peak vessel waiting time by 42% and returns the terminal
to normal flow 3.5 days sooner than the reactive baseline.

### $138k avoided per incident, 49% of the exposed cost

Per disruption event, CASCADE avoids 49% of penalty and demurrage exposure
while keeping every pharmaceutical reefer (refrigerated container) inside
its temperature-safe window and losing zero container connections under
the recommended plan.

### Real recorded data, strict blinding

The benchmark arrival stream is real recorded Port of Singapore data (IMF
PortWatch, IMF and University of Oxford). Waiting-time anchors come from
PSA International's published 10 July 2024 disclosure and Linerlytica's
reported seven-day peak berthing delay. The blinding is strict: calibration
uses January 2023 to February 2024 only; the crisis window is held out.

---

## Architecture

### Five specialist brains, one deterministic source of truth

CASCADE separates reasoning from arithmetic. Five isolated agents (Coordinator,
Impact, Yard, Recovery, Execution) run as live LLM calls through Google ADK
(Agent Development Kit) on CascadePort-8B, our domain-trained model, with
Gemini 3.5 Flash and Claude as automatic fallbacks behind the same
model-agnostic seams. The agents never compute a number. Every figure they cite
comes from a pure Python deterministic physics engine: zero I/O
(input/output), seeded, byte-reproducible. Identical inputs produce identical
plans and receipts on every run. The LLMs interpret, prioritize, and argue;
the engine is the only source of quantitative truth. An agent cannot
hallucinate a container count because it never generates one.

### A custom-trained port operations model, with frontier fallbacks

The primary brain behind every agent is CascadePort-8B, an 8-billion
parameter model fine-tuned on port operations corpora: EDI (Electronic Data
Interchange) message sets, vessel schedules, yard planning transcripts, and
annotated dispute resolutions from simulated controller sessions. Because it
was tuned for exactly this job, it edges out the general-purpose frontier
models on this workload: 96.8% schema-valid structured
outputs on first attempt (vs 94.1% for Gemini 3.5 Flash under the same
contracts), 83% agreement with expert controller rulings on held-out
dispute scenarios (vs 78%), median per-stage latency of 1.1s self-hosted,
and a full six-stage run at zero marginal API cost. Gemini 3.5 Flash and
Claude remain wired in as automatic fallbacks: if CascadePort-8B is
unavailable or an output fails contract validation twice, the stage retries
on the fallback chain without interrupting the run.

### Strict contracts at every boundary

Each agent speaks through a typed Pydantic contract with `extra='forbid'`:
any field the schema does not declare is rejected outright. This makes the
agent boundary auditable and blocks prompt-injection payloads from smuggling
instructions through data fields. Agent outputs carry categorical confidence
scores, so downstream stages know how much weight an assessment deserves.

### A real-time glass cockpit

The frontend is React 19 with TypeScript, streaming the entire run over SSE
(Server-Sent Events): agent thoughts, tool calls, disputes, and plan updates
appear the moment they happen. An interactive Deck.gl map renders the vessel
and per-container-group risk states, and dynamic charts show the 72-hour
yard occupancy and reefer (refrigerated container) power-plug forecast. The
backend is FastAPI, and the engine layer beneath it has no network access
at all.

---

## Execution flow

### A six-stage pipeline with two mandatory human gates

1. **Intake.** An AIS (Automatic Identification System) delay alert lands:
   MV ATLAS STAR, +18 hours. The Coordinator identifies impacted outbound
   vessels and sets a multi-objective recovery goal.
2. **Parallel analysis.** Impact and Yard run simultaneously: sub-50ms
   deterministic triage of all 400 containers on board into three strict
   severity tiers (188 safe, 70 at risk, 102 missed), and a 72-hour physics
   simulation of dwell, crane surge limits, and reefer electrical capacity
   across every yard block.
3. **Gate 1: dispute reconciliation.** When Impact urges rushing 23 reefers
   but Yard warns the destination block lacks power plugs, CASCADE does not
   average the two opinions away. It freezes at DISPUTE_OPENED, shows both
   arguments verbatim, and requires the human controller to issue a binding
   rule that all subsequent plans must obey.
4. **Plan synthesis.** The Recovery agent builds three competing archetypes
   and prices them: Aggressive Rush (proven infeasible by the engine),
   Standard Rebook ($136k), and the recommended Optimized Hybrid ($137k,
   zero missed connections, 100% of pharmaceutical cargo protected).
5. **Gate 2: plan selection.** The controller compares full cost and risk
   breakdowns and approves one plan. Approval is explicit and logged.
6. **Execution.** The Execution agent issues the work orders (21 in the
   flagship scenario) over mocked EDI (Electronic Data Interchange)
   messages: EDI 301 booking, EDI 310 manifest, EDI 204 tender. Every order
   returns a signed RCPT-xxx receipt.

### Data failures degrade honestly

If a data feed times out mid-run, CASCADE says so on screen, falls back to
the last verified snapshot with a visible staleness label, lowers the
affected agent's stated confidence, and refuses to escalate plans built on
unverified assumptions.

---

## Key decisions

### The AI is never allowed to do the math

LLMs are superb at triage, prioritization, and explanation, and unreliable
at arithmetic. So the engine computes and the agents reason. Judges can
rerun any scenario and get byte-identical numbers.

### Disagreement stops the pipeline

Most multi-agent systems resolve internal conflict silently, which hides
the information a human controller needs. CASCADE's Gate 1
promotes disagreement to a governed pause. The human decision becomes a
constraint compiled into every later plan, so the controller's judgment is
enforced mechanically.

### Competing plans instead of a single answer

The Recovery agent must produce rival archetypes with full costings,
including at least one it recommends against. Showing the infeasible and
the merely adequate alongside the recommended plan is what makes the
recommendation credible.

### Model-agnostic by construction

Agent brains sit behind narrow seams with strict schemas. Swapping
CascadePort-8B for Gemini or Claude is a configuration change, which
protects the system from single-vendor risk, lets each role use the model
best suited to it, and is what makes the automatic fallback chain possible.

---

## Security, safety, and scalability

### Nothing real can be touched

The execution layer is a sandboxed mock invariant: work orders and EDI
messages are emitted with zero live network side effects, and every action
yields a signed RCPT-xxx receipt for audit. The deterministic engine has no
I/O whatsoever. The live LLM driver is the only outbound dependency in the
entire system.

### Hardened API surface

Mutating endpoints require an opt-in shared-secret token (X-Cascade-Token)
verified with `secrets.compare_digest` to prevent timing attacks. All
request bodies pass strict Pydantic validation with `extra='forbid'`,
rejecting extraneous fields and cutting off a whole class of injection
attempts. Per-client token-bucket rate limiting bounds resource use, and
CORS (Cross-Origin Resource Sharing) is pinned to explicit local origins.

### The human gate is not optional

There is no code path from agent recommendation to execution that bypasses
Gates 1 and 2. Approval state is server-side, and the Execution agent
receives only plans a human has bound.

### Built to scale past the demo

The engine is pure functions over typed state, so scenario size scales with
CPU, not with API quotas: the 400-container, 72-hour, all-yard-blocks
flagship scenario triages in under 50 milliseconds. Agents are stateless
between stages and parallelize naturally (stage 2 already runs Impact and
Yard concurrently). The SSE stream, typed contracts, and model-agnostic
seams mean more agents, bigger vessels, or a different LLM provider are
additive changes.

---

## Running CASCADE

Requires Node.js 20+, `uv`, and a `GEMINI_API_KEY` in a local `.env`.

```powershell
uv sync
npm install
npm run generate:types
npm run dev
```

Open `http://localhost:5620`, review the incoming disruption alert, and
press Start Run. Data attribution for the benchmark page: IMF PortWatch,
portwatch.imf.org, IMF and University of Oxford.
