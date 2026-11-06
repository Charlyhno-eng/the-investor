"""Vectorized risk metrics. All returns are simple, net of execution costs."""

import numpy as np


def equity(returns):
    return np.concatenate(([1.0], np.cumprod(1.0 + returns)))


def metrics(returns, benchmark, periods_per_year, risk_free_rate):
    returns, benchmark = np.asarray(returns), np.asarray(benchmark)
    curve = equity(returns)
    rf = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess, market_excess = returns - rf, benchmark - rf
    vol = float(np.std(returns, ddof=1))
    downside = float(np.sqrt(np.mean(np.minimum(excess, 0) ** 2)))
    drawdown = curve / np.maximum.accumulate(curve) - 1
    mdd = float(-np.min(drawdown))
    annualized = float(curve[-1] ** (periods_per_year / len(returns)) - 1)
    variance = float(np.var(market_excess, ddof=1))
    beta = (
        float(np.cov(excess, market_excess, ddof=1)[0, 1] / variance)
        if variance > 1e-16
        else None
    )
    result = {
        "total_return": float(curve[-1] - 1),
        "annualized_return": annualized,
        "sharpe": float(np.mean(excess) / vol * np.sqrt(periods_per_year))
        if vol > 1e-12
        else None,
        "sortino": float(np.mean(excess) / downside * np.sqrt(periods_per_year))
        if downside > 1e-12
        else None,
        "calmar": annualized / mdd if mdd > 1e-12 else None,
        "annualized_volatility": vol * np.sqrt(periods_per_year),
        "maximum_drawdown": mdd,
        "var_95": max(0.0, float(-np.quantile(returns, 0.05))),
        "alpha": float(
            (np.mean(excess) - beta * np.mean(market_excess)) * periods_per_year
        )
        if beta is not None
        else None,
        "beta": beta,
    }
    return {
        key: float(value) if value is not None and np.isfinite(value) else None
        for key, value in result.items()
    }
