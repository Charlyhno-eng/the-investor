"""Local, explicitly retrospective refinement of the authorized defensive strategy."""

import hashlib
import json
import sqlite3
import tempfile
from itertools import product
from pathlib import Path

import numpy as np
from study_sp500_regression import PROTOCOL, features, simulate

from investor import db

OUT = Path("data/backtests/sp500-defensive-refinement.json")
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
    "baseline": BASE,
    "windows_months": [12, 15, 18, 21, 24],
    "entry": [-0.75, -0.5, -0.25],
    "exit": [1.25, 1.5, 1.75],
    "cadence_sessions": [3, 5, 10],
    "defensive_weight": [0.25, 0.35, 0.5, 0.65],
    "period": ["2018-09-17", "2026-11-13"],
    "periods": {k: PROTOCOL[k] for k in ["train", "validation", "reserved_test"]},
    "selection_before_results": "Replace authorized baseline only if full CAGR >=14%, full volatility <=95% baseline, full abs drawdown <=baseline, full Sharpe >=baseline. On EACH continuous subperiod require CAGR >=baseline-1 percentage point, volatility <=105% baseline, abs drawdown <=110% baseline. At 1% fees require full CAGR >=14% and at least baseline CAGR, with full volatility <=baseline. At extra session delay require full CAGR >=14% and volatility <=baseline. Rank qualified by lowest full volatility then highest full CAGR; if none, retain baseline. No tuning after outcomes.",
    "limitations": "All these historical dates have been seen. Exploratory local search, no untouched test or claim of statistical validation. 14% is a minimum historical annualized return on the stated full period after default 0.5% one-way commission, never a future or all-period guarantee.",
}


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"plan": PLAN}, indent=2) + "\n")
    PROTOCOL["windows_months"] = PLAN["windows_months"]
    configs = [
        dict(BASE, months=m, entry=a, exit=b, cadence=c, floor=f)
        for m, a, b, c, f in product(
            PLAN["windows_months"],
            PLAN["entry"],
            PLAN["exit"],
            PLAN["cadence_sessions"],
            PLAN["defensive_weight"],
        )
    ]
    if BASE not in configs:
        raise ValueError("Missing baseline")
    bi = configs.index(BASE)
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
        with sqlite3.connect(path) as c:
            rows = c.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-ese.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        adjusted, raw = np.array([[r[1], r[2]] for r in rows]).T
        f, ma = features(days, adjusted)
        full = simulate(days, raw, f, ma, configs, PLAN["period"])
        tr = simulate(days, raw, f, ma, configs, PROTOCOL["train"])
        va = simulate(
            days,
            raw,
            f,
            ma,
            configs,
            PROTOCOL["validation"],
            initial=tr["terminal_state"],
        )
        te = simulate(
            days,
            raw,
            f,
            ma,
            configs,
            PROTOCOL["reserved_test"],
            initial=va["terminal_state"],
        )
        fee = simulate(days, raw, f, ma, configs, PLAN["period"], fee=0.01)
        delay = simulate(days, raw, f, ma, configs, PLAN["period"], delay=2)
        b = full["candidates"][bi]
        qualify = []
        for i, m in enumerate(full["candidates"]):
            good = (
                m["cagr"] >= 0.14
                and m["volatility"] <= 0.95 * b["volatility"]
                and abs(m["max_drawdown"]) <= abs(b["max_drawdown"])
                and m["sharpe"] >= b["sharpe"]
            )
            for r in [tr, va, te]:
                c, ref = r["candidates"][i], r["candidates"][bi]
                good &= (
                    c["cagr"] >= ref["cagr"] - 0.01
                    and c["volatility"] <= 1.05 * ref["volatility"]
                    and abs(c["max_drawdown"]) <= 1.1 * abs(ref["max_drawdown"])
                )
            for r in [fee, delay]:
                c, ref = r["candidates"][i], r["candidates"][bi]
                good &= c["cagr"] >= 0.14 and c["volatility"] <= ref["volatility"]
            good &= fee["candidates"][i]["cagr"] >= fee["candidates"][bi]["cagr"]
            if good:
                qualify.append(i)
        winner = (
            min(
                qualify,
                key=lambda i: (
                    full["candidates"][i]["volatility"],
                    -full["candidates"][i]["cagr"],
                ),
            )
            if qualify
            else bi
        )
        report = dict(
            plan=PLAN,
            snapshot_sha256=sha,
            candidate_count=len(configs),
            qualified_count=len(qualify),
            selected=configs[winner],
            improvement_selected=bool(qualify),
            baseline_full=b,
            selected_full=full["candidates"][winner],
            benchmark=full["benchmark"],
            results=[
                dict(
                    config=c,
                    full=full["candidates"][i],
                    train=tr["candidates"][i],
                    validation=va["candidates"][i],
                    test=te["candidates"][i],
                    double_fees=fee["candidates"][i],
                    extra_delay=delay["candidates"][i],
                    qualified=i in qualify,
                )
                for i, c in enumerate(configs)
            ],
        )
        # Clearly separated diagnostic: good aggregate performance alone does not qualify.
        good_full = [
            i
            for i, m in enumerate(full["candidates"])
            if m["cagr"] >= 0.14 and m["volatility"] < b["volatility"]
        ]
        report["aggregate_only_best"] = (
            configs[min(good_full, key=lambda i: full["candidates"][i]["volatility"])]
            if good_full
            else None
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            json.dumps(
                {
                    k: report[k]
                    for k in [
                        "candidate_count",
                        "qualified_count",
                        "selected",
                        "baseline_full",
                        "selected_full",
                        "aggregate_only_best",
                    ]
                },
                indent=2,
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
