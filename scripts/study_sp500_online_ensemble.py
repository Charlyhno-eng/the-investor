"""Third declared branch: causal online expert mixing, ETF/cash only.

PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_online_ensemble.py
"""

import argparse
from itertools import product
from pathlib import Path

import numpy as np
import study_sp500_deep_search as engine

OUT = Path("data/backtests/sp500-online-ensemble.json")
ORIGINAL_WEIGHTS = engine.weights
PLAN = {
    **engine.PLAN,
    "novelty": "Third branch declared after both historical screens failed, BEFORE reviewing the first branch selection or any reserved outcomes. Hypothesis: complementary rules may be mixed using ONLY their previous performance and risk instead of selecting a fixed ex-post winner.324fixed policies vary trailing63/126/252sessions, learning rate2/5/10, variance penalty0/3/6, rolling DD penalty0/1, floor10/25%, and original v4 initial budget0/35/65%. Same strict objective and all audits; no threshold relaxation. No automatic adoption.",
    "signals": "Five advisory ETF/cash experts: warmed regression-state fixed target mix4875/1625/3500 (v5-inspired, NOT exact drift/rounding v5),90/10regression states floor10% with defensive exit2, CUSUM5/rebound6%/floor25%,CUSUM8/rebound6%/floor25%,Markov.98/multiple1.5/floor25%. Slow native60calendar-month z and original daily-cross monthly state; defensive18m state replayed on GLOBAL5session grid, not cold test restart. All signal models use prefixes only. Advisory expert daily return uses TWO-close-lag targets for next-close execution and.12%turnover proxy; no integer claim for advisory models. Actual trading ledger pays its own exact fees and whole shares, no historical profits credited. Scores are trailing annualized mean log return minus variance penalty*annual variance/2 minus DDpenalty*rolling loss. Softmax learning rate, fixed prior weights50/12.5/12.5/12.5/12.5. No winner selected using future returns. Core v4 account remains exact if allocated. Negative evidence and costs can defeat the mixture.",
    "selection": engine.PLAN["selection"].replace(
        "1310000..1310199", "1510000..1510199"
    ),
    "audit": engine.PLAN["audit"]
    .replace("1320000..1320999", "1520000..1520999")
    .replace("1330000..1330299", "1530000..1530299"),
    "sources": [*engine.PLAN["sources"], "https://arxiv.org/abs/1604.03266"],
}


def grid():
    return [
        dict(
            family="online_ensemble",
            window=w,
            eta=eta,
            aversion=aversion,
            dd_penalty=dd,
            floor=floor,
            active=active,
            step=5,
        )
        for w, eta, aversion, dd, floor, active in product(
            [63, 126, 252], [2, 5, 10], [0, 3, 6], [0, 1], [0.1, 0.25], [0, 0.35, 0.65]
        )
    ]


def experts(days, p, regression_scores=None):
    if regression_scores is None:
        f = engine.common.common.regression.previous.prepare(days, p)[0]
        regression_scores = f[60][0], f[18][0]
    z60, z18 = regression_scores
    state = False
    defensive = np.zeros(2, dtype=bool)
    targets = np.empty((2, len(p)))
    for i in range(len(p)):
        if i > 0 and days[i][:7] != days[i - 1][:7] and np.isfinite(z60[i]):
            if state:
                state = z60[i] <= 1.5
            else:
                state = z60[i] < -2 or (z60[i - 1] < 0 and z60[i] >= 0)
        if i > 0 and i % 5 == 0 and np.isfinite(z18[i]):
            defensive = np.where(
                defensive,
                z18[i] <= np.array([1.5, 2.0]),
                (z18[i - 1] < -0.5) & (z18[i] >= -0.5),
            )
        targets[0, i] = (
            0.4875 * (1 if state else 0.25)
            + 0.1625 * (1 if defensive[0] else 0.25)
            + 0.35
        )
        targets[1, i] = 0.9 * (1 if state else 0.1) + 0.1 * (1 if defensive[1] else 0.1)
    cs = [
        dict(family="cusum", threshold=h, rebound=0.06, floor=0.25, step=1, active=0)
        for h in [5, 8]
    ]
    cs.append(
        dict(
            family="markov",
            persistence=0.98,
            multiple=1.5,
            power=1,
            floor=0.25,
            step=5,
            active=0,
        )
    )
    targets = np.vstack([targets, ORIGINAL_WEIGHTS(p, cs)])
    r = np.r_[0, np.diff(p) / p[:-1]]
    holding = np.column_stack([np.zeros((5, 2)), targets[:, :-2]])
    executed = np.column_stack([np.zeros(5), targets[:, :-1]])
    turnover = np.abs(executed - np.column_stack([np.zeros(5), executed[:, :-1]]))
    returns = holding * r - 0.0012 * turnover
    assert np.all(returns > -0.99)
    return targets, np.log1p(returns)


def weights(p, cs, days=None, regression_scores=None):
    assert days is not None
    target, lr = experts(days, p, regression_scores)
    cache = {}
    prior = np.array([0.5, 0.125, 0.125, 0.125, 0.125])[:, None]
    result = []
    for c in cs:
        w = c["window"]
        if w not in cache:
            average = engine.common.common.average
            mu = average(lr, w) * 252
            variance = np.maximum(average(lr * lr, w) - (mu / 252) ** 2, 0) * 252
            # Rolling drawdown of each advisory model, no future peak allowed.
            wealth = np.exp(np.cumsum(lr, axis=1))
            padded = np.pad(wealth, ((0, 0), (w - 1, 0)), mode="edge")
            peak = np.lib.stride_tricks.sliding_window_view(padded, w, axis=1).max(
                axis=2
            )
            loss = 1 - wealth / peak
            cache[w] = mu, variance, loss
        mu, var, loss = cache[w]
        score = np.nan_to_num(
            c["eta"] * (mu - 0.5 * c["aversion"] * var - c["dd_penalty"] * loss),
            nan=0.0,
        )
        score -= score.max(axis=0)
        allocation = prior * np.exp(np.clip(score, -50, 0))
        allocation /= allocation.sum(axis=0)
        result.append(np.clip((allocation * target).sum(axis=0), c["floor"], 1))
    return np.array(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=2)
    engine.OUT, engine.PLAN, engine.grid, engine.weights = OUT, PLAN, grid, weights
    engine.main(seed_offset=200000, **vars(parser.parse_args()))
