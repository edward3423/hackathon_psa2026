"""Robustness sweep: does CASCADE still beat the baseline when the world moves?

    uv run python scripts/benchmark_sweep.py            # 25 seeds x 9 variants
    uv run python scripts/benchmark_sweep.py --quick    # 3 seeds x 3 variants
    uv run python scripts/benchmark_sweep.py --seeds 10 --seed-start 100

The win rate this prints is the headline claim of the project, so the design of
the sweep matters more than the code in it.

**A cell is one call to ``run_benchmark``, never one per arm.** All three
simulated arms in a cell come out of a single call, which is what guarantees
they share one calibration, one fitted world, one arrival stream and one RNG
seed. Running the arms in separate calls and comparing the answers would leave
a fairness argument to be made in prose; running them in one call makes the
argument structural. The arms differ in exactly one thing - which policy object
the engine is handed - because that is the only thing ``run_benchmark`` varies.

**The perturbations perturb the run, not the fit.** ``run_benchmark``
neutralises every sweep knob before calibrating (see ``_CALIBRATION_NEUTRAL``),
so a cell that makes the port 15% slower does not get a service model refitted
to make it fast again. It also means the whole sweep pays for one calibration
instead of one per cell, which is why this is worth running in a single
process: a cold calibration costs about 30 seconds and each cell after it costs
about half a second.

**Nothing is dropped, and a tie is not a win.** Every cell that runs is written
to ``logs/benchmarks/sweep_summary.json``, so the published win rate can be
recomputed from the record rather than trusted. A win means strictly lower peak
wait than the baseline, the same rule the single-run head-to-head uses. That
rule scores a cell where the port never congests - and the agentic arm
therefore never pulls a lever, leaving it bit-identical to the baseline - as a
non-win. The tables print ties and losses in their own columns so those two
very different kinds of non-win are never read as one.

The grid follows plan/prd_main.md: service rate +-15%, +-1 effective berth,
arrival jitter, and berth activation leads of 10, 14 and 21 days. The stress
arm ``CASCADE_NO_EXTRA_CAPACITY`` runs in every cell alongside the headline
arm, so the sweep also answers how much of the result survives with the
capacity lever taken away.
"""

import argparse
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from cascade.benchmark_run import default_world
from cascade.contracts import (
    BenchmarkConfig,
    BenchmarkResult,
    FleetArm,
    FleetBrainMode,
    SweepCell,
    SweepOutcome,
    SweepSummary,
)
from cascade.engine.fleet.benchmark import COMPARISON_BASE, recovery_rank, run_benchmark

REPO_ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = REPO_ROOT / "logs" / "benchmarks" / "sweep_summary.json"

#: The reactive baseline plus the two agentic arms. Order matters only for the
#: printed tables; ``run_benchmark`` scores every simulated arm against
#: ``COMPARISON_BASE`` regardless of position.
SWEEP_ARMS = [
    FleetArm.REACTIVE_BASELINE,
    FleetArm.CASCADE_AGENTIC,
    FleetArm.CASCADE_NO_EXTRA_CAPACITY,
]

DEFAULT_SEEDS = 25
DEFAULT_SEED_START = 42

#: Seeds and variants a smoke run uses. Small enough to finish in under a
#: minute after the calibration, large enough that a broken sweep still fails.
QUICK_SEEDS = 3
QUICK_VARIANTS = ("baseline", "service_15pct_slower", "one_berth_fewer")

SWEEP_NOTICE = (
    "Every cell is one run_benchmark call, so the arms within a cell share one "
    "calibration, one fitted world, one arrival stream and one seed and differ "
    "only in policy. The perturbations below are applied to the world the arms "
    "run in and never to the window the service model is fitted on, so a slower "
    "port stays slower instead of being calibrated back to normal. Every cell "
    "that ran is recorded here, losses and ties included. A win is strictly "
    "better on peak wait, so a cell where the port never congests and the "
    "agentic arm therefore never pulls a lever counts as a non-win, not a win."
)


