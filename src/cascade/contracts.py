from datetime import datetime
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
