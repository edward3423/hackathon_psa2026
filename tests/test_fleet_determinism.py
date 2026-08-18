"""The benchmark is a pure function of its config and the committed fixtures.

Every claim the project makes rests on a comparison between arms that share one
world. That argument only holds if a run is reproducible at all, so this file
checks the property directly: same config, byte-identical ``BenchmarkResult``.

Byte-identical is the right bar rather than "close enough". Floating-point
metrics compared with a tolerance would hide exactly the kind of drift that
matters - a reordered dict, an event tie broken differently, a set iterated -
and any of those would mean the arms are no longer being compared like for
like.
"""

import time

import pytest

from cascade.benchmark_run import DEFAULT_ARMS, default_world
from cascade.contracts import BenchmarkConfig, BenchmarkResult, FleetArm, FleetBrainMode
from cascade.engine.fleet.benchmark import run_benchmark

#: A cold run pays about 30 seconds for the calibration coordinate search, so
#: this file is slow by nature and marked as such. It stays in the default
#: suite: determinism is not an optional property here.
pytestmark = pytest.mark.slow

#: Ceiling for a warm run - one where the fitted world is already memoised.
#: Measured at about 0.5 s for three simulated arms over the 153-day blind
#: window on the development machine, so this is a roughly tenfold margin,
#: generous enough not to flake on a loaded CI box and tight enough to catch an
#: accidental per-arm recalibration, which would cost tens of seconds.
#:
#: The project plan quotes "<100 ms" for this guard. That figure predates the
#: real fixture: it was written for a toy window, and the benchmark now replays
#: 5,459 vessel calls per arm. It is not used.
WARM_RUNTIME_BUDGET_SECONDS = 5.0


def make_config(seed: int = 42) -> BenchmarkConfig:
    return BenchmarkConfig(
        seed=seed,
        arms=list(DEFAULT_ARMS),
        world=default_world(seed),
        brain=FleetBrainMode.SCRIPTED,
    )


def serialise(result: BenchmarkResult) -> str:
    """The result as bytes, minus the one field that is a wall clock."""
    return result.model_copy(update={"runtime_ms": 0}).model_dump_json()


def test_the_same_config_produces_a_byte_identical_result() -> None:
    # Two independently constructed configs, not one object passed twice, so a
    # result that quietly depended on object identity would still be caught.
    first = run_benchmark(make_config())
    second = run_benchmark(make_config())

    assert serialise(first) == serialise(second)


def test_a_different_seed_produces_a_different_result() -> None:
    """The counterpart guard: determinism must not be a constant function.

    Without this, an engine that ignored the seed entirely would sail through
    the test above.
    """
    assert serialise(run_benchmark(make_config(42))) != serialise(run_benchmark(make_config(7)))


def test_a_warm_run_stays_inside_its_runtime_budget() -> None:
    """The fitted world is memoised, so only the first run in a process is slow.

    This is what makes a 225-cell sweep affordable in one process. If the memo
    ever stops working the sweep does not fail, it just quietly takes hours, so
    the guard is here rather than in the sweep script.
    """
    config = make_config()
    run_benchmark(config)  # warm the calibration memo; deliberately not timed

    started = time.perf_counter()
    run_benchmark(config)
    elapsed = time.perf_counter() - started

    assert elapsed < WARM_RUNTIME_BUDGET_SECONDS, (
        f"a warm benchmark run took {elapsed:.2f} s against a "
        f"{WARM_RUNTIME_BUDGET_SECONDS:.0f} s budget; the calibration memo has probably "
        "stopped matching"
    )


def test_the_stress_arm_shares_the_headline_arm_calibration() -> None:
    """Adding the stress arm must not perturb the arms already in the run."""
    with_stress = run_benchmark(
        BenchmarkConfig(
            seed=42,
            arms=[*DEFAULT_ARMS, FleetArm.CASCADE_NO_EXTRA_CAPACITY],
            world=default_world(42),
            brain=FleetBrainMode.SCRIPTED,
        )
    )
    without = run_benchmark(make_config())

    by_arm = {arm.arm: arm for arm in with_stress.arms}
    for arm in without.arms:
        assert by_arm[arm.arm].model_dump_json() == arm.model_dump_json()
