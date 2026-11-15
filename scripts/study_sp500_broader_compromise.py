"""Broader single-ETF research, primary compromise vs ideal three-ratio objective.

PYTHONPATH=backend:scripts uv run python scripts/study_sp500_broader_compromise.py
No production changes. Persist plan before results; freeze before fresh draws.
"""

import hashlib
import json
import sqlite3
import tempfile
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

OUT = Path("data/backtests/sp500-broader-compromise.json")
PLAN = {
    "change": "User explicitly permits more risk and completely different strategies. Distinguish PRIMARY compromise from IDEAL three-ratio dominance. Previously rejected multiasset strategies not reinstated. No production adoption.",
    "primary": "On each synthetic horizon: mean CAGR>=current+1pp and >=BH-3pp; mean vol<=90%BH; mean absoluteDD<=90%BH; 95th percentile loss<=BH; each mean ratio>=97%BH. History3/5/10: each CAGR>=current-0.75pp, average CAGR gain>=0.25pp; each vol<=1.75current and <=90%BH; absDD<=90%BH and <=absDDcurrent+12pp. At least75% of quarterly5y windows retain CAGR>=current-0.75pp and reduce vol/DD>=10% vsBH. Double fees/delay2 retain positive average historical CAGR gain and same risk limits. No assertion of unchanged current risk.",
    "ideal": "All PRIMARY plus each mean Sharpe/Sortino/Calmar strictly higher than BH, >=55% paired wins in each. Report ratio failures separately; never claim full objective when only primary holds.",
    "selection": "All historical3/5/10 are ALREADY EXAMINED screening data (no independent validation claim). Search100 five-year draws seeds120000..120099. Rank primary-qualified by min relative mean ratio vsBH then CAGR. If none, freeze diagnostic with highest min ratio among mean-return/vol/DD eligible (or all). Freeze one before heldout seeds130000..1302995y and140000..14009910y. Fixed comparators: passive50%+v450%, constant80%, fullBH/current. Never reselect on heldout.",
    "execution": "PSP5 EUR own adjusted=raw history,10000EUR,whole units per sleeve,fee0.12%,cash0%,no leverage or shorts. Next close and delay2 stress. Independent hybrid pockets without transfers/rebalancing between sleeves; current v4 exact on its own initial capital, remainder passiveBH. New allocation policies weekly decisions and5pp band unless fixed quarterly allocation. TIPP/CPPI drawdown budgets have no guaranteed floor; minimum35% invested permits recovery.",
    "limits": "Repeated model search, common historical generator, no independent economic sample. Same stationary63block+5%noise app generator. Single ETF not globally diversified. No made-up correlations or assets from yield series. Ratios rate0 and252 annualization/calendarCAGR.",
}


def grid():
    cs = []
    for passive in [0.2, 0.35, 0.5, 0.65]:
        cs.append(dict(family="hybrid", passive=passive))
    for weight, step in product([0.7, 0.8, 0.9], [0, 63]):
        cs.append(dict(family="constant", weight=weight, step=step))
    for span, floor in product([100, 200, 300], [0.5, 0.65, 0.8]):
        cs.append(dict(family="smooth_trend", span=span, floor=floor))
    for ratio, cap in product([1.25, 1.5, 2], [0.4, 0.6, 0.8]):
        cs.append(dict(family="shock", ratio=ratio, cap=cap))
    for protection, multiple, ratchet in product(
        [0.8, 0.85, 0.9], [3, 5, 8], [False, True]
    ):
        cs.append(
            dict(
                family="insurance",
                protection=protection,
                multiple=multiple,
                ratchet=ratchet,
            )
        )
    for span, cap, ratio in product([63, 126], [0.6, 0.8], [1.25, 1.5]):
        cs.append(dict(family="risk_acceleration", span=span, cap=cap, ratio=ratio))
    # Keep an invested core and only move a tactical sleeve using gradual risk rules.
    for core, window, target in product([0.5, 0.7], [21, 63], [0.12, 0.16]):
        cs.append(dict(family="core_risk", core=core, window=window, target=target))
    return cs


