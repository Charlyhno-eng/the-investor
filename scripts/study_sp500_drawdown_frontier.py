"""Drawdown research against adopted v5; prefix signals and independent books.

PYTHONPATH=backend:scripts uv run python scripts/study_sp500_drawdown_frontier.py
The plan is written before any results. Production is never edited by this script.
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
import study_sp500_ratio_tradeoff as common
from study_sp500_amundi_upside import average

from investor import db
from investor.portfolio.sp500_simulation import (
    Sp500SimulationRequest,
    future_sessions,
    sampled_returns,
    simulate_history,
)

OUT = Path("data/backtests/sp500-drawdown-frontier.json")
PLAN = {
    "reference": "Adopted core35_slow_defensive_v5, not v4. PSP5 own EUR history; private DB copy. Generator unchanged.",
    "change": "New combinations: downside rather than symmetric risk, trend votes coupled to risk, rolling (not permanent) drawdown budgets with rebound override, volatility-scaled stops with fast rebound, shock gates with partial recovery, shrunk return/risk sizing. Full replacements and independent v4/tactical books at 35/65 and 65/35. Prior rejected single-factor variants not reinstated verbatim.",
    "selection": "150 five-year markets seeds210000..210149 plus already examined real3/5/10 years. Mean CAGR >=v5-0.25pp; mean loss and95th percentile loss <=90%v5; vol<=v5; all3 mean ratios>=v5. Historical each CAGR>=v5-0.75pp and DDloss<=v5+1pp. Rank qualified by smallest95th percentile loss, then CAGR. If none freeze ONE diagnostic by smallest worst normalized violation, then CAGR. No fallback adoption.",
    "audit": "Freeze once, then1000 five-year seeds220000..220999 and300 ten-year230000..230299. EACH horizon must retain selection synthetic gates, paired bootstrap95% lower CAGR delta>=-0.5pp, positive lower95% DD improvement. Historical1/3/5/10 and >=75%of completed quarterly five-year windows: CAGR>=v5-0.75pp, DDloss<=v5+1pp. Double fees and delay2 retain same historical3/5/10 gates. All required for implementation. No reselection on audit.",
    "execution": "10000EUR, integer shares per independent book, .0012 each side, zero cash yield, no leverage/shorts, next close (delay2 stress). Tactical decisions daily or5 sessions,5pp no-trade band. No rebalance between books. Fees charged per actual order, no end liquidation. Pending targets computed using positions known at signal, not execution.",
    "limits": "Repeated search on same history, overlapping real windows, synthetic seeds do not create independent economic evidence. No guaranteed drawdown floor. Academic ideas adapted, not literal replication. No new asset/currency or user DB change.",
    "sources": [
        "https://www.nber.org/papers/w22208",
        "https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing",
    ],
}


def grid():
    rules = []
    for window, target, floor, power in product(
        [10, 42, 84], [0.08, 0.10, 0.12], [0.2, 0.5], [1, 2]
    ):
        rules.append(
            dict(
                family="downside",
                window=window,
                target=target,
                floor=floor,
                power=power,
                step=5,
            )
        )
    for target, floor, mode in product(
        [0.12, 0.16, 0.20], [0.2, 0.5], ["soft", "votes"]
    ):
        rules.append(
            dict(family="trend_risk", target=target, floor=floor, mode=mode, step=5)
        )
    for window, budget, floor, rebound in product(
        [63, 126, 252], [0.08, 0.12, 0.18], [0.2, 0.5], [False, True]
    ):
        rules.append(
            dict(
                family="rolling_budget",
                window=window,
                budget=budget,
                floor=floor,
                rebound=rebound,
                step=5,
            )
        )
    for multiple, rebound, floor, step in product(
        [1.5, 2.5, 4], [0.03, 0.06], [0.2, 0.5], [1, 5]
    ):
        rules.append(
            dict(
                family="adaptive_stop",
                multiple=multiple,
                rebound=rebound,
                floor=floor,
                step=step,
            )
        )
    for ratio, recovery, floor in product([1.3, 1.7, 2.2], [0.025, 0.05], [0.2, 0.5]):
        rules.append(
            dict(
                family="shock_rebound",
                ratio=ratio,
                recovery=recovery,
                floor=floor,
                step=1,
            )
        )
    for prior, shrink, floor in product([0.04, 0.08, 0.12], [0.25, 0.5], [0.2, 0.5]):
        rules.append(
            dict(
                family="shrunk_growth", prior=prior, shrink=shrink, floor=floor, step=5
            )
        )
    return [dict(**r, active=active) for r in rules for active in [0, 0.35, 0.65]]


def features(p):
    r = np.r_[0, np.diff(p) / p[:-1]][None, :]
    windows = [10, 21, 42, 63, 84, 126, 252]
    risk = {
        w: np.sqrt(
            np.maximum(average(r * r, w) - average(r, w) ** 2, 0) * 252 * w / (w - 1)
        )[0]
        for w in windows
    }
    down = {w: np.sqrt(average(np.minimum(r, 0) ** 2, w) * 252)[0] for w in windows}
    ma = {w: average(p[None, :], w)[0] for w in [3, 10, 21, 63, 126, 252]}
    # Windows include only observations up to the current close.
    peak = {}
    for w in [63, 126, 252]:
        pad = np.r_[np.full(w - 1, p[0]), p]
        peak[w] = np.lib.stride_tricks.sliding_window_view(pad, w).max(axis=1)
    return risk, down, ma, peak


def tactical(days, p, cs, period, fee=0.0012, delay=1, target_weights=None):
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    risk, down, ma, peaks = features(p)
    n = len(cs)
    capitals = 10000.0 * (1 - np.array([c["active"] for c in cs], dtype=float))
    cash, units, fees = capitals.copy(), np.zeros(n), np.zeros(n)
    state = np.ones(n, bool)
    high, low = np.full(n, p[lo]), np.full(n, p[lo])
    curve = [cash.copy()]
    pending = {}
    # Precompute all exogenous targets once, then a vector book per daily close.
    weights = (
        np.ones((n, hi - lo)) if target_weights is None else target_weights[:, lo:hi]
    )
    for j, c in enumerate(cs) if target_weights is None else []:
        family, floor = c["family"], c["floor"]
        if family == "downside":
            t = (c["target"] / np.maximum(down[c["window"]], 1e-8)) ** c["power"]
        elif family == "trend_risk":
            if c["mode"] == "votes":
                signal = np.mean([p > ma[w] for w in [21, 63, 126, 252]], axis=0)
            else:
                z = np.log(p / ma[126]) / np.maximum(risk[63] * np.sqrt(0.5), 1e-8)
                signal = np.clip(0.5 + z, 0, 1)
            t = (floor + (1 - floor) * signal) * np.minimum(
                1, c["target"] / np.maximum(risk[21], 1e-8)
            )
        elif family == "rolling_budget":
            dd = 1 - p / peaks[c["window"]]
            t = 1 - dd / c["budget"]
            if c["rebound"]:
                prior_ma = np.r_[np.full(5, np.nan), ma[21][:-5]]
                t = np.where((p > ma[21]) & (ma[21] > prior_ma), 1, t)
        elif family == "shrunk_growth":
            # Shrink noisy one-year return to a fixed prior; no fitted future mean.
            lr = np.r_[np.zeros(252), np.log(p[252:] / p[:-252])]
            mu = c["shrink"] * lr + (1 - c["shrink"]) * c["prior"]
            t = mu / (4 * np.maximum(risk[63] ** 2, 1e-8))
        elif family in ["pullback", "rsi_reversal", "trend_pullback"]:
            if family == "rsi_reversal":
                ret = np.r_[0, np.diff(p) / p[:-1]][None, :]
                gain = average(np.maximum(ret, 0), c["window"])[0]
                loss = average(np.maximum(-ret, 0), c["window"])[0]
                balance = (gain - loss) / np.maximum(gain + loss, 1e-12)
                t = 0.8 - c["amplitude"] * balance
            else:
                z = np.log(p / ma[c["window"]]) / np.maximum(
                    risk[21] * np.sqrt(c["window"] / 252), 1e-8
                )
                base = c.get("base", 0.85)
                if family == "trend_pullback":
                    base = np.where(ma[63] > ma[252], 0.95, 0.55)
                t = base - c["amplitude"] * z
            # Distinct from the preexisting multiasset mean-reversion strategy:
            # continuous exposure, no cross-asset funding, optional crash gate.
            if c["guard"] == "trend":
                t = np.where((p < ma[252]) & (p < ma[10]), np.minimum(t, 0.5), t)
            elif c["guard"] == "shock":
                t = np.where(
                    (risk[10] > 1.5 * risk[126]) & (p < ma[10]), np.minimum(t, floor), t
                )
        elif family in ["adaptive_stop", "shock_rebound"]:
            continue
        else:
            raise ValueError(family)
        weights[j] = np.clip(t[lo:hi], floor, 1)
    families = np.array([c["family"] for c in cs])
    stop = families == "adaptive_stop"
    shock = families == "shock_rebound"
    multiples = np.array([c.get("multiple", 0) for c in cs])
    rebounds = np.array([c.get("rebound", c.get("recovery", 0)) for c in cs], float)
    floors = np.array([c["floor"] for c in cs])
    ratios = np.array([c.get("ratio", 0) for c in cs])
    steps = np.array([c["step"] for c in cs])
    for i in range(lo, hi):
        if i in pending:
            target, due = pending.pop(i)
            old = units * p[i]
            nav = cash + old
            buying = target * nav > old
            amount = (
                target
                * (nav + np.where(buying, fee * old, -fee * old))
                / (1 + np.where(buying, fee * target, -fee * target))
            )
            new = np.where(due, np.floor(amount / p[i] + 1e-10), units)
            delta = new - units
            cost = abs(delta) * p[i] * fee
            cash -= delta * p[i] + cost
            fees += cost
            units = new
            assert np.all(cash >= -1e-6)
        nav = cash + units * p[i]
        if i > lo:
            curve.append(nav.copy())
        high = np.where(state, np.maximum(high, p[i]), high)
        low = np.where(~state, np.minimum(low, p[i]), low)
        threshold = np.clip(multiples * risk[21][i] / np.sqrt(12), 0.04, 0.25)
        exit_ = (stop & (p[i] / high - 1 < -threshold)) | (
            shock & (risk[10][i] > ratios * risk[126][i]) & (p[i] < ma[21][i])
        )
        entry = (p[i] / low - 1 >= rebounds) | (
            (p[i] > ma[63][i]) & (risk[10][i] < risk[126][i])
        )
        scheduled = (i - lo) % steps == 0
        leaving = state & scheduled & exit_
        entering = ~state & scheduled & entry
        state = (state & ~leaving) | entering
        low = np.where(leaving, p[i], low)
        high = np.where(entering, p[i], high)
        t = weights[:, i - lo].copy()
        t = np.where(stop | shock, np.where(state, 1, floors), t)
        due = scheduled & ((i == lo) | (abs(t - units * p[i] / nav) >= 0.05))
        if i + delay < hi:
            pending[i + delay] = t, due
    return np.asarray(curve), fees


def evaluate(days, p, cs, period, fee=0.0012, delay=1):
    # Several real active budgets, no rescaling of a rounded EUR10000 backtest.
    shares = sorted({0.65, *[c["active"] for c in cs if c["active"]]})
    f = common.regression.previous.prepare(days, p)
    a = common.regression.simulate(
        days,
        p,
        p,
        f,
        [common.BASE] * len(shares),
        period,
        fee=fee,
        delay=delay,
        initial_capital=10000 * np.array(shares),
        keep_curve=True,
    )
    active = np.asarray(a["curve"])
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    curves, costs = [], []
    for capital in [10000, 3500]:
        units = np.floor(capital / (p[lo + delay] * (1 + fee)) + 1e-10)
        cost = units * p[lo + delay] * fee
        passive = np.full(hi - lo, float(capital))
        passive[delay:] = (
            capital - units * p[lo + delay] * (1 + fee) + units * p[lo + delay : hi]
        )
        if capital == 3500:
            j = shares.index(0.65)
            passive += active[:, j]
            cost += a["metrics"][j]["fees"]
        curves.append(passive)
        costs.append(cost)
    curve, fees = tactical(days, p, cs, period, fee, delay)
    for j, c in enumerate(cs):
        if c["active"]:
            k = shares.index(c["active"])
            curve[:, j] += active[:, k]
            fees[j] += a["metrics"][k]["fees"]
    all_curves = np.column_stack([*curves, curve])
    metrics = common.metrics(all_curves, years, np.r_[costs, fees])
    return [{k: float(v[j]) for k, v in metrics.items()} for j in range(len(cs) + 2)]


def stats(paths):
    return dict(
        means=common.summarize(paths),
        loss95=np.quantile(
            [[-m["max_drawdown"] for m in p] for p in paths], 0.95, axis=0
        ).tolist(),
        loss_max=np.max(
            [[-m["max_drawdown"] for m in p] for p in paths], axis=0
        ).tolist(),
    )


def violations(s, j):
    o, c = s["means"][1], s["means"][j]
    return [
        (o["cagr"] - 0.0025 - c["cagr"]) / 0.01,
        (-c["max_drawdown"] + 0.9 * o["max_drawdown"]) / 0.02,
        (s["loss95"][j] - 0.9 * s["loss95"][1]) / 0.02,
        (c["volatility"] - o["volatility"]) / 0.01,
        *[(o[k] - c[k]) / 0.05 for k in common.RATIOS],
    ]


def historical_ok(rows, j):
    o, c = rows[1], rows[j]
    return (
        c["cagr"] >= o["cagr"] - 0.0075
        and c["max_drawdown"] >= o["max_drawdown"] - 0.01
    )


def audit_summary(paths):
    s = stats(paths)
    rng = np.random.default_rng(20261116)
    ci, wins = {}, {}
    for k in s["means"][0]:
        delta = np.array([p[2][k] - p[1][k] for p in paths])
        ci[k] = np.quantile(
            delta[rng.integers(len(paths), size=(3000, len(paths)))].mean(axis=1),
            [0.025, 0.975],
        ).tolist()
        wins[k] = float(np.mean(delta < 0 if k in common.LOWER else delta > 0))
    s.update(
        paired_ci95=ci,
        wins_vs_current=wins,
        paths=paths,
        passed=max(violations(s, 2)) <= 1e-12
        and ci["cagr"][0] >= -0.005
        and ci["max_drawdown"][0] > 0,
    )
    return s


def sampled_case(args):
    days, p, configs, years, seed = args
    future = future_sessions(date.fromisoformat(days[-1]), years)
    pp = np.r_[
        p,
        p[-1]
        * np.exp(np.cumsum(sampled_returns(np.diff(np.log(p)), len(future), seed))),
    ]
    return evaluate(days + future, pp, configs, [days[-1], future[-1]])


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Retain frozen selection and source snapshot",
    )
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=1)
    return vars(parser.parse_args())


def main(seed_offset=0, resume=False, workers=1):
    cs = grid()
    report = (
        json.loads(OUT.read_text())
        if resume
        else dict(plan=PLAN, configs=cs, count=len(cs), adopted=False)
    )
    if resume:
        assert report["configs"] == cs and "chosen" in report
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
            assert digest == report["snapshot_sha256"], (
                "Historical source changed; do not resume"
            )
        report["snapshot_sha256"] = digest
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        p = np.array([r[1] for r in rows])
        assert np.array_equal(p, [r[2] for r in rows])
        report["source"] = dict(start=days[0], end=days[-1], observations=len(days))
        hist = (
            report["historical_screen"]
            if resume
            else {
                str(y): evaluate(days, p, cs, [f"{2026 - y}-11-13", days[-1]])
                for y in [3, 5, 10]
            }
        )
        report["historical_screen"] = hist
        save()

        def batch(configs, years, seed, count):
            paths = []
            tasks = ((days, p, configs, years, seed + i) for i in range(count))
            pool = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
            results = (
                pool.map(sampled_case, tasks) if pool else map(sampled_case, tasks)
            )
            for i, result in enumerate(results):
                paths.append(result)
                if i == 0:
                    prod = simulate_history(
                        rows, Sp500SimulationRequest(years=years, seed=seed)
                    )["comparison"]["metrics"]
                    for j, key in [(0, "benchmark"), (1, "strategy")]:
                        for k, val in paths[-1][j].items():
                            np.testing.assert_allclose(
                                val, prod[key][k], atol=1e-9, rtol=0, err_msg=k
                            )
                if (i + 1) % 25 == 0:
                    print("batch", years, seed, i + 1, "/", count, flush=True)
            if pool:
                pool.shutdown()
            return paths

        train = (
            report["training"]["paths"]
            if resume
            else batch(cs, 5, 210000 + seed_offset, 150)
        )
        s = stats(train)
        qualified = [
            j
            for j in range(2, len(cs) + 2)
            if max(violations(s, j)) <= 1e-12
            and all(historical_ok(ms, j) for ms in hist.values())
        ]

        def penalty(j):
            v = violations(s, j)
            for ms in hist.values():
                v.extend(
                    [
                        (ms[1]["cagr"] - 0.0075 - ms[j]["cagr"]) / 0.01,
                        (ms[1]["max_drawdown"] - 0.01 - ms[j]["max_drawdown"]) / 0.02,
                    ]
                )
            return max(v)

        chosen = (
            min(qualified, key=lambda j: (s["loss95"][j], -s["means"][j]["cagr"]))
            if qualified
            else min(
                range(2, len(cs) + 2),
                key=lambda j: (penalty(j), -s["means"][j]["cagr"]),
            )
        )
        if resume:
            assert report["chosen"] == cs[chosen - 2], "Frozen selection changed"
        report.update(
            training=dict(
                **s,
                paths=train,
                qualified=qualified,
                worst_violation=[penalty(j) for j in range(2, len(cs) + 2)],
            ),
            chosen=cs[chosen - 2],
            chosen_index=chosen - 2,
            diagnostic_only=not bool(qualified),
        )
        save()
        print("FROZEN", report["chosen"], "qualified", len(qualified), flush=True)
        selected = [report["chosen"]]
        report.setdefault("audit", {})
        for y, seed, count in [
            (5, 220000 + seed_offset, 1000),
            (10, 230000 + seed_offset, 300),
        ]:
            if str(y) not in report["audit"]:
                report["audit"][str(y)] = audit_summary(batch(selected, y, seed, count))
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
        report["rolling_pass"] = sum(
            historical_ok(ms, 2) for ms in report["rolling"].values()
        )
        report["all_pass"] = (
            bool(qualified)
            and all(a["passed"] for a in report["audit"].values())
            and all(historical_ok(ms, 2) for ms in report["historical"].values())
            and report["rolling_pass"] >= 0.75 * len(report["rolling"])
            and all(
                historical_ok(ms, 2)
                for periods in report["stress"].values()
                for ms in periods.values()
            )
        )
        save()
        print("DONE", OUT, "PASS", report["all_pass"], flush=True)


if __name__ == "__main__":
    main(**arguments())
