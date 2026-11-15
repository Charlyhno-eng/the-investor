"""Broader causal long/cash research against v5; never edits production.

PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_deep_search.py
"""

import argparse
import hashlib
import json
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np
import study_sp500_drawdown_frontier as common
from scipy.signal import lfilter
from scipy.special import expit

from investor import db
from investor.portfolio.sp500_simulation import (
    Sp500SimulationRequest,
    future_sessions,
    sampled_returns,
    simulate_history,
)

OUT = Path("data/backtests/sp500-deep-search.json")
BASE = common.common.BASE
PLAN = {
    "objective": "Beat adopted core35_slow_defensive_v5, not just BH. Same PSP5 EUR, fee.0012, integer shares, no short, leverage, derivatives or new assets. Private SQLite copy only, no production edits or adoption.",
    "novelty": "Eight new/adapted tactical families: asymmetric prior-close channels; causal two-state Markov volatility/return posterior; MACD confidence allocation inspired by semi-Markov theory; local-linear Kalman FILTER (never smoother); standardized negative CUSUM with rebound reset; bounded two-asset OLMAR advisory updates; kernel conditional-return forecasting with labels fully matured before training; Markov-conditioned short reversal. Alone or separate35/65%v4 budgets. Joint regression search varies passive budget, internal slow/defensive budgets, defensive floor/exit/cadence and slow exit. Prior rejected policies not adopted; overlapping controls explicitly not new discoveries.",
    "selection": "200 five-year markets seeds1310000..1310199 and already examined historical3/5/10. Synthetic mean CAGR>=v5+0.5pp; mean DDloss<=v5+0.5pp,95th loss<=v5+1pp,vol<=1.10v5,Sharpe and Sortino>=v5-0.03. History EACH CAGR>=v5-0.25pp,mean gain>=0.5pp,DDloss<=v5+1pp,vol<=1.10v5. Rank qualified by mean CAGR,then lower loss95. If none freeze diagnostic minimizing worst normalized violation, then CAGR. Freeze ONE champion per family by same rule, plus overall champion; no reselection.",
    "audit": "Frozen champions only:1000 five-year seeds1320000..1320999 and300 ten-year1330000..1330299. Each horizon retains synthetic gates AND bootstrap95% lower paired CAGR improvement>0, upper DDloss increase<=0.5pp. Hist1/3/5/10 reported, gates3/5/10 as selection; >=75%of24quarterly5ywindows CAGR>=v5-0.5pp,DDloss<=v5+1pp,vol<=1.15v5. Fee doubled and delay2: retain history gates. Overall success requires selection and ALL audits. Family diagnostics can never become fallback adoption.",
    "execution": "10000EUR, fresh capital, adjusted=raw PSP5, cash yield0. Next close, delay2 stress;5pp band tactical, steps1/5. Warm tactical state replay with no gains; no missing data imputation from future. Regression exact independent accounts with their own integer orders and variable real budgets; passive initial buy once. No transfers or rebalance between accounts. No final liquidation. Fees applied to each actual trade, metrics252sessions and calendarCAGR.",
    "signals": "Markov fixed persistent transitions, bull drift8%/yr vs bear-12%, sigma estimated from causal252window with high-state multiplier1.5/2.5. Kalman loglevel/velocity fixed Q/R, prior-only recursive filtering. OLMAR predicts relative price from SMA, simplex[ETF,cash], limits advisory turnover; trading ledger then pays real fees at later prices. Kernel uses standardized3d/63d return and10/126volratio, matches past observations every5d over504/1008sessions,5d target labels ending no later than signal,21session refit, Gaussian bandwidth. All implemented as adaptations, not exact replications of cited multiasset papers or a fit of their published performance.",
    "limits": "Repeated search on already examined2014+history. New seeds are only independent random draws within SAME economic model, not independent financial validation. Overlapping windows, selection/multiplicity bias; all failures retained. No2000/2008crisis for PSP5. Taxes omitted,cash0. No guarantees; probabilistic model parameters are assumptions, not reliable forecasts. No CVaR reintroduced.",
    "undefined_metrics": "Retain all-cash paths; undefined ratios stored null, means use explicit valid denominators, require >=95%valid paths for each gated ratio. Early unavailable volatility uses fixed16%annual prior, never future backfill. This serialization/warmup clarification was made before any selection-market results.",
    "sources": [
        "https://concretumgroup.com/wp-content/uploads/2026/02/A-Century-of-Profitable-Industry-Trends.pdf",
        "https://www.nber.org/papers/w10080",
        "https://www.nber.org/papers/w17182",
        "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4217513",
        "https://arxiv.org/abs/1811.11618",
        "https://icml.cc/2012/papers/168.pdf",
        "https://onlinelibrary.wiley.com/doi/10.1111/j.1467-9965.2006.00274.x",
        "https://arxiv.org/abs/1909.04327",
        "https://www.web.stanford.edu/~boyd/papers/kelly.html",
        "https://www.aqr.com/-/media/AQR/Documents/Insights/White-Papers/Market-Timing-Sin-a-Little.pdf",
    ],
}


