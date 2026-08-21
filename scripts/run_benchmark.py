"""Run the Red Sea 2024 crisis benchmark once and score it at the terminal.

    uv run python scripts/run_benchmark.py [--seed 42] [--arms ...] [--brain ...]
    uv run python scripts/run_benchmark.py --write-golden

This is a thin wrapper. Every number it prints comes from
``cascade.engine.fleet.benchmark.run_benchmark``; nothing is recomputed here,
because a scoring table that does its own arithmetic is a second source of
truth waiting to disagree with the first.

Two output conventions are worth stating.

**The anchor rows are context, not a grade.** They hold recorded 2024 scalars
next to what the simulation produced, and the simulation is driven by a
throughput series that congestion suppresses, so it cannot reproduce the
recorded crisis and does not claim to. Each row therefore prints its
``interpretation`` - the structural reason it lands where it does - and the
word PASS never appears next to one. See ``BENCHMARK_NOTICE``.

**Blanks stay blank.** The historical arm is a reconstructed wait curve and
knows nothing about vessels served or port stay, so those cells print "-"
rather than the zero the contract stores. A plausible-looking fabricated
number is worse than an obvious blank.

The full ``BenchmarkResult`` is written to
``logs/benchmarks/<config_hash>_<seed>.json``, where the hash is a short digest
of the config JSON. Two runs of the same config land on the same file; changing
any knob lands on a different one, so a log directory is a record of what was
actually run rather than a pile of overwritten files.
"""

import argparse
import hashlib
import json
import textwrap
from pathlib import Path

from cascade.benchmark_run import DEFAULT_ARMS, default_world
from cascade.contracts import (
    AnchorComparison,
    ArmComparison,
    ArmResult,
    BenchmarkConfig,
    BenchmarkResult,
    FleetArm,
    FleetBrainMode,
)
from cascade.engine.fleet.benchmark import run_benchmark

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "logs" / "benchmarks"
GOLDEN_PATH = REPO_ROOT / "fixtures" / "benchmark_golden.json"

#: Width of the short config digest. Twelve hex characters is far more than a
#: handful of local runs will ever need and short enough to type.
HASH_CHARS = 12

#: Every rule, table row and wrapped paragraph is this wide, so the report is
#: one rectangle rather than a ragged stack of blocks.
TABLE_WIDTH = 100

ARMS_HEADER = (
    f"{'arm':<25} {'provenance':<13} {'peak wait':>9} {'peak date':>10} "
    f"{'recovery':>10} {'mean wait':>9} {'vessels':>7} {'decisions':>10}"
)


def config_hash(config: BenchmarkConfig) -> str:
    """A short, stable digest of everything that decides the result.

    Hashing the serialised config rather than a hand-picked tuple of fields
    means a knob added to ``BenchmarkConfig`` later changes the hash without
    anyone having to remember to update this function.
    """
    payload = config.model_dump_json()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:HASH_CHARS]


def build_config(seed: int, arms: list[FleetArm], brain: FleetBrainMode) -> BenchmarkConfig:
    return BenchmarkConfig(seed=seed, arms=arms, world=default_world(seed), brain=brain)


def pinnable(result: BenchmarkResult) -> BenchmarkResult:
    """The result with its one non-deterministic field neutralised.

    ``runtime_ms`` is wall-clock, so it is the single field that stops two runs
    of the same config from being byte-identical. Zeroing it is what makes a
    golden fixture possible; the test that reads the golden zeroes the same
    field, so nothing is being hidden.
    """
    return result.model_copy(update={"runtime_ms": 0})


def render(result: BenchmarkResult) -> str:
    return json.dumps(result.model_dump(mode="json"), indent=2) + "\n"


def write_result(result: BenchmarkResult) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{config_hash(result.config)}_{result.config.seed}.json"
    path.write_text(render(result), encoding="utf-8", newline="\n")
    return path


# --- scoring table ----------------------------------------------------------


def _days(value: float | None, unit: str = " d") -> str:
    return "-" if value is None else f"{value:.2f}{unit}"


def _arm_row(arm: ArmResult) -> str:
    metrics = arm.metrics
    # Vessels served and decisions are meaningless for a reconstructed curve;
    # the contract stores zero for them and the table must not draw that as a
    # measurement. See the module docstring.
    served = f"{metrics.vessels_served:d}" if arm.is_simulation else "-"
    decisions = f"{len(arm.decisions):d}" if arm.is_simulation else "-"
    return (
        f"{arm.arm.value:<25} {arm.provenance.value:<13} "
        f"{_days(metrics.peak_wait_days):>9} {metrics.peak_wait_date.isoformat():>10} "
        f"{(metrics.recovery_date.isoformat() if metrics.recovery_date else 'never'):>10} "
        f"{_days(metrics.mean_wait_days):>9} {served:>7} {decisions:>10}"
    )


def format_arms(result: BenchmarkResult) -> list[str]:
    lines = ["ARMS", ARMS_HEADER, "-" * TABLE_WIDTH]
    lines.extend(_arm_row(arm) for arm in result.arms)
    for arm in result.arms:
        if arm.caveat:
            lines.append("")
            lines.extend(textwrap.wrap(f"{arm.arm.value}: {arm.caveat}", TABLE_WIDTH))
    return lines


