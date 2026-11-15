"""Mix shortlisted entry policies with current defensive policy, no leverage."""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import study_sp500_regression as engine
from study_sp500_return_drawdown import BASE, qualifies

from investor import db

OUT = Path("data/backtests/sp500-compromise-blends.json")
PLAN = {
    "reason": "Exploratory follow-up to relaxed-volatility results. Mix each of103 train/validation-qualified rules with incumbent at25/50/75% initial capital, no inter-sleeve rebalance. No ESE test-driven component reselection. Both components trade only ESE/cash; no leverage.",
    "selection": "Same0.5-point CAGR gain/no DD increase/vol<=1.3 incumbent criteria on train and validation, rank worst CAGR gain; freeze mix before later and5/10-year outcomes. Both5/10 plus later must pass; 75% of14 rolling cases must have DD<=incumbent and no less CAGR. No reselect after outcomes.",
    "accounting": "10000 total; each sleeve buys integer shares using its actual assigned initial capital, all fees paid separately including offsetting orders (conservative without netting). Separate cash budgets, no borrowing. No rebalancing between sleeves. This is NOT averaging CAGR or DD numbers.",
    "limitations": "Repeated historical exploration after previous results, not untouched verification.14% target audited separately; no guaranteed future return.",
}


def combine(a, b, days, period):
    curves = np.array(a["curve"])[:, :-1] + np.array(b["curve"])[:, 0, None]
    changes = curves[1:] / curves[:-1] - 1
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    vol = changes.std(axis=0, ddof=1) * np.sqrt(252)
    sharp = np.divide(
        changes.mean(axis=0) * 252, vol, out=np.zeros_like(vol), where=vol > 1e-12
    )
    dd = (curves / np.maximum.accumulate(curves, axis=0) - 1).min(axis=0)
    return [
        dict(
            cagr=float((curves[-1, i] / 10000) ** (1 / years) - 1),
            volatility=float(vol[i]),
            sharpe=float(sharp[i]),
            max_drawdown=float(dd[i]),
            fees=a["candidates"][i]["fees"] + b["candidates"][0]["fees"],
            final_value=float(curves[-1, i]),
        )
        for i in range(curves.shape[1])
    ]


def main():
    OUT.write_text(json.dumps({"plan": PLAN}, indent=2) + "\n")
    source = json.loads(Path("data/backtests/sp500-return-drawdown.json").read_text())
    ids = [
        i
        for i in range(source["candidate_count"])
        if all(
            qualifies(
                source["results"][k]["candidates"][i],
                source["baselines"][k]["candidates"][0],
            )
            for k in ["train", "validation"]
        )
    ]
    configs = [source["configs"][i] for i in ids]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "copy.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["snapshot_sha256"]:
            raise ValueError("Data changed")
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-ese.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        adjusted, raw = np.array([[r[1], r[2]] for r in rows]).T
        f, ma = engine.features(days, adjusted)

        def run(period):
            metrics = []
            for weight in [0.25, 0.5, 0.75]:
                a = engine.simulate(
                    days,
                    raw,
                    f,
                    ma,
                    configs,
                    period,
                    calendar=True,
                    keep_curve=True,
                    initial_capital=10000 * weight,
                )
                b = engine.simulate(
                    days,
                    raw,
                    f,
                    ma,
                    [BASE],
                    period,
                    keep_curve=True,
                    initial_capital=10000 * (1 - weight),
                )
                metrics.extend(combine(a, b, days, period))
            return metrics

        combinations = [
            dict(rule=c, new_rule_share=w) for w in [0.25, 0.5, 0.75] for c in configs
        ]
        periods = {
            "train": ["2018-09-17", "2020-12-31"],
            "validation": ["2021-01-04", "2023-12-29"],
            "later": ["2024-01-02", days[-1]],
            "five_years": ["2021-11-13", days[-1]],
            "ten_years": ["2016-11-13", days[-1]],
        }
        results = {k: run(periods[k]) for k in ["train", "validation"]}
        qualified = [
            i
            for i in range(len(combinations))
            if all(
                qualifies(results[k][i], source["baselines"][k]["candidates"][0])
                for k in ["train", "validation"]
            )
        ]
        selected = (
            max(
                qualified,
                key=lambda i: min(
                    results[k][i]["cagr"]
                    - source["baselines"][k]["candidates"][0]["cagr"]
                    for k in ["train", "validation"]
                ),
            )
            if qualified
            else None
        )
        report = dict(
            plan=PLAN,
            snapshot_sha256=source["snapshot_sha256"],
            candidate_count=len(combinations),
            screen_qualified=len(qualified),
            selected=combinations[selected] if selected is not None else None,
        )
        OUT.write_text(json.dumps(report, indent=2) + "\n")
        print("Mix frozen", report, flush=True)
        for k in ["later", "five_years", "ten_years"]:
            results[k] = run(periods[k])
        both = [
            i
            for i in range(len(combinations))
            if all(
                qualifies(results[k][i], source["baselines"][k]["candidates"][0])
                for k in ["five_years", "ten_years"]
            )
        ]
        report["results"] = results
        report["combinations"] = combinations
        report["descriptive_both_horizons_count"] = len(both)
        report["selected_results"] = (
            {k: r[selected] for k, r in results.items()} if selected is not None else {}
        )
        report["initial_gate_pass"] = bool(
            selected is not None
            and all(
                qualifies(results[k][selected], source["baselines"][k]["candidates"][0])
                for k in ["later", "five_years", "ten_years"]
            )
        )
        report["adopt"] = False
        if report["initial_gate_pass"]:
            # Further validation would be required; never claim automatic adoption.
            report["remaining"] = (
                "Rolling-date and stress checks still required before adoption."
            )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            "Results",
            report["selected_results"],
            "both-horizons candidates",
            len(both),
            "initial gate",
            report["initial_gate_pass"],
            flush=True,
        )


if __name__ == "__main__":
    main()
