"""Frozen-plan refinements of the active v4 policy, research only.

Run: PYTHONPATH=backend:scripts uv run python scripts/study_sp500_v4_refinements.py
Uses a private read-only SQLite snapshot and never changes application rules.
"""

import hashlib
import json
import sqlite3
import tempfile
from itertools import product
from pathlib import Path

import numpy as np
import study_sp500_three_years as engine

from investor import db

OUT = Path("data/backtests/sp500-v4-refinements.json")
BASE = {**engine.BASE, "warm": True}
PLAN = {
    "baseline": "Active slow_defensive_warm_state_v4; slow historical state, defensive cold state.",
    "hypotheses": [
        "Change initial sleeve budgets without subsequent transfers.",
        "Change defensive exposure floor without leverage.",
        "Change defensive crossing, exit or decision cadence.",
        "Reduce exposure during negative 63-session momentum below a price moving average.",
        "Combine small budget, floor and defensive-exit changes.",
    ],
    "selection": "Train2018-09-17..2020-12-31 and validation2021-01-04..2023-12-29: CAGR gain>=0.25pp on BOTH, no worse absolute DD, vol<=1.15baseline, Sharpe>=baseline-0.03. Select highest worst CAGR gain, then mean. Freeze before recent audits; no fallback.",
    "audit": "On3/5/10y: CAGR gain>=0.25pp EACH, no worse DD, vol<=1.15baseline, Sharpe>=baseline-0.03. At least90% of completed monthly-start3/5y windows retain CAGR within0.2pp and DD within0.5pp, vol<=1.15baseline. Fee1% and delay2: retain positive CAGR gain and no worse DD on3/5/10y. USD2000-03,2007-09,1993+ DD no worse. All required.",
    "execution": "10000EUR; ESE EUR; integer shares, fee0.5% each side, next close. Separate sleeves, no transfers or netting, cash earns0. Guards checked at each signal close and executed later; re-entry to underlying target when guard clears incurs fees. No pre-start cash or profits.",
    "limitations": "Repeated historical research on already examined data. No untouched future data. Overlapping windows not independent. Proxy USD total return is not ESE EUR trading history. No automatic production changes.",
}


def grid():
    variants = []
    for key, values in [
        ("slow_share", [0.5, 0.6, 0.65, 0.7, 0.8, 0.85, 0.9]),
        ("floor", [0.1, 0.15, 0.2, 0.3, 0.35]),
        ("defensive_entry", [-1, -0.75, -0.25, 0]),
        ("defensive_exit", [1, 1.25, 1.75, 2]),
        ("defensive_step", [1, 10]),
    ]:
        variants.extend({key: v} for v in values)
    variants.extend(
        dict(guard_ma=ma, guard_momentum=m, guard_cap=c, guard_both=b)
        for ma, m, c, b in product(
            [100, 200], [0, -0.05], [0.1, 0.25, 0.5], [False, True]
        )
    )
    variants.extend(
        dict(slow_share=w, floor=f, defensive_exit=e)
        for w, f, e in product(
            [0.65, 0.75, 0.85], [0.15, 0.25, 0.35], [1.25, 1.5, 1.75]
        )
        if (w, f, e) != (0.75, 0.25, 1.5)
    )
    return [BASE] + [{**BASE, **v} for v in variants]


def strict(m, b, gain=0.0025):
    return bool(
        m["cagr"] >= b["cagr"] + gain - 1e-12
        and abs(m["max_drawdown"]) <= abs(b["max_drawdown"]) + 1e-12
        and m["volatility"] <= 1.15 * b["volatility"]
        and m["sharpe"] >= b["sharpe"] - 0.03
    )