@dataclass(frozen=True, slots=True)
class Variant:
    """One point of the parameter grid, as an override on the default world."""

    name: str
    overrides: dict[str, object]
    rationale: str


#: The grid. Each entry perturbs exactly one dimension, because a sweep whose
#: cells move two things at once cannot say which one broke the result.
VARIANTS: tuple[Variant, ...] = (
    Variant("baseline", {}, "The default world, unperturbed."),
    Variant(
        "service_15pct_slower",
        {"service_rate_multiplier": 1.15},
        "Every call takes 15% longer at the berth: a port less capable than the fit says.",
    ),
    Variant(
        "service_15pct_faster",
        {"service_rate_multiplier": 0.85},
        "Every call takes 15% less: a port that never congests enough to need a policy.",
    ),
    Variant(
        "one_berth_fewer",
        {"berth_delta": -1},
        "One effective berth below the calibrated count: the fit wrong in the tight direction.",
    ),
    Variant(
        "one_berth_more",
        {"berth_delta": 1},
        "One effective berth above the calibrated count, the loose direction.",
    ),
    Variant(
        "arrival_jitter_6h",
        {"arrival_jitter_hours": 6.0},
        "Arrival times shifted by up to 6 hours either way, which is what the seed drives.",
    ),
    Variant(
        "activation_lead_10d",
        {"activation_lead_override_days": 10},
        "Reserve berths stand up faster than the 14-day estimate.",
    ),
    Variant(
        "activation_lead_14d",
        {"activation_lead_override_days": 14},
        "Both tranches held to the 14-day estimate, overriding the shorter Tuas lead.",
    ),
    Variant(
        "activation_lead_21d",
        {"activation_lead_override_days": 21},
        "Reserve berths take three weeks, the pessimistic end of the estimate.",
    ),
)

VARIANTS_BY_NAME = {variant.name: variant for variant in VARIANTS}


# --- running ----------------------------------------------------------------


def cell_config(seed: int, variant: Variant) -> BenchmarkConfig:
    """The config for one cell. Only ``world`` carries the perturbation."""
    return BenchmarkConfig(
        seed=seed,
        arms=list(SWEEP_ARMS),
        world=default_world(seed).model_copy(update=variant.overrides),
        brain=FleetBrainMode.SCRIPTED,
    )


def cells_from(result: BenchmarkResult, variant: str) -> list[SweepCell]:
    """Flatten one benchmark result into one row per simulated arm.

    ``recovery_day_index`` is days from the first day of the blind window
    rather than a date, so cells stay comparable if the window ever moves.
    """
    start = result.blind_window.start
    return [
        SweepCell(
            seed=result.config.seed,
            variant=variant,
            arm=arm.arm,
            peak_wait_days=arm.metrics.peak_wait_days,
            recovery_day_index=(
                None
                if arm.metrics.recovery_date is None
                else (arm.metrics.recovery_date - start).days
            ),
            days_above_two_day_wait=arm.metrics.days_above_two_day_wait,
            mean_wait_days=arm.metrics.mean_wait_days,
        )
        for arm in result.arms
        if arm.is_simulation
    ]


def run_sweep(
    seeds: Sequence[int], variants: Sequence[Variant], *, verbose: bool
) -> list[SweepCell]:
    cells: list[SweepCell] = []
    total = len(seeds) * len(variants)
    for index, (variant, seed) in enumerate(
        ((variant, seed) for variant in variants for seed in seeds), start=1
    ):
        result = run_benchmark(cell_config(seed, variant))
        cells.extend(cells_from(result, variant.name))
        if verbose:
            print(f"  [{index:>4}/{total}] {variant.name} seed={seed}", flush=True)
    return cells


# --- scoring ----------------------------------------------------------------