def grid():
    rules = []
    for entry, exit_, floor, step in product(
        [63, 126, 252], [21, 63], [0.25, 0.5], [1, 5]
    ):
        if exit_ < entry:
            rules.append(
                dict(
                    family="channel",
                    entry=entry,
                    exit_window=exit_,
                    floor=floor,
                    step=step,
                )
            )
    for persistence, multiple, floor, power in product(
        [0.95, 0.98, 0.995], [1.5, 2.5], [0.25, 0.5], [1, 2]
    ):
        rules.append(
            dict(
                family="markov",
                persistence=persistence,
                multiple=multiple,
                floor=floor,
                power=power,
                step=5,
            )
        )
    for fast, slow, floor, scale in product([21, 63], [126, 252], [0.25, 0.5], [1, 2]):
        rules.append(
            dict(family="macd", fast=fast, slow=slow, floor=floor, scale=scale, step=5)
        )
    for q, observation, floor, scale in product(
        [1e-5, 1e-4, 1e-3], [0.01, 0.03], [0.25, 0.5], [1, 2]
    ):
        rules.append(
            dict(
                family="kalman",
                q=q,
                observation=observation,
                floor=floor,
                scale=scale,
                step=5,
            )
        )
    for threshold, rebound, floor in product([3, 5, 8], [0.03, 0.06], [0.25, 0.5]):
        rules.append(
            dict(
                family="cusum",
                threshold=threshold,
                rebound=rebound,
                floor=floor,
                step=1,
            )
        )
    for window, epsilon, limit, step in product(
        [3, 5, 10], [1.0, 1.001, 1.005], [0.1, 0.3], [1, 5]
    ):
        rules.append(
            dict(
                family="olmar",
                window=window,
                epsilon=epsilon,
                limit=limit,
                floor=0.0,
                step=step,
            )
        )
    for window, bandwidth, aversion, floor in product(
        [504, 1008], [0.5, 1.5], [3, 6], [0.25, 0.5]
    ):
        rules.append(
            dict(
                family="kernel",
                window=window,
                bandwidth=bandwidth,
                aversion=aversion,
                floor=floor,
                step=5,
            )
        )
    for persistence, multiple, amplitude, floor in product(
        [0.95, 0.995], [1.5, 2.5], [0.15, 0.3], [0.25, 0.5]
    ):
        rules.append(
            dict(
                family="regime_reversal",
                persistence=persistence,
                multiple=multiple,
                amplitude=amplitude,
                floor=floor,
                step=5,
            )
        )
    cs = [dict(**r, active=a) for r in rules for a in [0, 0.35, 0.65]]
    for passive, share, floor, exit_, step, slow_exit in product(
        [0, 0.2, 0.35],
        [0.5, 0.65, 0.75, 0.85],
        [0.15, 0.25, 0.35],
        [1.25, 1.5, 1.75, 2],
        [1, 5, 10],
        ["level1.5", "level2"],
    ):
        reg = dict(
            **BASE,
            slow_share=share,
            floor=floor,
            defensive_exit=exit_,
            defensive_step=step,
        )
        reg["exit"] = slow_exit
        cs.append(dict(family="regression_joint", passive=passive, regression=reg))
    return cs


def ema(values, span):
    alpha = 2 / (span + 1)
    return lfilter([alpha], [1, -(1 - alpha)], values, zi=[values[0] * (1 - alpha)])[0]


