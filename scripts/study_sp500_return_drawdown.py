"""Return-first compromise with an explicit no-worse-drawdown constraint."""

import hashlib
import json
import sqlite3
import tempfile
from itertools import product
from pathlib import Path

import numpy as np
import study_sp500_regression as engine

from investor import db

OUT = Path("data/backtests/sp500-return-drawdown.json")
BASE = dict(
    months=18,
    entry=-0.5,
    exit=1.5,
    rule="level",
    filter="none",
    cadence=5,
    floor=0.25,
    entry_rule="rebound",
)
PLAN = {
    "reference": "Current defensive policy, independently simulated from cash on identical dates; ESE buy-and-hold also reported. No special default start date in application.",
    "volatility_budget": "Up to 30% relative above current defensive volatility, not +30 percentage points. Benchmark implied risk also reported.",
    "search": "Regression windows6/12/18/24/36/60 months,8 entry levels,6 exit levels with entry<exit, direct/trailing0.5/trailing1 exits, below/upcross entries,1/5/21-session decisions, defensive weights10/25/40/55/70%. New candidate schedules daily/Friday/first session of month; current baseline retains production cadence anchored on start.",
    "selection": "Historical exploration explicitly, no untouched claim. First screen2018-2020 and2021-2023; on each require abs DD<=current baseline, volatility<=1.3 baseline, CAGR>=baseline+0.005. Rank by worst excess CAGR across the two periods; freeze selected candidate before2024-2026 and5/10-year verification. No reselection based on those outcomes.",
    "adoption": "Selected must improve CAGR>=0.5 point with abs DD<=baseline and vol<=1.3baseline on both5/10 years; satisfy same criteria on2024-2026; satisfy DD<=baseline and CAGR>=baseline on>=75% of14 overlapping rolling3/5-year cases. Five/ten-year double-fee and extra-delay scenarios must also have DD<=respective stressed baseline and higher CAGR. Earlier14% historical target counted separately; never implied guaranteed.",
    "limitations": "All dates already seen in previous experiments. Testing many variants is multiple selection on historical data, not prospective proof. DD is realized historical, never a future loss cap. Whole shares,10000 EUR,0.5% one-way fees,cash0%,next close; no leverage.",
}


def qualifies(m, b, gain=0.005):
    return bool(
        m["cagr"] >= b["cagr"] + gain
        and abs(m["max_drawdown"]) <= abs(b["max_drawdown"]) + 1e-12
        and m["volatility"] <= 1.3 * b["volatility"]
    )


