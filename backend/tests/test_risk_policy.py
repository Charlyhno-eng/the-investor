"""Execution/risk properties, independently known prices and event times."""

from datetime import date, timedelta

import numpy as np
import pytest
from investor.analysis.metrics import equity
from investor.analysis.schemas import AnalysisRequest
from investor.analysis.strategy import POLICIES, Policy, simulate, trend_filter


@pytest.fixture
def analysis_request():
    return AnalysisRequest(
        train_start="2010-01-01",
        train_end="2015-01-01",
        test_start="2016-01-01",
        test_end="2025-01-01",
        fee_bps=0,
    )


def run(analysis_request, returns, *, policy=None, p=None, start="2023-12-25"):
    days = [
        (date.fromisoformat(start) + timedelta(days=i)).isoformat()
        for i in range(len(returns))
    ]
    probs = (
        np.column_stack([p, 1 - np.asarray(p)])
        if p is not None
        else np.tile([1.0, 0.0], (len(returns), 1))
    )
    events = []
    net, benchmark, trades, positions = simulate(
        np.log1p(returns),
        probs,
        days,
        0,
        analysis_request,
        365,
        policy=policy or POLICIES["daily_guard"],
        risk_events=events,
    )
    return net, benchmark, trades, positions, events


def test_stop_uses_equity_peak_and_liquidates_next_close(analysis_request):
    net, _, trades, positions, events = run(
        analysis_request, [0, 0, 0.25, -0.1, 0, 1, 1]
    )
    assert events == [
        {
            "triggered_at": "2023-12-28",
            "executed_at": "2023-12-29",
            "drawdown_at_trigger": pytest.approx(0.1),
            "already_in_cash": False,
        }
    ]
    assert [(t["side"], t["reason"]) for t in trades] == [
        ("buy", "signal"),
        ("sell", "drawdown_stop"),
    ]
    assert positions == [0, 1, 1, 1, 0, 0, 0]
    assert equity(net)[-1] == pytest.approx(1.25 * 0.9)


def test_gap_and_execution_lag_are_never_clipped_to_ten_percent(analysis_request):
    net, _, trades, _, events = run(analysis_request, [0, 0, -0.15, -0.1, 2, 2])
    assert events[0]["drawdown_at_trigger"] == pytest.approx(0.15)
    assert trades[1]["time"] == "2023-12-28"
    assert equity(net)[-1] == pytest.approx(0.85 * 0.9)
    assert 1 - equity(net).min() == pytest.approx(0.235)


def test_stop_includes_fees_and_has_no_calendar_reset(analysis_request):
    analysis_request = analysis_request.model_copy(update={"fee_bps": 500})
    net, _, trades, _, events = run(
        analysis_request, [0, 0, -0.06, 0, 2, 2, 2, 2, 2, 2], start="2023-12-28"
    )
    assert events[0]["drawdown_at_trigger"] == pytest.approx(1 - 0.95 * 0.94)
    assert len(trades) == 2
    assert trades[-1]["reason"] == "drawdown_stop"
    assert equity(net)[-1] == pytest.approx(0.95 * 0.94 * 0.95)
    assert net[-1] == 0  # No reentry after New Year or bullish recovery.


def test_emergency_exit_does_not_wait_for_weekly_review(analysis_request):
    _, _, trades, _, events = run(
        analysis_request, [0, 0, -0.11, 0, 0, 0, 0, 0], policy=POLICIES["weekly_hmm"]
    )
    assert events[0]["triggered_at"] == "2023-12-27"
    assert trades[-1]["time"] == "2023-12-28"  # Thursday, not next Monday.


def test_weekly_review_and_hysteresis_suppress_daily_churn(analysis_request):
    p = np.array([0.9] * 30)
    p[[1, 3, 8, 10, 15, 17, 22, 24]] = 0.1
    weekly = run(analysis_request, np.zeros(30), p=p, policy=POLICIES["weekly_hmm"])
    daily = run(analysis_request, np.zeros(30), p=p, policy=POLICIES["daily_original"])
    assert len(weekly[2]) == 2
    assert len(daily[2]) > 10
    assert weekly[2][-1]["reason"] == "final_liquidation"


def test_weekly_exit_requires_distinct_threshold(analysis_request):
    # Monday observations: .9 enters, .5 holds, .1 exits, .5 stays out.
    p = np.repeat([0.9, 0.5, 0.1, 0.5], 7)
    _, _, trades, _, _ = run(
        analysis_request, np.zeros(28), p=p, policy=POLICIES["weekly_hmm"]
    )
    assert [t["time"] for t in trades] == ["2023-12-26", "2024-01-09"]


def test_week_review_uses_first_observation_after_holiday(analysis_request):
    dates = ["2024-01-05", "2024-01-09", "2024-01-10", "2024-01-11"]
    probs = np.array([[0.0, 1.0], [1.0, 0.0], [1.0, 0.0], [1.0, 0.0]])
    _, _, trades, _ = simulate(np.zeros(4), probs, dates, 0, analysis_request, 252)
    assert [t["time"] for t in trades] == ["2024-01-10", "2024-01-11"]


def test_fee_on_each_order_is_symmetric_without_stop(analysis_request):
    analysis_request = analysis_request.model_copy(update={"fee_bps": 100})
    net, benchmark, trades, _, _ = run(
        analysis_request, np.zeros(30), policy=POLICIES["weekly_hmm"]
    )
    assert len(trades) == 2
    assert equity(net)[-1] == pytest.approx(0.99**2)
    assert equity(benchmark)[-1] == pytest.approx(0.99**2)


def test_risk_prefix_is_unchanged_by_future_gains(analysis_request):
    returns = [0, 0, -0.11, 0, 0, 0, 0, 0]
    original = run(analysis_request, returns)
    revised = run(analysis_request, returns + [10, 10, 10])
    assert original[2:] == revised[2:3] + (revised[3][:8], revised[4])
    np.testing.assert_allclose(original[0], revised[0][:8])


def test_trailing_trend_has_known_values_and_no_future_dependency():
    values = np.array([1.0, 2.0, 3.0, 1.0, 5.0, 2.0])
    np.testing.assert_array_equal(
        trend_filter(values, 3), [False, False, True, False, True, False]
    )
    np.testing.assert_array_equal(
        trend_filter(values[:4], 3), trend_filter(values, 3)[:4]
    )


def test_trend_policy_requires_causal_prices(analysis_request):
    with pytest.raises(ValueError, match="historique causal"):
        run(analysis_request, np.zeros(30), policy=Policy(trend_window=200))
