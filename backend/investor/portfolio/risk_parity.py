"""Equal risk contributions using the convex risk-budgeting formulation."""

import numpy as np
from fastapi import HTTPException
from scipy.optimize import minimize


def risk_parity_weights(returns):
    """All eligible assets, positive weights, full investment, no leverage.

    Minimize x' C x / 2 - sum(log(x)), then normalize x. The first-order
    conditions give equal x_i (C x)_i. Scaling by marginal volatility improves
    conditioning without changing the covariance or the risk budgets.
    """
    returns = np.asarray(returns, dtype=float)
    if (
        returns.ndim != 2
        or len(returns) < 2
        or returns.shape[1] == 0
        or not np.all(np.isfinite(returns))
    ):
        raise HTTPException(422, "Parité de risque : rendements invalides.")
    covariance = np.atleast_2d(np.cov(returns, rowvar=False, ddof=1))
    deviations = np.sqrt(np.maximum(np.diag(covariance), 0))
    if np.any(deviations <= 1e-12):
        raise HTTPException(
            422, "Parité de risque indéfinie : un actif a une volatilité nulle."
        )
    correlation = covariance / np.outer(deviations, deviations)
    count = len(deviations)

    def objective(x):
        return float(x @ correlation @ x / 2 - np.log(x).sum())

    def gradient(x):
        return correlation @ x - 1 / x

    if count <= 2:
        # For two assets ERC is inverse volatility for every correlation > -1.
        # Avoid an ill-conditioned numerical solve near a perfect hedge.
        weights = 1 / deviations
    else:
        result = minimize(
            objective,
            np.ones(count),
            jac=gradient,
            bounds=[(1e-12, None)] * count,
            method="L-BFGS-B",
            options={"ftol": 1e-15, "gtol": 1e-10, "maxiter": 2000},
        )
        # A line-search status is not evidence that risk budgets are satisfied.
        # Refine the same convex objective by exact coordinate minimizations.
        x = result.x.copy()
        if not np.all(np.isfinite(x)) or np.any(x <= 0):
            x = np.ones(count)
        for _ in range(10000):
            cx = correlation @ x
            variance_x = float(x @ cx)
            if (
                variance_x > 0
                and np.max(np.abs(x * cx / variance_x - 1 / count)) <= 1e-9
            ):
                break
            for j in range(count):
                a = correlation[j, j]
                b = float(correlation[j] @ x - a * x[j])
                root = np.hypot(b, 2 * np.sqrt(a))
                x[j] = 2 / (root + b) if b >= 0 else (root - b) / (2 * a)
            if not np.all(np.isfinite(x)) or np.max(x) > 1e12:
                break
        weights = x / deviations
    weights /= weights.sum()
    contributions = weights * (covariance @ weights)
    variance = contributions.sum()
    if (
        not np.all(np.isfinite(weights))
        or np.any(weights <= 0)
        or variance <= 1e-20
        or np.max(np.abs(contributions / variance - 1 / count)) > 1e-6
    ):
        raise HTTPException(
            503,
            "Parité de risque non calculable : convergence ou risque total insuffisant."
            " Aucun poids de remplacement n’est utilisé.",
        )
    return weights


def risk_contributions(values, covariance):
    """Signed variance contributions of actual holdings; cash has zero risk."""
    values = np.asarray(values, dtype=float)
    contributions = values * (covariance @ values)
    variance = float(contributions.sum())
    if not np.isfinite(variance) or variance <= 1e-20:
        return None
    return contributions / variance
