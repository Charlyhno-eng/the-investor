"""Frozen local comparison against buy-and-hold, including exposure diagnostics.

Run: PYTHONPATH=backend .venv/bin/python scripts/backtest_hmm_literature.py
Results stay under ignored data/. No network, database writes or Git operations.
"""

import csv
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
from backtest_regimes import windows
from hmm_regime_candidates import (
    CANDIDATES,
    LOOKBACK,
    REFIT,
    SPAN,
    candidate_signals,
    ewm_observations,
    execute,
)
from investor.analysis.metrics import equity, metrics
from investor.analysis.schemas import AnalysisRequest
from investor.market_catalog import REMOVED_CRYPTO

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/backtests/hmm-literature"
BASELINE = ROOT / "data/backtests/hmm-directional-final/results.json"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def diagnostics(net, market, held, value, changes, annual):
    strategy, benchmark = (
        metrics(net, market, annual, 0),
        metrics(market, market, annual, 0),
    )
    # Signal at t first earns return at t+2; evaluate directional separation
    # on that return, never on the observation used to generate the signal.
    bullish = value[:-2] > 0
    earned = np.expm1(changes[2:])
    bull_return = float(earned[bullish].mean()) if bullish.any() else None
    bear_return = float(earned[~bullish].mean()) if (~bullish).any() else None
    correlation = None
    if np.std(net) > 1e-12 and np.std(market) > 1e-12:
        correlation = float(np.corrcoef(net, market)[0, 1])
    return {
        "strategy_metrics": strategy,
        "benchmark_metrics": benchmark,
        "excess_return": strategy["total_return"] - benchmark["total_return"],
        "exposure": float(held.mean()),
        "inactive_fraction": float(1 - held.mean()),
        "return_correlation": correlation,
        "bull_next_earned_return": bull_return,
        "bear_next_earned_return": bear_return,
        "future_separation": bull_return - bear_return
        if bull_return is not None and bear_return is not None
        else None,
        "capital": equity(net).tolist(),
        "benchmark_capital": equity(market).tolist(),
    }


