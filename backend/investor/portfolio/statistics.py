"""Shared risk and return conventions for portfolios and individual assets."""

import numpy as np


def factor_regression(returns, factor_returns, periods):
    """OLS annualized intercept and beta for synchronous simple returns."""
    if len(factor_returns) < 2 or float(np.var(factor_returns, ddof=1)) <= 1e-16:
        return None, None
    design = np.column_stack((np.ones(len(factor_returns)), factor_returns))
    intercept, slope = np.linalg.lstsq(design, returns, rcond=None)[0]
    alpha = float(intercept * periods)
    return 0.0 if abs(alpha) < 1e-12 else alpha, float(slope)


def curve_metrics(
    curve, changes, benchmark_returns, elapsed_years, periods, *, benchmark=False
):
    """Calendar CAGR; sample volatility; downside target and reference rate 0%."""
    with np.errstate(over="ignore", invalid="ignore"):
        cagr = float((curve[-1] / curve[0]) ** (1 / elapsed_years) - 1)
    downside = float(np.sqrt(np.mean(np.minimum(changes, 0) ** 2)))
    drawdown = float(np.min(curve / np.maximum.accumulate(curve) - 1))
    alpha, beta = factor_regression(changes, benchmark_returns, periods)
    deviation = float(np.std(changes, ddof=1)) if len(changes) > 1 else None
    metrics = {
        "beta": 1.0 if benchmark else beta,
        "alpha": alpha,
        "total_return": float(curve[-1] / curve[0] - 1),
        "cagr": cagr,
        "volatility": deviation * np.sqrt(periods) if deviation is not None else None,
        "downside_volatility": downside * float(np.sqrt(periods)),
        "max_drawdown": drawdown,
        "sortino": float(changes.mean() / downside * np.sqrt(periods))
        if downside > 1e-12
        else None,
        "calmar": float(cagr / abs(drawdown)) if drawdown < -1e-12 else None,
        "sharpe": float(changes.mean() / deviation * np.sqrt(periods))
        if deviation is not None and deviation > 1e-12
        else None,
    }
    return {
        key: float(value) if value is not None and np.isfinite(value) else None
        for key, value in metrics.items()
    }