def _percentile(values: Sequence[float], fraction: float) -> float:
    """Linearly interpolated percentile, defined for a single value too.

    ``statistics.quantiles`` refuses fewer than two points and only yields a
    fixed lattice of cut points, which a --quick run and a p10/p50/p90 report
    both fall foul of.
    """
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = fraction * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _beats_on_recovery(arm: SweepCell, base: SweepCell) -> bool:
    """Coming through the crisis better than the baseline; a tie is not a win.

    Literally the same function ``benchmark._compare`` applies, not merely the
    same rule, so a cell and a single-run head-to-head cannot disagree about
    who won.
    """
    return recovery_rank(arm.days_above_two_day_wait, arm.recovery_day_index) < recovery_rank(
        base.days_above_two_day_wait, base.recovery_day_index
    )


def score(cells: Iterable[SweepCell], base_arm: FleetArm = COMPARISON_BASE) -> list[SweepOutcome]:
    """One ``SweepOutcome`` per challenger arm, over every cell it appears in.

    A cell without its baseline counterpart is skipped rather than scored
    against a substitute: an unpaired win is not a win.
    """
    by_key: dict[tuple[int, str, FleetArm], SweepCell] = {
        (cell.seed, cell.variant, cell.arm): cell for cell in cells
    }
    arms = sorted({arm for _, _, arm in by_key if arm is not base_arm}, key=lambda arm: arm.value)

    outcomes: list[SweepOutcome] = []
    for arm in arms:
        deltas: list[float] = []
        peak_wins = 0
        recovery_wins = 0
        for (seed, variant, cell_arm), cell in by_key.items():
            if cell_arm is not arm:
                continue
            base = by_key.get((seed, variant, base_arm))
            if base is None:
                continue
            deltas.append(base.peak_wait_days - cell.peak_wait_days)
            peak_wins += cell.peak_wait_days < base.peak_wait_days
            recovery_wins += _beats_on_recovery(cell, base)
        if not deltas:
            continue
        outcomes.append(
            SweepOutcome(
                arm=arm,
                versus=base_arm,
                runs=len(deltas),
                wins_on_peak=peak_wins,
                wins_on_recovery=recovery_wins,
                win_rate_peak=peak_wins / len(deltas),
                win_rate_recovery=recovery_wins / len(deltas),
                peak_delta_p10=_percentile(deltas, 0.10),
                peak_delta_p50=_percentile(deltas, 0.50),
                peak_delta_p90=_percentile(deltas, 0.90),
            )
        )
    return outcomes


# --- reporting --------------------------------------------------------------


def tally(cells: Iterable[SweepCell], arm: FleetArm) -> tuple[int, int, int]:
    """Wins, exact ties and losses on peak wait against the baseline.

    ``SweepOutcome.win_rate_peak`` counts strictly-better cells only, matching
    the head-to-head rule in ``benchmark._compare``. That is the right rule to
    publish, but on its own it reads a tie as a defeat, and the ties here are
    not close calls: in a world with slack capacity the scripted brain never
    pulls a lever, so the agentic arm is bit-identical to the baseline. The
    split is printed next to the win rate so nobody has to guess which kind of
    non-win they are looking at.
    """
    by_key: dict[tuple[int, str, FleetArm], SweepCell] = {
        (cell.seed, cell.variant, cell.arm): cell for cell in cells
    }
    wins = ties = losses = 0
    for (seed, variant, cell_arm), cell in by_key.items():
        base = by_key.get((seed, variant, COMPARISON_BASE))
        if cell_arm is not arm or base is None:
            continue
        wins += cell.peak_wait_days < base.peak_wait_days
        ties += cell.peak_wait_days == base.peak_wait_days
        losses += cell.peak_wait_days > base.peak_wait_days
    return wins, ties, losses


OUTCOME_HEADER = (
    f"{'arm':<26} {'runs':>5} {'peak win':>9} {'tie':>6} {'loss':>6} "
    f"{'recov win':>10} {'p10':>7} {'p50':>7} {'p90':>7}"
)


