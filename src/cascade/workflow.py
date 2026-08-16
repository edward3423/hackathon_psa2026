from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import uuid4

from cascade.contracts import (
    AgentActivity,
    AgentName,
    AgentStatus,
    RunMode,
    ScenarioControls,
    ScenarioState,
    TraceEvent,
    WorkflowStage,
)
from cascade.fixtures import load_fake_events, load_golden_scenario

AGENT_OBJECTIVES: dict[AgentName, str] = {
    AgentName.COORDINATOR: "Interpret the alert and coordinate the recovery workflow.",
    AgentName.IMPACT: "Analyze connection impact and cargo urgency.",
    AgentName.YARD: "Analyze yard occupancy and reefer plug constraints.",
    AgentName.RECOVERY: "Generate and compare validated recovery plans.",
    AgentName.EXECUTION: "Prepare validated mocked actions after approval.",
}


@dataclass
class DemoRun:
    run_id: str
    controls: ScenarioControls
    mode: RunMode = RunMode.LIVE_STUB
    stage: WorkflowStage = WorkflowStage.READY
    trace: list[TraceEvent] = field(default_factory=list)

    def events(self) -> Iterator[TraceEvent]:
        for recorded in load_fake_events():
            event = recorded.model_copy(deep=True)
            if event.sequence == 1:
                event.input_summary = (
                    f"MV ATLAS STAR revised ETA is {self.controls.delay_hours} hours late; "
                    f"priority is {self.controls.priority_emphasis.value}."
                )
            self.stage = event.stage
            self.trace.append(event)
            yield event

    def activities(self) -> list[AgentActivity]:
        latest: dict[AgentName, TraceEvent] = {
            event.agent: event for event in self.trace if event.agent is not None
        }
        activities: list[AgentActivity] = []
        for agent, objective in AGENT_OBJECTIVES.items():
            event = latest.get(agent)
            status = AgentStatus.WAITING
            if event is not None:
                status = (
                    AgentStatus.BLOCKED
                    if event.stage in {WorkflowStage.DISPUTE, WorkflowStage.AWAITING_APPROVAL}
                    else AgentStatus.COMPLETED
                )
            activities.append(
                AgentActivity(
                    agent=agent,
                    objective=objective,
                    status=status,
                    confidence=event.confidence if event else None,
                    last_summary=(event.result or event.decision_summary) if event else None,
                )
            )
        return activities


class DemoRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, DemoRun] = {}

    def create(self, controls: ScenarioControls) -> DemoRun:
        run = DemoRun(run_id=str(uuid4()), controls=controls)
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> DemoRun | None:
        return self._runs.get(run_id)

    def reset(self) -> None:
        self._runs.clear()


def scenario_with_controls(controls: ScenarioControls | None = None) -> ScenarioState:
    scenario = load_golden_scenario()
    if controls is None:
        return scenario
    alert = scenario.alert.model_copy(
        update={"revised_eta": scenario.alert.original_eta + timedelta(hours=controls.delay_hours)}
    )
    return scenario.model_copy(update={"alert": alert, "controls": controls})
