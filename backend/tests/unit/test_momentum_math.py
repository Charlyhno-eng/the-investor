"""Numerical invariants for the custom, descriptive momentum score."""

import math
from datetime import date, timedelta

import pytest

from investor.assets.momentum import analyze, months_before

AS_OF = date(2026, 11, 9)


def series(slope=0.3, noise=0):
    start = months_before(AS_OF, 36)
    return [
        (
            start + timedelta(days=i),
            100 * math.exp(slope * i / 365.25 + noise * math.sin(i)),
        )
        for i in range((AS_OF - start).days + 1)
    ]


def test_calendar_months_clamp_end_of_month_and_leap_year():
    assert months_before(date(2024, 3, 31), 1) == date(2024, 2, 29)
    assert months_before(date(2025, 3, 31), 1) == date(2025, 2, 28)
    assert months_before(date(2024, 2, 29), 24) == date(2022, 2, 28)


def test_exact_exponential_regression_and_relative_strength():
    points = series()
    reference = dict(series(0.1))
    h = analyze(points, reference, AS_OF, 12)
    assert h["start"] == "2025-11-09"
    assert h["end"] == "2026-10-09"
    assert h["slope"] == pytest.approx(0.3)
    assert h["annual_trend"] == pytest.approx(math.expm1(0.3))
    assert h["r2"] == pytest.approx(1)
    assert h["sigma"] == pytest.approx(0, abs=1e-12)
    duration = (date(2026, 10, 9) - date(2025, 11, 9)).days / 365.25
    assert h["relative_performance"] == pytest.approx(math.expm1(0.2 * duration))
    expected = 50 + 50 * (0.7 * math.tanh(1) + 0.3 * math.tanh(1))
    assert h["score"] == pytest.approx(expected)
    assert max(abs(p["residual"]) for p in h["rows"]) < 1e-12


def test_last_month_crash_is_excluded_from_all_horizons():
    points = series()
    reference = dict(series(0.1))
    crash = [(d, v * 0.1 if d > months_before(AS_OF, 1) else v) for d, v in points]
    for months in (6, 12, 36):
        assert analyze(crash, reference, AS_OF, months)["score"] == pytest.approx(
            analyze(points, reference, AS_OF, months)["score"]
        )


def test_declining_flat_and_noisy_series():
    reference = dict(series(0))
    falling = analyze(series(-0.3), reference, AS_OF, 12)
    flat = analyze(series(0), reference, AS_OF, 12)
    clean = analyze(series(), reference, AS_OF, 12)
    noisy = analyze(series(noise=0.15), reference, AS_OF, 12)
    assert falling["r2"] == pytest.approx(1)
    assert falling["score"] < 50
    assert flat["score"] == 50
    assert noisy["sigma"] > clean["sigma"]
    assert 50 < noisy["score"] < clean["score"] <= 100


def test_old_rally_can_coexist_with_negative_short_term_momentum():
    points = [
        (d, v if i < 730 else 100 * math.exp(2.4 - 0.4 * (i - 730) / 365.25))
        for i, (d, v) in enumerate(series(1.2))
    ]
    reference = dict(series(0))
    long = analyze(points, reference, AS_OF, 36)
    short = analyze(points, reference, AS_OF, 6)
    assert long["performance"] > 1
    assert short["performance"] < 0
    assert short["score"] < 50


@pytest.mark.parametrize("kind", ["short", "gap", "reference", "negative"])
def test_missing_invalid_and_discontinuous_history_is_not_scored(kind):
    points = series()
    reference = dict(series(0.1))
    if kind == "short":
        points = points[400:]
    elif kind == "gap":
        points = points[:100] + points[130:]
    elif kind == "reference":
        reference = {}
    else:
        points[100] = (points[100][0], -1)
    assert "error" in analyze(points, reference, AS_OF, 36)


def test_long_exchange_holiday_remains_eligible():
    points = series()
    # A 12-day gap between shared sessions is normal around some exchange holidays.
    points = points[:200] + points[211:]
    result = analyze(points, dict(series(0.1)), AS_OF, 36)
    assert "score" in result