def format_outcomes(
    title: str, outcomes: Sequence[SweepOutcome], cells: Sequence[SweepCell]
) -> list[str]:
    lines = [title, OUTCOME_HEADER, "-" * len(OUTCOME_HEADER)]
    for outcome in outcomes:
        _, ties, losses = tally(cells, outcome.arm)
        lines.append(
            f"{outcome.arm.value:<26} {outcome.runs:>5} "
            f"{outcome.win_rate_peak:>8.1%} {ties:>6} {losses:>6} "
            f"{outcome.win_rate_recovery:>10.1%} "
            f"{outcome.peak_delta_p10:>+7.2f} {outcome.peak_delta_p50:>+7.2f} "
            f"{outcome.peak_delta_p90:>+7.2f}"
        )
    lines.append("Peak win counts strictly-better cells; ties and losses are listed separately.")
    lines.append("p10/p50/p90 are the peak-wait advantage in days: positive means less waiting.")
    return lines


def format_by_variant(cells: Sequence[SweepCell], variants: Sequence[Variant]) -> list[str]:
    """One row per grid point, so a hostile variant cannot hide inside the mean."""
    arms = sorted({cell.arm for cell in cells if cell.arm is not COMPARISON_BASE})
    header = (
        f"{'variant':<22} {'arm':<26} {'win':>7} {'tie':>5} {'loss':>5} {'median advantage':>17}"
    )
    lines = ["BY VARIANT", header, "-" * len(header)]
    for variant in variants:
        subset = [cell for cell in cells if cell.variant == variant.name]
        outcomes = {outcome.arm: outcome for outcome in score(subset)}
        for arm in arms:
            outcome = outcomes.get(arm)
            if outcome is None:
                continue
            _, ties, losses = tally(subset, arm)
            lines.append(
                f"{variant.name:<22} {arm.value:<26} {outcome.win_rate_peak:>7.1%} "
                f"{ties:>5} {losses:>5} {outcome.peak_delta_p50:>+16.2f} d"
            )
    return lines


def write_summary(summary: SweepSummary, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary.model_dump(mode="json"), indent=2) + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")
    return path


# --- entry point ------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--seeds", type=int, default=DEFAULT_SEEDS, help=f"How many seeds. Default {DEFAULT_SEEDS}."
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=DEFAULT_SEED_START,
        help=f"First seed; the sweep uses a contiguous run. Default {DEFAULT_SEED_START}.",
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=[variant.name for variant in VARIANTS],
        help="Restrict the grid to these variants. Default: all of them.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help=f"Smoke run: {QUICK_SEEDS} seeds over {len(QUICK_VARIANTS)} variants.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=SUMMARY_PATH,
        help="Where to write the summary JSON. Default logs/benchmarks/sweep_summary.json.",
    )
    parser.add_argument("--quiet", action="store_true", help="Do not print per-cell progress.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    count = QUICK_SEEDS if args.quick else args.seeds
    seeds = list(range(args.seed_start, args.seed_start + count))
    names = args.variants or (QUICK_VARIANTS if args.quick else [v.name for v in VARIANTS])
    variants = [VARIANTS_BY_NAME[name] for name in names]

    print(
        f"sweeping {len(seeds)} seed(s) x {len(variants)} variant(s) x "
        f"{len(SWEEP_ARMS)} arm(s); the first cell pays for the calibration"
    )
    cells = run_sweep(seeds, variants, verbose=not args.quiet)
    summary = SweepSummary(
        seeds=seeds,
        variants=[variant.name for variant in variants],
        cells=cells,
        outcomes=score(cells),
        notice=SWEEP_NOTICE,
    )

    print()
    print("\n".join(format_outcomes("OVERALL", summary.outcomes, cells)))
    print()
    print("\n".join(format_by_variant(cells, variants)))
    path = write_summary(summary, args.out)
    try:
        shown = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        shown = str(path)
    print(f"\nwrote {shown} ({len(cells)} cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
