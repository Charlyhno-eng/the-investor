"""Fixed literature benchmarks and explicit adaptations, research only.

PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_published_rules.py
"""

import hashlib
import json
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import study_sp500_drawdown_frontier as engine

from investor import db
from investor.portfolio.sp500_simulation import Sp500SimulationRequest, simulate_history

OUT = Path("data/backtests/sp500-published-rules.json")
PLAN = {
    "sources": [
        "https://mebfaber.com/timing-model/",
        "https://www.optimalmomentum.com/faq/",
        "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2759734",
        "https://www.nber.org/papers/w22208",
    ],
    "scope": "PSP5 own adjusted EUR history, private SQLite snapshot. Long ETF/cash only, no derivatives, shorting or leverage. Production unchanged. Published benchmarks can overlap prior research: diagnostic replication, not new discoveries. PAA multiasset breadth and GEM relative rotation NOT claimed replicated. Moreira-Muir not rerun unchanged after prior rejection.",
    "fixed_rules": "Six rules, each alone or tactical35%/v4 65%, tactical65%/v4 35%: SMA10 monthly Faber-style; absolute12 month return>0 (Antonacci-inspired, zero cash rate, no latest-month exclusion); equal vote SMA6/8/10/12; consensus SMA10 AND absolute12; hysteresis SMA10 +/-1%; fast monthly return average1/3/6/12>0. Last four are explicit research adaptations, not published strategy performance. No parameter tuning or winner reselection.",
    "execution": "10000EUR; fees .0012 each side, whole units, cash yield0. Last completed calendar month closes only. Initialise from latest completed month, order at next close after start. Month-end signals executed first observed session next month; delay2 stress adds one session. Rebalance monthly only,5pp band. Independent v4 budgets with no transfers; no end liquidation. Missing history stays cash. All metrics same as existing research.",
    "gates": "On EACH historical3/5/10y and synthetic5/10y mean: CAGR>=BH-2pp and >=v5-1pp; DDloss<=75%BH and <=90%v5; volatility<=BH. At least75% quarterly5y windows must meet same gates. All3/5/10 fee-doubled and delay2 stresses meet gates. No automatic adoption, even on success.",
    "audit": "All18 fixed candidates evaluated without selection:300 five-year seeds1210000..1210299 and100 ten-year1220000..1220099. Paired bootstrap95% CAGR and DD delta versus v5, diagnostic only, not multiplicity-adjusted. Per-path results retained. Tail95 loss and frequency loss>30% reported. Seeds reserved for this campaign only, same historical generator is NOT independent economic evidence.",
    "limits": "PSP5 starts2014, excludes2000/2008 crises; all historical data already inspected. Overlapping windows and repeated research. Foreign-exchange effects inherent to EUR ETF. Taxes omitted, zero cash return. Weekday synthetic calendar vs252-session metrics unchanged. No guarantee of drawdown protection or future return.",
}


def grid():
    return [
        dict(family=family, active=active)
        for family in [
            "sma10",
            "absolute12",
            "ma_votes",
            "consensus",
            "hysteresis",
            "fast_momentum",
        ]
        for active in [0, 0.65, 0.35]
    ]


def monthly_weights(days, p, cs):
    # A month becomes completed only when the next observed month starts.
    # Thus truncating or extending the future cannot alter any executed signal.
    ends = np.flatnonzero(
        np.array([a[:7] != b[:7] for a, b in zip(days[:-1], days[1:], strict=True)])
    )
    result = np.zeros((len(cs), len(p)))
    states = np.zeros(len(cs), dtype=bool)
    for k, end in enumerate(ends):
        history = p[ends[: k + 1]]
        signals = {}
        signals["sma10"] = len(history) >= 10 and history[-1] > history[-10:].mean()
        signals["absolute12"] = len(history) >= 13 and history[-1] > history[-13]
        signals["ma_votes"] = (
            np.mean([history[-1] > history[-w:].mean() for w in [6, 8, 10, 12]])
            if len(history) >= 12
            else 0.0
        )
        signals["consensus"] = signals["sma10"] and signals["absolute12"]
        signals["fast_momentum"] = (
            np.mean([history[-1] / history[-1 - w] - 1 for w in [1, 3, 6, 12]]) > 0
            if len(history) >= 13
            else False
        )
        for j, c in enumerate(cs):
            if c["family"] == "hysteresis":
                if len(history) >= 10:
                    ratio = history[-1] / history[-10:].mean()
                    if ratio > 1.01:
                        states[j] = True
                    elif ratio < 0.99:
                        states[j] = False
                weight = float(states[j])
            else:
                weight = float(signals[c["family"]])
            # Weight available starting on the first session of next month.
            stop = ends[k + 1] + 1 if k + 1 < len(ends) else len(p)
            result[j, end + 1 : stop] = weight
    return result


