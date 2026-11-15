"""Bootstrap sequencing and chronological comparison without user DB access."""

from datetime import date

import numpy as np
import pytest
from sp500_support import historical_rows

from investor.portfolio import etf_switch
from investor.portfolio.sp500_simulation import (
    Sp500SimulationRequest,
    future_sessions,
    sampled_returns,
    simulate_history,
)


def test_seed_reproduction_and_real_tail_blocks_not_clipped():
    returns = np.r_[np.full(100, 0.001), np.full(30, -0.02), np.full(100, 0.001)]
    a = sampled_returns(returns, 1300, 42)
    np.testing.assert_array_equal(a, sampled_returns(returns, 1300, 42))
    np.testing.assert_array_equal(a[:100], sampled_returns(returns, 100, 42))
    assert not np.array_equal(a, sampled_returns(returns, 1300, 43))
    # Existing crash sequence is preserved by some draws, never forced in all.
    falls = []
    for seed in range(60):
        path = np.exp(np.r_[0, np.cumsum(sampled_returns(returns, 260, seed))])
        falls.append((path / np.maximum.accumulate(path) - 1).min() <= -0.3)
    assert 0 < sum(falls) < len(falls)
    assert np.any(a < -0.019)


def test_weekday_calendar_and_leap_year_horizon():
    dates = future_sessions(date(2024, 2, 29), 1)
    assert dates[0] == "2024-03-01"
    assert dates[-1] == "2025-02-28"
    assert all(date.fromisoformat(d).weekday() < 5 for d in dates)


@pytest.mark.parametrize("whole", [True, False])
def test_comparison_reproducible_same_path_full_current_policy_and_entry_fees(whole):
    rows = historical_rows()
    request = Sp500SimulationRequest(years=1, seed=42, whole_shares=whole)
    result = simulate_history(rows, request)
    assert result["status"] == "ready", result
    assert result == simulate_history(rows, request)
    comparison = result["comparison"]
    assert comparison["protocol"]["etf_switch"] == etf_switch.protocol()
    assert comparison["start"] == rows[-1][0]
    assert comparison["equity"][0] == dict(
        time=rows[-1][0], benchmark=100, strategy=100
    )
    assert set(comparison["metrics"]) == {"benchmark", "strategy"}
    assert set(comparison["equity"][1]) == {"time", "benchmark", "strategy"}
    assert comparison["metrics"]["benchmark"]["cost_eur"] > 0
    assert comparison["metrics"]["strategy"]["cost_eur"] > 0
    assert all(
        t["signal"] >= rows[-1][0] and t["execution"] > t["signal"]
        for t in comparison["transactions"]
    )
    assert comparison["final_portfolio"]["cash"] >= 0
    assert comparison["final_portfolio"]["initial_capital"] == 10000
    assert all(
        np.isfinite(v)
        for m in comparison["metrics"].values()
        for v in m.values()
        if v is not None
    )
    if whole:
        assert all(isinstance(t["quantity"], int) for t in comparison["transactions"])
    else:
        first = comparison["equity"][1]["benchmark"]
        assert first == pytest.approx(100 / 1.0012)
    different = simulate_history(rows, request.model_copy(update={"seed": 43}))
    assert different["comparison"]["equity"] != comparison["equity"]


def test_insufficient_and_invalid_source_do_not_fabricate_history():
    request = Sp500SimulationRequest(seed=1)
    assert simulate_history([], request)["status"] == "insufficient"
    rows = historical_rows()
    invalid = list(rows)
    invalid[-1] = (rows[-1][0], -1, 100)
    assert simulate_history(invalid, request)["status"] == "insufficient"
    invalid[-1] = (rows[-1][0], rows[-1][1], None)
    assert simulate_history(invalid, request)["status"] == "insufficient"


def test_unseeded_requests_receive_distinct_replayable_ids(monkeypatch):
    from investor.portfolio import sp500_simulation as module

    seeds = iter([71, 72])
    monkeypatch.setattr(module.secrets, "randbits", lambda bits: next(seeds))
    first = simulate_history(historical_rows(), Sp500SimulationRequest(years=1))
    second = simulate_history(historical_rows(), Sp500SimulationRequest(years=1))
    assert first["simulation"]["seed"] == 71
    assert second["simulation"]["seed"] == 72
    assert first["comparison"]["equity"] != second["comparison"]["equity"]


def test_paired_summary_direction_ties_missing_metrics_and_means():
    from investor.portfolio.sp500_simulation import BatchSummary

    summary = BatchSummary()
    for benchmark, strategy in [
        (
            {"cagr": 0.1, "max_drawdown": -0.3, "volatility": 0.2, "sharpe": 1},
            {"cagr": 0.2, "max_drawdown": -0.1, "volatility": 0.1, "sharpe": 2},
        ),
        (
            {"cagr": 0.2, "max_drawdown": -0.1, "volatility": 0.1, "sharpe": None},
            {"cagr": 0.1, "max_drawdown": -0.3, "volatility": 0.2, "sharpe": 1},
        ),
        (
            {"cagr": 0.1, "max_drawdown": -0.2, "volatility": 0.1, "sharpe": 1},
            {"cagr": 0.1, "max_drawdown": -0.2, "volatility": 0.1, "sharpe": 1},
        ),
    ]:
        summary.add({"metrics": {"benchmark": benchmark, "strategy": strategy}})
    result = summary.snapshot(3, 42)
    assert result["status"] == "complete"
    assert result["completed"] == 3
    for key in ("cagr", "max_drawdown", "volatility"):
        row = result["metrics"][key]
        assert (row["benchmark_wins"], row["strategy_wins"], row["ties"]) == (1, 1, 1)
        assert row["valid"] == 3
    assert result["metrics"]["cagr"]["strategy_mean"] == pytest.approx(0.4 / 3)
    sharpe = result["metrics"]["sharpe"]
    assert sharpe["valid"] == 2 and sharpe["strategy_wins"] == 1
    assert sharpe["strategy_mean"] == 1.5
    assert result["metrics"]["sortino"]["valid"] == 0
    assert result["metrics"]["sortino"]["benchmark_mean"] is None


def test_default_fees_change_only_for_sp500_and_explicit_value_wins():
    from investor.portfolio.validation import ValidationRequest

    assert (
        ValidationRequest(asset_ids=["yf-psp5.pa"], mode="etf_switch").fee_rate
        == 0.0012
    )
    assert ValidationRequest(asset_ids=["other"]).fee_rate == 0.005
    assert (
        ValidationRequest(
            asset_ids=["yf-psp5.pa"], mode="etf_switch", fee_rate=0
        ).fee_rate
        == 0
    )


def test_disconnected_batch_stops_without_starting_another_path(monkeypatch):
    import asyncio
    import json

    from investor.portfolio import sp500_simulation as simulation
    from investor.portfolio.sp500_batch import PreparedBatch

    monkeypatch.setattr(simulation, "load_simulation_history", historical_rows)
    calls = []
    real = PreparedBatch.simulate

    def run(self, seeds):
        calls.extend(seeds)
        return real(self, seeds)

    monkeypatch.setattr(PreparedBatch, "simulate", run)

    async def collect():
        snapshots = []

        async def disconnected():
            return bool(snapshots and snapshots[-1]["completed"] >= 1)

        async for line in simulation.stream_sp500_batch(
            simulation.Sp500BatchRequest(count=1000, years=1, seed=44), disconnected
        ):
            snapshots.append(json.loads(line))
        return snapshots

    snapshots = asyncio.run(collect())
    assert [s["completed"] for s in snapshots] == [0, 1]
    assert calls == [44]