def weights(p, cs, days=None):
    r = np.r_[0, np.diff(p) / p[:-1]]
    risk, _, _, _ = common.features(p)
    # Fixed warm-up prior, never backfill missing early windows from later data.
    risk = {w: np.nan_to_num(v, nan=0.16) for w, v in risk.items()}
    sigma = np.maximum(risk[252] / np.sqrt(252), 0.003)
    ret3 = np.r_[np.zeros(3), p[3:] / p[:-3] - 1]
    ret63 = np.r_[np.zeros(63), p[63:] / p[:-63] - 1]
    cache, posteriors, filters, extrema = {}, {}, {}, {}

    def posterior(c):
        key = c["persistence"], c["multiple"]
        if key not in posteriors:
            persistence, multiple = key
            prob, path = 0.8, np.empty(len(p))
            for i in range(len(p)):
                prior = prob * persistence + (1 - prob) * (1 - persistence)
                # Stable log likelihood ratio. No backward smoothed probability.
                low, high = sigma[i] * 0.7, sigma[i] * multiple
                ll = (
                    np.log(high / low)
                    - 0.5 * ((r[i] - 0.08 / 252) / low) ** 2
                    + 0.5 * ((r[i] + 0.12 / 252) / high) ** 2
                )
                prob = expit(np.log(prior / (1 - prior)) + ll)
                path[i] = prob
            posteriors[key] = path
        return posteriors[key]

    def extreme(window, maximum):
        key = window, maximum
        if key not in extrema:
            padded = np.r_[np.full(window, p[0]), p[:-1]]
            a = np.lib.stride_tricks.sliding_window_view(padded, window)
            extrema[key] = a.max(axis=1) if maximum else a.min(axis=1)
        return extrema[key]

    result = []
    for c in cs:
        key = json.dumps({k: v for k, v in c.items() if k != "active"}, sort_keys=True)
        if key in cache:
            result.append(cache[key])
            continue
        family, floor = c["family"], c["floor"]
        if family == "markov":
            t = floor + (1 - floor) * posterior(c) ** c["power"]
        elif family == "regime_reversal":
            short = ret3 / np.maximum(risk[21] * np.sqrt(3 / 252), 0.005)
            bullish = np.clip(0.9 - c["amplitude"] * short, floor, 1)
            t = floor + posterior(c) * (bullish - floor)
        elif family == "macd":
            signal = np.log(ema(p, c["fast"]) / ema(p, c["slow"])) / np.maximum(
                risk[63] * np.sqrt(c["fast"] / 252), 0.005
            )
            t = floor + (1 - floor) * expit(c["scale"] * 3 * signal)
        elif family == "kalman":
            fkey = c["q"], c["observation"]
            if fkey not in filters:
                # Local linear trend: [log level, daily velocity], causal filter.
                x = np.array([np.log(p[0]), 0.08 / 252])
                cov = np.diag([0.01, 0.0001])
                F = np.array([[1.0, 1.0], [0.0, 1.0]])
                Q = np.diag([c["q"] * 0.01, c["q"] * 0.0001])
                R = c["observation"] ** 2
                confidence = np.empty(len(p))
                for i, y in enumerate(np.log(p)):
                    pred = F @ x
                    pc = F @ cov @ F.T + Q
                    gain = pc[:, 0] / (pc[0, 0] + R)
                    x = pred + gain * (y - pred[0])
                    cov = pc - np.outer(gain, pc[0])
                    confidence[i] = x[1] / np.sqrt(max(cov[1, 1], 1e-15))
                filters[fkey] = confidence
            t = floor + (1 - floor) * expit(c["scale"] * filters[fkey])
        elif family in ["channel", "cusum"]:
            t = np.empty(len(p))
            state, low, evidence = False, p[0], 0.0
            if family == "channel":
                highs, lows = (
                    extreme(c["entry"], True),
                    extreme(c["exit_window"], False),
                )
            for i in range(len(p)):
                low = min(low, p[i]) if not state else p[i]
                if family == "channel":
                    if i >= c["entry"]:
                        if state and p[i] < lows[i]:
                            state = False
                        elif not state and p[i] >= highs[i]:
                            state = True
                else:
                    evidence = max(0, evidence - r[i] / sigma[i] - 0.1)
                    if state and evidence > c["threshold"]:
                        state, low = False, p[i]
                    elif not state and (
                        p[i] / low - 1 >= c["rebound"]
                        or (i >= 63 and ret63[i] > 0 and evidence == 0)
                    ):
                        state, evidence = True, 0.0
                t[i] = 1 if state else floor
        elif family == "olmar":
            predicted = common.common.average(p[None, :], c["window"])[0] / p
            t, w = np.empty(len(p)), 0.5
            for i in range(len(p)):
                w = w * (1 + r[i]) / (1 + w * r[i])
                diff = predicted[i] - 1
                # Two-dimensional OLMAR projection onto ETF+cash simplex.
                loss = max(0, c["epsilon"] - (1 + w * diff))
                move = loss / diff if abs(diff) > 1e-10 else 0.0
                w = float(np.clip(w + np.clip(move, -c["limit"], c["limit"]), 0, 1))
                t[i] = w
        elif family == "kernel":
            x = np.column_stack(
                [
                    ret3 / np.maximum(risk[21] * np.sqrt(3 / 252), 0.005),
                    ret63 / np.maximum(risk[63] * 0.5, 0.005),
                    risk[10] / np.maximum(risk[126], 0.03) - 1,
                ]
            )
            x = np.clip(x, -5, 5)
            target = np.r_[p[5:] / p[:-5] - 1, np.zeros(5)]
            t = np.full(len(p), floor)
            for i in range(252, len(p), 21):
                ids = np.arange(max(63, i - c["window"]), i - 4, 5)
                assert np.all(ids + 5 <= i)
                distance = np.sum((x[ids] - x[i]) ** 2, axis=1)
                w = np.exp(-0.5 * distance / c["bandwidth"] ** 2)
                # Shrink to a fixed8% prior with20 pseudo-observations.
                forecast = (w @ target[ids] + 20 * 0.08 * 5 / 252) / (w.sum() + 20)
                exposure = (
                    forecast
                    * 252
                    / 5
                    / (c["aversion"] * max(risk[21][i] ** 2, 0.04**2))
                )
                t[i : i + 21] = np.clip(exposure, floor, 1)
        else:
            raise ValueError(family)
        t = np.clip(t, floor, 1)
        assert np.all(np.isfinite(t))
        cache[key] = t
        result.append(t)
    return np.asarray(result)


