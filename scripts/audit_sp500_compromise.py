"""Post-hoc audit of small Pareto improvements; never presented as unseen validation."""

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import study_sp500_regression as engine
from study_sp500_compromise_blends import combine
from study_sp500_return_drawdown import BASE

from investor import db

OUT = Path("data/backtests/sp500-compromise-audit.json")


def main():
    singles = json.loads(Path("data/backtests/sp500-return-drawdown.json").read_text())
    mixes = json.loads(Path("data/backtests/sp500-compromise-blends.json").read_text())
    pareto = []
    for i in range(mixes["candidate_count"]):
        vals = [mixes["results"][k][i] for k in ["five_years", "ten_years"]]
        refs = [
            singles["baselines"][k]["candidates"][0]
            for k in ["five_years", "ten_years"]
        ]
        if all(
            m["cagr"] > b["cagr"]
            and abs(m["max_drawdown"]) <= abs(b["max_drawdown"])
            and m["volatility"] <= 1.3 * b["volatility"]
            for m, b in zip(vals, refs, strict=True)
        ):
            pareto.append(i)
    best = max(
        pareto,
        key=lambda i: min(
            mixes["results"][k][i]["cagr"]
            - singles["baselines"][k]["candidates"][0]["cagr"]
            for k in ["five_years", "ten_years"]
        ),
    )
    selected = mixes["combinations"][best]
    report = dict(
        plan="EXPLORATORY POST-HOC audit: remove arbitrary0.5pt improvement floor only, retain positive gain/DD<=incumbent/vol<=1.3 on5/10 years. Rank12 qualifying mixes by worst of5/10 excess CAGR. This selects using ESE outcomes: not an independent validation. Audit rolling cases, fees, delay, USD crises; no production adoption or 14% claim.",
        pareto_count=len(pareto),
        selected=selected,
        results={},
    )
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "copy.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        if hashlib.sha256(path.read_bytes()).hexdigest() != singles["snapshot_sha256"]:
            raise ValueError("Data changed")
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT date,value FROM observations WHERE asset_id='yf-ese.pa' ORDER BY date"
            ).fetchall()
            proxy = conn.execute(
                "SELECT date,value FROM reference_observations WHERE symbol='^SP500TR' ORDER BY date"
            ).fetchall()
        for dataset, data in [("ese", rows), ("usd_index", proxy)]:
            days = [r[0] for r in data]
            prices = np.array([r[1] for r in data])
            f, ma = engine.features(days, prices)

            def run(period, days=days, prices=prices, f=f, ma=ma, **kw):
                w = selected["new_rule_share"]
                a = engine.simulate(
                    days,
                    prices,
                    f,
                    ma,
                    [selected["rule"]],
                    period,
                    calendar=True,
                    keep_curve=True,
                    initial_capital=10000 * w,
                    **kw,
                )
                b = engine.simulate(
                    days,
                    prices,
                    f,
                    ma,
                    [BASE],
                    period,
                    keep_curve=True,
                    initial_capital=10000 * (1 - w),
                    **kw,
                )
                ref = engine.simulate(days, prices, f, ma, [BASE], period, **kw)
                m = combine(a, b, days, period)[0]
                base = ref["candidates"][0]
                return dict(
                    metrics=m,
                    baseline=base,
                    benchmark=ref["benchmark"],
                    pass_gate=bool(
                        m["cagr"] >= base["cagr"]
                        and abs(m["max_drawdown"]) <= abs(base["max_drawdown"])
                        and m["volatility"] <= 1.3 * base["volatility"]
                    ),
                )

            if dataset == "ese":
                cases = {
                    f"{span}y_{y}": [f"{y}-11-13", f"{y + span}-11-13"]
                    for span in [3, 5]
                    for y in range(2016, 2027 - span)
                }
                cases["ten_years"] = ["2016-11-13", days[-1]]
                for name, period in cases.items():
                    report["results"][name] = run(period)
                report["stresses"] = {}
                for name, kw in [
                    ("double_fees", {"fee": 0.01}),
                    ("extra_delay", {"delay": 2}),
                ]:
                    report["stresses"][name] = {
                        k: run(p, **kw)
                        for k, p in [
                            ("five_years", ["2021-11-13", days[-1]]),
                            ("ten_years", ["2016-11-13", days[-1]]),
                        ]
                    }
                report["rolling_pass"] = sum(
                    r["pass_gate"]
                    for k, r in report["results"].items()
                    if k != "ten_years"
                )
            else:
                report["usd_proxy"] = {
                    k: run(p, whole=False)
                    for k, p in [
                        ("dotcom", ["2000-01-03", "2003-12-31"]),
                        ("crisis", ["2007-01-03", "2009-12-31"]),
                        ("long", ["1993-01-04", days[-1]]),
                    ]
                }
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            "Pareto",
            len(pareto),
            "selected",
            selected,
            "rolling",
            report["rolling_pass"],
            "/14",
        )
        for name, cases in report["stresses"].items():
            print(name, [(k, r["pass_gate"]) for k, r in cases.items()])
        print(
            "USD",
            [
                (k, r["pass_gate"], r["metrics"]["cagr"], r["baseline"]["cagr"])
                for k, r in report["usd_proxy"].items()
            ],
        )


if __name__ == "__main__":
    main()
