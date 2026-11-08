from datetime import date

import numpy as np
import pytest
from fastapi import HTTPException

from investor.portfolio.performance import (
    comparison_data,
    factor_regression,
    optimize_weights,
)


@pytest.mark.parametrize(
    "mode", ["balanced", "volatility", "performance", "drawdown", "correlation"]
)
def test_optimizer_matches_dense_two_asset_search(mode):
    rng = np.random.default_rng(91)
    returns = rng.normal([0.001, 0.0003], [0.025, 0.007], (750, 2))
    current = np.array([0.7, 0.3])
    w = optimize_weights(returns, current, mode)
    grid = np.column_stack((np.linspace(0, 1, 3001), np.linspace(1, 0, 3001)))

    grid = grid[np.all((grid < 1e-10) | (grid >= 0.03 - 1e-10), axis=1)]

    def objective(weights):
        changes = returns @ weights.T
        if changes.ndim == 1:
            changes = changes[:, None]
        logs = np.vstack(
            [np.zeros(changes.shape[1]), np.cumsum(np.log1p(changes), axis=0)]
        )
        if mode == "balanced":
            return -changes.mean(axis=0) / changes.std(axis=0, ddof=1)
        if mode == "volatility":
            return changes.var(axis=0, ddof=1)
        if mode == "performance":
            return -logs[-1]
        if mode == "correlation":
            return np.einsum(
                "ij,jk,ik->i",
                np.atleast_2d(weights),
                np.corrcoef(returns, rowvar=False),
                np.atleast_2d(weights),
            )
        return np.max(np.maximum.accumulate(logs, axis=0) - logs, axis=0)

    assert objective(w)[0] <= np.min(objective(grid)) + 1e-7
    assert objective(w)[0] <= objective(current)[0] + 1e-8
    assert w.sum() == pytest.approx(1)
    assert w.min() >= 0


@pytest.mark.parametrize("case", ["single", "identical", "zero", "negative"])
def test_degenerate_and_negative_return_portfolios(case):
    rng = np.random.default_rng(2)
    changes = rng.normal(-0.002, 0.01, 200)
    returns = {
        "single": changes[:, None],
        "identical": np.column_stack([changes, changes]),
        "zero": np.zeros((200, 3)),
        "negative": np.column_stack([changes, -0.001 + changes * 0.2]),
    }[case]
    current = np.full(returns.shape[1], 1 / returns.shape[1])
    weights = optimize_weights(returns, current, "volatility")
    assert weights.sum() == pytest.approx(1)
    assert np.min(weights) >= 0
    assert np.var(returns @ weights) <= np.var(returns @ current) + 1e-10


def test_extended_history_reserves_cash_before_inception_and_does_not_fill_gaps():
    from datetime import timedelta

    days = [
        (date(2026, 1, 1) - timedelta(days=900 - i)).isoformat() for i in range(900)
    ]
    old = {d: 100 + i * 0.1 for i, d in enumerate(days)}
    young = {d: 100 + i * 0.2 for i, d in enumerate(days[-150:])}
    assets = [
        {"id": "old", "name": "Old", "frequency": "daily"},
        {"id": "young", "name": "Young", "frequency": "daily"},
    ]
    positions = [{"weight": 0.5, "value": 100, "price": 100}] * 2
    short = comparison_data(assets, [old, young], old, positions, 1)
    long = comparison_data(assets, [old, young], old, positions, 3, history="extended")
    common = comparison_data(assets, [old, young], old, positions, 3)
    assert short["start"] == common["start"] == days[-150]
    assert long["start"] == days[0]
    assert long["cash_until"] == [{"id": "young", "name": "Young", "date": days[-150]}]
    # The young asset's reserved half stays cash, rather than inventing prices
    # or giving the old asset its weight. Entry occurs at its first known price.
    assert long["equity"][1]["portfolio"] == pytest.approx(100 * (1 + 0.5 * 0.001))
    prior, inception, active = long["equity"][749:752]
    assert inception["portfolio"] / prior["portfolio"] - 1 == pytest.approx(
        0.5 * (old[days[750]] / old[days[749]] - 1)
    )
    assert active["portfolio"] / inception["portfolio"] - 1 == pytest.approx(
        0.5 * (old[days[751]] / old[days[750]] - 1)
        + 0.5 * (young[days[751]] / young[days[750]] - 1)
    )
    del young[days[-50]]
    gap = comparison_data(assets, [old, young], old, positions, 3, history="extended")
    assert days[-50] not in [p["time"] for p in gap["equity"]]
    assert gap["observations"] == long["observations"] - 1


@pytest.mark.parametrize(
    "mode", ["balanced", "volatility", "performance", "drawdown", "correlation"]
)
@pytest.mark.parametrize("case", ["positive", "negative", "zero"])
def test_all_modes_enforce_concentration_even_when_current_portfolio_is_concentrated(
    mode, case
):
    rng = np.random.default_rng(13)
    returns = rng.normal(
        [0.003, 0.001, 0.0002, 0.0005], [0.02, 0.01, 0.015, 0.008], (200, 4)
    )
    if case == "negative":
        returns = -np.abs(returns)
    elif case == "zero":
        returns = np.zeros((200, 4))
    if mode == "correlation" and case == "zero":
        with pytest.raises(HTTPException, match="Corrélations non mesurables"):
            optimize_weights(returns, np.array([1.0, 0.0, 0.0, 0.0]), mode)
        return
    weights = optimize_weights(returns, np.array([1.0, 0.0, 0.0, 0.0]), mode)
    assert weights.sum() == pytest.approx(1)
    assert weights.min() >= 0
    assert weights.max() <= 0.35 + 1e-8
    assert np.count_nonzero(weights > 1e-8) >= 3


