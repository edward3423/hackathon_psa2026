"""Guards on the Act 2 crisis fixtures.

These tests never touch the network. They read the committed PortWatch CSV and
the committed fixtures, and they rebuild the fixtures into a tmp_path to prove
that regeneration is byte-identical.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

from cascade.contracts import ArrivalDay, ArrivalStreamFixture, DateWindow, GroundTruthFixture
from cascade.fixtures import (
    CRISIS_ARRIVALS_FILE,
    CRISIS_GROUND_TRUTH_FILE,
    load_crisis_arrivals,
    load_crisis_ground_truth,
    load_crisis_manifest,
    sha256_of,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"

PEAK_WAIT_DAYS = 7.0
RECOVERED_WAIT_DAYS = 2.0
RECOVERY_ANCHOR_DATE = date(2024, 7, 31)
PUBLISHED_2023_THROUGHPUT_TEU = 39.01e6


def _load_builder() -> ModuleType:
    """Import scripts/build_crisis_fixture.py, which is not an installed module."""
    path = ROOT / "scripts" / "build_crisis_fixture.py"
    spec = importlib.util.spec_from_file_location("build_crisis_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Regenerate the fixtures into a scratch directory."""
    target = tmp_path_factory.mktemp("crisis-fixtures")
    _load_builder().build_all(target)
    return target


@pytest.fixture(scope="module")
def arrivals() -> ArrivalStreamFixture:
    return load_crisis_arrivals()


@pytest.fixture(scope="module")
def ground_truth() -> GroundTruthFixture:
    return load_crisis_ground_truth()


def _window_days(window: DateWindow) -> list[date]:
    span = (window.end - window.start).days
    return [window.start + timedelta(days=offset) for offset in range(span + 1)]


def _all_days(fixture: ArrivalStreamFixture) -> list[ArrivalDay]:
    return [*fixture.calibration.days, *fixture.blind.days]


@pytest.mark.parametrize("name", [CRISIS_ARRIVALS_FILE, CRISIS_GROUND_TRUTH_FILE])
def test_regeneration_is_byte_identical(rebuilt: Path, name: str) -> None:
    assert (rebuilt / name).read_bytes() == (FIXTURES / name).read_bytes()


def test_manifest_hashes_match_the_files_on_disk() -> None:
    manifest = load_crisis_manifest()
    assert manifest.hashes["fixtures/crisis_arrivals.json"] == sha256_of(CRISIS_ARRIVALS_FILE)
    assert manifest.hashes["fixtures/crisis_ground_truth.json"] == sha256_of(
        CRISIS_GROUND_TRUTH_FILE
    )


def test_manifest_pins_the_raw_snapshot() -> None:
    manifest = load_crisis_manifest()
    raw = ROOT / "data" / "raw" / "portwatch_singapore.csv"
    assert (
        manifest.hashes["data/raw/portwatch_singapore.csv"]
        == hashlib.sha256(raw.read_bytes()).hexdigest()
    )


def test_fixtures_validate_against_contracts(
    arrivals: ArrivalStreamFixture, ground_truth: GroundTruthFixture
) -> None:
    # The loaders validate on the way in; these assertions pin the shape the
    # rest of the benchmark relies on.
    assert arrivals.seed == 42
    assert "PortWatch" in arrivals.source
    assert arrivals.calibration.days and arrivals.blind.days
    assert ground_truth.anchors and ground_truth.historical_wait_curve
    assert {anchor.key for anchor in ground_truth.anchors} >= {
        "peak_berthing_delay_days",
        "recovered_wait_days",
        "port_stay_inflation_pct",
        "rehandling_increase_pct",
        "offschedule_arrivals_pct_2024",
        "offschedule_arrivals_pct_2023",
        "h1_volume_growth_pct",
        "teu_waiting_peak",
    }


def test_slices_are_disjoint(arrivals: ArrivalStreamFixture) -> None:
    calibration = {day.date for day in arrivals.calibration.days}
    blind = {day.date for day in arrivals.blind.days}
    assert not calibration & blind


def test_slices_cover_their_windows_exactly(arrivals: ArrivalStreamFixture) -> None:
    for slice_ in (arrivals.calibration, arrivals.blind):
        expected = _window_days(slice_.window)
        assert [day.date for day in slice_.days] == expected


def test_march_2024_is_in_neither_slice(arrivals: ArrivalStreamFixture) -> None:
    march = {
        day.date for day in _all_days(arrivals) if (day.date.year, day.date.month) == (2024, 3)
    }
    assert march == set()


def test_every_day_emits_one_arrival_per_recorded_port_call(
    arrivals: ArrivalStreamFixture,
) -> None:
    for day in _all_days(arrivals):
        assert len(day.arrivals) == day.portcalls_container


def test_arrival_times_stay_inside_their_own_day(arrivals: ArrivalStreamFixture) -> None:
    for day in _all_days(arrivals):
        for arrival in day.arrivals:
            assert arrival.arrival.tzinfo is not None
            assert arrival.arrival.date() == day.date
            assert isinstance(arrival.arrival, datetime)


def test_vessel_ids_are_unique_and_stable(arrivals: ArrivalStreamFixture) -> None:
    ids = [arrival.vessel_id for day in _all_days(arrivals) for arrival in day.arrivals]
    assert len(ids) == len(set(ids))
    sample = arrivals.blind.days[0]
    assert sample.arrivals[0].vessel_id == f"SGSIN-{sample.date.isoformat()}-001"


def test_connection_teu_never_exceeds_teu(arrivals: ArrivalStreamFixture) -> None:
    for day in _all_days(arrivals):
        for arrival in day.arrivals:
            assert 0.0 <= arrival.connection_teu <= arrival.teu


def test_synthesised_2023_throughput_matches_the_published_figure(
    arrivals: ArrivalStreamFixture,
) -> None:
    total = sum(
        arrival.teu
        for day in arrivals.calibration.days
        if day.date.year == 2023
        for arrival in day.arrivals
    )
    assert total == pytest.approx(PUBLISHED_2023_THROUGHPUT_TEU, rel=0.10)


def test_wait_curve_covers_the_blind_window_exactly(
    arrivals: ArrivalStreamFixture, ground_truth: GroundTruthFixture
) -> None:
    expected = _window_days(arrivals.blind.window)
    assert [point.date for point in ground_truth.historical_wait_curve] == expected


def test_wait_curve_is_anchored_to_the_recorded_scalars(
    ground_truth: GroundTruthFixture,
) -> None:
    curve = ground_truth.historical_wait_curve
    assert max(point.wait_days for point in curve) == pytest.approx(PEAK_WAIT_DAYS, abs=0.05)
    by_date = {point.date: point.wait_days for point in curve}
    assert by_date[RECOVERY_ANCHOR_DATE] <= RECOVERED_WAIT_DAYS + 1e-6


def test_wait_curve_is_labelled_a_reconstruction(ground_truth: GroundTruthFixture) -> None:
    assert ground_truth.historical_curve_provenance.value == "RECONSTRUCTED"
    assert "not measurement" in ground_truth.historical_curve_method.lower()
    assert ground_truth.charter_rate_usd_per_day > 0
    assert "illustrative" in ground_truth.notice.lower()