def tactical(days, p, cs, period, fee=0.0012, delay=1):
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    weights = monthly_weights(days, p, cs)
    cash = 10000 * (1 - np.array([c["active"] for c in cs]))
    units, fees = np.zeros(len(cs)), np.zeros(len(cs))
    curve, pending = [cash.copy()], {}
    for i in range(lo, hi):
        # Month boundary is observed now; only prior month prices enter target.
        monthly = i > lo and days[i][:7] != days[i - 1][:7]
        if i == lo or monthly:
            target = weights[:, i].copy()
            due = (i == lo) | (
                abs(
                    target
                    - units * p[max(lo, i - 1)] / (cash + units * p[max(lo, i - 1)])
                )
                >= 0.05
            )
            execution = i + delay if i == lo else i + delay - 1
            pending[execution] = target, due
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
            units = new
            fees += cost
            assert np.all(cash >= -1e-6) and np.all(units >= 0)
        if i > lo:
            curve.append((cash + units * p[i]).copy())
    return np.asarray(curve), fees


def gates(rows, j):
    bh, current, candidate = rows[0], rows[1], rows[j]
    return bool(
        candidate["cagr"] >= bh["cagr"] - 0.02
        and candidate["cagr"] >= current["cagr"] - 0.01
        and candidate["max_drawdown"] >= 0.75 * bh["max_drawdown"]
        and candidate["max_drawdown"] >= 0.90 * current["max_drawdown"]
        and candidate["volatility"] <= bh["volatility"]
    )


def sampled(args):
    engine.tactical = tactical
    return engine.sampled_case(args)


def main():
    cs = grid()
    report = dict(plan=PLAN, configs=cs, adopted=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    def save():
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    save()  # Protocol persisted BEFORE computing outcomes.
    engine.tactical = tactical
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
        days, p = [r[0] for r in rows], np.array([r[1] for r in rows])
        assert np.array_equal(p, [r[2] for r in rows])
        report["source"] = dict(start=days[0], end=days[-1], observations=len(p))
        report["historical"] = {
            str(y): engine.evaluate(days, p, cs, [f"{2026 - y}-11-13", days[-1]])
            for y in [1, 3, 5, 10]
        }
        report["rolling"] = {
            f"{y}-{m:02}-13": engine.evaluate(
                days, p, cs, [f"{y}-{m:02}-13", f"{y + 5}-{m:02}-13"]
            )
            for y in range(2016, 2022)
            for m in [2, 5, 8, 11]
            if f"{y + 5}-{m:02}-13" <= days[-1]
        }
        report["stress"] = {
            name: {
                str(y): engine.evaluate(
                    days, p, cs, [f"{2026 - y}-11-13", days[-1]], **kw
                )
                for y in [3, 5, 10]
            }
            for name, kw in [
                ("double_fees", dict(fee=0.0024)),
                ("delay2", dict(delay=2)),
            ]
        }
        report["audit"] = {}
        save()
        for years, seed, count in [(5, 1210000, 300), (10, 1220000, 100)]:
            paths = []
            with ProcessPoolExecutor(max_workers=4) as pool:
                for i, result in enumerate(
                    pool.map(
                        sampled, ((days, p, cs, years, seed + i) for i in range(count))
                    )
                ):
                    paths.append(result)
                    if i == 0:
                        prod = simulate_history(
                            rows, Sp500SimulationRequest(years=years, seed=seed)
                        )["comparison"]["metrics"]
                        for j, key in [(0, "benchmark"), (1, "strategy")]:
                            for metric, value in result[j].items():
                                np.testing.assert_allclose(
                                    value, prod[key][metric], atol=1e-9, rtol=0
                                )
                    if (i + 1) % 25 == 0:
                        print("audit", years, i + 1, "/", count, flush=True)
            s = engine.stats(paths)
            s["paths"] = paths
            s["loss_over30"] = np.mean(
                [[-m["max_drawdown"] > 0.3 for m in row] for row in paths], axis=0
            ).tolist()
            rng = np.random.default_rng(seed)
            indices = rng.integers(count, size=(2000, count))
            s["paired_ci95_vs_v5"] = {
                metric: np.quantile(
                    (
                        np.array([[r[metric] for r in row] for row in paths])
                        - np.array([row[1][metric] for row in paths])[:, None]
                    )[indices].mean(axis=1),
                    [0.025, 0.975],
                    axis=0,
                ).T.tolist()
                for metric in ["cagr", "max_drawdown"]
            }
            report["audit"][str(years)] = s
            save()
        report["rolling_pass"] = [
            sum(gates(ms, j) for ms in report["rolling"].values())
            for j in range(2, len(cs) + 2)
        ]
        report["qualified"] = [
            j - 2
            for j in range(2, len(cs) + 2)
            if all(gates(report["historical"][str(y)], j) for y in [3, 5, 10])
            and all(gates(s["means"], j) for s in report["audit"].values())
            and report["rolling_pass"][j - 2] >= 0.75 * len(report["rolling"])
            and all(
                gates(ms, j)
                for stress in report["stress"].values()
                for ms in stress.values()
            )
        ]
        save()
        print("DONE", OUT, "qualified", report["qualified"], flush=True)


if __name__ == "__main__":
    main()