def main():
    configs = grid()
    report = dict(plan=PLAN, configs=configs, count=len(configs), adopted=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    def save():
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    save()  # Criteria and full grid persisted before reading prices/results.
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as source,
            sqlite3.connect(path) as dest,
        ):
            source.backup(dest)
        report["snapshot_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-ese.pa' ORDER BY o.date"
            ).fetchall()
            proxy = conn.execute(
                "SELECT date,value FROM reference_observations WHERE symbol='^SP500TR' ORDER BY date"
            ).fetchall()
        days = [r[0] for r in rows]
        adjusted, raw = np.array([[r[1], r[2]] for r in rows]).T
        features = engine.previous.prepare(days, adjusted)
        frozen = json.loads(
            Path(
                "data/backtests/sp500-warm-state-production-verification.json"
            ).read_text()
        )
        if frozen["snapshot_sha256"] != report["snapshot_sha256"]:
            raise ValueError("Snapshot differs from current production verification")

        def run(cs, p, **kw):
            return engine.simulate(days, raw, adjusted, features, cs, p, **kw)[
                "metrics"
            ]

        for name, case in frozen["results"].items():
            actual = run([BASE], [case["start"], case["end"]])[0]
            for key in ["cagr", "volatility", "sharpe", "max_drawdown"]:
                assert abs(actual[key] - case["metrics"]["strategy"][key]) < 1e-9, (
                    name,
                    key,
                )
            assert abs(actual["fees"] - case["metrics"]["strategy"]["cost_eur"]) < 1e-6
            assert abs(actual["final_value"] - case["final_portfolio"]["total"]) < 1e-6
        report["baseline_production_cases_matched"] = len(frozen["results"])
        periods = dict(
            train=["2018-09-17", "2020-12-31"],
            validation=["2021-01-04", "2023-12-29"],
            three_years=["2023-11-13", days[-1]],
            five_years=["2021-11-13", days[-1]],
            ten_years=["2016-11-13", days[-1]],
        )
        report["periods"] = periods
        results = {k: run(configs, periods[k]) for k in ["train", "validation"]}
        qualified = [
            j
            for j in range(1, len(configs))
            if all(strict(results[k][j], results[k][0]) for k in results)
        ]
        selected = (
            max(
                qualified,
                key=lambda j: (
                    min(results[k][j]["cagr"] - results[k][0]["cagr"] for k in results),
                    np.mean(
                        [results[k][j]["cagr"] - results[k][0]["cagr"] for k in results]
                    ),
                ),
            )
            if qualified
            else None
        )
        report.update(
            results=results,
            qualified=qualified,
            selected_index=selected,
            selected=configs[selected] if selected is not None else None,
        )
        save()
        print(
            "Selection frozen:",
            len(configs) - 1,
            "variants;",
            len(qualified),
            "qualified;",
            report["selected"],
            flush=True,
        )
        for k in ["three_years", "five_years", "ten_years"]:
            results[k] = run(configs, periods[k])
        report["recent_strict_pass"] = [
            j
            for j in range(1, len(configs))
            if all(
                strict(results[k][j], results[k][0])
                for k in ["three_years", "five_years", "ten_years"]
            )
        ]
        report["rolling"] = {
            f"{span}y_{year}": run(configs, [f"{year}-11-13", f"{year + span}-11-13"])
            for span in [3, 5]
            for year in range(2016, 2027 - span)
        }
        save()
        # Diagnostic on ALL candidates, never a fallback selection from recent data.
        monthly = {}
        for span in [3, 5]:
            for year in range(2016, 2027 - span):
                for month in range(1, 13):
                    p = [f"{year}-{month:02d}-13", f"{year + span}-{month:02d}-13"]
                    if p[1] <= days[-1]:
                        monthly[f"{span}y_{year}_{month:02d}"] = run(configs, p)
                print("Monthly audit:", span, year, flush=True)
        report["monthly"] = monthly
        report["monthly_summary"] = [
            dict(
                windows=len(monthly),
                cagr_gains=sum(
                    ms[j]["cagr"] > ms[0]["cagr"] + 1e-10 for ms in monthly.values()
                ),
                cagr_losses=sum(
                    ms[j]["cagr"] < ms[0]["cagr"] - 1e-10 for ms in monthly.values()
                ),
                worse_dd=sum(
                    abs(ms[j]["max_drawdown"]) > abs(ms[0]["max_drawdown"]) + 1e-10
                    for ms in monthly.values()
                ),
                worst_dd_increase=max(
                    abs(ms[j]["max_drawdown"]) - abs(ms[0]["max_drawdown"])
                    for ms in monthly.values()
                ),
                risk_pass=sum(
                    ms[j]["cagr"] >= ms[0]["cagr"] - 0.002
                    and abs(ms[j]["max_drawdown"]) <= abs(ms[0]["max_drawdown"]) + 0.005
                    and ms[j]["volatility"] <= 1.15 * ms[0]["volatility"]
                    for ms in monthly.values()
                ),
            )
            for j in range(len(configs))
        ]
        report["stress"] = {
            name: {
                k: run(configs, periods[k], **kw)
                for k in ["three_years", "five_years", "ten_years"]
            }
            for name, kw in [("fee1pct", dict(fee=0.01)), ("delay2", dict(delay=2))]
        }
        pdays = [r[0] for r in proxy]
        prices = np.array([r[1] for r in proxy])
        pf = engine.previous.prepare(pdays, prices)
        report["usd_proxy"] = {
            k: engine.simulate(pdays, prices, prices, pf, configs, p, whole=False)[
                "metrics"
            ]
            for k, p in [
                ("dotcom", ["2000-01-03", "2003-12-31"]),
                ("crisis", ["2007-01-03", "2009-12-31"]),
                ("long", ["1993-01-04", pdays[-1]]),
            ]
        }
        report["all_audit_pass"] = [
            j
            for j in report["recent_strict_pass"]
            if report["monthly_summary"][j]["risk_pass"] >= 0.9 * len(monthly)
            and all(
                ms[j]["cagr"] > ms[0]["cagr"]
                and abs(ms[j]["max_drawdown"]) <= abs(ms[0]["max_drawdown"]) + 1e-12
                for cases in report["stress"].values()
                for ms in cases.values()
            )
            and all(
                abs(ms[j]["max_drawdown"]) <= abs(ms[0]["max_drawdown"]) + 1e-12
                for ms in report["usd_proxy"].values()
            )
        ]
        report["selected_passes"] = selected in report["all_audit_pass"]
        save()
        print(
            "Completed:",
            OUT,
            "selected passes:",
            report["selected_passes"],
            "all audit passes:",
            report["all_audit_pass"],
            flush=True,
        )


if __name__ == "__main__":
    main()
