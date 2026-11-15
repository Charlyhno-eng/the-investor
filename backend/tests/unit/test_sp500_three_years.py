"""Verify the research ledgers, historical state replay and decision timing."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import study_sp500_next_iteration as previous  # noqa: E402
import study_sp500_three_years as study  # noqa: E402


def sample():
    days = [
        "2020-01-30",
        "2020-01-31",
        "2020-02-03",
        "2020-02-04",
        "2020-03-02",
        "2020-03-03",
    ]
    prices = np.array([100.0, 105.0, 110.0, 115.0, 120.0, 125.0])
    slow = np.array([-0.5, -0.2, 0.1, 0.2, 0.3, 0.4])
    features = (
        {60: (slow, slow), 18: (np.full(6, 2.0), slow)},
        {m: prices - 1 for m in [50, 100, 200]},
        np.ones(6),
    )
    return days, prices, features


@pytest.mark.parametrize("whole", [True, False])
@pytest.mark.parametrize("delay", [1, 2])
@pytest.mark.parametrize("fee", [0.005, 0.01])
def test_baseline_matches_independent_v3_books(whole, delay, fee):
    days, prices, features = sample()
    kwargs = dict(whole=whole, delay=delay, fee=fee, keep_curve=True)
    a = study.simulate(
        days, prices, prices, features, [study.BASE], [days[0], days[-1]], **kwargs
    )
    b = previous.simulate(
        days,
        prices,
        prices,
        features,
        [{**previous.BASE, "recovery": "rebound0"}],
        [days[0], days[-1]],
        **kwargs,
    )
    np.testing.assert_allclose(a["curve"], b["curve"], atol=1e-9)
    assert a["metrics"][0]["fees"] == pytest.approx(b["metrics"][0]["fees"])


def test_replay_initializes_state_without_prior_profit_or_future_prices():
    days, prices, features = sample()
    period = [days[3], days[-1]]
    configs = [study.BASE, {**study.BASE, "warm": True}]
    result = study.simulate(
        days, prices, prices, features, configs, period, keep_curve=True
    )
    assert result["curve"][0] == [10000, 10000]
    # February crossing was before the test. Warm target buys next close at 120,
    # with 7500 initial slow capital, no pre-start gains and no free ETF holdings.
    warm_units = result["trace"][0]["units"][1]
    assert warm_units == [62, 5]
    assert result["trace"][0]["state"] == [[False, False], [True, False]]
    expected_fee = sum(warm_units) * 120 * 0.005
    assert result["curve"][1][1] == pytest.approx(10000 - expected_fee)
    changed = prices.copy()
    changed[-1] *= 10
    other = study.simulate(
        days, changed, changed, features, configs, period, keep_curve=True
    )
    np.testing.assert_allclose(
        np.array(result["curve"])[:-1], np.array(other["curve"])[:-1]
    )
    assert other["trace"][0] == result["trace"][0]


def test_monthly_cross_catches_midmonth_recovery_but_waits_for_next_close():
    days, prices, features = sample()
    # First monthly decision in February is negative, crossing occurs later;
    # March sees a positive prior daily score but a negative prior monthly one.
    features[0][60][0][:] = [-0.5, -0.4, -0.2, 0.1, 0.2, 0.3]
    configs = [study.BASE, {**study.BASE, "entry": "monthly_cross"}]
    result = study.simulate(
        days, prices, prices, features, configs, [days[0], days[-1]], keep_curve=True
    )
    curve = np.array(result["curve"])
    np.testing.assert_allclose(curve[:-1, 0], curve[:-1, 1])
    assert result["trace"][-1]["signal"] == days[-2]
    assert result["trace"][-1]["execution"] == days[-1]
    assert result["trace"][-1]["state"] == [[False, False], [True, False]]


def test_refinement_budgets_and_floor_pay_fees_from_each_sleeve():
    days, prices, features = sample()
    result = study.simulate(
        days,
        prices,
        prices,
        features,
        [{**study.BASE, "slow_share": 0.6, "floor": 0.1}],
        [days[0], days[-1]],
        keep_curve=True,
    )
    assert result["trace"][0]["units"] == [[5, 3]]
    np.testing.assert_allclose(
        result["trace"][0]["cash"], [[6000 - 5 * 105 * 1.005, 4000 - 3 * 105 * 1.005]]
    )


def test_refinement_guard_trades_next_close_and_pays_for_reentry():
    days, prices, features = sample()
    features[1][100][:] = prices + 1
    features[2][:] = -0.1
    features[2][4:] = 0.1
    config = {**study.BASE, "warm": True, "guard_ma": 100, "guard_cap": 0.1}
    result = study.simulate(
        days,
        prices,
        prices,
        features,
        [config],
        [days[3], days[-1]],
        keep_curve=True,
    )
    first, second = result["trace"]
    assert first["signal"] == days[3]
    assert first["execution"] == days[4]
    assert first["units"] == [[6, 2]]
    assert first["state"] == [[True, False]]  # Guard does not erase slow state.
    assert second["units"][0][0] > first["units"][0][0]
    assert result["metrics"][0]["fees"] > 8 * 120 * 0.005
    changed = prices.copy()
    changed[-1] *= 2
    other = study.simulate(
        days, changed, changed, features, [config], [days[3], days[-1]], keep_curve=True
    )
    assert other["trace"][0] == first


def test_refinement_defensive_exit_and_cadence_preserve_signal_delay():
    days, prices, features = sample()
    features[0][60][0][:] = 2
    features[0][18][0][:] = [-1, -0.6, 1.6, 1.8, 1.9, 2]
    daily = {**study.BASE, "defensive_entry": -0.75, "defensive_step": 1}
    result = study.simulate(
        days,
        prices,
        prices,
        features,
        [daily, {**daily, "defensive_exit": 1.75}, {**daily, "defensive_step": 10}],
        [days[0], days[-1]],
        keep_curve=True,
    )
    trace = result["trace"]
    assert trace[1]["state"] == [[False, True], [False, True], [False, False]]
    assert trace[2]["state"] == [[False, False], [False, True], [False, False]]
    assert trace[2]["signal"] == days[2]
    assert trace[2]["execution"] == days[3]
    assert trace[3]["state"] == [[False, False], [False, False], [False, False]]