def main():
    OUT.write_text(json.dumps({"plan": PLAN}, indent=2) + "\n")
    configs = [
        dict(
            months=m,
            entry=a,
            exit=b,
            rule=r,
            filter="none",
            cadence=c,
            floor=f,
            entry_rule=e,
        )
        for m, a, b, r, c, f, e in product(
            [6, 12, 18, 24, 36, 60],
            [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5],
            [0.5, 1, 1.5, 2, 2.5, 3],
            ["level", "trail_0.5", "trail_1"],
            [1, 5, 21],
            [0.1, 0.25, 0.4, 0.55, 0.7],
            ["below", "rebound"],
        )
        if a < b
    ]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "snapshot.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-ese.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        adjusted, raw = np.array([[r[1], r[2]] for r in rows]).T
        f, ma = engine.features(days, adjusted)

        def run(cs, period, **kw):
            return engine.simulate(days, raw, f, ma, cs, period, **kw)

        periods = {
            "train": ["2018-09-17", "2020-12-31"],
            "validation": ["2021-01-04", "2023-12-29"],
            "later": ["2024-01-02", days[-1]],
            "five_years": ["2021-11-13", days[-1]],
            "ten_years": ["2016-11-13", days[-1]],
        }
        results = {}
        baselines = {}
        for name in ["train", "validation"]:
            results[name] = run(configs, periods[name], calendar=True)
            baselines[name] = run([BASE], periods[name])
        qualified = [
            i
            for i in range(len(configs))
            if all(
                qualifies(results[k]["candidates"][i], baselines[k]["candidates"][0])
                for k in ["train", "validation"]
            )
        ]
        winner = (
            max(
                qualified,
                key=lambda i: min(
                    results[k]["candidates"][i]["cagr"]
                    - baselines[k]["candidates"][0]["cagr"]
                    for k in ["train", "validation"]
                ),
            )
            if qualified
            else None
        )
        report = dict(
            plan=PLAN,
            snapshot_sha256=sha,
            candidate_count=len(configs),
            screen_qualified=len(qualified),
            selected=configs[winner] if winner is not None else None,
            configs=configs,
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            "Choice frozen",
            len(configs),
            "candidates",
            len(qualified),
            "qualified;",
            report["selected"],
            flush=True,
        )
        for name in ["later", "five_years", "ten_years"]:
            results[name] = run(configs, periods[name], calendar=True)
            baselines[name] = run([BASE], periods[name])
        report["results"] = results
        report["baselines"] = baselines
        both = [
            i
            for i in range(len(configs))
            if all(
                qualifies(results[k]["candidates"][i], baselines[k]["candidates"][0])
                for k in ["five_years", "ten_years"]
            )
        ]
        report["descriptive_both_horizons_count"] = len(both)
        report["descriptive_14pct_both_count"] = sum(
            all(
                results[k]["candidates"][i]["cagr"] >= 0.14
                for k in ["five_years", "ten_years"]
            )
            for i in both
        )
        # Do not select from five/ten-year outcomes. At most list qualifying configs
        # as explicitly post-hoc descriptions for inspecting the tradeoff.
        report["descriptive_examples"] = [
            dict(
                config=configs[i],
                five=results["five_years"]["candidates"][i],
                ten=results["ten_years"]["candidates"][i],
            )
            for i in both[:10]
        ]
        report["selected_results"] = (
            {
                k: dict(
                    metrics=r["candidates"][winner],
                    baseline=baselines[k]["candidates"][0],
                    benchmark=r["benchmark"],
                )
                for k, r in results.items()
            }
            if winner is not None
            else {}
        )
        report["rolling"] = []
        report["stresses"] = {}
        if winner is not None:
            for span in [3, 5]:
                for year in range(2016, 2027 - span):
                    p = [f"{year}-11-13", f"{year + span}-11-13"]
                    r = run([configs[winner]], p, calendar=True)
                    b = run([BASE], p)
                    m, base = r["candidates"][0], b["candidates"][0]
                    report["rolling"].append(
                        dict(
                            period=p,
                            metrics=m,
                            baseline=base,
                            pass_gate=qualifies(m, base, gain=0),
                        )
                    )
            for name, kw in [
                ("double_fees", {"fee": 0.01}),
                ("extra_delay", {"delay": 2}),
            ]:
                report["stresses"][name] = {}
                for horizon in ["five_years", "ten_years"]:
                    r = run([configs[winner]], periods[horizon], calendar=True, **kw)
                    b = run([BASE], periods[horizon], **kw)
                    report["stresses"][name][horizon] = dict(
                        metrics=r["candidates"][0],
                        baseline=b["candidates"][0],
                        pass_gate=qualifies(
                            r["candidates"][0], b["candidates"][0], gain=0
                        ),
                    )
        report["adopt"] = bool(
            winner is not None
            and all(
                qualifies(
                    results[k]["candidates"][winner], baselines[k]["candidates"][0]
                )
                for k in ["later", "five_years", "ten_years"]
            )
            and np.mean([r["pass_gate"] for r in report["rolling"]]) >= 0.75
            and all(
                r["pass_gate"]
                for cases in report["stresses"].values()
                for r in cases.values()
            )
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            json.dumps(
                {
                    k: report[k]
                    for k in [
                        "screen_qualified",
                        "selected",
                        "descriptive_both_horizons_count",
                        "descriptive_14pct_both_count",
                        "adopt",
                        "selected_results",
                    ]
                },
                indent=2,
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