def features(p):
    r = np.r_[0, np.diff(p) / p[:-1]][None, :]
    risk = {
        w: np.sqrt(
            np.maximum(average(r * r, w) - average(r, w) ** 2, 0) * 252 * w / (w - 1)
        )[0]
        for w in [21, 63, 126]
    }
    ma = {w: average(p[None, :], w)[0] for w in [100, 200, 300]}
    mom = np.full(len(p), np.nan)
    mom[21:] = p[21:] / p[:-21] - 1
    return risk, ma, mom


def ledger(days, p, cs, period, fee=0.0012, delay=1, trace=False):
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    risk, ma, mom = features(p)
    n = len(cs)
    cash = np.full(n, 10000.0)
    units = np.zeros(n)
    fees = np.zeros(n)
    peak = np.full(n, 10000.0)
    state = np.ones(n, dtype=bool)
    curves = [cash.copy()]
    records = []
    # Signals explicitly queued at close s, then executed at s+delay. Decisions
    # never use positions or portfolio peaks that became known after signal s.
    pending = {}
    for i in range(lo, hi):
        if i in pending:
            target, changed = pending.pop(i)
            nav = cash + units * p[i]
            old = units * p[i]
            buy = target * nav > old
            amount = (
                target
                * (nav + np.where(buy, fee * old, -fee * old))
                / (1 + np.where(buy, fee * target, -fee * target))
            )
            new = np.where(changed, np.floor(amount / p[i] + 1e-10), units)
            delta = new - units
            cost = abs(delta) * p[i] * fee
            cash -= delta * p[i] + cost
            fees += cost
            units = new
            assert np.all(cash >= -1e-6)
            if trace:
                records.append(
                    dict(execution=days[i], units=units.tolist(), cash=cash.tolist())
                )
        nav = cash + units * p[i]
        peak = np.maximum(peak, nav)
        if i > lo:
            curves.append(nav.copy())
        targets = np.ones(n)
        changed = np.zeros(n, dtype=bool)
        for j, c in enumerate(cs):
            fam = c["family"]
            step = c.get("step", 5)
            if i != lo and (step == 0 or (i - lo) % step):
                continue
            if fam == "constant":
                t = c["weight"]
            elif fam == "smooth_trend":
                # Smooth volatility-scaled price trend; no fitted future threshold.
                score = np.log(p[i] / ma[c["span"]][i]) / max(
                    risk[63][i] * np.sqrt(c["span"] / 252), 1e-8
                )
                t = c["floor"] + (1 - c["floor"]) * np.clip(0.5 + score, 0, 1)
            elif fam == "shock":
                if risk[21][i] > c["ratio"] * risk[126][i] and mom[i] < 0:
                    state[j] = False
                elif risk[21][i] < 1.1 * risk[126][i] or mom[i] > 0:
                    state[j] = True
                t = 1 if state[j] else c["cap"]
            elif fam == "insurance":
                floor = c["protection"] * (peak[j] if c["ratchet"] else 10000)
                t = np.clip(c["multiple"] * (nav[j] - floor) / nav[j], 0.35, 1)
            elif fam == "risk_acceleration":
                t = (
                    c["cap"]
                    if risk[21][i] > c["ratio"] * risk[c["span"]][i] and mom[i] < 0
                    else 1
                )
            elif fam == "core_risk":
                t = c["core"] + (1 - c["core"]) * min(
                    1, c["target"] / max(risk[c["window"]][i], 1e-8)
                )
            else:
                raise ValueError(fam)
            assert np.isfinite(t) and 0 <= t <= 1
            targets[j] = t
            changed[j] = i == lo or abs(t - units[j] * p[i] / nav[j]) >= 0.05
        if i + delay < hi:
            pending[i + delay] = (targets, changed)
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    return dict(
        curve=np.array(curves),
        fees=fees,
        metrics=common.metrics(curves, years, fees),
        trace=records,
    )


