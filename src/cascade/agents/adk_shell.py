from dataclasses import dataclass

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import Workflow

from cascade.tools import (
    analyse_connections,
    compare_plans,
    dispatch_plan,
    find_alternative_sailings,
    retrieve_context,
    simulate_yard,
    validate_actions,
)

MODEL = "gemini-3.5-flash"


@dataclass(frozen=True)
class AgentShell:
    """Named ADK agents plus the parallel assessment stage.

    Creation is side-effect free. The deterministic workflow engine will invoke
    this shell only after the live Gemini workstream is implemented.
    """

    app: App
    coordinator: Agent
    impact: Agent
    yard: Agent
    recovery: Agent
    execution: Agent
    parallel_assessment: Workflow


def _model() -> Gemini:
    return Gemini(model=MODEL)


def build_agent_shell() -> AgentShell:
    impact = Agent(
        name="impact_agent",
        model=_model(),
        instruction=(
            "Analyze synthetic connection impact and cargo urgency. "
            "Use tool values as facts and do not invent operational data."
        ),
        tools=[analyse_connections],
    )
    yard = Agent(
        name="yard_agent",
        model=_model(),
        instruction=(
            "Analyze synthetic yard occupancy and reefer plug constraints. "
            "Use tool values as facts and surface capacity breaches."
        ),
        tools=[simulate_yard],
    )
    parallel_assessment = Workflow(
        name="parallel_assessment",
        description="Run Impact and Yard assessments concurrently.",
        edges=[("START", (impact, yard))],
    )
    recovery = Agent(
        name="recovery_agent",
        model=_model(),
        instruction=(
            "Generate exactly three recovery plans within the documented archetypes. "
            "Revise any proposal rejected by deterministic validation."
        ),
        tools=[find_alternative_sailings, compare_plans, retrieve_context],
    )
    execution = Agent(
        name="execution_agent",
        model=_model(),
        instruction=(
            "Only after human approval, translate the approved synthetic plan into "
            "allowlisted mocked actions."
        ),
        tools=[validate_actions, dispatch_plan],
    )
    coordinator = Agent(
        name="coordinator_agent",
        model=_model(),
        instruction=(
            "Coordinate disruption recovery, reconcile specialist evidence, open disputes, "
            "and require human approval before execution. Never alter calculated values."
        ),
    )
    app = App(name="cascade", root_agent=coordinator)
    return AgentShell(
        app=app,
        coordinator=coordinator,
        impact=impact,
        yard=yard,
        recovery=recovery,
        execution=execution,
        parallel_assessment=parallel_assessment,
    )
