"""Independent checks for degenerate ratios and constrained target betas."""

import numpy as np
import pytest

from investor.portfolio.performance import optimize_weights


@pytest.mark.parametrize("mode", ["sortino", "beta_sharpe"])
def test_constant_positive_returns_do_not_cause_solver_failure(mode):
    returns = np.tile([0.001, 0.002, 0.003, 0.004], (100, 1))
    weights = optimize_weights(returns, np.full(4, 0.25), mode)
    assert weights == pytest.approx([0, 0.3, 0.35, 0.35], abs=1e-7)


@pytest.mark.parametrize("locked", [{0: 0.5}, {0: 0.5, 1: 0.2, 2: 0.15}])
def test_beta_redundant_after_locks_remains_feasible(locked):
    market = np.random.default_rng(49).normal(0.0004, 0.01, 300)
    betas = np.array([0.2, 0.8, 0.8, 0.8])
    returns = market[:, None] * betas + [0.0003, 0.0004, 0.0002, 0.0001]
    current = np.array([0.5, 0.2, 0.15, 0.15])
    weights = optimize_weights(
        returns, current, "beta_sharpe", locked, betas=betas, target_beta=0.5
    )
    assert weights.sum() == pytest.approx(1)
    assert betas @ weights == pytest.approx(0.5, abs=1e-8)
    for i, value in locked.items():
        assert weights[i] == pytest.approx(value, abs=1e-8)


@pytest.mark.parametrize("mode", ["sortino", "beta_sharpe"])
def test_positive_ratio_matches_dense_search_with_fixed_quantity(mode):
    rng = np.random.default_rng(116)
    returns = rng.normal([0.001, 0.0008, 0.0002], [0.025, 0.012, 0.008], (400, 3))
    current = np.array([0.4, 0.3, 0.3])
    kwargs = {}
    if mode == "beta_sharpe":
        # The fixed position has a different beta from the two free positions.
        kwargs = {"betas": np.array([0.2, 0.7, 0.7]), "target_beta": 0.5}
    weights = optimize_weights(returns, current, mode, {0: 0.4}, **kwargs)
    grid = np.linspace(0.25, 0.35, 2001)
    candidates = np.column_stack([np.full(len(grid), 0.4), grid, 0.6 - grid])

    def score(w):
        changes = returns @ w.T
        risk = (
            np.sqrt(np.mean(np.minimum(changes, 0) ** 2, axis=0))
            if mode == "sortino"
            else np.std(changes, axis=0, ddof=1)
        )
        return changes.mean(axis=0) / risk

    assert weights[0] == pytest.approx(0.4, abs=1e-8)
    assert score(weights) >= np.max(score(candidates)) - 1e-8


def test_positive_sharpe_with_independent_beta_matches_dense_search():
    rng = np.random.default_rng(781)
    betas = np.array([0.1, 0.5, 0.9, 1.3])
    market = rng.normal(0.0005, 0.01, 400)
    returns = market[:, None] * betas + rng.normal(0.0007, 0.01, (400, 4))
    weights = optimize_weights(
        returns, np.full(4, 0.25), "beta_sharpe", betas=betas, target_beta=0.7
    )
    # Budget and beta determine the last two weights for every first pair.
    x, y = np.meshgrid(np.linspace(0, 0.35, 351), np.linspace(0, 0.35, 351))
    z = (1.3 * (1 - x - y) + 0.1 * x + 0.5 * y - 0.7) / 0.4
    grid = np.column_stack([x.ravel(), y.ravel(), z.ravel(), (1 - x - y - z).ravel()])
    grid = grid[np.all((grid >= -1e-10) & (grid <= 0.35 + 1e-10), axis=1)]
    grid = grid[np.all((np.abs(grid) < 1e-10) | (grid >= 0.03 - 1e-10), axis=1)]
    means, covariance = returns.mean(axis=0), np.cov(returns, rowvar=False)
    scores = grid @ means / np.sqrt(np.einsum("ij,jk,ik->i", grid, covariance, grid))
    actual = (means @ weights) / np.sqrt(weights @ covariance @ weights)
    assert actual >= scores.max() - 1e-8
    assert betas @ weights == pytest.approx(0.7, abs=1e-8)
