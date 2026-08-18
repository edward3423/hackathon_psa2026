from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunMode(StrEnum):
    LIVE_STUB = "LIVE_STUB"
    LIVE_GEMINI = "LIVE_GEMINI"
    LIVE_CLAUDE = "LIVE_CLAUDE"
    DEMO_REPLAY = "DEMO_REPLAY"


class PriorityEmphasis(StrEnum):
    CARGO_PROTECTION = "CARGO_PROTECTION"
    CONGESTION_REDUCTION = "CONGESTION_REDUCTION"
    BALANCED = "BALANCED"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class WorkflowStage(StrEnum):
    READY = "READY"
    ASSESSING = "ASSESSING"
    DISPUTE = "DISPUTE"
    PLANNING = "PLANNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class EventKind(StrEnum):
    RUN_STARTED = "RUN_STARTED"
    AGENT_STARTED = "AGENT_STARTED"
    TOOL_CALLED = "TOOL_CALLED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    HANDOFF = "HANDOFF"
    DISPUTE_OPENED = "DISPUTE_OPENED"
    HUMAN_DECISION = "HUMAN_DECISION"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    ACTION_DISPATCHED = "ACTION_DISPATCHED"
    ERROR = "ERROR"
    RUN_COMPLETED = "RUN_COMPLETED"


class AgentName(StrEnum):
    COORDINATOR = "Coordinator Agent"
    IMPACT = "Impact Agent"
    YARD = "Yard Agent"
    RECOVERY = "Recovery Agent"
    EXECUTION = "Execution Agent"


