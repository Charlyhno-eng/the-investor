"""Risk matrix propagation and full-universe correlation optimization."""

import numpy as np
import pytest
from fastapi import HTTPException

from investor.portfolio.performance import optimize_weights


def exact_returns(matrix, observations=900):
    rng = np.random.default_rng(554)
    sample = rng.normal(size=(observations, len(matrix)))
    sample -= sample.mean(axis=0)
    orthogonal, _ = np.linalg.qr(sample)
    return orthogonal @ np.linalg.cholesky(matrix).T


def test_covariance_override_reaches_inner_support_solver():
    returns = exact_returns(np.eye(4))
    current = np.full(4, 0.25)
    original = optimize_weights(returns, current, "volatility")
    changed = optimize_weights(
        returns, current, "volatility", covariance_override=np.diag([1, 2, 4, 8])
    )
    np.testing.assert_allclose(original, current, atol=1e-6)
    np.testing.assert_allclose(changed, [0.35, 0.35, 0.2, 0.1], atol=1e-6)


def test_covariance_override_reaches_large_universe_relaxed_solver():
    returns = exact_returns(np.eye(10))
    covariance = np.diag(np.arange(1, 11, dtype=float))
    current = np.full(10, 0.1)
    target = optimize_weights(
        returns, current, "volatility", covariance_override=covariance
    )
    assert target @ covariance @ target < 0.9 * (current @ covariance @ current)
    assert target[0] > 2 * target[-1]


def test_correlated_pair_can_diversify_other_holdings():
    correlation = np.full((14, 14), 0.45)
    np.fill_diagonal(correlation, 1)
    correlation[:2, 2:] = correlation[2:, :2] = 0.05
    correlation[0, 1] = correlation[1, 0] = 0.98
    returns = exact_returns(correlation)
    weights = optimize_weights(
        returns, np.full(14, 1 / 14), "correlation", continuous_correlation=True
    )
    assert weights[:2].sum() > 0.30
    assert weights.sum() == pytest.approx(1)
    assert weights.min() >= 0
    assert weights.max() <= 0.35 + 1e-8


def test_continuous_correlation_dominates_support_search_and_is_permutation_equivariant():
    rng = np.random.default_rng(18)
    factors = rng.normal(size=(900, 3))
    returns = factors @ rng.normal(size=(3, 14)) + rng.normal(size=(900, 14))
    current = np.full(14, 1 / 14)
    legacy = optimize_weights(returns, current, "correlation")
    target = optimize_weights(
        returns, current, "correlation", continuous_correlation=True
    )
    matrix = np.corrcoef(returns, rowvar=False)
    assert target @ matrix @ target <= legacy @ matrix @ legacy + 1e-9
    assert np.any((target > 1e-7) & (target < 0.03))
    order = rng.permutation(14)
    permuted = optimize_weights(
        returns[:, order], current[order], "correlation", continuous_correlation=True
    )
    np.testing.assert_allclose(permuted, target[order], atol=1e-6)


def test_constant_series_is_rejected_for_correlation():
    returns = exact_returns(np.eye(4))
    returns[:, 0] = 0
    with pytest.raises(HTTPException) as error:
        optimize_weights(
            returns, np.full(4, 0.25), "correlation", continuous_correlation=True
        )
    assert "volatilité nulle" in error.value.detail