def evaluate(days, p, cs, period, fee=0.0012, delay=1):
    hybrids = [c for c in cs if c["family"] == "hybrid"]
    others = [c for c in cs if c["family"] != "hybrid"]
    result = ledger(
        days,
        p,
        [dict(family="constant", weight=1, step=0), *others],
        period,
        fee,
        delay,
    )
    f = common.regression.previous.prepare(days, p)
    capitals = np.array([10000, *[10000 * (1 - c["passive"]) for c in hybrids]])
    active = common.regression.simulate(
        days,
        p,
        p,
        f,
        [common.BASE] * (len(hybrids) + 1),
        period,
        fee=fee,
        delay=delay,
        initial_capital=capitals,
        keep_curve=True,
    )
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    curves = np.asarray(active["curve"])
    afees = np.array([m["fees"] for m in active["metrics"]])
    hybrid_metrics = []
    for j, c in enumerate(hybrids):
        capital = 10000 * c["passive"]
        entry = p[lo + delay]
        units = np.floor(capital / (entry * (1 + fee)) + 1e-10)
        cost = units * entry * fee
        passive = np.full(hi - lo, capital)
        passive[delay:] = (
            capital - units * entry * (1 + fee) + units * p[lo + delay : hi]
        )
        hybrid_metrics.append(
            common.metrics(curves[:, j + 1] + passive, years, afees[j + 1] + cost)
        )
    old = common.metrics(curves[:, 0], years, afees[0])
    rows = [
        {k: float(v[0]) for k, v in result["metrics"].items()},
        {k: float(v[0]) for k, v in old.items()},
    ]
    jh = jo = 0
    for c in cs:
        if c["family"] == "hybrid":
            m = hybrid_metrics[jh]
            jh += 1
            index = 0
        else:
            jo += 1
            m = result["metrics"]
            index = jo
        rows.append({k: float(v[index]) for k, v in m.items()})
    return rows


def historical_gate(rows, j):
    b, o, c = rows[0], rows[1], rows[j]
    return (
        c["cagr"] >= o["cagr"] - 0.0075
        and c["volatility"] <= min(1.75 * o["volatility"], 0.9 * b["volatility"])
        and abs(c["max_drawdown"])
        <= min(0.9 * abs(b["max_drawdown"]), abs(o["max_drawdown"]) + 0.12)
    )


def primary(paths, j):
    b, o, c = [common.summarize(paths)[k] for k in [0, 1, j]]
    tail = np.quantile([-p[j]["max_drawdown"] for p in paths], 0.95)
    bh_tail = np.quantile([-p[0]["max_drawdown"] for p in paths], 0.95)
    return bool(
        c["cagr"] >= o["cagr"] + 0.01
        and c["cagr"] >= b["cagr"] - 0.03
        and c["volatility"] <= 0.9 * b["volatility"]
        and abs(c["max_drawdown"]) <= 0.9 * abs(b["max_drawdown"])
        and tail <= bh_tail
        and all(c[k] >= 0.97 * b[k] for k in common.RATIOS)
    )


def summary(paths):
    means = common.summarize(paths)
    rng = np.random.default_rng(20261115)
    ci = {}
    for key, ref in [("cagr", 1), *[(k, 0) for k in common.RATIOS]]:
        delta = np.array([p[2][key] - p[ref][key] for p in paths])
        ci[key] = np.quantile(
            delta[rng.integers(len(delta), size=(5000, len(delta)))].mean(axis=1),
            [0.025, 0.975],
        ).tolist()
    wins = {
        k: float(
            np.mean(
                [
                    p[2][k] < p[0][k] if k in common.LOWER else p[2][k] > p[0][k]
                    for p in paths
                ]
            )
        )
        for k in means[0]
    }
    return dict(
        means=means,
        wins_vs_bh=wins,
        paired_ci95=ci,
        primary=primary(paths, 2),
        ideal=primary(paths, 2)
        and all(means[2][k] > means[0][k] and wins[k] >= 0.55 for k in common.RATIOS),
        paths=paths,
    )


