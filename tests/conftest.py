import pytest

from cascade import guardrails


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the wall-clock rate limiter out of tests.

    The API test suites fire POSTs far faster than any human, so the default
    bucket would make them order- and speed-dependent. Tests that exercise the
    limiter install their own bucket with a fake clock on top of this.
    """
    monkeypatch.setattr(guardrails, "_limiter", None)
    monkeypatch.setattr(guardrails, "_limiter_built", True)
