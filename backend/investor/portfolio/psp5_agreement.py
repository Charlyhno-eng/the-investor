"""Frozen PSP5 downside filter and five advisory models. Signals are close-t only."""

from datetime import date
from functools import lru_cache

import numpy as np
from scipy.special import expit

from investor.assets.momentum import months_before

WINDOW = 32
BAND = 0.05


def rolling_mean(values, window):
    prefix = np.cumsum(np.pad(values, [(0, 0)] * (values.ndim - 1) + [(1, 0)]), axis=-1)
    result = np.full_like(values, np.nan)
    result[..., window - 1 :] = (prefix[..., window:] - prefix[..., :-window]) / window
    return result


@lru_cache(maxsize=8)
def calendar(days):
    dates = [date.fromisoformat(d) for d in days]
    x = np.array([(d - dates[0]).days / 365.25 for d in dates])
    windows = []
    for months in (60, 18):
        cutoff = np.array([months_before(d, months).isoformat() for d in dates])
        windows.append((np.searchsorted(days, cutoff), cutoff >= days[0]))
    return x, windows


def regression_scores(days, prices):
    x, windows = calendar(tuple(days))
    y = np.log(prices / prices[0])
    for lower, valid in windows:

        def total(values, lower=lower):
            prefix = np.r_[0.0, np.cumsum(values)]
            return prefix[1:] - prefix[lower]

        count = np.arange(1, len(prices) + 1) - lower
        sx, sy = total(x), total(y)
        covariance = total(x * y) - sx * sy / count
        slope = covariance / np.maximum(total(x * x) - sx * sx / count, 1e-14)
        deviation = np.sqrt(
            np.maximum(total(y * y) - sy * sy / count - slope * covariance, 0)
            / np.maximum(count - 2, 1)
        )
        residual = y - sy / count - slope * (x - sx / count)
        yield np.where(
            valid & (count >= 41) & (deviation > 1e-10),
            residual / np.maximum(deviation, 1e-14),
            np.nan,
        )


def targets(days, prices):
    prices = np.asarray(prices, dtype=float)
    slow_z, fast_z = regression_scores(days, prices)
    returns = np.r_[0.0, np.diff(prices) / prices[:-1]]
    variance = np.maximum(
        0, rolling_mean(returns**2, 252) - rolling_mean(returns, 252) ** 2
    )
    sigma = np.maximum(
        0.003, np.nan_to_num(np.sqrt(variance * 252 / 251), nan=0.16 / np.sqrt(252))
    )
    prior = 0.8
    slow = False
    fast = [False, False]
    active = [False, False]
    low = [prices[0], prices[0]]
    evidence = [0.0, 0.0]
    experts = np.empty((5, len(prices)))
    log_likelihood = (
        np.log(1.5 / 0.7)
        - 0.5 * ((returns - 0.08 / 252) / (0.7 * sigma)) ** 2
        + 0.5 * ((returns + 0.12 / 252) / (1.5 * sigma)) ** 2
    )
    for i, price in enumerate(prices):
        if i and days[i][:7] != days[i - 1][:7] and np.isfinite(slow_z[i]):
            slow = (
                slow_z[i] <= 1.5
                if slow
                else slow_z[i] < -2 or slow_z[i - 1] < 0 <= slow_z[i]
            )
        if i and i % 5 == 0 and np.isfinite(fast_z[i]):
            for j, exit_z in enumerate((1.5, 2.0)):
                fast[j] = (
                    fast_z[i] <= exit_z
                    if fast[j]
                    else fast_z[i - 1] < -0.5 <= fast_z[i]
                )
        experts[0, i] = (
            0.4875 * (1 if slow else 0.25) + 0.1625 * (1 if fast[0] else 0.25) + 0.35
        )
        experts[1, i] = 0.9 * (1 if slow else 0.1) + 0.1 * (1 if fast[1] else 0.1)
        for j, threshold in enumerate((5, 8)):
            low[j] = price if active[j] else min(low[j], price)
            evidence[j] = max(0.0, evidence[j] - returns[i] / sigma[i] - 0.1)
            if active[j] and evidence[j] > threshold:
                active[j], low[j] = False, price
            elif not active[j] and (
                price / low[j] - 1 >= 0.06
                or (i >= 63 and price > prices[i - 63] and evidence[j] == 0)
            ):
                active[j], evidence[j] = True, 0.0
            experts[2 + j, i] = 1 if active[j] else 0.25
        prior = 0.98 * prior + 0.02 * (1 - prior)
        prior = expit(np.log(prior / (1 - prior)) + log_likelihood[i])
        experts[4, i] = 0.25 + 0.75 * prior
    executed = np.pad(experts[:, :-1], ((0, 0), (1, 0)))
    held = np.pad(executed[:, :-1], ((0, 0), (1, 0)))
    logs = np.log1p(held * returns - 0.0012 * abs(executed - held))
    mean = rolling_mean(logs, 252)
    var = np.maximum(rolling_mean(logs**2, 252) - mean**2, 0)
    scores = np.nan_to_num(2 * 252 * (mean - 1.5 * var), nan=0.0)
    weights = np.array([0.5, 0.125, 0.125, 0.125, 0.125])[:, None] * np.exp(
        np.clip(scores - scores.max(axis=0), -50, 0)
    )
    ensemble = np.clip((weights * experts).sum(axis=0) / weights.sum(axis=0), 0.1, 1.0)
    changes = np.diff(np.log(prices), prepend=np.log(prices[0]))
    binary = rolling_mean(np.minimum(changes, 0) ** 2, WINDOW) <= 0.8 * np.maximum(
        rolling_mean(changes**2, WINDOW), 1e-12
    )
    return (0.25 * ensemble + 0.75 * binary) * (
        0.5 + 0.5 * np.minimum(ensemble, binary)
    )


def books(days, prices, start, capital, fee, whole):
    """Two fresh accounts, next-close execution and no terminal liquidation."""
    prices = np.asarray(prices, dtype=float)
    target = targets(days, prices)
    cash = np.full(2, float(capital))
    units = np.zeros(2)
    costs = np.zeros(2)
    turnover = np.zeros(2)
    entered = np.zeros(2, dtype=bool)
    curves = np.full((len(prices) - start, 2), float(capital))
    for i in range(start + 1, len(prices)):
        signal = i - 1
        nav = cash + units * prices[i]
        weight = target[signal]
        prior_weight = units[1] * prices[signal] / curves[signal - start, 1]
        for j, due, desired in (
            (0, signal == start, 1.0),
            (1, signal == start or abs(weight - prior_weight) >= BAND, weight),
        ):
            if not due:
                continue
            old = units[j] * prices[i]
            rate = fee if desired * nav[j] > old else -fee
            quantity = (
                desired * (nav[j] + rate * old) / (prices[i] * (1 + desired * rate))
            )
            if whole:
                quantity = np.floor(quantity + 1e-10)
            trade = (quantity - units[j]) * prices[i]
            cost = abs(trade) * fee
            cash[j] -= trade + cost
            units[j] = quantity
            costs[j] += cost
            if entered[j]:
                turnover[j] += abs(trade) / nav[j]
            entered[j] |= abs(trade) > 1e-9
        curves[i - start] = cash + units * prices[i]
    return curves, costs, turnover