def aggregate(results):
    summary = []
    cases = list(dict.fromkeys(r["case"] for r in results))
    policies = ["current_hmm", *CANDIDATES]
    for case in cases:
        for multiple in (1, 2):
            for policy in policies:
                group = [
                    r
                    for r in results
                    if r["case"] == case
                    and r["policy"] == policy
                    and r["fee_multiple"] == multiple
                ]
                valid = [r for r in group if "error" not in r]
                if not valid:
                    continue
                wins = sum(r["excess_return"] > 1e-10 for r in valid)
                exposed = sum(r["exposure"] >= 0.95 for r in valid)
                empty = sum(r["exposure"] <= 0.05 for r in valid)
                row = {
                    "case": case,
                    "policy": policy,
                    "fee_multiple": multiple,
                    "count": len(group),
                    "errors": len(group) - len(valid),
                    "wins": wins,
                    "win_rate": wins / len(group),
                    "median_return": float(
                        np.median(
                            [r["strategy_metrics"]["total_return"] for r in valid]
                        )
                    ),
                    "median_hold_return": float(
                        np.median(
                            [r["benchmark_metrics"]["total_return"] for r in valid]
                        )
                    ),
                    "median_excess_return": float(
                        np.median([r["excess_return"] for r in valid])
                    ),
                    "median_drawdown": float(
                        np.median(
                            [r["strategy_metrics"]["maximum_drawdown"] for r in valid]
                        )
                    ),
                    "median_orders": float(
                        np.median([len(r["trades"]) for r in valid])
                    ),
                    "median_exposure": float(np.median([r["exposure"] for r in valid])),
                    "nearly_always_invested": exposed,
                    "nearly_always_cash": empty,
                }
                # An evaluation gate, never a parameter that forces trades.
                row["passes_gate"] = (
                    row["errors"] == 0
                    and row["win_rate"] >= 0.8
                    and (exposed + empty) / len(group) <= 0.2
                )
                summary.append(row)
    return summary


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "plan.json").exists():
        raise SystemExit("Refusing to overwrite a frozen research run.")
    history = json.loads(BASELINE.read_text())
    baselines = {
        (r["asset"], r["case"], r["fee_multiple"]): r
        for r in history["results"]
        if r["policy"] == "directional_hmm"
    }
    with sqlite3.connect(
        f"file:{ROOT / 'data/investor.sqlite3'}?mode=ro", uri=True
    ) as db:
        db.row_factory = sqlite3.Row
        assets = []
        for item in db.execute(
            "SELECT * FROM assets WHERE category IN ('stock','crypto') ORDER BY id"
        ):
            asset = dict(item)
            if asset["id"] in REMOVED_CRYPTO:
                continue
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT date,value FROM observations WHERE asset_id=? ORDER BY date",
                    (asset["id"],),
                )
            ]
            assets.append((asset, rows))
    (OUT / "data.json").write_text(json.dumps(assets, allow_nan=False))
    source_paths = [
        "scripts/hmm_regime_candidates.py",
        "scripts/backtest_hmm_literature.py",
        "scripts/backtest_regimes.py",
        "backend/investor/analysis/model.py",
        "backend/investor/analysis/research_legacy.py",
        "backend/investor/analysis/switching.py",
        "backend/investor/analysis/metrics.py",
    ]
    plan = {
        "rules_fixed_before_run": True,
        "candidates": list(CANDIDATES),
        "states": 3,
        "span": SPAN,
        "refit_every_observations": REFIT,
        "lookback_observations": LOOKBACK,
        "initializations": [17, 41, 83],
        "selection": "No choice by test P&L. Three ablations, no parameter grid.",
        "features": "causal EW log-return mean, EW central standard deviation; 29 warm-up rows",
        "policies": "forecast PESR sign at h=2; alternatively fee-aware Bellman approximation",
        "execution": "close t signal, close t+1 execution, first earned return t+2; symmetric fees; terminal liquidation; cash interest zero; no leverage/short/stop",
        "fees": "stock 50bps, crypto 1bps, then double fees",
        "windows": "same 149 windows as archived current HMM, all listed 22 assets",
        "gate": "At least 80% beat net buy-and-hold per window family and fee scenario; at most 20% degenerate exposures >=95% or <=5%; zero errors. Evaluation only, never forces orders/exposure.",
        "limitations": "Existing research data, overlapping windows and survivor assets. Exploratory test, not untouched confirmation. No promise of a profitable candidate.",
        "sources": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths
        },
        "data_sha256": digest(assets),
        "baseline_sha256": hashlib.sha256(BASELINE.read_bytes()).hexdigest(),
    }
    (OUT / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    results, skipped = [], []
    for asset, rows in assets:
        for case, data, period in windows(rows):
            if (asset["id"], case, 1) not in baselines:
                skipped.append([asset["id"], case])
                continue
            data_hash = digest(data)
            changes, x = ewm_observations(np.array([r["value"] for r in data]))
            dates = np.array([r["date"] for r in data[1:]])
            for multiple in (1, 2):
                old = baselines[(asset["id"], case, multiple)]
                if old["data_sha256"] != data_hash:
                    raise ValueError(
                        "Baseline data revised; frozen comparisons no longer match"
                    )
                request = AnalysisRequest(**old["parameters"])
                test = (dates >= request.test_start.isoformat()) & (
                    dates <= request.test_end.isoformat()
                )
                common = {
                    "asset": asset["id"],
                    "name": asset["name"],
                    "category": asset["category"],
                    "case": case,
                    "fee_multiple": multiple,
                    "fee_bps": request.fee_bps,
                    "parameters": old["parameters"],
                    "data_sha256": data_hash,
                    "test_points": int(test.sum()),
                }
                results.append(
                    {
                        **common,
                        **old,
                        "policy": "current_hmm",
                        "excess_return": old["strategy_metrics"]["total_return"]
                        - old["benchmark_metrics"]["total_return"],
                    }
                )
                try:
                    signals = candidate_signals(x, dates, request)
                    for policy in CANDIDATES:
                        signal = signals[policy]
                        net, market, trades, held = execute(
                            changes[test],
                            dates[test],
                            signal["value"],
                            signal["cost"],
                            signal["probability"],
                            request.fee_bps,
                        )
                        result = diagnostics(
                            net,
                            market,
                            held,
                            signal["value"],
                            changes[test],
                            365 if asset["category"] == "crypto" else 252,
                        )
                        np.testing.assert_allclose(
                            result["benchmark_metrics"]["total_return"],
                            old["benchmark_metrics"]["total_return"],
                            rtol=1e-12,
                            atol=1e-12,
                        )
                        results.append(
                            {
                                **common,
                                "policy": policy,
                                **result,
                                "trades": trades,
                                "calibrations": signal["calibrations"],
                                "signal": signal["value"].tolist(),
                                "held": held.tolist(),
                            }
                        )
                except ValueError as exc:
                    for policy in CANDIDATES:
                        results.append({**common, "policy": policy, "error": str(exc)})
            print(asset["id"], case, "completed", flush=True)
            (OUT / "progress.json").write_text(
                json.dumps({"results": results, "skipped": skipped}, allow_nan=False)
            )
    summary = aggregate(results)
    (OUT / "results.json").write_text(
        json.dumps(
            {"plan": plan, "results": results, "skipped": skipped}, allow_nan=False
        )
    )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    with (OUT / "summary.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print(
        "Completed",
        len(results),
        "cases;",
        sum("error" in r for r in results),
        "errors.",
    )


if __name__ == "__main__":
    main()
