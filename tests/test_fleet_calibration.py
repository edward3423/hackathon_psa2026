"""Calibration on the pre-crisis window only (PRD 9.27)."""

from typing import cast

import pytest
from fleet_world import make_blind_slice, make_calibration_slice, make_world_config

from cascade.contracts import CalibrationSlice
from cascade.engine.fleet import calibrate, erlang_c_wait_days
from cascade.engine.fleet.calibrate import HEALTHY_WAIT_DAYS, THROUGHPUT_TOLERANCE_PCT


def test_calibration_on_a_healthy_window_passes() -> None:
    report = calibrate(make_calibration_slice(), make_world_config())

    assert report.passed, report.notes
    assert abs(report.throughput_error_pct) <= THROUGHPUT_TOLERANCE_PCT
    assert report.simulated_mean_wait_days < HEALTHY_WAIT_DAYS
    assert 0.3 <= report.utilisation <= 0.92
    assert report.effective_berths > 0
    assert report.fitted.efficiency > 0


def test_erlang_c_cross_check_bounds_the_simulated_wait() -> None:
    """M/M/c is the pessimistic reference, and both figures say 'healthy'.

    Erlang-C assumes exponential service times. Real call sizes here are
    lognormal and far less variable, so the closed form over-predicts the
    wait; the useful cross-check is that it bounds the simulation from above
    and that both land well inside a healthy port's range.
    """
    report = calibrate(make_calibration_slice(), make_world_config())

    assert 0.0 <= report.simulated_mean_wait_days <= report.erlang_c_wait_days
    assert report.erlang_c_wait_days < HEALTHY_WAIT_DAYS


def test_erlang_c_is_infinite_above_capacity() -> None:
    assert erlang_c_wait_days(20.0, 0.25, 4) == float("inf")
    assert erlang_c_wait_days(0.0, 0.25, 4) == 0.0


def test_calibrate_rejects_blind_window_data_at_runtime() -> None:
    blind = make_blind_slice()
    with pytest.raises(TypeError, match="CalibrationSlice"):
        # A BlindSlice is a type error for mypy; this is the runtime guard.
        calibrate(cast(CalibrationSlice, blind), make_world_config())


def test_calibrate_rejects_an_empty_window() -> None:
    empty = CalibrationSlice(window=make_calibration_slice().window, days=[])
    with pytest.raises(ValueError, match="empty window"):
        calibrate(empty, make_world_config())


def test_report_is_deterministic_for_a_fixed_seed() -> None:
    world = make_world_config()
    first = calibrate(make_calibration_slice(), world)
    second = calibrate(make_calibration_slice(), world)
    assert first.model_dump() == second.model_dump()