def evaluate(days, p, cs, period, fee=0.0012, delay=1):
    regids = [j for j, c in enumerate(cs) if c["family"] == "regression_joint"]
    tactids = [j for j, c in enumerate(cs) if c["family"] != "regression_joint"]
    tactical_cs = [cs[j] for j in tactids]
    active_shares = sorted({c["active"] for c in tactical_cs if c["active"]})
    configs = [
        BASE,
        *[cs[j]["regression"] for j in regids],
        *[BASE for _ in active_shares],
    ]
    capitals = 10000 * np.array(
        [0.65, *[1 - cs[j]["passive"] for j in regids], *active_shares]
    )
    f = common.common.regression.previous.prepare(days, p)
    a = common.common.regression.simulate(
        days,
        p,
        p,
        f,
        configs,
        period,
        fee=fee,
        delay=delay,
        initial_capital=capitals,
        keep_curve=True,
        keep_trace=False,
    )
    ac = np.asarray(a["curve"])
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25

    def passive(capital):
        units = np.floor(capital / (p[lo + delay] * (1 + fee)) + 1e-10)
        cost = units * p[lo + delay] * fee
        curve = np.full(hi - lo, float(capital))
        curve[delay:] = (
            capital - units * p[lo + delay] * (1 + fee) + units * p[lo + delay : hi]
        )
        return curve, cost

    bh, bhfee = passive(10000)
    core, corefee = passive(3500)
    curves = np.zeros((hi - lo, len(cs) + 2))
    costs = np.zeros(len(cs) + 2)
    curves[:, 0], costs[0] = bh, bhfee
    curves[:, 1], costs[1] = ac[:, 0] + core, a["metrics"][0]["fees"] + corefee
    for k, j in enumerate(regids, 1):
        pc, pf = passive(10000 * cs[j]["passive"])
        curves[:, j + 2] = ac[:, k] + pc
        costs[j + 2] = a["metrics"][k]["fees"] + pf
    if tactical_cs:
        tc, tf = common.tactical(
            days,
            p,
            tactical_cs,
            period,
            fee,
            delay,
            target_weights=weights(p, tactical_cs, days=days),
        )
        for k, j in enumerate(tactids):
            c = cs[j]
            if c["active"]:
                aidx = 1 + len(regids) + active_shares.index(c["active"])
                tc[:, k] += ac[:, aidx]
                tf[k] += a["metrics"][aidx]["fees"]
            curves[:, j + 2] = tc[:, k]
            costs[j + 2] = tf[k]
    metrics = common.common.metrics(curves, years, costs)
    return [
        {k: float(v[j]) if np.isfinite(v[j]) else None for k, v in metrics.items()}
        for j in range(len(cs) + 2)
    ]