class AgentStatus(StrEnum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class DisruptionAlert(ContractModel):
    vessel_name: str
    port_call: str
    original_eta: datetime
    revised_eta: datetime
    event_time: datetime
    synthetic: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def delay_hours(self) -> int:
        return round((self.revised_eta - self.original_eta).total_seconds() / 3600)


class ScenarioControls(ContractModel):
    delay_hours: Annotated[int, Field(ge=6, le=24)] = 18
    priority_emphasis: PriorityEmphasis = PriorityEmphasis.BALANCED
    alternative_sailing_failure: bool = True


class ScenarioState(ContractModel):
    name: str
    description: str
    alert: DisruptionAlert
    objective: str
    planning_horizon_hours: int
    controls: ScenarioControls
    synthetic_notice: str


class AgentActivity(ContractModel):
    agent: AgentName
    objective: str
    status: AgentStatus = AgentStatus.WAITING
    confidence: Confidence | None = None
    last_summary: str | None = None


class ModelExchange(ContractModel):
    """One live model call (prompt in, raw response out) behind a trace event."""

    provider: str  # "claude-cli" | "gemini"
    model: str
    effort: str | None = None  # CLI effort level, or Gemini thinking budget
    agent: AgentName
    prompt: str
    response: str
    duration_ms: Annotated[int | None, Field(ge=0)] = None


class TraceEvent(ContractModel):
    event_id: str
    sequence: Annotated[int, Field(ge=1)]
    timestamp: datetime
    kind: EventKind
    stage: WorkflowStage
    agent: AgentName | None = None
    objective: str | None = None
    input_summary: str | None = None
    tool: str | None = None
    decision_summary: str | None = None
    confidence: Confidence | None = None
    assumptions: list[str] = Field(default_factory=list)
    result: str | None = None
    error: str | None = None
    elapsed_ms: Annotated[int | None, Field(ge=0)] = None
    next_handoff: AgentName | None = None
    parallel_group: str | None = None
    model_exchanges: list[ModelExchange] = Field(default_factory=list)


class DisputePosition(ContractModel):
    agent: AgentName
    position: str
    evidence: list[str]


class Dispute(ContractModel):
    dispute_id: str
    question: str
    positions: list[DisputePosition]
    confirmed_constraint: str | None = None
    resolved_by_human: bool = False


class WorkflowState(ContractModel):
    run_id: str
    mode: RunMode
    stage: WorkflowStage
    scenario: ScenarioState
    activities: list[AgentActivity]
    trace: list[TraceEvent] = Field(default_factory=list)
    active_dispute: Dispute | None = None
    results: "RunResults | None" = None


class RunCreated(ContractModel):
    run_id: str
    mode: RunMode
    stage: WorkflowStage
    events_url: str


class HealthResponse(ContractModel):
    status: str
    version: str


class CargoType(StrEnum):
    PHARMA_REEFER = "PHARMA_REEFER"
    TIME_CRITICAL_MANUFACTURING = "TIME_CRITICAL_MANUFACTURING"
    GENERAL_DRY = "GENERAL_DRY"


class ConnectionStatus(StrEnum):
    SAFE = "SAFE"
    AT_RISK = "AT_RISK"
    MISSED = "MISSED"
    RESOLVED = "RESOLVED"


class VesselRole(StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class PlanArchetype(StrEnum):
    AGGRESSIVE_RUSH = "AGGRESSIVE_RUSH"
    STANDARD_REBOOK = "STANDARD_REBOOK"
    OPTIMIZED_HYBRID = "OPTIMIZED_HYBRID"


class RecoveryActionType(StrEnum):
    RUSH = "RUSH"
    REBOOK = "REBOOK"
    HOLD = "HOLD"


class MockedActionType(StrEnum):
    TERMINAL_WORK_ORDER = "TERMINAL_WORK_ORDER"
    REEFER_CHECK = "REEFER_CHECK"
    CARRIER_NOTICE = "CARRIER_NOTICE"


class SailingLookupStatus(StrEnum):
    MOCK_SUCCESS = "MOCK_SUCCESS"
    TIMEOUT_CACHED_FALLBACK = "TIMEOUT_CACHED_FALLBACK"


class Vessel(ContractModel):
    name: str
    role: VesselRole
    port_call: str
    eta: datetime
    etd: datetime
    connection_cutoff: datetime | None = None


class YardBlock(ContractModel):
    block_id: str
    container_capacity: Annotated[int, Field(gt=0)]
    reefer_plugs: Annotated[int, Field(ge=0)]
    initial_containers: Annotated[int, Field(ge=0)]
    initial_reefers_on_power: Annotated[int, Field(ge=0)]


class Container(ContractModel):
    container_id: str
    cargo_type: CargoType
    requires_power: bool
    inbound_vessel: str
    onward_vessel: str | None = None
    yard_block: str
    handling_hours: Annotated[float, Field(ge=0)]


class AlternativeSailing(ContractModel):
    vessel_name: str
    replaces_onward_vessel: str
    departs: datetime
    connection_cutoff: datetime
    available_capacity: Annotated[int, Field(ge=0)]


class CostRates(ContractModel):
    dwell_per_container_hour: Annotated[float, Field(ge=0)]
    reefer_risk_per_hour: Annotated[float, Field(ge=0)]
    missed_connection_penalty: Annotated[float, Field(ge=0)]
    crane_hour: Annotated[float, Field(ge=0)]
    rebooking_fee: Annotated[float, Field(ge=0)]


class WorldFixture(ContractModel):
    seed: int
    terminal: str
    vessels: list[Vessel]
    yard_blocks: list[YardBlock]
    containers: list[Container]
    alternative_sailings: list[AlternativeSailing]
    cost_rates: CostRates
    synthetic_notice: str


class ContainerConnection(ContractModel):
    container_id: str
    cargo_type: CargoType
    onward_vessel: str
    ready_time: datetime
    connection_cutoff: datetime
    margin_hours: float
    status: ConnectionStatus
    priority_rank: Annotated[int, Field(ge=1)]
    priority_reason: str


class ConnectionGroupSummary(ContractModel):
    onward_vessel: str
    cargo_type: CargoType
    status: ConnectionStatus
    container_count: Annotated[int, Field(ge=0)]


class ConnectionAnalysis(ContractModel):
    delay_hours: int
    safe_count: Annotated[int, Field(ge=0)]
    at_risk_count: Annotated[int, Field(ge=0)]
    missed_count: Annotated[int, Field(ge=0)]
    groups: list[ConnectionGroupSummary]
    connections: list[ContainerConnection]


class RushSlot(ContractModel):
    """One container position in a group's fixed rush order."""

    yard_block: str
    requires_power: bool


class PlanningFacts(ContractModel):
    """Deterministic feasibility facts a live brain needs to allocate plans.

    Rushing K containers from a group rushes exactly its first K slots in
    rush_order_by_group (priority order, fixed by the engine); every powered
    slot rushed consumes one free reefer plug in its yard block.
    """

    crane_surge_allowance: Annotated[int, Field(ge=0)]
    free_plugs_by_block: dict[str, Annotated[int, Field(ge=0)]]
    rush_order_by_group: dict[str, list[RushSlot]]


class YardOccupancyPoint(ContractModel):
    time: datetime
    occupancy: Annotated[int, Field(ge=0)]
    congested: bool
    full: bool


class BlockForecast(ContractModel):
    block_id: str
    container_capacity: Annotated[int, Field(gt=0)]
    series: list[YardOccupancyPoint]
    peak_occupancy: Annotated[int, Field(ge=0)]
    peak_time: datetime


class ReeferShortage(ContractModel):
    block_id: str
    start_time: datetime
    required_plugs: Annotated[int, Field(ge=0)]
    available_plugs: Annotated[int, Field(ge=0)]


class YardForecast(ContractModel):
    horizon_hours: Annotated[int, Field(gt=0)]
    blocks: list[BlockForecast]
    reefer_shortages: list[ReeferShortage]


class CostComponent(ContractModel):
    name: str
    amount: Annotated[float, Field(ge=0)]
    basis: str


class CostEstimate(ContractModel):
    components: list[CostComponent]
    total: Annotated[float, Field(ge=0)]
    illustrative: bool = True


class PlanAction(ContractModel):
    action: RecoveryActionType
    onward_vessel: str
    cargo_type: CargoType
    container_count: Annotated[int, Field(ge=0)]
    target_sailing: str | None = None
    rationale: str


class RecoveryPlan(ContractModel):
    archetype: PlanArchetype
    title: str
    actions: list[PlanAction]
    assumptions: list[str] = Field(default_factory=list)


class PlanMetrics(ContractModel):
    cost: CostEstimate
    missed_connections: Annotated[int, Field(ge=0)]
    critical_cargo_protected_pct: Annotated[float, Field(ge=0, le=100)]
    yard_peak_occupancy_pct: Annotated[float, Field(ge=0)]
    max_additional_delay_hours: Annotated[float, Field(ge=0)]


class PlanEvaluation(ContractModel):
    plan: RecoveryPlan
    metrics: PlanMetrics
    feasible: bool
    rejection_reasons: list[str] = Field(default_factory=list)


class PlanComparison(ContractModel):
    evaluations: list[PlanEvaluation]
    recommended: PlanArchetype | None = None
    rationale: str
    confidence: Confidence


class AlternativeSailingResult(ContractModel):
    status: SailingLookupStatus
    sailings: list[AlternativeSailing]
    stale_notice: str | None = None


class MockedAction(ContractModel):
    action_id: str
    action_type: MockedActionType
    plan_archetype: PlanArchetype
    description: str
    payload_summary: str


class ActionReceiptStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ActionReceipt(ContractModel):
    action_id: str
    status: ActionReceiptStatus
    receipt_ref: str | None = None
    detail: str


class RunResults(ContractModel):
    connection_analysis: ConnectionAnalysis | None = None
    baseline_yard: YardForecast | None = None
    planned_yard: YardForecast | None = None
    alternative_sailings: AlternativeSailingResult | None = None
    plan_comparison: PlanComparison | None = None
    dispatched_actions: list[MockedAction] = Field(default_factory=list)
    receipts: list[ActionReceipt] = Field(default_factory=list)


class DisputeResolutionRequest(ContractModel):
    dispute_id: str
    confirmed_constraint: str


class ApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalRequest(ContractModel):
    plan_archetype: PlanArchetype
    decision: ApprovalDecision
    note: str | None = None


WorkflowState.model_rebuild()


# ---------------------------------------------------------------------------
# Act 2: Red Sea 2024 crisis benchmark (fleet scale).
#
# Everything below is additive. Act 1 contracts above are frozen: the fleet
# benchmark never reuses or mutates WorldFixture, ScenarioState, EventKind, or
# any single-vessel model. Where a concept has both a single-vessel and a fleet
# form (events, decisions, results), the fleet form gets its own name.
# ---------------------------------------------------------------------------

# Several models below carry a field literally named `date`, which shadows the
# imported type inside those class bodies. This alias keeps the type reachable.
DateValue = date


class FleetArm(StrEnum):
    """One line on the benchmark chart."""

    HISTORICAL = "HISTORICAL"
    REACTIVE_BASELINE = "REACTIVE_BASELINE"
    CASCADE_AGENTIC = "CASCADE_AGENTIC"
    CASCADE_NO_EXTRA_CAPACITY = "CASCADE_NO_EXTRA_CAPACITY"


class SeriesProvenance(StrEnum):
    """How a displayed number came to exist. Never inferred, always carried."""

    RECORDED = "RECORDED"
    RECONSTRUCTED = "RECONSTRUCTED"
    SIMULATED = "SIMULATED"


class QueueDiscipline(StrEnum):
    FCFS = "FCFS"
    CONNECTION_WEIGHTED = "CONNECTION_WEIGHTED"
    PRIORITY_DISCHARGE = "PRIORITY_DISCHARGE"


class FleetDecisionType(StrEnum):
    ACTIVATE_RESERVE_BERTHS = "ACTIVATE_RESERVE_BERTHS"
    SET_QUEUE_DISCIPLINE = "SET_QUEUE_DISCIPLINE"
    FAST_CONNECTION_MODE = "FAST_CONNECTION_MODE"
    WORKFORCE_SURGE = "WORKFORCE_SURGE"
    HOLD = "HOLD"


class FleetBrainMode(StrEnum):
    """Which brain supplies weekly strategy. SCRIPTED is the scored default."""

    SCRIPTED = "SCRIPTED"
    LIVE_GEMINI = "LIVE_GEMINI"
    LIVE_CLAUDE = "LIVE_CLAUDE"


class DecisionSource(StrEnum):
    SCRIPTED = "SCRIPTED"
    MODEL = "MODEL"
    SCRIPTED_FALLBACK = "SCRIPTED_FALLBACK"


class AuditVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


# --- Arrival stream fixture -------------------------------------------------


class DateWindow(ContractModel):
    label: str
    start: date
    end: date


class VesselArrival(ContractModel):
    """One synthesised vessel call on a recorded arrival day.

    Counts per day come from IMF PortWatch. Per-vessel sizes do not exist in
    any public source and are synthesised from a seeded distribution fitted on
    the calibration window only.
    """

    vessel_id: str
    arrival: datetime
    teu: Annotated[float, Field(gt=0)]
    connection_teu: Annotated[float, Field(ge=0)]


class ArrivalDay(ContractModel):
    date: date
    portcalls_container: Annotated[int, Field(ge=0)]
    arrivals: list[VesselArrival]


class CalibrationSlice(ContractModel):
    """Pre-crisis days. The only slice the calibrator will accept."""

    window: DateWindow
    days: list[ArrivalDay]


class BlindSlice(ContractModel):
    """Crisis days. Reachable only through BlindFeed, never by the calibrator."""

    window: DateWindow
    days: list[ArrivalDay]


class ArrivalStreamFixture(ContractModel):
    seed: int
    source: str
    source_url: str
    generated_by: str
    calibration: CalibrationSlice
    blind: BlindSlice
    synthesis_notice: str


# --- Ground truth -----------------------------------------------------------


class GroundTruthAnchor(ContractModel):
    key: str
    label: str
    value: float
    unit: str
    provenance: SeriesProvenance
    source: str
    source_date: date
    url: str


class HistoricalWaitPoint(ContractModel):
    date: date
    wait_days: Annotated[float, Field(ge=0)]


class GroundTruthFixture(ContractModel):
    anchors: list[GroundTruthAnchor]
    historical_wait_curve: list[HistoricalWaitPoint]
    historical_curve_provenance: SeriesProvenance = SeriesProvenance.RECONSTRUCTED
    historical_curve_method: str
    charter_rate_usd_per_day: Annotated[float, Field(ge=0)]
    notice: str


class FixtureManifest(ContractModel):
    """SHA-256 of every crisis input, embedded in each BenchmarkResult."""

    hashes: dict[str, str]
    generated_by: str


# --- World configuration ----------------------------------------------------


class ReserveBerthTranche(ContractModel):
    tranche_id: str
    label: str
    berths: Annotated[int, Field(gt=0)]
    activation_lead_days: Annotated[int, Field(ge=0)]
    available_from: date | None = None
    basis: str


class BerthPoolConfig(ContractModel):
    active_berths: Annotated[int, Field(gt=0)]
    reserve_tranches: list[ReserveBerthTranche] = Field(default_factory=list)


class ServiceModelConfig(ContractModel):
    """Vessel service time model. Fitted on the calibration window only."""

    base_hours: Annotated[float, Field(ge=0)]
    cranes_per_berth: Annotated[float, Field(gt=0)]
    moves_per_crane_hour: Annotated[float, Field(gt=0)]
    teu_per_move: Annotated[float, Field(gt=0)]
    efficiency: Annotated[float, Field(gt=0)]
    congestion_alpha: Annotated[float, Field(ge=0)]
    congestion_queue_ref: Annotated[float, Field(gt=0)]
    congestion_cap: Annotated[float, Field(ge=0)]
    surge_alpha_factor: Annotated[float, Field(gt=0, le=1)]
    surge_efficiency_gain: Annotated[float, Field(ge=0)]
    fast_connection_speedup: Annotated[float, Field(gt=0, le=1)]


class FleetWorldConfig(ContractModel):
    """Parallel to WorldFixture, for the fleet scale. Never replaces it."""

    seed: int
    berths: BerthPoolConfig
    service: ServiceModelConfig
    arrival_jitter_hours: Annotated[float, Field(ge=0)] = 0.0
    service_rate_multiplier: Annotated[float, Field(gt=0)] = 1.0
    berth_delta: int = 0
    activation_lead_override_days: Annotated[int | None, Field(ge=0)] = None


# --- Policy interface -------------------------------------------------------


class PendingActivation(ContractModel):
    tranche_id: str
    berths: Annotated[int, Field(gt=0)]
    effective_date: date


class DailyKpi(ContractModel):
    date: date
    day_index: Annotated[int, Field(ge=0)]
    arrivals: Annotated[int, Field(ge=0)]
    berthings: Annotated[int, Field(ge=0)]
    departures: Annotated[int, Field(ge=0)]
    queue_length: Annotated[int, Field(ge=0)]
    mean_wait_days: Annotated[float, Field(ge=0)]
    rolling_wait_days: Annotated[float, Field(ge=0)]
    active_berths: Annotated[int, Field(ge=0)]
    teu_waiting: Annotated[float, Field(ge=0)]
    utilisation: Annotated[float, Field(ge=0)]


class FleetPolicyView(ContractModel):
    """Everything a policy is allowed to see at a decision epoch.

    Deliberately contains no arrival feed, no fixture path, and no day beyond
    `today`. A policy that wants the future has nowhere to get it.
    """

    today: date
    day_index: Annotated[int, Field(ge=0)]
    history: list[DailyKpi]
    active_berths: Annotated[int, Field(ge=0)]
    reserves_available: list[ReserveBerthTranche]
    pending_activations: list[PendingActivation]
    queue_discipline: QueueDiscipline
    fast_connection_mode: bool
    workforce_surge_level: Annotated[int, Field(ge=0, le=2)]


class FleetDecision(ContractModel):
    """One lever pull. Numeric effect is fixed by the engine, never by a model."""

    type: FleetDecisionType
    tranche_id: str | None = None
    discipline: QueueDiscipline | None = None
    enabled: bool | None = None
    surge_level: Annotated[int | None, Field(ge=0, le=2)] = None
    rationale: str


class FleetStrategy(ContractModel):
    decisions: Annotated[list[FleetDecision], Field(max_length=4)]
    summary: str
    confidence: Confidence


class RecordedDecision(ContractModel):
    date: date
    day_index: Annotated[int, Field(ge=0)]
    agent: AgentName
    decision: FleetDecision
    accepted: bool
    rejection_reason: str | None = None
    source: DecisionSource
    effective_date: DateValue | None = None


# --- Blind-mode audit -------------------------------------------------------


class BlindAuditEntry(ContractModel):
    day_index: Annotated[int, Field(ge=0)]
    clock: datetime
    requested_until: datetime
    lookahead_seconds: float


class BlindAuditSummary(ContractModel):
    total_reads: Annotated[int, Field(ge=0)]
    max_lookahead_seconds: float
    violations: Annotated[int, Field(ge=0)]
    verdict: AuditVerdict
    worst_entry: BlindAuditEntry | None = None


# --- Calibration ------------------------------------------------------------


class CalibrationReport(ContractModel):
    window: DateWindow
    fitted: ServiceModelConfig
    effective_berths: Annotated[int, Field(gt=0)]
    observed_mean_daily_portcalls: float
    simulated_mean_daily_portcalls: float
    throughput_error_pct: float
    simulated_mean_wait_days: float
    simulated_mean_port_stay_hours: float
    erlang_c_wait_days: float
    utilisation: float
    passed: bool
    notes: list[str] = Field(default_factory=list)


# --- Results ----------------------------------------------------------------


class FleetMetrics(ContractModel):
    peak_wait_days: Annotated[float, Field(ge=0)]
    peak_wait_date: date
    recovery_date: date | None = None
    days_above_two_day_wait: Annotated[int, Field(ge=0)]
    mean_wait_days: Annotated[float, Field(ge=0)]
    mean_port_stay_hours: Annotated[float, Field(ge=0)]
    port_stay_inflation_pct: float
    vessels_served: Annotated[int, Field(ge=0)]
    teu_served: Annotated[float, Field(ge=0)]
    missed_connection_proxy: Annotated[int, Field(ge=0)]
    wait_cost_usd: Annotated[float, Field(ge=0)]


class ArmResult(ContractModel):
    arm: FleetArm
    label: str
    provenance: SeriesProvenance
    is_simulation: bool
    daily: list[DailyKpi]
    metrics: FleetMetrics
    decisions: list[RecordedDecision] = Field(default_factory=list)
    blind_audit: BlindAuditSummary | None = None
    calibration: CalibrationReport | None = None
    caveat: str | None = None


class ArmComparison(ContractModel):
    arm: FleetArm
    versus: FleetArm
    peak_wait_delta_days: float
    peak_wait_reduction_pct: float
    recovery_days_saved: float | None = None
    mean_wait_delta_days: float
    wait_cost_delta_usd: float
    wins_on_peak: bool
    wins_on_recovery: bool


class AnchorComparison(ContractModel):
    """A recorded scalar held next to what the baseline arm produced.

    ``within_tolerance`` is context, not a grade. The simulation is driven by
    Singapore's recorded arrival and volume series, and those series measure
    throughput - which congestion suppresses - rather than the load that caused
    it. The model therefore cannot be expected to reproduce the recorded crisis,
    and these rows are published so the gap is visible instead of hidden. See
    ``BenchmarkResult.notice``.
    """

    anchor_key: str
    label: str
    recorded_value: float
    recorded_provenance: SeriesProvenance
    simulated_value: float
    unit: str
    tolerance: float
    within_tolerance: bool
    #: Why the simulated figure sits where it does relative to the recorded one.
    #: Always populated, including when the row happens to fall inside tolerance.
    interpretation: str = ""


class BenchmarkConfig(ContractModel):
    seed: int
    arms: Annotated[list[FleetArm], Field(min_length=1)]
    world: FleetWorldConfig
    brain: FleetBrainMode = FleetBrainMode.SCRIPTED
    rolling_window_days: Annotated[int, Field(ge=1)] = 3
    recovery_threshold_days: Annotated[float, Field(gt=0)] = 2.0
    recovery_sustain_days: Annotated[int, Field(ge=1)] = 5


class BenchmarkResult(ContractModel):
    benchmark_id: str
    config: BenchmarkConfig
    calibration_window: DateWindow
    blind_window: DateWindow
    historical_arm_provenance: SeriesProvenance
    arms: list[ArmResult]
    comparisons: list[ArmComparison]
    anchor_comparisons: list[AnchorComparison]
    fixture_hashes: dict[str, str]
    runtime_ms: Annotated[int, Field(ge=0)]
    notice: str


# --- Robustness sweep -------------------------------------------------------


class SweepCell(ContractModel):
    seed: int
    variant: str
    arm: FleetArm
    peak_wait_days: float
    recovery_day_index: int | None = None
    #: Needed to score the cell, not merely to describe it. A ``None`` recovery
    #: index means "never recovered" only if the arm was ever in breach; with a
    #: zero count here it means there was nothing to recover from, which is the
    #: best outcome rather than the worst. See ``benchmark.recovery_rank``.
    days_above_two_day_wait: int = 0
    mean_wait_days: float


class SweepOutcome(ContractModel):
    arm: FleetArm
    versus: FleetArm
    runs: Annotated[int, Field(ge=1)]
    wins_on_peak: Annotated[int, Field(ge=0)]
    wins_on_recovery: Annotated[int, Field(ge=0)]
    win_rate_peak: Annotated[float, Field(ge=0, le=1)]
    win_rate_recovery: Annotated[float, Field(ge=0, le=1)]
    peak_delta_p10: float
    peak_delta_p50: float
    peak_delta_p90: float


class SweepSummary(ContractModel):
    seeds: list[int]
    variants: list[str]
    cells: list[SweepCell]
    outcomes: list[SweepOutcome]
    notice: str


# --- Benchmark run and streaming --------------------------------------------


class BenchmarkStage(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class BenchmarkEventKind(StrEnum):
    BENCHMARK_STARTED = "BENCHMARK_STARTED"
    ARM_STARTED = "ARM_STARTED"
    DAY_TICK = "DAY_TICK"
    DECISION_TAKEN = "DECISION_TAKEN"
    ARM_COMPLETED = "ARM_COMPLETED"
    BENCHMARK_COMPLETED = "BENCHMARK_COMPLETED"
    BENCHMARK_FAILED = "BENCHMARK_FAILED"


class BenchmarkEvent(ContractModel):
    event_id: str
    sequence: Annotated[int, Field(ge=1)]
    timestamp: datetime
    kind: BenchmarkEventKind
    arm: FleetArm | None = None
    day: DailyKpi | None = None
    decision: RecordedDecision | None = None
    message: str
    error: str | None = None


class CreateBenchmarkRequest(ContractModel):
    seed: int = 42
    arms: list[FleetArm] | None = None
    brain: FleetBrainMode = FleetBrainMode.SCRIPTED
    playback_speed: Annotated[float, Field(gt=0, le=100)] = 1.0


class BenchmarkCreated(ContractModel):
    benchmark_id: str
    stage: BenchmarkStage
    events_url: str
    playback_notice: str


class BenchmarkState(ContractModel):
    benchmark_id: str
    stage: BenchmarkStage
    config: BenchmarkConfig
    events: list[BenchmarkEvent] = Field(default_factory=list)
    result: BenchmarkResult | None = None
    playback_notice: str
    error: str | None = None
