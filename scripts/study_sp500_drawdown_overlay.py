"""Final predeclared refinement: protect ALL three v5 books, compensate exposure.

PYTHONPATH=backend:scripts uv run python scripts/study_sp500_drawdown_overlay.py --workers 4
No production changes. Fresh selection/audit seeds, no reuse as unseen evidence.
"""

from itertools import product
from pathlib import Path

import numpy as np
import study_sp500_drawdown_frontier as engine


def grid():
    return [
        dict(
            family="protected_core",
            floor=floor,
            multiple=multiple,
            rebound=rebound,
            cap=cap,
            step=5,
        )
        for floor, multiple, rebound, cap in product(
            [0.25, 0.35, 0.5], [1.5, 2.5], [0.03, 0.06], [0.25, 0.5]
        )
    ]


def caps(days, p, cs, period):
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    risk, _, ma, _ = engine.features(p)
    n = len(cs)
    state = np.ones(n, bool)
    high = np.full(n, p[lo])
    low = high.copy()
    result = np.ones((n, len(p)))
    multiples = np.array([c["multiple"] for c in cs])
    rebounds = np.array([c["rebound"] for c in cs])
    defensive = np.array([c["cap"] for c in cs])
    for s in range(lo, hi):
        high = np.where(state, np.maximum(high, p[s]), high)
        low = np.where(~state, np.minimum(low, p[s]), low)
        if (s - lo) % 5 == 0:
            threshold = np.clip(multiples * risk[21][s] / np.sqrt(12), 0.04, 0.25)
            leaving = state & (p[s] / high - 1 < -threshold)
            entering = ~state & (
                (p[s] / low - 1 >= rebounds)
                | ((p[s] > ma[63][s]) & (risk[10][s] < risk[126][s]))
            )
            state = (state & ~leaving) | entering
            low = np.where(leaving, p[s], low)
            high = np.where(entering, p[s], high)
        result[:, s] = np.where(state, 1, defensive)
    return result


def passive(days, p, targets, period, fee=0.0012, delay=1):
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    n = len(targets)
    cash, units, fees = np.full(n, 3500.0), np.zeros(n), np.zeros(n)
    last = np.full(n, np.nan)
    curve = [cash.copy()]
    for i in range(lo + 1, hi):
        s = i - delay
        if s >= lo:
            target = targets[:, s]
            changed = target != last
            old = units * p[i]
            nav = cash + old
            buying = target * nav > old
            amount = (
                target
                * (nav + np.where(buying, fee * old, -fee * old))
                / (1 + np.where(buying, fee * target, -fee * target))
            )
            new = np.where(changed, np.floor(amount / p[i] + 1e-10), units)
            delta = new - units
            cost = abs(delta) * p[i] * fee
            cash -= delta * p[i] + cost
            fees += cost
            units, last = new, target
            assert np.all(cash >= -1e-6)
        curve.append(cash + units * p[i])
    return np.asarray(curve), fees


def evaluate(days, p, cs, period, fee=0.0012, delay=1):
    limits = np.vstack([np.ones(len(p)), caps(days, p, cs, period)])
    f = engine.common.regression.previous.prepare(days, p)
    active = engine.common.regression.simulate(
        days,
        p,
        p,
        f,
        [
            engine.common.BASE,
            *[dict(**engine.common.BASE, floor=c["floor"]) for c in cs],
        ],
        period,
        fee=fee,
        delay=delay,
        initial_capital=6500.0,
        exposure_caps=limits,
        keep_curve=True,
    )
    curve, fees = passive(days, p, limits, period, fee, delay)
    curve += np.asarray(active["curve"])
    fees += [m["fees"] for m in active["metrics"]]
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    years = (
        engine.date.fromisoformat(days[hi - 1]) - engine.date.fromisoformat(days[lo])
    ).days / 365.25
    units = np.floor(10000 / (p[lo + delay] * (1 + fee)) + 1e-10)
    cost = units * p[lo + delay] * fee
    bh = np.full(hi - lo, 10000.0)
    bh[delay:] = 10000 - units * p[lo + delay] * (1 + fee) + units * p[lo + delay : hi]
    metrics = engine.common.metrics(
        np.column_stack([bh, curve]), years, np.r_[cost, fees]
    )
    return [{k: float(v[j]) for k, v in metrics.items()} for j in range(len(cs) + 2)]


if __name__ == "__main__":
    engine.OUT = Path("data/backtests/sp500-drawdown-overlay.json")
    engine.PLAN = {
        **engine.PLAN,
        "change": "Third and FINAL campaign, declared after reserved five-year results of the first two: do not treat those results as unseen. Protect slow/defensive/passive books with a common stop; raise normal defensive floor25/35/50% to try compensating opportunity costs. Original thresholds, schedules and warm replay unchanged. Never reselect against earlier reserved markets.",
        "selection": engine.PLAN["selection"].replace(
            "210000..210149", "810000..810149"
        ),
        "audit": engine.PLAN["audit"]
        .replace("220000..220999", "820000..820999")
        .replace("230000..230299", "830000..830299"),
        "execution": "Independent original budgets4875/1625/3500EUR; original active state logic with defensive floor25/35/50%. All target weights capped25/50% while common adaptive stop is off. Each book rebalances only on desired target change. Stops use current close and execute next (delay2 stress); no band or cross-book transfers. Other conditions and metrics same as previous two campaigns.",
    }
    engine.grid = grid
    engine.evaluate = evaluate
    engine.main(seed_offset=600000, **engine.arguments())
