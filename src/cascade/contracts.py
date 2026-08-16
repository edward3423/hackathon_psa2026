from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunMode(StrEnum):
    LIVE_STUB = "LIVE_STUB"
    LIVE_GEMINI = "LIVE_GEMINI"
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


class RunCreated(ContractModel):
    run_id: str
    mode: RunMode
    stage: WorkflowStage
    events_url: str


class HealthResponse(ContractModel):
    status: str
    version: str