def main():
    cs = grid()
    report = dict(plan=PLAN, configs=cs, adopted=False)
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
        report["snapshot_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        p = np.array([r[1] for r in rows])
        assert np.array_equal(p, np.array([r[2] for r in rows]))
        report["source"] = dict(start=days[0], end=days[-1], observations=len(days))
        logret = np.diff(np.log(p))
        hist = {
            str(y): evaluate(days, p, cs, [f"{2026 - y}-11-13", days[-1]])
            for y in [3, 5, 10]
        }
        report["historical_screen"] = hist
        save()

        def batch(configs, years, seed, count):
            future = future_sessions(date.fromisoformat(days[-1]), years)
            paths = []
            for i in range(count):
                pp = np.r_[
                    p,
                    p[-1]
                    * np.exp(np.cumsum(sampled_returns(logret, len(future), seed + i))),
                ]
                paths.append(
                    evaluate(days + future, pp, configs, [days[-1], future[-1]])
                )
                if i == 0:
                    prod = simulate_history(
                        rows, Sp500SimulationRequest(years=years, seed=seed)
                    )["comparison"]["metrics"]
                    for j, key in [(0, "benchmark"), (1, "strategy")]:
                        for k in paths[-1][j]:
                            np.testing.assert_allclose(
                                paths[-1][j][k], prod[key][k], atol=1e-9, rtol=0
                            )
                if (i + 1) % 25 == 0:
                    print("batch", years, seed, i + 1, "/", count, flush=True)
            return paths

        train = batch(cs, 5, 120000, 100)
        means = common.summarize(train)
        hpass = [
            j
            for j in range(2, len(cs) + 2)
            if all(historical_gate(ms, j) for ms in hist.values())
            and np.mean([ms[j]["cagr"] - ms[1]["cagr"] for ms in hist.values()])
            >= 0.0025
        ]
        qualified = [j for j in hpass if primary(train, j)]

        def rank(j):
            return min(means[j][k] / means[0][k] - 1 for k in common.RATIOS), means[j][
                "cagr"
            ]

        eligible = [
            j
            for j in range(2, len(cs) + 2)
            if means[j]["cagr"] >= means[1]["cagr"] + 0.01
            and means[j]["cagr"] >= means[0]["cagr"] - 0.03
            and means[j]["volatility"] <= 0.9 * means[0]["volatility"]
            and abs(means[j]["max_drawdown"]) <= 0.9 * abs(means[0]["max_drawdown"])
        ]
        chosen = max(qualified or eligible or list(range(2, len(cs) + 2)), key=rank)
        selected = cs[chosen - 2]
        controls = [
            dict(family="hybrid", passive=0.5),
            dict(family="constant", weight=0.8, step=63),
        ]
        audited = [selected, *[c for c in controls if c != selected]]
        report.update(
            training=dict(
                means=means, paths=train, qualified=qualified, historical_pass=hpass
            ),
            chosen=selected,
            chosen_index=chosen - 2,
            diagnostic_only=not bool(qualified),
            audited=audited,
        )
        save()
        print(
            "FROZEN",
            selected,
            "qualified",
            len(qualified),
            "historical",
            len(hpass),
            flush=True,
        )
        report["audit"] = {}
        for y, seed, count in [(5, 130000, 300), (10, 140000, 100)]:
            paths = batch(audited, y, seed, count)
            report["audit"][str(y)] = summary(paths)
            save()
        report["historical"] = {
            str(y): evaluate(days, p, audited, [f"{2026 - y}-11-13", days[-1]])
            for y in [3, 5, 10]
        }
        report["rolling"] = {
            f"{y}-{m:02}-13": evaluate(
                days, p, audited, [f"{y}-{m:02}-13", f"{y + 5}-{m:02}-13"]
            )
            for y in range(2016, 2022)
            for m in [2, 5, 8, 11]
            if f"{y + 5}-{m:02}-13" <= days[-1]
        }
        report["stress"] = {
            name: {
                str(y): evaluate(
                    days, p, audited, [f"{2026 - y}-11-13", days[-1]], **kw
                )
                for y in [3, 5, 10]
            }
            for name, kw in [
                ("double_fees", dict(fee=0.0024)),
                ("delay2", dict(delay=2)),
            ]
        }
        report["rolling_pass"] = sum(
            historical_gate(ms, 2) for ms in report["rolling"].values()
        )
        report["stress_pass"] = all(
            all(historical_gate(ms, 2) for ms in periods.values())
            and np.mean([ms[2]["cagr"] - ms[1]["cagr"] for ms in periods.values()]) > 0
            for periods in report["stress"].values()
        )
        report["all_primary_pass"] = (
            bool(qualified)
            and all(a["primary"] for a in report["audit"].values())
            and report["rolling_pass"] >= 0.75 * len(report["rolling"])
            and report["stress_pass"]
        )
        report["all_ideal_pass"] = report["all_primary_pass"] and all(
            a["ideal"] for a in report["audit"].values()
        )
        save()
        print(
            "DONE",
            OUT,
            "PRIMARY",
            report["all_primary_pass"],
            "IDEAL",
            report["all_ideal_pass"],
            flush=True,
        )


if __name__ == "__main__":
    main()
