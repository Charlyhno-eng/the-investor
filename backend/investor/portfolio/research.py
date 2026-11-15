"""Experimental, past-only estimators; no claim of predictive superiority."""

from bisect import bisect_left

import numpy as np

from investor.assets.momentum import months_before


def shrunk_covariance(returns):
    """Oracle Approximating Shrinkage (OAS), towards scaled identity.

    Uses the closed-form OAS coefficient, not the constant-correlation
    Ledoit-Wolf estimator. Gaussian derivation; heavy tails remain a limitation.
    """
    x = np.asarray(returns, dtype=float)
    n, p = x.shape
    x = x - x.mean(axis=0)
    empirical = x.T @ x / n
    mu = np.trace(empirical) / p
    alpha = np.mean(empirical**2)
    denominator = (n + 1) * (alpha - mu**2 / p)
    shrinkage = 1.0 if denominator <= 0 else min(1.0, (alpha + mu**2) / denominator)
    return (1 - shrinkage) * empirical + shrinkage * mu * np.eye(p)


def residual_diagnostics(prices, dates, signal):
    """Describe three-year residual persistence; filter fixed before evaluation.

    Admission: positive AR(1) coefficient with half-life <= 63 observations,
    and last-quarter residual mean within one full-window residual deviation.
    These descriptive checks do not establish stationarity.
    """
    lower = bisect_left(dates, months_before(dates[signal], 36))
    y = np.log(np.asarray(prices[lower : signal + 1], dtype=float))
    x = np.array([(d - dates[lower]).days for d in dates[lower : signal + 1]])
    x = x - x.mean()
    residual = y - y.mean(axis=0) - x[:, None] * (x @ (y - y.mean(axis=0)) / (x @ x))
    lag, nxt = residual[:-1], residual[1:]
    lag = lag - lag.mean(axis=0)
    nxt = nxt - nxt.mean(axis=0)
    denominator = (lag**2).sum(axis=0)
    phi = np.divide(
        (lag * nxt).sum(axis=0),
        denominator,
        out=np.full(y.shape[1], np.nan),
        where=denominator > 1e-20,
    )
    half_life = np.full(y.shape[1], np.inf)
    valid = (phi > 0) & (phi < 1)
    half_life[valid] = -np.log(2) / np.log(phi[valid])
    sigma = residual.std(axis=0, ddof=2)
    shift = np.divide(
        np.abs(residual[-63:].mean(axis=0)),
        sigma,
        out=np.full(y.shape[1], np.inf),
        where=sigma > 1e-10,
    )
    allowed = valid & (half_life <= 63) & (shift <= 1) & (len(y) >= 501)
    # Compare annualized log slopes on the first and last halves of the window.
    slopes = []
    for part in (slice(None, len(y) // 2), slice(len(y) // 2, None)):
        t = x[part] - x[part].mean()
        slopes.append(365.25 * (t @ (y[part] - y[part].mean(axis=0))) / (t @ t))
    return {
        "slope_change": slopes[1] - slopes[0],
        "phi": phi,
        "half_life": half_life,
        "recent_shift": shift,
        "allowed": allowed,
    }
