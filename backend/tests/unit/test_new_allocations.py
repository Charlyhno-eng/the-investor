from datetime import date, timedelta

import numpy as np
import pytest
from fastapi import HTTPException

from investor.portfolio.performance import (
    annual_equal_returns,
    comparison_data,
    optimize_weights,
)


def test_equal_allocation_drifts_and_rebalances_annually_with_both_trading_fees():
    dates = ["2024-01-01", "2024-07-01", "2025-01-01", "2025-07-01"]
    changes = np.array([[1.0, 0], [0, 0], [1.0, 0]])
    fee = 0.005
    actual = annual_equal_returns(changes, dates, fee)
    # Buy equal units with the initial fee; then only the first asset doubles.
    stake = 0.5 / (1 + fee)
    wealth = 3 * stake
    # Sell the winner and buy the loser. Net target includes both fees.
    net = wealth - fee * stake
    expected = [wealth - 1, net / wealth - 1, 0.5]
    assert actual == pytest.approx(expected)
    assert annual_equal_returns(changes, dates, 0) == pytest.approx([0.5, 0, 0.5])
    # Without the annual rebalance the last gain would have been 2/3.
    assert actual[-1] != pytest.approx(2 / 3)


@pytest.mark.parametrize("mode", ["sortino", "sharpe", "calmar"])
def test_new_ratio_objectives_match_independent_dense_search(mode):
    rng = np.random.default_rng(71)
    returns = rng.normal([0.001, 0.0005], [0.02, 0.008], (300, 2))
    weights = optimize_weights(returns, np.array([0.5, 0.5]), mode, elapsed_years=1.5)

    def score(w):
        changes = returns @ w
        if mode == "sortino":
            return changes.mean() / np.sqrt(np.mean(np.minimum(changes, 0) ** 2))
        if mode == "sharpe":
            return changes.mean() / changes.std(ddof=1)
        wealth = np.r_[1, np.cumprod(1 + changes)]
        return (wealth[-1] ** (1 / 1.5) - 1) / -np.min(
            wealth / np.maximum.accumulate(wealth) - 1
        )

    grid = np.linspace(0.03, 0.97, 2001)
    best = max(score([w, 1 - w]) for w in [0, *grid, 1])
    assert score(weights) >= best - 1e-5


def test_beta_constraint_is_exact_and_respects_locks():
    rng = np.random.default_rng(52)
    market = rng.normal(0.0004, 0.01, 500)
    returns = np.column_stack([market * 0.2, market * 1.2])
    betas = np.array([0.2, 1.2])
    for target in (0.3, 0.4, 0.5, 0.6, 0.7):
        weights = optimize_weights(
            returns,
            np.array([0.5, 0.5]),
            "beta_sharpe",
            betas=betas,
            target_beta=target,
        )
        assert weights.sum() == pytest.approx(1)
        assert betas @ weights == pytest.approx(target, abs=1e-7)
    with pytest.raises(HTTPException):
        optimize_weights(
            returns,
            np.array([0.5, 0.5]),
            "beta_sharpe",
            {0: 0.5, 1: 0.5},
            betas=betas,
            target_beta=0.5,
        )


def comparison_fixture():
    rng = np.random.default_rng(52)
    market = rng.normal(0.0004, 0.01, 500)
    dates = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(501)]
    histories = [
        dict(zip(dates, 100 * np.r_[1, np.cumprod(1 + market * beta)], strict=True))
        for beta in (0.2, 1.2, 1)
    ]
    assets = [{"id": str(i), "name": str(i), "frequency": "daily"} for i in range(2)]
    positions = [
        {
            "id": str(i),
            "name": str(i),
            "quantity": 1,
            "value": 100,
            "price": 100,
            "weight": 0.5,
        }
        for i in range(2)
    ]
    return assets, histories, positions


