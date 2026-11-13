"""Past-only log-price regression and self-financing reversion orders."""

from bisect import bisect_left

import numpy as np

from investor.assets.momentum import months_before


def regression_z(prices, dates, signal):
    """Fit the last three calendar years through the known signal close only."""
    lower = bisect_left(dates, months_before(dates[signal], 36))
    x = np.array([(d - dates[lower]).days / 365.25 for d in dates[lower : signal + 1]])
    y = np.log(prices[lower : signal + 1])
    valid = np.all(np.isfinite(y), axis=0)
    y = np.where(valid, y, 0.0)
    if len(x) < 501 or (dates[lower] - months_before(dates[signal], 36)).days > 7:
        return [None] * prices.shape[1]
    centered = x - x.mean()
    mean = y.mean(axis=0)
    slope = centered @ (y - mean) / (centered @ centered)
    residuals = y - (mean + centered[:, None] * slope)
    sigma = np.sqrt((residuals**2).sum(axis=0) / (len(x) - 2))
    return [
        float(r / s) if usable and s > 1e-10 * max(1, abs(float(m))) else None
        for r, s, m, usable in zip(residuals[-1], sigma, mean, valid, strict=True)
    ]


def reversion_orders(
    values,
    cash,
    z,
    fee,
    *,
    unit_prices=None,
    whole=None,
    active=None,
    portfolio_value=None,
    entry_z=1.4,
    exit_z=1.4,
    funding_min_z=0.0,
    exits=None,
):
    """Open meaningful positions, capped at 25%, with one funding holding.

    Passive holdings and their reserved cash never finance reversion orders.
    Entries require min(10%, 1/N active assets) of total NAV including fees.
    Whole-share minimums round up; simultaneous
    unaffordable entries are considered by signal strength, then unit price.
    At most one holding can fund the session's entries. Only known,
    nonnegative scores can fund entries, protecting still-depressed holdings.
    """
    after = values.copy()
    active = (
        np.ones(len(values), dtype=bool)
        if active is None
        else np.asarray(active, dtype=bool)
    )
    whole = (
        np.zeros(len(values), dtype=bool)
        if whole is None
        else np.asarray(whole, dtype=bool)
    )
    capital = float(values.sum() + cash) if portfolio_value is None else portfolio_value
    entry_cap = 0.25 * capital / (1 + fee)
    floor_share = min(0.10, 1 / max(1, int(active.sum())))
    entry_floor = floor_share * capital / (1 + fee)
    minimums = np.full(len(values), entry_floor)
    if np.any(whole & active):
        mask = whole & active
        minimums[mask] = (
            np.ceil(entry_floor / unit_prices[mask] - 1e-10) * unit_prices[mask]
        )
    for j, score in enumerate(z):
        if (
            active[j]
            and score is not None
            and values[j] > 1e-12
            and (bool(exits[j]) if exits is not None else score >= exit_z)
        ):
            cash += values[j] * (1 - fee)
            after[j] = 0.0
    entries = [
        j
        for j, score in enumerate(z)
        if active[j]
        and score is not None
        and values[j] <= 1e-12
        and score <= -entry_z
        and minimums[j] <= entry_cap
    ]
    if not entries:
        return after, float(cash)
    held = active & (after > 1e-12)
    pool = float(after[active].sum() + cash)
    previous = after.copy()
    donors = sorted(
        (j for j in np.flatnonzero(held) if z[j] is not None and z[j] >= funding_min_z),
        key=lambda j: (-z[j], j),
    )[:1]
    if cash <= 1e-10 and not donors:
        return after, float(cash)

    def plan(budget, candidates):
        target = previous.copy()
        for j in candidates:
            target[j] = max(budget, minimums[j])
            if whole[j]:
                target[j] = (
                    np.floor(target[j] / unit_prices[j] + 1e-10) * unit_prices[j]
                )
        # Use cash first, then only the necessary proceeds from one donor.
        # The ranking uses the same known close as the entry signal, never
        # tomorrow's execution close. Whole-share sales round up to cover fees.
        deficit = max(0.0, sum(target[j] for j in candidates) * (1 + fee) - cash)
        for j in donors:
            if deficit <= 0:
                break
            sale = min(previous[j], deficit / (1 - fee))
            if whole[j]:
                sale = min(
                    previous[j],
                    np.ceil(sale / unit_prices[j] - 1e-10) * unit_prices[j],
                )
            target[j] -= sale
            deficit -= sale * (1 - fee)
        cost = float(np.abs(target - previous).sum()) * fee
        required = float(target[active].sum()) + cost
        return target, required, deficit <= max(1e-12, np.spacing(pool) * 8)

    # Only retain candidates whose meaningful minimum can actually be funded.
    # Never sell for an order that will subsequently be dropped as too small.
    selected = []
    for j in sorted(entries, key=lambda j: (z[j], unit_prices[j] if whole[j] else 0)):
        if plan(0.0, [*selected, j])[2]:
            selected.append(j)
    if not selected:
        return after, float(cash)
    low, high = 0.0, min(entry_cap, pool / (int(held.sum()) + len(selected)))
    # Cash-only sizing is allowed only above the meaningful minimum, rather
    # than accepting the last few euros as a permanently undersized position.
    minimum = sum(minimums[j] for j in selected) * (1 + fee)
    if cash > 1e-10 and cash >= minimum:
        donors = []
        high = min(high, cash / ((1 + fee) * len(selected)))
    else:
        # Finance only the minimum useful entry, preserving the donor and
        # avoiding extra turnover just to reach the much larger 25% ceiling.
        target, required, _ = plan(0.0, selected)
        return target, max(0.0, pool - required)
    target, required, feasible = plan(high, selected)
    if feasible:
        return target, max(0.0, pool - required)
    for _ in range(60):
        middle = (low + high) / 2
        if plan(middle, selected)[2]:
            low = middle
        else:
            high = middle
    target, required, _ = plan(low, selected)
    return target, max(0.0, pool - required)


def reversion_exits(values, scores, peaks, *, exit_z=1.4, mode="threshold", gap=0.5):
    """Update peaks with the known close; never arm from a future observation."""
    exits = np.zeros(len(values), dtype=bool)
    for j, score in enumerate(scores):
        if values[j] <= 1e-12:
            peaks[j] = np.nan
        elif score is not None:
            peaks[j] = max(score, peaks[j]) if np.isfinite(peaks[j]) else score
            exits[j] = (
                score >= exit_z
                if mode == "threshold"
                else peaks[j] >= exit_z and score <= peaks[j] - gap
            )
    return exits