def _verdict(won: bool) -> str:
    return "WIN " if won else "LOSS"


def format_comparisons(result: BenchmarkResult, comparisons: list[ArmComparison]) -> list[str]:
    if not comparisons:
        return ["HEAD-TO-HEAD", "no simulated arm to compare against the reactive baseline"]
    lines = ["HEAD-TO-HEAD"]
    for comparison in comparisons:
        base = next(
            (arm for arm in result.arms if arm.arm is comparison.versus),
            None,
        )
        never = base is not None and base.metrics.recovery_date is None
        lines.append(f"{comparison.arm.value} vs {comparison.versus.value}")
        lines.append(
            f"  {_verdict(comparison.wins_on_peak)} peak wait     "
            f"{comparison.peak_wait_delta_days:+.2f} d "
            f"({comparison.peak_wait_reduction_pct:+.1f}% against the baseline peak)"
        )
        recovery = (
            "the baseline never recovers"
            if comparison.recovery_days_saved is None and never
            else _days(comparison.recovery_days_saved, " days sooner")
        )
        lines.append(f"  {_verdict(comparison.wins_on_recovery)} recovery      {recovery}")
        lines.append(
            f"       mean wait     {comparison.mean_wait_delta_days:+.3f} d, "
            f"wait cost {comparison.wait_cost_delta_usd:+,.0f} USD"
        )
    return lines


def format_anchors(anchors: list[AnchorComparison]) -> list[str]:
    """Recorded scalars next to simulated ones. Deliberately ungraded.

    ``within_tolerance`` is reported as "inside"/"outside" rather than
    pass/fail, and every row carries its interpretation, because the
    simulation is not attempting to reproduce these figures.
    """
    if not anchors:
        return []
    lines = [
        "ANCHOR CONTEXT (published 2024 figures, not a pass/fail grade)",
        "The comparator is the reactive baseline throughout. These rows exist so the",
        "gap between the model and the record stays visible; they do not score it.",
    ]
    for anchor in anchors:
        lines.append("")
        lines.append(
            f"  {anchor.anchor_key}: recorded {anchor.recorded_value:g} {anchor.unit}, "
            f"simulated {anchor.simulated_value:.2f} {anchor.unit} "
            f"(tolerance +-{anchor.tolerance:g}, "
            f"{'inside' if anchor.within_tolerance else 'outside'})"
        )
        lines.extend(
            textwrap.wrap(
                anchor.interpretation,
                TABLE_WIDTH,
                initial_indent="    ",
                subsequent_indent="    ",
            )
        )
    return lines


def format_report(result: BenchmarkResult) -> str:
    calibration = next((arm.calibration for arm in result.arms if arm.calibration), None)
    header = [
        f"CASCADE benchmark {result.benchmark_id}  "
        f"seed={result.config.seed} brain={result.config.brain.value}",
        f"calibration {result.calibration_window.start} .. {result.calibration_window.end}   "
        f"blind {result.blind_window.start} .. {result.blind_window.end}",
    ]
    if calibration is not None:
        header.append(
            f"calibration: {calibration.effective_berths} effective berths, "
            f"utilisation {calibration.utilisation:.3f}, "
            f"throughput error {calibration.throughput_error_pct:+.2f}%, "
            f"{'PASSED' if calibration.passed else 'FAILED'}"
        )
    blocks = [
        header,
        format_arms(result),
        format_comparisons(result, result.comparisons),
        format_anchors(result.anchor_comparisons),
        textwrap.wrap(result.notice, TABLE_WIDTH),
        [f"runtime {result.runtime_ms} ms"],
    ]
    separator = "\n" + "=" * TABLE_WIDTH + "\n"
    return separator.join("\n".join(block) for block in blocks if block)


# --- entry point ------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42, help="World seed. Default 42.")
    parser.add_argument(
        "--arms",
        nargs="+",
        type=FleetArm,
        choices=list(FleetArm),
        default=list(DEFAULT_ARMS),
        help="Arms to run, in chart order. Default: the three headline arms.",
    )
    parser.add_argument(
        "--brain",
        type=FleetBrainMode,
        choices=list(FleetBrainMode),
        default=FleetBrainMode.SCRIPTED,
        help="Strategy brain. SCRIPTED is the scored, offline default.",
    )
    parser.add_argument(
        "--write-golden",
        action="store_true",
        help=(
            "Also rewrite fixtures/benchmark_golden.json from this run. Only the "
            "pinned configuration (seed 42, default arms, scripted brain) may be "
            "written, so the golden cannot be quietly replaced by a friendlier run."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = build_config(args.seed, list(args.arms), args.brain)
    result = run_benchmark(config)
    print(format_report(result))
    path = write_result(result)
    print(f"\nwrote {path.relative_to(REPO_ROOT).as_posix()}")

    if args.write_golden:
        pinned = build_config(42, list(DEFAULT_ARMS), FleetBrainMode.SCRIPTED)
        if config != pinned:
            print(
                "refusing to write the golden: it pins seed 42, the default arms and "
                "the scripted brain, and this run used a different configuration"
            )
            return 1
        GOLDEN_PATH.write_text(render(pinnable(result)), encoding="utf-8", newline="\n")
        print(f"wrote {GOLDEN_PATH.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
