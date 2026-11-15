"""Declared second-stage diversified selection; no selection on final-test returns."""

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

import numpy as np
from study_sp500_regression import PROTOCOL, features, passes, score, simulate

from investor import db

SOURCE = Path("data/backtests/sp500-regression-study.json")
OUT = Path("data/backtests/sp500-regression-diversified.json")
PLAN = {
    "reason": "Stage one top-20 were nearly duplicate configurations and none passed validation. Separate follow-up, not part of the initial predeclared protocol.",
    "selection": "One train-ranked representative per (months, exit rule, trend filter, floor, entry rule), then validation ranks only representatives passing train AND validation; if none, diagnostic fallback. Final-test results never enter selection.",
    "gate": PROTOCOL["gate"],
    "limitations": "Exploratory second stage after stage-one validation. Reserved historical period already computed for stage one, so not independent untouched data. No genuine prospective claim.",
    "proxy": "SP500 total-return index in USD, fractional units, same commissions, no FX or ETF tracking. Stress diagnostic only, never a substitute for actual ESE EUR results.",
    "neighborhood": "One adjacent grid step in entry/exit and adjacent regression windows, other rules unchanged; no reselection.",
}


def main():
    OUT.write_text(json.dumps({"plan": PLAN}, indent=2) + "\n")
    first = json.loads(SOURCE.read_text())
    families = {}
    train = first["train_results"]
    ref = first["train_benchmark"]
    for r in train:
        c = r["config"]
        key = tuple(c[k] for k in ["months", "rule", "filter", "floor", "entry_rule"])
        old = families.get(key)

        def rank(item):
            return (passes(item["metrics"], ref, True), score(item["metrics"], ref))

        if old is None or rank(r) > rank(old):
            families[key] = r
    representatives = list(families.values())
    report = {"plan": PLAN, "family_count": len(representatives)}
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
        if report["snapshot_sha256"] != first["snapshot_sha256"]:
            raise ValueError("Data changed between research phases")
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-ese.pa' ORDER BY o.date"
            ).fetchall()
            proxy = conn.execute(
                "SELECT date,value FROM reference_observations WHERE symbol='^SP500TR' ORDER BY date"
            ).fetchall()
        days = [r[0] for r in rows]
        adjusted, raw = np.array([[r[1], r[2]] for r in rows]).T
        feat, ma = features(days, adjusted)
        configs = [r["config"] for r in representatives]
        val = simulate(days, raw, feat, ma, configs, PROTOCOL["validation"])
        qualified = [
            i
            for i, r in enumerate(representatives)
            if passes(r["metrics"], ref, True)
            and passes(val["candidates"][i], val["benchmark"])
        ]
        pool = qualified or list(range(len(configs)))
        chosen = max(pool, key=lambda i: score(val["candidates"][i], val["benchmark"]))
        selected = configs[chosen]
        report.update(
            qualified_count=len(qualified),
            selected=selected,
            representatives=[
                dict(
                    config=r["config"],
                    train=r["metrics"],
                    validation=val["candidates"][i],
                )
                for i, r in enumerate(representatives)
            ],
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            "Diversified selection frozen",
            len(qualified),
            "qualified:",
            selected,
            flush=True,
        )
        baseline = dict(
            months=36,
            entry=1,
            exit=2,
            rule="level",
            filter="none",
            cadence=1,
            floor=0,
            entry_rule="below",
        )
        chosen_configs = [selected, baseline, first["selected"]["config"]]
        report["evaluations"] = {}
        for name, period in [
            ("train", PROTOCOL["train"]),
            ("validation", PROTOCOL["validation"]),
            ("reserved_test", PROTOCOL["reserved_test"]),
            ("full", ["2018-09-17", days[-1]]),
            ("last_five_years", ["2021-11-15", days[-1]]),
        ]:
            report["evaluations"][name] = simulate(
                days, raw, feat, ma, chosen_configs, period, keep_curve=True
            )
        report["stresses"] = {}
        for name, kwargs in [
            ("double_fees", {"fee": 0.01}),
            ("extra_delay", {"delay": 2}),
            ("extra_cost_20bp", {"fee": 0.007}),
            ("fractional", {"whole": False}),
        ]:
            report["stresses"][name] = simulate(
                days, raw, feat, ma, chosen_configs, PROTOCOL["reserved_test"], **kwargs
            )
        months = PROTOCOL["windows_months"]
        mi = months.index(selected["months"])
        allowed = months[max(0, mi - 1) : mi + 2]
        neighbors = [
            r["config"]
            for r in train
            if all(
                r["config"][k] == selected[k]
                for k in ["rule", "filter", "cadence", "floor", "entry_rule"]
            )
            and abs(r["config"]["entry"] - selected["entry"]) <= 0.5
            and abs(r["config"]["exit"] - selected["exit"]) <= 0.5
            and r["config"]["months"] in allowed
        ]
        result = simulate(days, raw, feat, ma, neighbors, PROTOCOL["reserved_test"])
        report["neighbors"] = [
            dict(config=c, metrics=m, pass_gate=passes(m, result["benchmark"]))
            for c, m in zip(neighbors, result["candidates"], strict=True)
        ]
        pdays = [r[0] for r in proxy]
        pprices = np.array([r[1] for r in proxy])
        pf, pm = features(pdays, pprices)
        report["proxy_stresses"] = {}
        for name, period in [
            ("dotcom", ["2000-01-03", "2003-12-31"]),
            ("financial_crisis", ["2007-01-03", "2009-12-31"]),
            ("pre_ESE", ["1993-01-04", "2013-09-13"]),
            ("long", ["1993-01-04", pdays[-1]]),
        ]:
            report["proxy_stresses"][name] = simulate(
                pdays, pprices, pf, pm, chosen_configs, period, whole=False
            )
        report["adopt"] = bool(
            qualified
            and all(
                passes(
                    report["evaluations"][name]["candidates"][0],
                    report["evaluations"][name]["benchmark"],
                )
                for name in ["train", "validation", "reserved_test"]
            )
            and all(
                passes(s["candidates"][0], s["benchmark"])
                for s in report["stresses"].values()
            )
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print("Complete. Adopt:", report["adopt"], flush=True)


if __name__ == "__main__":
    main()
