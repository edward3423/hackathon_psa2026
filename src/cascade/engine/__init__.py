"""Pure deterministic simulation engine for CASCADE.

Every function in this package is free of I/O, randomness, and clock reads.
All times come from the inputs, so repeated calls with equal inputs return
equal outputs.
"""

from cascade.engine.actions import build_actions, validate_actions
from cascade.engine.connections import analyse_connections
from cascade.engine.costs import estimate_cost
from cascade.engine.plans import compare_plans, evaluate_plan
from cascade.engine.yard import simulate_yard

__all__ = [
    "analyse_connections",
    "build_actions",
    "compare_plans",
    "estimate_cost",
    "evaluate_plan",
    "simulate_yard",
    "validate_actions",
]
