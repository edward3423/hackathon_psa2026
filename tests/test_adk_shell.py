from cascade.agents import build_agent_shell


def test_adk_shell_contains_five_named_agents() -> None:
    shell = build_agent_shell()

    assert shell.coordinator.name == "coordinator_agent"
    assert shell.impact.name == "impact_agent"
    assert shell.yard.name == "yard_agent"
    assert shell.recovery.name == "recovery_agent"
    assert shell.execution.name == "execution_agent"
    assert shell.parallel_assessment.graph is not None
    graph_agents = {node.name for node in shell.parallel_assessment.graph.nodes}
    assert {"impact_agent", "yard_agent"}.issubset(graph_agents)
