"""Causality, month-close convention and integer execution for research rules."""

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import study_sp500_published_rules as study  # noqa: E402


def sample():
    dates = [date(2016, 1, 1) + timedelta(days=i) for i in range(2500)]
    days = [d.isoformat() for d in dates if d.weekday() < 5]
    p = 100 * np.exp(
        np.cumsum(np.random.default_rng(71).normal(0.0004, 0.01, len(days)))
    )
    return days, p


def test_monthly_signal_matches_completed_month_closes():
    days, p = sample()
    cs = study.grid()
    weights = study.monthly_weights(days, p, cs)
    for i in [400, 900, 1300]:
        ends = [k for k in range(i) if days[k][:7] != days[k + 1][:7]]
        values = p[ends]
        assert weights[0, i] == float(values[-1] > values[-10:].mean())
        assert weights[3, i] == float(values[-1] > values[-13])
    # Initial incomplete month cannot create a signal.
    assert np.all(weights[:, :190] == 0)


@pytest.mark.parametrize("delay", [1, 2])
def test_future_prices_and_dates_cannot_change_executed_history(delay):
    days, p = sample()
    cs = study.grid()
    period = [days[600], days[-1]]
    full, _ = study.tactical(days, p, cs, period, delay=delay)
    cut, _ = study.tactical(
        days[:1200], p[:1200], cs, [days[600], days[1199]], delay=delay
    )
    np.testing.assert_allclose(full[:600], cut, rtol=0, atol=1e-9)
    changed = p.copy()
    changed[1200:] *= 10
    future, _ = study.tactical(days, changed, cs, period, delay=delay)
    np.testing.assert_allclose(full[:600], future[:600], rtol=0, atol=1e-9)


def test_next_close_gap_whole_units_fees_and_independent_budget():
    days, p = sample()
    p = np.linspace(50, 100, len(p))
    lo = next(i for i in range(800, 1000) if days[i][8:10] == "10")
    p[lo + 1] = 200
    c = dict(family="sma10", active=0.65)
    curve, fees = study.tactical(days, p, [c], [days[lo], days[lo + 1]])
    units = np.floor(3500 / (200 * 1.0012))
    expected = units * 200 * 0.0012
    assert fees[0] == pytest.approx(expected)
    np.testing.assert_allclose(curve[:, 0], [3500, 3500 - expected])


def test_january_prices_do_not_change_december_signal():
    days, p = sample()
    cs = study.grid()
    i = next(i for i in range(800, 1200) if days[i][:7] != days[i - 1][:7])
    before = study.monthly_weights(days, p, cs)
    changed = p.copy()
    changed[i:] *= 100
    after = study.monthly_weights(days, changed, cs)
    np.testing.assert_array_equal(before[:, : i + 1], after[:, : i + 1])
