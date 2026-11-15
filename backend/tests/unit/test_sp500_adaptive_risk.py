"""Causality and accounting checks for the expanded research engine."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import study_sp500_adaptive_extension as research  # noqa: E402


def sample():
    days = np.busday_offset("2000-01-03", np.arange(1400)).astype(str).tolist()
    t = np.arange(len(days))
    prices = 100 * np.exp(0.0003 * t + 0.1 * np.sin(t / 51) + 0.03 * np.cos(t / 11))
    return days, prices


def test_all_signal_families_are_prefix_invariant():
    days, prices = sample()
    configs = research.grid()
    full = research.features(prices, configs)
    short = research.features(prices[:1100], configs)
    np.testing.assert_allclose(full[:, :1100], short, atol=1e-12)
    assert np.all(np.isfinite(full))
    assert np.all((full >= 0) & (full <= 1))


@pytest.mark.parametrize("whole", [True, False])
def test_constant_exposure_cash_ledger_and_delayed_execution(whole):
    days = ["2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09", "2020-01-10"]
    prices = np.array([100, 110, 120, 130, 140.0])
    config = dict(cadence=5, band=1)
    weights = np.full((1, 5), 0.6)
    r = research.ORIGINAL_SIMULATE(
        days,
        prices,
        weights,
        [config],
        days[::4],
        whole=whole,
        delay=2,
        calendar=True,
        curve=True,
    )
    quantity = 6000 / (120 * 1.003)
    if whole:
        quantity = np.floor(quantity)
    # target fraction is 60% of post-fee wealth, hence denominator1+.005*.6.
    cost = quantity * 120 * 0.005
    expected = [
        10000,
        10000,
        10000 - cost,
        10000 + quantity * 10 - cost,
        10000 + quantity * 20 - cost,
    ]
    np.testing.assert_allclose(np.array(r["curve"])[:, 0], expected, atol=1e-8)
    assert r["candidates"][0]["fees"] == pytest.approx(cost)
    assert r["orders"][0]["signal"] == days[0]
    assert r["orders"][0]["execution"] == days[2]


def test_calendar_decision_dates_do_not_shift_with_chart_start():
    days, prices = sample()
    prices[:] = 100
    config = dict(cadence=5, band=0.05)
    # Alternating weekly targets force genuine weekly transitions.
    weights = np.array([[(i // 5) % 2 for i in range(len(days))]], dtype=float)
    cases = []
    for start in [days[700], days[701]]:
        r = research.ORIGINAL_SIMULATE(
            days,
            prices,
            weights,
            [config],
            [start, days[750]],
            calendar=True,
            curve=True,
        )
        orders = [
            o for o in r["orders"] if o["instrument"] == 0 and o["signal"] > days[705]
        ]
        cases.append([o["signal"] for o in orders])
    assert cases[0] == cases[1]
    assert len(cases[0]) >= 5
    assert all(np.datetime64(d).astype(object).weekday() == 4 for d in cases[0])
