"""Separate predeclared research: PSP5 regression continuation and crash guards.

PYTHONPATH=backend:scripts uv run python scripts/study_sp500_amundi_regression.py
Actual v4 reproduced against production; no production rule changes.
"""

import json
import sqlite3
import tempfile
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np
import study_sp500_three_years as engine

from investor import db
from investor.portfolio.sp500_simulation import future_sessions, sampled_returns

OUT = Path("data/backtests/sp500-amundi-regression.json")
BASE = {**engine.BASE, "warm": True}


def main():
    configs = [BASE]
    for entry, exit_, floor, share, guard in product(
        ["daily_cross", "ma100", "ma200"],
        ["level1.5", "armed_ma50", "armed_ma100"],
        [0, 0.15, 0.25],
        [0.5, 0.75, 1.0],
        ["none", "slow200", "both100"],
    ):
        c = {**BASE, "entry": entry, "exit": exit_, "floor": floor, "slow_share": share}
        if guard != "none":
            c.update(
                guard_ma=200 if guard == "slow200" else 100,
                guard_momentum=0,
                guard_cap=0,
                guard_both=guard == "both100",
            )
        if c != BASE:
            configs.append(c)
    report = dict(
        plan={
            "difference": "PSP5 EUR actual history and0.12% fees, continuation exits plus explicit negative63session momentum / moving-average crisis guards. Not reinstating multi-asset rejected policies. Whole units, separate75/25 or other fixed initial sleeves, no leverage, zero cash yield.",
            "selection": "Same strict BH gate as first study: CAGR higher, volatility and absoluteDD <=80%BH, Sharpe higher on BOTH2016-2020 and2021-2023. Rank worst CAGR gain. If none, diagnostic best worst CAGR among risk qualified only, else all. No adoption fallback.",
            "audit": "Both5/10y must pass same gate; >=75% quarterly-start completed5y windows; double fees and additional session delay. Fixed seeds0..99 MonteCarlo5/10y for selected-or-diagnostic and v4; >=60% return wins and >=90% volatility/DD wins; mean CAGR>BH, mean volatility/DD <=80%BH. Fewer paths than first study, reported explicitly. Rules frozen before audits.",
            "limits": "Repeated examined historical data; no prospective proof. No production strategy modification. Single-period best observations are post-hoc only.",
        },
        configs=configs,
        adopted=False,
    )
    OUT.parent.mkdir(exist_ok=True, parents=True)

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
        with sqlite3.connect(path) as c:
            rows = c.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.date=p.date AND o.asset_id=p.asset_id WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        prices = np.array([r[1] for r in rows])
        raw = np.array([r[2] for r in rows])
        f = engine.previous.prepare(days, prices)
        prefix = engine.previous.prepare(days[:-300], prices[:-300])
        for span in [18, 60]:
            np.testing.assert_allclose(
                prefix[0][span][0], f[0][span][0][:-300], equal_nan=True
            )
        source = json.loads(Path("data/backtests/sp500-amundi-upside.json").read_text())
        periods = source["periods"]

        def run(cs, p, **kw):
            return engine.simulate(
                days, raw, prices, f, cs, p, fee=kw.pop("fee", 0.0012), **kw
            )["metrics"]

        early = {k: run(configs, periods[k]) for k in ["train", "validation"]}

        def gate(m, b):
            return bool(
                m["cagr"] > b["cagr"]
                and m["volatility"] <= 0.8 * b["volatility"]
                and abs(m["max_drawdown"]) <= 0.8 * abs(b["max_drawdown"])
                and m["sharpe"] > b["sharpe"]
            )

        qualified = [
            j
            for j in range(1, len(configs))
            if all(gate(ms[j], source["historical"][k][-1]) for k, ms in early.items())
        ]
        risk = [
            j
            for j in range(1, len(configs))
            if all(
                ms[j]["volatility"] <= 0.8 * source["historical"][k][-1]["volatility"]
                and abs(ms[j]["max_drawdown"])
                <= 0.8 * abs(source["historical"][k][-1]["max_drawdown"])
                for k, ms in early.items()
            )
        ]

        def rank(j):
            return min(
                ms[j]["cagr"] - source["historical"][k][-1]["cagr"]
                for k, ms in early.items()
            )

        selected = max(qualified, key=rank) if qualified else None
        diagnostic = max(risk or list(range(1, len(configs))), key=rank)
        chosen = selected if selected is not None else diagnostic
        report.update(
            early=early,
            qualified=qualified,
            selected=selected,
            diagnostic=diagnostic,
            chosen=chosen,
        )
        save()
        print(
            "Frozen regression selection:",
            len(configs) - 1,
            "variants;",
            len(qualified),
            "qualified; diagnostic",
            chosen,
            configs[chosen],
            flush=True,
        )
        report["historical"] = {k: run(configs, p) for k, p in periods.items()}
        for name in ["five_years", "ten_years"]:
            for key in ["cagr", "volatility", "max_drawdown", "sharpe"]:
                assert (
                    abs(
                        report["historical"][name][0][key]
                        - source["production"][name]["metrics"]["strategy"][key]
                    )
                    < 1e-9
                ), (name, key)
            assert (
                abs(
                    report["historical"][name][0]["fees"]
                    - source["production"][name]["metrics"]["strategy"]["cost_eur"]
                )
                < 1e-6
            )
        report["production_match"] = True
        report["recent_pass"] = [
            j
            for j in range(1, len(configs))
            if all(
                gate(report["historical"][k][j], source["historical"][k][-1])
                for k in ["five_years", "ten_years"]
            )
        ]
        audited = [BASE, configs[chosen]]
        report["rolling"] = {
            start: run(audited, [start, f"{int(start[:4]) + 5}{start[4:]}"])
            for start in source["rolling"]
        }
        report["stress"] = {
            label: {
                k: run(audited, periods[k], **kw) for k in ["five_years", "ten_years"]
            }
            for label, kw in [
                ("double_fee", dict(fee=0.0024)),
                ("extra_delay", dict(delay=2)),
            ]
        }
        save()
        print(
            "Regression historical complete; recent pass",
            len(report["recent_pass"]),
            flush=True,
        )
        report["synthetic"] = {}
        for years in [5, 10]:
            future = future_sessions(date.fromisoformat(days[-1]), years)
            all_days = days + future
            metrics = []
            benchmarks = []
            for seed in range(100):
                values = prices[-1] * np.exp(
                    np.cumsum(
                        sampled_returns(np.diff(np.log(prices)), len(future), seed)
                    )
                )
                p = np.r_[prices, values]
                features = engine.previous.prepare(all_days, p)
                ms = engine.simulate(
                    all_days,
                    p,
                    p,
                    features,
                    audited,
                    [days[-1], future[-1]],
                    fee=0.0012,
                )["metrics"]
                # Exact BH entry next close, same fee and integer convention.
                units = np.floor(10000 / (values[0] * 1.0012) + 1e-10)
                cash = 10000 - units * values[0] * 1.0012
                nav = np.r_[10000, cash + units * values]
                ret = nav[1:] / nav[:-1] - 1
                elapsed = (
                    date.fromisoformat(future[-1]) - date.fromisoformat(days[-1])
                ).days / 365.25
                benchmarks.append(
                    dict(
                        cagr=(nav[-1] / 10000) ** (1 / elapsed) - 1,
                        volatility=ret.std(ddof=1) * np.sqrt(252),
                        max_drawdown=(nav / np.maximum.accumulate(nav) - 1).min(),
                        sharpe=ret.mean() / ret.std(ddof=1) * np.sqrt(252),
                    )
                )
                metrics.append(ms)
                if (seed + 1) % 25 == 0:
                    print("Regression synthetic", years, seed + 1, "/100", flush=True)
            summary = []
            for j in range(2):
                summary.append(
                    {
                        k: dict(
                            mean=float(np.mean([ms[j][k] for ms in metrics])),
                            benchmark_mean=float(np.mean([b[k] for b in benchmarks])),
                            wins=int(
                                sum(
                                    (ms[j][k] < b[k] - 1e-10)
                                    if k == "volatility"
                                    else (ms[j][k] > b[k] + 1e-10)
                                    for ms, b in zip(metrics, benchmarks, strict=True)
                                ),
                            ),
                        )
                        for k in ["cagr", "volatility", "max_drawdown", "sharpe"]
                    }
                )
            report["synthetic"][str(years)] = dict(
                count=100, seeds=[0, 99], summary=summary
            )
            save()
    print(OUT, flush=True)


if __name__ == "__main__":
    main()
