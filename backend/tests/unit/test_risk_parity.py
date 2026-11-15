import numpy as np
import pytest
from fastapi import HTTPException

from investor.portfolio.risk_parity import risk_parity_weights


def observations(covariance):
    # Orthonormal centered columns give the exact requested sample covariance.
    n = len(covariance)
    q, _ = np.linalg.qr(np.eye(n + 1)[:, :n] - 1 / (n + 1))
    return np.sqrt(n) * q @ np.linalg.cholesky(covariance).T


def test_diagonal_covariance_gives_inverse_volatility_weights():
    returns = observations(np.diag([1, 4, 16]))
    assert risk_parity_weights(returns) == pytest.approx(np.array([4, 2, 1]) / 7)


def test_correlations_matter_and_contributions_are_equal():
    covariance = np.array([[1, 0.6, -0.2], [0.6, 4, 0.4], [-0.2, 0.4, 9]])
    returns = observations(covariance)
    weights = risk_parity_weights(returns)
    rc = weights * (covariance @ weights)
    assert rc / rc.sum() == pytest.approx(np.full(3, 1 / 3), abs=1e-6)
    assert not np.allclose(weights, np.array([6, 3, 2]) / 11)
    assert weights.sum() == pytest.approx(1)
    assert risk_parity_weights(returns * 0.001) == pytest.approx(weights)
    assert risk_parity_weights(returns[:, ::-1]) == pytest.approx(weights[::-1])


def test_single_asset_and_duplicate_assets():
    returns = np.arange(20.0)[:, None]
    assert risk_parity_weights(returns) == pytest.approx([1])
    assert risk_parity_weights(np.repeat(returns, 3, axis=1)) == pytest.approx(
        [1 / 3] * 3
    )


@pytest.mark.parametrize(
    "returns",
    [np.ones((20, 2)), np.array([[np.nan], [1]]), np.array([[1.0, -1.0], [-1.0, 1.0]])],
)
def test_undefined_risk_is_rejected(returns):
    with pytest.raises(HTTPException):
        risk_parity_weights(returns)


def test_nearly_anticorrelated_pair_uses_analytic_solution():
    covariance = np.array([[1, -1.999999], [-1.999999, 4]])
    weights = risk_parity_weights(observations(covariance))
    assert weights == pytest.approx([2 / 3, 1 / 3])


def test_actual_contributions_use_holdings_and_ignore_cash_scale():
    from investor.portfolio.risk_parity import risk_contributions

    covariance = np.diag([1.0, 4.0])
    assert risk_contributions(np.array([100.0, 50.0]), covariance) == pytest.approx(
        [0.5, 0.5]
    )
    assert risk_contributions(np.array([200.0, 50.0]), covariance) == pytest.approx(
        [0.8, 0.2]
    )
    assert risk_contributions(np.zeros(2), covariance) is None


def test_refines_stalled_optimizer_without_replacing_risk_budgets(monkeypatch):
    from types import SimpleNamespace

    from investor.portfolio import risk_parity

    covariance = np.array([[1, 0.6, -0.2], [0.6, 4, 0.4], [-0.2, 0.4, 9]])
    monkeypatch.setattr(
        risk_parity,
        "minimize",
        lambda *args, **kwargs: SimpleNamespace(x=np.ones(3), success=False),
    )
    weights = risk_parity_weights(observations(covariance))
    rc = weights * (covariance @ weights)
    assert rc / rc.sum() == pytest.approx(np.full(3, 1 / 3), abs=1e-8)
    assert not np.allclose(weights, np.full(3, 1 / 3))


def test_correlated_and_hedging_assets_have_equal_risk_contributions():
    rng = np.random.default_rng(21)
    factor = rng.normal(size=(800, 1))
    returns = factor * np.array([1, 1.2, -0.8, 0.3, -0.2]) + rng.normal(
        scale=0.12, size=(800, 5)
    )
    weights = risk_parity_weights(returns)
    covariance = np.cov(returns, rowvar=False)
    rc = weights * (covariance @ weights)
    assert rc / rc.sum() == pytest.approx(np.full(5, 0.2), abs=1e-6)