def summary(paths):
    means, counts = [], []
    for j in range(len(paths[0])):
        m, n = {}, {}
        for key in paths[0][j]:
            valid = [row[j][key] for row in paths if row[j][key] is not None]
            m[key] = float(np.mean(valid)) if valid else None
            n[key] = len(valid)
        means.append(m)
        counts.append(n)
    losses = np.array([[-m["max_drawdown"] for m in row] for row in paths])
    return dict(
        means=means,
        valid_counts=counts,
        count=len(paths),
        loss95=np.quantile(losses, 0.95, axis=0).tolist(),
        loss_max=losses.max(axis=0).tolist(),
    )


def synthetic_violations(s, j):
    b, c = s["means"][1], s["means"][j]
    if any(
        c[k] is None or s["valid_counts"][j][k] < 0.95 * s["count"]
        for k in ["sharpe", "sortino"]
    ):
        return [1e6]
    return [
        (b["cagr"] + 0.005 - c["cagr"]) / 0.01,
        (b["max_drawdown"] - 0.005 - c["max_drawdown"]) / 0.01,
        (s["loss95"][j] - s["loss95"][1] - 0.01) / 0.02,
        (c["volatility"] - 1.1 * b["volatility"]) / 0.02,
        *[(b[k] - 0.03 - c[k]) / 0.1 for k in ["sharpe", "sortino"]],
    ]


def history_violations(hist, j):
    rows = [hist[str(y)] for y in [3, 5, 10]]
    return [
        (0.005 - np.mean([r[j]["cagr"] - r[1]["cagr"] for r in rows])) / 0.01,
        *[
            v
            for r in rows
            for v in [
                (r[1]["cagr"] - 0.0025 - r[j]["cagr"]) / 0.01,
                (r[1]["max_drawdown"] - 0.01 - r[j]["max_drawdown"]) / 0.01,
                (r[j]["volatility"] - 1.1 * r[1]["volatility"]) / 0.02,
            ]
        ],
    ]


def sampled(args):
    days, p, cs, years, seed = args
    future = future_sessions(date.fromisoformat(days[-1]), years)
    pp = np.r_[
        p,
        p[-1]
        * np.exp(np.cumsum(sampled_returns(np.diff(np.log(p)), len(future), seed))),
    ]
    return evaluate(days + future, pp, cs, [days[-1], future[-1]])