def test_performance_cap_is_part_of_the_optimum_and_two_assets_are_exempt():
    returns = np.tile([0.01, 0.005, 0.001], (100, 1))
    weights = optimize_weights(returns, np.array([1.0, 0.0, 0.0]), "performance")
    assert weights == pytest.approx([0.35, 0.35, 0.3], abs=1e-7)
    two = optimize_weights(returns[:, :2], np.array([0.5, 0.5]), "performance")
    assert two == pytest.approx([1.0, 0.0], abs=1e-7)


@pytest.mark.parametrize("beta", [-1.3, 0.0, 0.7, 2.4])
@pytest.mark.parametrize("periods", [12, 252])
def test_factor_regression_recovers_intercept_and_signed_beta(beta, periods):
    factor = np.array([-0.02, 0.01, 0.03, -0.01, 0.005])
    intercept = 0.0004
    alpha, slope = factor_regression(intercept + beta * factor, factor, periods)
    assert alpha == pytest.approx(intercept * periods)
    assert slope == pytest.approx(beta, abs=1e-12)
    assert factor_regression(factor, factor, periods) == pytest.approx((0, 1))
    assert factor_regression(factor, np.zeros(5), periods) == (None, None)


def test_correlation_is_independent_of_volatility_and_means():
    rng = np.random.default_rng(21)
    returns = rng.normal(0, [0.01, 0.03], (2000, 2))
    current = np.array([0.5, 0.5])
    weights = optimize_weights(returns, current, "correlation")
    assert weights == pytest.approx([0.5, 0.5], abs=1e-6)
    transformed = returns * [2, 0.5] + [0.005, -0.003]
    assert optimize_weights(transformed, current, "correlation") == pytest.approx(
        weights, abs=1e-7
    )
    with_cash = np.column_stack((np.zeros(2000), returns[:, 0]))
    with pytest.raises(HTTPException, match="Corrélations non mesurables"):
        optimize_weights(with_cash, current, "correlation")


@pytest.mark.parametrize(
    "mode", ["balanced", "volatility", "performance", "drawdown", "correlation"]
)
@pytest.mark.parametrize("count", [7, 11])
def test_all_modes_keep_half_the_assets_with_a_three_percent_floor(mode, count):
    rng = np.random.default_rng(74)
    returns = rng.normal(0.0004, 0.012, (120, count))
    returns[:, 0] += 0.008
    weights = optimize_weights(returns, np.full(count, 1 / count), mode)
    active = weights[weights > 1e-8]
    assert len(active) >= (count + 1) // 2
    assert active.min() >= 0.03 - 1e-8
    assert active.max() <= 0.35 + 1e-8
    assert weights.sum() == pytest.approx(1)


def test_infeasible_asset_count_is_explicit():
    with pytest.raises(HTTPException, match="Contraintes incompatibles"):
        optimize_weights(np.zeros((30, 67)), np.full(67, 1 / 67), "performance")


def test_performance_optimizes_with_floor_instead_of_adding_tiny_positions_afterwards():
    returns = np.tile([0.02, 0.01, 0.005, 0.003, 0.002, 0.001, -0.001], (60, 1))
    weights = optimize_weights(returns, np.full(7, 1 / 7), "performance")
    assert weights == pytest.approx([0.35, 0.35, 0.27, 0.03, 0, 0, 0], abs=1e-7)


def test_correlation_favors_negative_relationships_over_a_correlated_cluster():
    rng = np.random.default_rng(9)
    factor = rng.normal(0, 0.01, 1000)
    returns = np.column_stack((factor, factor, -factor, rng.normal(0, 0.01, 1000)))
    weights = optimize_weights(returns, np.full(4, 0.25), "correlation")
    # Give the negatively correlated holding the maximum available weight.
    assert weights[2] == pytest.approx(0.35, abs=1e-6)
    corr = np.corrcoef(returns, rowvar=False)
    assert weights @ corr @ weights < np.full(4, 0.25) @ corr @ np.full(4, 0.25)


def test_largest_feasible_universe_retains_33_positions():
    returns = np.tile(np.linspace(0.01, 0.0001, 66), (30, 1))
    weights = optimize_weights(returns, np.full(66, 1 / 66), "performance")
    active = weights[weights > 1e-8]
    assert len(active) == 33
    assert active.min() >= 0.03 - 1e-8
    assert weights.sum() == pytest.approx(1)


@pytest.mark.parametrize(
    "mode", ["balanced", "volatility", "performance", "drawdown", "correlation"]
)
def test_locked_quantities_are_hard_constraints_in_every_mode(mode):
    rng = np.random.default_rng(32)
    changes = rng.normal(
        [0.001, 0.0004, 0.0002, 0.0008], [0.02, 0.01, 0.03, 0.015], (150, 4)
    )
    current = np.array([0.72, 0.01, 0.17, 0.10])
    locked = {0: 0.72, 1: 0.01}
    weights = optimize_weights(changes, current, mode, locked)
    assert weights[:2] == pytest.approx(current[:2], abs=1e-8)
    assert weights.sum() == pytest.approx(1)
    assert all(
        w == pytest.approx(0, abs=1e-8) or 0.03 - 1e-8 <= w <= 0.35 + 1e-8
        for w in weights[2:]
    )
    assert optimize_weights(
        changes, current, mode, dict(enumerate(current))
    ) == pytest.approx(current)


def test_incompatible_locks_raise_instead_of_changing_locked_position():
    rng = np.random.default_rng(7)
    changes = rng.normal(0, 0.01, (100, 3))
    with pytest.raises(HTTPException) as error:
        optimize_weights(
            changes, np.array([0.99, 0.005, 0.005]), "volatility", {0: 0.99}
        )
    assert error.value.status_code == 422
