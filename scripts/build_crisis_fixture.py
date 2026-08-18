"""Deterministic builder for the Act 2 Red Sea 2024 crisis fixtures.

    uv run python scripts/build_crisis_fixture.py

Regenerating rewrites fixtures/crisis_arrivals.json,
fixtures/crisis_ground_truth.json and fixtures/crisis_manifest.json
byte-identically. All randomness flows through random.Random instances seeded
from SEED; the system clock and the global random module are never used.

What is recorded and what is synthesised
----------------------------------------
RECORDED (IMF PortWatch, unmodified): the daily count of container port calls
at the Port of Singapore, `ArrivalDay.portcalls_container`. One VesselArrival
is emitted per recorded call, so the arrival COUNT on every day is real.

SYNTHESISED (seeded, fitted on the calibration window only): each call's TEU
exchange, its transhipment share, and its time of day. No public source
publishes per-vessel exchange volumes or berth-request timestamps for
Singapore, so these are drawn from documented distributions rather than
measured. They are labelled as such in `synthesis_notice`.

Window separation
-----------------
Calibration: 2023-01-01 .. 2024-02-29 (pre-crisis).
Blind:       2024-04-01 .. 2024-08-31 (crisis replay).
March 2024 is deliberately in neither slice. It is a buffer: the Red Sea
diversions were already reshaping arrival patterns by then, so it is neither
clean pre-crisis calibration data nor part of the replay. The two slices are
physically separate lists and share no day.

Every distribution parameter below is fitted on calibration days only. No
blind-window day is read when deriving the size distribution, the correction
factor, the day-of-week bunching profile, or the 2023 seasonal baseline.

TEU size arithmetic
-------------------
MPA Singapore reports 39.01 million TEU of container throughput for calendar
2023 (media release, 12 January 2024). Throughput counts every box move at the
quay, which is exactly the quantity a vessel call exchanges, so:

    mean TEU per call = 39.01e6 / (total recorded container calls in 2023)

Call sizes are drawn as lognormal(mu=0, sigma=SIZE_SIGMA) shape factors. The
shape factors are rescaled by a single correction constant, chosen so the mean
over the 2023 calendar-year draws equals the target above; the correction is
then refined once after clamping to [MIN_TEU, MAX_TEU] so the clamp does not
drag the mean off target. Both passes look only at 2023 draws. Multiplying the
resulting mean call size by the recorded number of 2023 calls reproduces the
published 39.01 million TEU to well under one percent.

Transhipment share
------------------
Roughly 85 percent of Singapore's throughput is transhipment. Each call draws
a share around that mean with a modest seeded spread, clamped to a plausible
band; `connection_teu` is that share times `teu`.

Historical wait curve
---------------------
A reconstruction, never a measurement. See HISTORICAL_CURVE_METHOD.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from cascade.contracts import (
    ArrivalDay,
    ArrivalStreamFixture,
    BlindSlice,
    CalibrationSlice,
    DateWindow,
    FixtureManifest,
    GroundTruthAnchor,
    GroundTruthFixture,
    HistoricalWaitPoint,
    SeriesProvenance,
    VesselArrival,
)

SEED = 42
ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "portwatch_singapore.csv"
CURATED_GROUND_TRUTH = ROOT / "data" / "ground_truth_redsea_2024.json"
FIXTURES = ROOT / "fixtures"
ARRIVALS_PATH = FIXTURES / "crisis_arrivals.json"
GROUND_TRUTH_PATH = FIXTURES / "crisis_ground_truth.json"
MANIFEST_PATH = FIXTURES / "crisis_manifest.json"

GENERATED_BY = "scripts/build_crisis_fixture.py"

SOURCE = "IMF PortWatch, a joint IMF and University of Oxford project"
SOURCE_URL = "https://portwatch.imf.org/datasets/959214444157458aad969389b3ebe1a0_0/about"

CALIBRATION_WINDOW = DateWindow(
    label="Pre-crisis calibration",
    start=date(2023, 1, 1),
    end=date(2024, 2, 29),
)
BLIND_WINDOW = DateWindow(
    label="Red Sea crisis blind replay",
    start=date(2024, 4, 1),
    end=date(2024, 8, 31),
)

# MPA Singapore, 12 January 2024: 39.01 million TEU handled in calendar 2023.
PUBLISHED_2023_THROUGHPUT_TEU = 39.01e6
BASELINE_YEAR = 2023

# Call-size distribution. sigma is in log space; 0.80 gives a right-skewed
# spread that keeps the bulk of calls in feeder-to-mid-size territory with a
# thin mega-vessel tail, which is what a transhipment hub's call mix looks
# like.
SIZE_SIGMA = 0.80
MIN_TEU = 150.0
MAX_TEU = 24000.0

# Transhipment share per call, around Singapore's published ~85 percent.
CONNECTION_SHARE_MEAN = 0.85
CONNECTION_SHARE_SD = 0.05
CONNECTION_SHARE_MIN = 0.55
CONNECTION_SHARE_MAX = 0.97

# Intraday arrival shape, one relative weight per UTC hour. Singapore is
# UTC+8, so 00:00Z is 08:00 local: the profile peaks through the local
# business day and thins overnight. Illustrative, not measured.
HOURLY_WEIGHTS = (
    1.45, 1.50, 1.40, 1.25, 1.15, 1.20, 1.30, 1.40,
    1.35, 1.20, 1.05, 0.95, 0.85, 0.75, 0.65, 0.60,
    0.55, 0.60, 0.70, 0.85, 1.00, 1.15, 1.30, 1.40,
)  # fmt: skip

# How strongly a busy weekday bunches arrivals into the peak hours. The
# exponent applied to HOURLY_WEIGHTS is 1 + BUNCHING_STRENGTH * (factor - 1),
# where factor is that weekday's mean call count over the CALIBRATION window
# divided by the calibration-window mean. Busy weekdays sharpen the profile,
# quiet weekdays flatten it.
BUNCHING_STRENGTH = 2.0

# Reconstructed wait curve. DISPERSION_WINDOW_DAYS is the trailing window over
# which arrival regularity is measured; SMOOTHING_WINDOW_DAYS is the centred
# moving average applied afterwards.
DISPERSION_WINDOW_DAYS = 35
SMOOTHING_WINDOW_DAYS = 21

SYNTHESIS_NOTICE = (
    "Recorded: the daily container port-call count for the Port of Singapore "
    "(portcalls_container) is IMF PortWatch data, unmodified, and one vessel "
    "arrival is emitted per recorded call. Synthesised: each arrival's TEU "
    "exchange, its transhipment share (connection_teu) and its time of day. "
    "No public source publishes per-vessel exchange volumes or berth-request "
    "timestamps for Singapore, so these are drawn from seeded distributions "
    "fitted on the calibration window only (2023-01-01 to 2024-02-29) and "
    "scaled so 2023 reproduces Singapore's published 39.01 million TEU. "
    "March 2024 is excluded from both slices as a buffer."
)

HISTORICAL_CURVE_METHOD = (
    "Reconstruction, not measurement. No public source publishes a daily "
    "berth-waiting series for the Port of Singapore, so the shape of this "
    "curve is derived from a recorded series and its scale is set by two "
    "recorded anchors. Step 1: take the recorded IMF PortWatch daily "
    "container port-call series for Singapore. Step 2: divide each day by a "
    "2023 seasonal baseline - the 2023 mean daily call count times a "
    "calendar-month index times a day-of-week index, all computed from 2023 "
    "only - leaving a deseasonalised arrival-regularity residual. Step 3: for "
    "each day of the blind window take the coefficient of variation of that "
    "residual over the trailing 35 days. This is the arrival-dispersion, or "
    "off-schedule, signal: standard queueing theory (Kingman) makes berth "
    "waiting time rise with the variability of arrivals, not only with their "
    "number, and PSA International recorded exactly that mechanism for 2024 "
    "with about 90 percent of vessels arriving off-schedule against 77 "
    "percent in 2023. Step 4: smooth with a centred 21-day moving average. "
    "Step 5: apply one affine map, the same two constants for every day, "
    "chosen so the curve's peak equals the recorded 7.0-day peak berthing "
    "delay (Linerlytica, 28 May 2024) and its 2024-07-31 value equals the "
    "recorded 2.0-day recovered wait (PSA International, 10 July 2024); "
    "values are floored at zero. Known limitations: the reconstructed peak "
    "falls in mid-June rather than on the late-May date Linerlytica reported, "
    "and the curve shows a secondary rise through August that the anchors say "
    "nothing about. No individual point on this curve was ever observed. "
    "A simple cumulative call-deficit proxy was tried first and rejected: "
    "recorded Singapore container calls in 2024 run below 2023 in every month "
    "of the year, crisis or not, so a cumulative deficit rises monotonically "
    "into December and carries no crisis signal at all."
)

GROUND_TRUTH_NOTICE = (
    "Recorded: every anchor below is a figure published by the named source "
    "on the named date, copied unchanged. Reconstructed: historical_wait_curve "
    "is a derived daily series, not an observation - see "
    "historical_curve_method. Illustrative: charter_rate_usd_per_day is a "
    "round proxy for the daily cost of a waiting mid-size container ship, "
    "used only to express wait-days in money; it is not a quoted rate for any "
    "particular vessel."
)

PEAK_WAIT_DAYS = 7.0
RECOVERED_WAIT_DAYS = 2.0
RECOVERY_ANCHOR_DATE = date(2024, 7, 31)
PEAK_ANCHOR_KEY = "peak_berthing_delay_days"
RECOVERED_ANCHOR_KEY = "recovered_wait_days"


# --- Curated ground truth ---------------------------------------------------


def read_curated_anchors() -> tuple[list[GroundTruthAnchor], float]:
    """Load the hand-curated published scalars.

    data/ground_truth_redsea_2024.json is the human-editable source of truth
    for every published figure, quote and citation. This function is the only
    place those numbers enter the build, so the fixture can never drift from
    the curated file. Anchor order follows the file.
    """
    curated = json.loads(CURATED_GROUND_TRUTH.read_text(encoding="utf-8"))
    anchors = [
        GroundTruthAnchor(
            key=entry["key"],
            label=entry["label"],
            value=float(entry["value"]),
            unit=entry["unit"],
            provenance=SeriesProvenance(entry["provenance"]),
            source=entry["source"],
            source_date=date.fromisoformat(entry["source_date"]),
            url=entry["url"],
        )
        for entry in curated["anchors"]
    ]
    by_key = {anchor.key: anchor for anchor in anchors}
    for key, expected in (
        (PEAK_ANCHOR_KEY, PEAK_WAIT_DAYS),
        (RECOVERED_ANCHOR_KEY, RECOVERED_WAIT_DAYS),
    ):
        if key not in by_key:
            raise ValueError(f"{CURATED_GROUND_TRUTH} is missing the {key!r} anchor")
        if by_key[key].value != expected:
            raise ValueError(
                f"{key} is {by_key[key].value} in {CURATED_GROUND_TRUTH} but the wait "
                f"curve is anchored to {expected}; update both together"
            )
    throughput = float(curated["throughput_2023_teu"]["value"])
    if throughput != PUBLISHED_2023_THROUGHPUT_TEU:
        raise ValueError(
            f"published 2023 throughput is {throughput} in {CURATED_GROUND_TRUTH} but "
            f"{PUBLISHED_2023_THROUGHPUT_TEU} in this script; update both together"
        )
    return anchors, float(curated["charter_rate_usd_per_day"]["value"])


# --- Recorded input ---------------------------------------------------------


def read_portcalls() -> dict[date, int]:
    """Recorded daily container port calls for Singapore, straight from the CSV."""
    calls: dict[date, int] = {}
    with RAW_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            day = date.fromisoformat(row["date"])
            if day in calls:
                raise ValueError(f"duplicate row for {day} in {RAW_CSV}")
            calls[day] = int(row["portcalls_container"])
    if not calls:
        raise ValueError(f"{RAW_CSV} contains no rows")
    return calls


def window_days(window: DateWindow) -> list[date]:
    span = (window.end - window.start).days
    return [window.start + timedelta(days=offset) for offset in range(span + 1)]


def require_coverage(calls: dict[date, int], window: DateWindow) -> list[date]:
    days = window_days(window)
    missing = [day for day in days if day not in calls]
    if missing:
        raise ValueError(
            f"{RAW_CSV} is missing {len(missing)} day(s) in {window.label}, "
            f"first {missing[0]}; re-run scripts/fetch_portwatch.py"
        )
    return days


# --- Synthesis fitted on the calibration window -----------------------------


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def fit_size_scale(shapes_2023: list[float]) -> float:
    """Scale factor turning lognormal shape factors into TEU per call.

    Fitted on 2023 draws only, then refined once so the post-clamp mean still
    reproduces the published 2023 throughput.
    """
    target_mean = PUBLISHED_2023_THROUGHPUT_TEU / len(shapes_2023)
    scale = target_mean / (sum(shapes_2023) / len(shapes_2023))
    for _ in range(2):
        clamped = [_clamp(shape * scale, MIN_TEU, MAX_TEU) for shape in shapes_2023]
        scale *= target_mean / (sum(clamped) / len(clamped))
    return scale


def day_of_week_factors(calls: dict[date, int], days: list[date]) -> list[float]:
    """Mean calls per weekday over the given days, relative to their overall mean."""
    totals: dict[int, list[int]] = defaultdict(list)
    for day in days:
        totals[day.weekday()].append(calls[day])
    overall = sum(calls[day] for day in days) / len(days)
    return [sum(totals[weekday]) / len(totals[weekday]) / overall for weekday in range(7)]


def hour_weights(dow_factor: float) -> list[float]:
    exponent = 1.0 + BUNCHING_STRENGTH * (dow_factor - 1.0)
    return [weight**exponent for weight in HOURLY_WEIGHTS]


def build_day(
    day: date,
    portcalls: int,
    shapes: list[float],
    size_scale: float,
    dow_factors: list[float],
    share_rng: random.Random,
    time_rng: random.Random,
) -> ArrivalDay:
    weights = hour_weights(dow_factors[day.weekday()])
    hours = time_rng.choices(range(24), weights=weights, k=portcalls)
    seconds = [hour * 3600 + time_rng.randrange(3600) for hour in hours]
    midnight = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    arrivals: list[VesselArrival] = []
    for index, (offset, shape) in enumerate(sorted(zip(seconds, shapes, strict=True)), start=1):
        teu = _clamp(shape * size_scale, MIN_TEU, MAX_TEU)
        share = _clamp(
            share_rng.gauss(CONNECTION_SHARE_MEAN, CONNECTION_SHARE_SD),
            CONNECTION_SHARE_MIN,
            CONNECTION_SHARE_MAX,
        )
        arrivals.append(
            VesselArrival(
                vessel_id=f"SGSIN-{day.isoformat()}-{index:03d}",
                arrival=midnight + timedelta(seconds=offset),
                teu=round(teu, 1),
                connection_teu=round(teu * share, 1),
            )
        )
    return ArrivalDay(date=day, portcalls_container=portcalls, arrivals=arrivals)


def build_arrivals(calls: dict[date, int]) -> ArrivalStreamFixture:
    calibration_days = require_coverage(calls, CALIBRATION_WINDOW)
    blind_days = require_coverage(calls, BLIND_WINDOW)
    overlap = set(calibration_days) & set(blind_days)
    if overlap:
        raise ValueError(f"calibration and blind slices overlap on {sorted(overlap)[:3]}")

    size_rng = random.Random(SEED)
    share_rng = random.Random(SEED + 1)
    time_rng = random.Random(SEED + 2)

    # Draw every calibration shape factor first, so the scale can be fitted on
    # 2023 before a single arrival object exists, and so no blind-window draw
    # can influence it.
    calibration_shapes = {
        day: [size_rng.lognormvariate(0.0, SIZE_SIGMA) for _ in range(calls[day])]
        for day in calibration_days
    }
    shapes_2023 = [
        shape
        for day in calibration_days
        if day.year == BASELINE_YEAR
        for shape in calibration_shapes[day]
    ]
    size_scale = fit_size_scale(shapes_2023)
    dow_factors = day_of_week_factors(calls, calibration_days)

    calibration = [
        build_day(
            day,
            calls[day],
            calibration_shapes[day],
            size_scale,
            dow_factors,
            share_rng,
            time_rng,
        )
        for day in calibration_days
    ]
    blind = [
        build_day(
            day,
            calls[day],
            [size_rng.lognormvariate(0.0, SIZE_SIGMA) for _ in range(calls[day])],
            size_scale,
            dow_factors,
            share_rng,
            time_rng,
        )
        for day in blind_days
    ]

    return ArrivalStreamFixture(
        seed=SEED,
        source=SOURCE,
        source_url=SOURCE_URL,
        generated_by=GENERATED_BY,
        calibration=CalibrationSlice(window=CALIBRATION_WINDOW, days=calibration),
        blind=BlindSlice(window=BLIND_WINDOW, days=blind),
        synthesis_notice=SYNTHESIS_NOTICE,
    )


# --- Reconstructed historical wait curve ------------------------------------


def seasonal_residuals(calls: dict[date, int]) -> dict[date, float]:
    """Recorded daily calls divided by their 2023 seasonal baseline.

    The baseline is the 2023 mean daily call count times a calendar-month
    index times a day-of-week index, all computed from 2023 only. Dividing it
    out leaves the day-to-day irregularity of arrivals, which is the quantity
    the wait reconstruction is built on.
    """
    year_days = [day for day in calls if day.year == BASELINE_YEAR]
    if not year_days:
        raise ValueError(f"{RAW_CSV} has no {BASELINE_YEAR} rows to build a baseline from")
    overall = sum(calls[day] for day in year_days) / len(year_days)

    by_month: dict[int, list[int]] = defaultdict(list)
    by_weekday: dict[int, list[int]] = defaultdict(list)
    for day in year_days:
        by_month[day.month].append(calls[day])
        by_weekday[day.weekday()].append(calls[day])
    month_index = {
        month: (sum(values) / len(values)) / overall for month, values in by_month.items()
    }
    weekday_index = {
        weekday: (sum(values) / len(values)) / overall for weekday, values in by_weekday.items()
    }
    return {
        day: count / (overall * month_index[day.month] * weekday_index[day.weekday()])
        for day, count in calls.items()
    }


def _coefficient_of_variation(values: list[float]) -> float:
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance) / mean


def _smooth(series: list[float]) -> list[float]:
    half = SMOOTHING_WINDOW_DAYS // 2
    smoothed: list[float] = []
    for index in range(len(series)):
        low = max(0, index - half)
        high = min(len(series), index + half + 1)
        smoothed.append(sum(series[low:high]) / (high - low))
    return smoothed


def build_wait_curve(calls: dict[date, int]) -> list[HistoricalWaitPoint]:
    days = require_coverage(calls, BLIND_WINDOW)
    residuals = seasonal_residuals(calls)

    proxy: list[float] = []
    for day in days:
        window = [day - timedelta(days=back) for back in range(DISPERSION_WINDOW_DAYS)]
        missing = [entry for entry in window if entry not in residuals]
        if missing:
            raise ValueError(
                f"{RAW_CSV} does not reach back {DISPERSION_WINDOW_DAYS} days before "
                f"{days[0]}; re-run scripts/fetch_portwatch.py with an earlier --start-year"
            )
        proxy.append(_coefficient_of_variation([residuals[entry] for entry in window]))
    smoothed = _smooth(proxy)

    peak = max(smoothed)
    anchor = smoothed[days.index(RECOVERY_ANCHOR_DATE)]
    if peak <= anchor:
        raise ValueError(
            "congestion proxy does not peak above its 2024-07-31 level; the affine "
            "anchoring in HISTORICAL_CURVE_METHOD cannot be applied to this data"
        )
    slope = (PEAK_WAIT_DAYS - RECOVERED_WAIT_DAYS) / (peak - anchor)
    return [
        HistoricalWaitPoint(
            date=day,
            wait_days=round(max(0.0, RECOVERED_WAIT_DAYS + slope * (value - anchor)), 4),
        )
        for day, value in zip(days, smoothed, strict=True)
    ]


def build_ground_truth(calls: dict[date, int]) -> GroundTruthFixture:
    anchors, charter_rate = read_curated_anchors()
    return GroundTruthFixture(
        anchors=anchors,
        historical_wait_curve=build_wait_curve(calls),
        historical_curve_provenance=SeriesProvenance.RECONSTRUCTED,
        historical_curve_method=HISTORICAL_CURVE_METHOD,
        charter_rate_usd_per_day=charter_rate,
        notice=GROUND_TRUTH_NOTICE,
    )


# --- Output -----------------------------------------------------------------


def render(model: ArrivalStreamFixture | GroundTruthFixture | FixtureManifest) -> str:
    return json.dumps(model.model_dump(mode="json"), indent=2) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(fixtures_dir: Path) -> FixtureManifest:
    """Hash the bytes as written, so the manifest is always generated last."""
    return FixtureManifest(
        hashes={
            "data/raw/portwatch_singapore.csv": _sha256(RAW_CSV),
            "fixtures/crisis_arrivals.json": _sha256(fixtures_dir / ARRIVALS_PATH.name),
            "fixtures/crisis_ground_truth.json": _sha256(fixtures_dir / GROUND_TRUTH_PATH.name),
        },
        generated_by=GENERATED_BY,
    )


def build_all(fixtures_dir: Path) -> None:
    calls = read_portcalls()
    _write(fixtures_dir / ARRIVALS_PATH.name, render(build_arrivals(calls)))
    _write(fixtures_dir / GROUND_TRUTH_PATH.name, render(build_ground_truth(calls)))
    _write(fixtures_dir / MANIFEST_PATH.name, render(build_manifest(fixtures_dir)))


def main() -> None:
    build_all(FIXTURES)
    arrivals = json.loads(ARRIVALS_PATH.read_text(encoding="utf-8"))
    calibration_calls = sum(day["portcalls_container"] for day in arrivals["calibration"]["days"])
    blind_calls = sum(day["portcalls_container"] for day in arrivals["blind"]["days"])
    print(f"wrote {ARRIVALS_PATH} ({calibration_calls} calibration calls, {blind_calls} blind)")
    print(f"wrote {GROUND_TRUTH_PATH}")
    print(f"wrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
