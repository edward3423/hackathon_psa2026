# CASCADE Low-Priority Backlog

## Purpose

Everything in this file is intentionally excluded from the hackathon build. These items are low priority because CASCADE is a local demonstration using synthetic data and mocked actions.

Do not begin these items until the golden end-to-end demonstration, failure path, reset flow, slides, and video are complete.

E2E means end-to-end. It tests the product the way a user experiences it, from the browser through the backend and back.

## Priority definition

`LOW`: not required for judging or the demonstration. Consider only for a post-hackathon pilot or production project.

## Security and access

- [ ] `LOW` Add user authentication.
- [ ] `LOW` Add role-based approval permissions.
- [ ] `LOW` Add signed and independently verified approvals.
- [ ] `LOW` Add production secret management and credential rotation.
- [ ] `LOW` Encrypt sensitive data at rest.
- [ ] `LOW` Add tamper-resistant audit records.
- [ ] `LOW` Add production prompt-injection detection and content isolation.
- [ ] `LOW` Add configurable tool permissions and least-privilege service identities.
- [ ] `LOW` Add security monitoring, alerting, and incident response.
- [ ] `LOW` Complete a formal threat model and penetration test.

Prompt injection is when untrusted text tries to give the agent new instructions. The hackathon uses controlled synthetic data, so full protection is documented rather than implemented.

## Production infrastructure

- [ ] `LOW` Replace in-memory state with a production relational database.
- [ ] `LOW` Add database migrations, backups, and restore procedures.
- [ ] `LOW` Add a durable event bus.
- [ ] `LOW` Add independent simulation workers and job queues.
- [ ] `LOW` Add horizontal scaling for APIs and event streams.
- [ ] `LOW` Partition operational data by terminal and time window.
- [ ] `LOW` Add distributed tracing and production correlation IDs.
- [ ] `LOW` Add metrics, dashboards, logs, and operational alerts.
- [ ] `LOW` Add disaster recovery and regional failover.
- [ ] `LOW` Define production data retention and deletion policies.
- [ ] `LOW` Add load, stress, endurance, and capacity testing.

An event bus is a shared delivery system for updates between services.

## Reliability and workflow recovery

- [ ] `LOW` Add complete idempotency for every write operation.
- [ ] `LOW` Resume an approval safely after a backend restart.
- [ ] `LOW` Resume SSE event streams from the last event ID.
- [ ] `LOW` Add versioned workflow migrations.
- [ ] `LOW` Add full scenario replay across simulator versions.
- [ ] `LOW` Add configurable retry, timeout, and circuit-breaker policies.
- [ ] `LOW` Add duplicate-action reconciliation with external systems.
- [ ] `LOW` Guarantee byte-equivalent results across supported platforms.

SSE means Server-Sent Events. It lets the server keep sending updates to the browser over one connection.

## Real data and external integration

- [ ] `LOW` Connect to approved PSA operational feeds.
- [ ] `LOW` Connect to live MPA vessel-arrival and departure APIs.
- [ ] `LOW` Import real container manifests and connection bookings.
- [ ] `LOW` Integrate with a real terminal operating system.
- [ ] `LOW` Integrate with carrier EDI messages.
- [ ] `LOW` Integrate with berth and crane planning systems.
- [ ] `LOW` Retrieve real alternative-sailing capacity.
- [ ] `LOW` Import customer contracts, free-time rules, and penalties.
- [ ] `LOW` Add automated source checksums, licence validation, and field-level provenance.
- [ ] `LOW` Establish data-sharing approvals and privacy controls.

EDI means Electronic Data Interchange. It is a standard way for companies to exchange booking and cargo messages.

## Advanced simulation

- [ ] `LOW` Scale the simulator beyond 5,000 individual containers.
- [ ] `LOW` Model multiple terminals and inter-terminal transfers.
- [ ] `LOW` Model detailed berth assignment and vessel sequencing.
- [ ] `LOW` Model crane productivity, crane interference, and gang allocation.
- [ ] `LOW` Model labor shifts and equipment availability.
- [ ] `LOW` Model gate, truck, rail, and road congestion.
- [ ] `LOW` Model dangerous-goods segregation and handling rules.
- [ ] `LOW` Model reefer temperatures, plug failures, and power interruption.
- [ ] `LOW` Add calibrated probabilistic ETA models.
- [ ] `LOW` Add Monte Carlo disruption simulation.
- [ ] `LOW` Add weather, tide, and sea-state models.
- [ ] `LOW` Add detailed carbon and energy calculations per action.
- [ ] `LOW` Search a larger plan space instead of comparing three defined strategies.

Monte Carlo simulation runs the same situation many times with different random outcomes. It helps estimate how often each result may happen.

## Advanced financial modelling

- [ ] `LOW` Add versioned customer-specific rate cards.
- [ ] `LOW` Model billing boundaries and partial-day rounding.
- [ ] `LOW` Model demurrage, detention, storage, and service penalties separately.
- [ ] `LOW` Prevent double counting across complex real contracts.
- [ ] `LOW` Validate financial savings against historical PSA outcomes.
- [ ] `LOW` Add currency conversion and financial audit controls.

Demurrage is a charge for keeping a container longer than the agreed free period at a terminal.

## Advanced user experience

- [ ] `LOW` Support mobile and tablet layouts.
- [ ] `LOW` Add comprehensive screen-reader optimization.
- [ ] `LOW` Add complete keyboard-shortcut customization.
- [ ] `LOW` Add localization and multiple languages.
- [ ] `LOW` Add user preferences and saved dashboard layouts.
- [ ] `LOW` Add full visual-regression coverage across browsers and screen sizes.
- [ ] `LOW` Add multi-user collaboration and live presence.
- [ ] `LOW` Add historical scenario search and comparison.

## Extended quality engineering

- [ ] `LOW` Add property-based tests for every formula.
- [ ] `LOW` Add mutation testing.
- [ ] `LOW` Add broad cross-browser and device testing.
- [ ] `LOW` Add automated accessibility certification checks.
- [ ] `LOW` Add long-running test-flakiness monitoring.
- [ ] `LOW` Add production dependency and container vulnerability scanning.
- [ ] `LOW` Add formal simulator verification against real operational cases.

## Re-entry criteria

Move an item out of this backlog only when:

1. the golden demonstration is complete and stable;
2. the item supports a defined pilot or production objective;
3. an owner and acceptance test are defined;
4. required real data and external approvals are available;
5. the change does not weaken the demonstration path.