def test_comparison_returns_five_distinct_beta_curves_and_allocations():
    assets, histories, positions = comparison_fixture()
    result = comparison_data(
        assets, histories[:2], histories[-1], positions, 3, True, "beta_sharpe"
    )
    assert len(result["allocations"]) == 5
    assert result["unavailable"] == {}
    for digit in (3, 4, 5, 6, 7):
        key = f"beta_0{digit}"
        assert result["metrics"][key]["beta"] == pytest.approx(digit / 10, abs=1e-7)
        assert key in result["equity"][-1]
    assert result["metrics"]["benchmark"]["beta"] == 1
    # Five failures remain explicit and do not erase the two comparators.
    impossible = comparison_data(
        assets, [histories[-1]] * 2, histories[-1], positions, 3, True, "beta_sharpe"
    )
    assert len(impossible["unavailable"]) == 5
    assert impossible["allocations"] == {}
    assert set(impossible["metrics"]) == {"portfolio", "benchmark"}


def test_equal_api_path_ignores_concentration_cap_but_preserves_locks():
    assets, histories, positions = comparison_fixture()
    result = comparison_data(
        assets, histories[:2], histories[-1], positions, 3, True, "equal"
    )
    expected = annual_equal_returns(
        np.column_stack(
            [
                np.array(list(h.values()))[1:] / np.array(list(h.values()))[:-1] - 1
                for h in histories[:2]
            ]
        ),
        list(histories[-1]),
    )
    assert result["equity"][-1]["optimized"] == pytest.approx(
        100 * np.prod(1 + expected)
    )
    positions[0]["weight"], positions[1]["weight"] = 0.7, 0.3
    with pytest.raises(HTTPException, match="verrouillées"):
        comparison_data(
            assets,
            histories[:2],
            histories[-1],
            positions,
            3,
            True,
            "equal",
            locked_asset_ids=["0"],
        )


def test_equal_cash_is_charged_only_when_the_asset_becomes_available():
    dates = ["2024-01-01", "2024-06-01", "2024-08-01", "2024-09-01"]
    fee = 0.005
    changes = annual_equal_returns(np.zeros((3, 2)), dates, fee, [dates[0], dates[2]])
    assert np.prod(1 + changes[:1]) == pytest.approx(0.5 / (1 + fee) + 0.5)
    assert np.prod(1 + changes[:2]) == pytest.approx(1 / (1 + fee))
    assert changes[-1] == pytest.approx(0)


def test_downside_minimum_matches_dense_search_and_does_not_penalize_gains():
    rng = np.random.default_rng(281)
    returns = rng.normal([0.001, 0.0004], [0.025, 0.009], (500, 2))
    weights = optimize_weights(returns, np.array([0.5, 0.5]), "downside")

    def loss(w):
        return np.mean(np.minimum(returns @ w, 0) ** 2)

    grid = [0, *np.linspace(0.03, 0.97, 3001), 1]
    assert loss(weights) <= min(loss([w, 1 - w]) for w in grid) + 1e-10
    # High upside dispersion is desirable here: the first asset loses less on
    # every negative day despite being far more volatile overall.
    asymmetric = np.tile([[0.10, 0.001], [-0.001, -0.002]], (100, 1))
    downside = optimize_weights(asymmetric, np.array([0.5, 0.5]), "downside")
    total = optimize_weights(asymmetric, np.array([0.5, 0.5]), "volatility")
    assert downside == pytest.approx([1, 0], abs=1e-7)
    assert total == pytest.approx([0, 1], abs=1e-7)


def test_downside_preserves_locked_weights_and_concentration_bounds():
    rng = np.random.default_rng(58)
    returns = rng.normal(0.001, 0.01, (300, 4))
    current = np.array([0.55, 0.15, 0.15, 0.15])
    weights = optimize_weights(returns, current, "downside", {0: 0.55})
    assert weights[0] == pytest.approx(0.55)
    assert weights.sum() == pytest.approx(1)
    assert np.count_nonzero(weights > 1e-8) >= 2
    assert all(w < 1e-8 or 0.03 - 1e-8 <= w <= 0.35 + 1e-8 for w in weights[1:])
