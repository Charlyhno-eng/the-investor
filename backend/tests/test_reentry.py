from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pytest
from investor.analysis.metrics import equity
from investor.analysis.reentry import model_signals, simulate_reentry
from investor.analysis.schemas import AnalysisRequest


def simulate(returns, *, forecast=None, band=None, bars=None, fee=0):
    n = len(returns)
    request = AnalysisRequest(
        train_start="2010-01-01",
        train_end="2015-01-01",
        test_start="2016-01-01",
        test_end="2025-01-01",
        fee_bps=fee,
    )
    events = []
    out = simulate_reentry(
        np.log1p(returns),
        np.tile([1.0, 0.0], (n, 1)),
        [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)],
        0,
        request,
        np.full(n, 0.002) if forecast is None else np.array(forecast),
        np.zeros(n) if band is None else np.array(band),
        bars=bars,
        risk_events=events,
    )
    return (*out, events)


def test_resting_stop_sells_at_ten_percent_without_waiting_another_close():
    bars = [None, None, {"open_ratio": 1.0, "low_ratio": 0.85}, None, None]
    net, _, trades, pos, events = simulate([0, 0, -0.15, 0, 0], bars=bars)
    assert equity(net)[-1] == pytest.approx(0.9)
    assert trades[1]["reason"] == "position_stop"
    assert trades[1]["time"] == "2024-01-03"
    assert pos[2] == 0
    assert events[0]["gap"] is False
    assert events[0]["drawdown_at_trigger"] == pytest.approx(0.1)


def test_gap_executes_at_open_without_fictitious_fill_at_stop():
    bars = [None, None, {"open_ratio": 0.8, "low_ratio": 0.7}, None, None]
    net, _, _, _, events = simulate([0, 0, -0.25, 0, 0], bars=bars)
    assert equity(net)[-1] == pytest.approx(0.8)
    assert events[0]["gap"] is True
    assert events[0]["drawdown_at_trigger"] == pytest.approx(0.2)


def test_close_only_fallback_never_clips_losses():
    net, _, _, _, events = simulate([0, 0, -0.2, 0, 0])
    assert equity(net)[-1] == pytest.approx(0.8)
    assert events[0]["source"] == "close_only"
    assert events[0]["triggered_at"] == events[0]["executed_at"]


def test_entry_and_exit_fees_are_in_stop_budget():
    bars = [None, None, {"open_ratio": 1.0, "low_ratio": 0.8}, None, None]
    net, _, _, _, events = simulate([0, 0, -0.15, 0, 0], bars=bars, fee=100)
    assert equity(net)[-1] == pytest.approx(0.9)
    assert events[0]["drawdown_at_trigger"] == pytest.approx(0.1)


def test_reentry_on_fresh_model_rise_without_permanent_lock():
    net, _, trades, pos, events = simulate([0, 0, -0.1, 0.02, 0.03, 0.04, 0.05, 0])
    assert [t["side"] for t in trades] == ["buy", "sell", "buy", "sell"]
    assert trades[2]["time"] == "2024-01-05"
    assert events[0]["reentered_at"] == "2024-01-05"
    assert pos[4] == 1
    assert equity(net)[-1] == pytest.approx(0.9 * 1.04 * 1.05)


def test_no_reentry_while_model_is_bearish_even_if_prices_bounce():
    _, _, trades, _, events = simulate(
        [0, 0, -0.1, 0.1, 0.1, 0.1, 0.1],
        forecast=[0.002, 0.002, -0.002, -0.002, -0.002, -0.002, -0.002],
    )
    assert [t["side"] for t in trades] == ["buy", "sell"]
    assert events[0]["reentered_at"] is None


def test_multiple_stops_rearm_per_position_and_global_drawdown_is_real():
    bars = [None] * 10
    bars[2] = {"open_ratio": 1.0, "low_ratio": 0.8}
    bars[6] = {"open_ratio": 1.0, "low_ratio": 0.8}
    net, _, trades, _, events = simulate(
        [0, 0, -0.15, 0.02, 0, 0, -0.15, 0.01, 0, 0], bars=bars
    )
    assert len(events) == 2
    assert all(e["drawdown_at_trigger"] == pytest.approx(0.1) for e in events)
    assert equity(net)[-1] == pytest.approx(0.9**2)
    assert len([t for t in trades if t["side"] == "buy"]) == 3


def test_high_inside_stop_bar_does_not_raise_stop_before_unknown_low_order():
    # Stop fixed at previous close; adding arbitrary high data cannot alter fill.
    bars = [None, None, {"open_ratio": 1.0, "low_ratio": 0.95, "high_ratio": 2.0}, None]
    net, _, trades, _, events = simulate([0, 0, 0, 0], bars=bars)
    assert not events
    assert len(trades) == 2
    assert equity(net)[-1] == 1


def test_cost_band_ignores_small_changes_without_trade_quota():
    forecast = [
        0.003,
        -0.0001,
        0.0001,
        -0.0001,
        0.0001,
        -0.003,
        -0.003,
        0.003,
        0.003,
        0,
    ]
    _, _, trades, _, _ = simulate(np.zeros(10), forecast=forecast, band=[0.001] * 10)
    assert [t["side"] for t in trades] == ["buy", "sell", "buy", "sell"]
    assert [t["time"] for t in trades] == [
        "2024-01-02",
        "2024-01-07",
        "2024-01-09",
        "2024-01-10",
    ]


def test_forecast_uses_transition_matrix_and_costs_not_future_prices():
    model = SimpleNamespace(transmat_=np.array([[0.9, 0.1], [0.2, 0.8]]))
    probs = np.array([[1.0, 0.0], [0.0, 1.0]])
    means = np.array([0.01, -0.02])
    forecast, band = model_signals(model, probs, means, 10, 252)
    np.testing.assert_allclose(forecast, [0.007, -0.014])
    assert np.all(band > 0)
    _, zero = model_signals(model, probs, means, 0, 252)
    np.testing.assert_array_equal(zero, [0, 0])
    _, larger = model_signals(model, probs, means, 50, 252)
    assert np.all(larger > band)


def test_prefix_causality_after_stop_and_recovery():
    returns = [0, 0, -0.1, 0.02, 0.03, 0.04, 0.05, 0]
    one = simulate(returns)
    two = simulate(returns + [1.0, -0.5])
    np.testing.assert_allclose(one[0][:-1], two[0][: len(returns) - 1])
    assert one[2][:-1] == two[2][: len(one[2]) - 1]
