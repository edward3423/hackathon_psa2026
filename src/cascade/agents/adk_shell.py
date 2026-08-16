from dataclasses import dataclass

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import Workflow

from cascade.agents.base import load_prompt
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
        instruction=load_prompt("impact"),
        tools=[analyse_connections],
    )
    yard = Agent(
        name="yard_agent",
        model=_model(),
        instruction=load_prompt("yard"),
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
        instruction=load_prompt("recovery"),
        tools=[find_alternative_sailings, compare_plans, retrieve_context],
    )
    execution = Agent(
        name="execution_agent",
        model=_model(),
        instruction=load_prompt("execution"),
        tools=[validate_actions, dispatch_plan],
    )
    coordinator = Agent(
        name="coordinator_agent",
        model=_model(),
        instruction=load_prompt("coordinator"),
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