def main(resume=False, workers=4, seed_offset=0):
    cs = grid()
    report = (
        json.loads(OUT.read_text())
        if resume
        else dict(plan=PLAN, configs=cs, count=len(cs), adopted=False)
    )
    assert report["configs"] == cs and report["plan"] == PLAN
    OUT.parent.mkdir(parents=True, exist_ok=True)

    def save():
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    save()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "snapshot.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if resume:
            assert digest == report["snapshot_sha256"]
        report["snapshot_sha256"] = digest
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
        days, p = [r[0] for r in rows], np.array([r[1] for r in rows])
        assert np.array_equal(p, [r[2] for r in rows])
        report["source"] = dict(start=days[0], end=days[-1], observations=len(p))
        if "historical_screen" not in report:
            report["historical_screen"] = {
                str(y): evaluate(days, p, cs, [f"{2026 - y}-11-13", days[-1]])
                for y in [3, 5, 10]
            }
            save()

        def batch(configs, years, seed, count):
            paths = []
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for i, result in enumerate(
                    pool.map(
                        sampled,
                        ((days, p, configs, years, seed + i) for i in range(count)),
                    )
                ):
                    paths.append(result)
                    if i == 0:
                        prod = simulate_history(
                            rows, Sp500SimulationRequest(years=years, seed=seed)
                        )["comparison"]["metrics"]
                        for j, key in [(0, "benchmark"), (1, "strategy")]:
                            for k, value in result[j].items():
                                np.testing.assert_allclose(
                                    value, prod[key][k], rtol=0, atol=1e-9, err_msg=k
                                )
                    if (i + 1) % 25 == 0:
                        print("batch", years, seed, i + 1, "/", count, flush=True)
            return paths

        if "training" not in report:
            train = batch(cs, 5, 1310000 + seed_offset, 200)
            report["training"] = dict(**summary(train), paths=train)
            save()
        s = report["training"]

        def penalty(j):
            return max(
                synthetic_violations(s, j)
                + history_violations(report["historical_screen"], j)
            )

        qualified = [j for j in range(2, len(cs) + 2) if penalty(j) <= 1e-12]

        def pick(ids):
            eligible = [j for j in ids if penalty(j) <= 1e-12]
            return (
                max(eligible, key=lambda j: (s["means"][j]["cagr"], -s["loss95"][j]))
                if eligible
                else min(ids, key=lambda j: (penalty(j), -s["means"][j]["cagr"]))
            )

        champion = pick(list(range(2, len(cs) + 2)))
        champions = {
            family: pick(
                [j for j in range(2, len(cs) + 2) if cs[j - 2]["family"] == family]
            )
            - 2
            for family in sorted({c["family"] for c in cs})
        }
        chosen = list(dict.fromkeys([champion - 2, *champions.values()]))
        if "frozen_indices" in report:
            assert chosen == report["frozen_indices"]
        report.update(
            qualified=[j - 2 for j in qualified],
            champion_index=champion - 2,
            family_champions=champions,
            frozen_indices=chosen,
            selection_penalty=[penalty(j) for j in range(2, len(cs) + 2)],
        )
        save()
        print(
            "FROZEN",
            len(cs),
            "qualified",
            len(qualified),
            "champion",
            cs[champion - 2],
            flush=True,
        )
        selected = [cs[j] for j in chosen]
        report.setdefault("audit", {})
        for years, seed, count in [
            (5, 1320000 + seed_offset, 1000),
            (10, 1330000 + seed_offset, 300),
        ]:
            if str(years) in report["audit"]:
                continue
            paths = batch(selected, years, seed, count)
            a = dict(**summary(paths), paths=paths)
            rng = np.random.default_rng(seed)
            ids = rng.integers(count, size=(2000, count))
            a["paired_ci95"] = {
                k: np.quantile(
                    (
                        np.array([[m[k] for m in row] for row in paths])
                        - np.array([row[1][k] for row in paths])[:, None]
                    )[ids].mean(axis=1),
                    [0.025, 0.975],
                    axis=0,
                ).T.tolist()
                for k in ["cagr", "max_drawdown"]
            }
            a["loss_over30"] = [
                sum(row[j]["max_drawdown"] < -0.3 for row in paths)
                for j in range(len(selected) + 2)
            ]
            a["passed"] = [
                max(synthetic_violations(a, j)) <= 1e-12
                and a["paired_ci95"]["cagr"][j][0] > 0
                and a["paired_ci95"]["max_drawdown"][j][0] >= -0.005
                for j in range(2, len(selected) + 2)
            ]
            report["audit"][str(years)] = a
            save()
        report["historical"] = {
            str(y): evaluate(days, p, selected, [f"{2026 - y}-11-13", days[-1]])
            for y in [1, 3, 5, 10]
        }
        report["rolling"] = {
            f"{y}-{m:02}-13": evaluate(
                days, p, selected, [f"{y}-{m:02}-13", f"{y + 5}-{m:02}-13"]
            )
            for y in range(2016, 2022)
            for m in [2, 5, 8, 11]
            if f"{y + 5}-{m:02}-13" <= days[-1]
        }
        report["stress"] = {
            name: {
                str(y): evaluate(
                    days, p, selected, [f"{2026 - y}-11-13", days[-1]], **kw
                )
                for y in [3, 5, 10]
            }
            for name, kw in [
                ("double_fees", dict(fee=0.0024)),
                ("delay2", dict(delay=2)),
            ]
        }
        report["rolling_pass"] = [
            sum(
                ms[j]["cagr"] >= ms[1]["cagr"] - 0.005
                and ms[j]["max_drawdown"] >= ms[1]["max_drawdown"] - 0.01
                and ms[j]["volatility"] <= 1.15 * ms[1]["volatility"]
                for ms in report["rolling"].values()
            )
            for j in range(2, len(selected) + 2)
        ]
        report["all_pass"] = [
            chosen[k] in report["qualified"]
            and all(a["passed"][k] for a in report["audit"].values())
            and max(history_violations(report["historical"], k + 2)) <= 1e-12
            and report["rolling_pass"][k] >= 0.75 * len(report["rolling"])
            and all(
                max(history_violations(h, k + 2)) <= 1e-12
                for h in report["stress"].values()
            )
            for k in range(len(selected))
        ]
        save()
        print("DONE", OUT, "all_pass", report["all_pass"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    main(**vars(parser.parse_args()))
