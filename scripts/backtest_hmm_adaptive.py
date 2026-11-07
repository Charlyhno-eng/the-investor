"""Fixed-design local evaluation of the trend-regime HMM, with a cash ledger.

Uses the already frozen research prices, never downloads data or writes the DB.
This is exploratory reused data, not an untouched financial validation.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from backtest_regimes import windows
from investor.analysis import adaptive
from investor.analysis.schemas import AnalysisRequest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/backtests/hmm-adaptive"
SNAPSHOT = ROOT / "data/backtests/hmm-literature/data.json"
BASELINE = ROOT / "data/backtests/hmm-directional-final/results.json"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def verify_ledger(result, rows):
    """Independently rebuild capital from cash, shares, actual prices and orders."""
    prices = {r["date"]: r["value"] for r in rows}
    trades = {t["time"]: t["side"] for t in result["trades"]}
    fee = result["parameters"]["fee_bps"] / 10000
    cash, units, held = 1.0, 0.0, []
    reconstructed = [1.0]
    for point in result["equity"][1:]:
        held.append(int(units > 0))
        price, side = prices[point["time"]], trades.get(point["time"])
        if side == "buy":
            assert units == 0
            units, cash = cash * (1 - fee) / price, 0.0
        elif side == "sell":
            assert units > 0
            cash, units = units * price * (1 - fee), 0.0
        reconstructed.append(cash + units * price)
    np.testing.assert_allclose(
        reconstructed,
        [p["strategy"] / 100 for p in result["equity"]],
        atol=1e-11,
        rtol=1e-11,
    )
    np.testing.assert_allclose(np.mean(held), result["exposure"], atol=1e-14)
    assert units == 0
    return float(
        np.max(
            np.abs(
                np.array(reconstructed)
                - [p["strategy"] / 100 for p in result["equity"]]
            )
        )
    )


def summary(results):
    output = []
    for case in dict.fromkeys(r["case"] for r in results):
        for multiple in (1, 2):
            group = [
                r
                for r in results
                if r["case"] == case and r["fee_multiple"] == multiple
            ]
            good = [r for r in group if "error" not in r]
            if not good:
                continue
            get = lambda name, group=good: [r["result"][name] for r in group]
            returns = [v["total_return"] for v in get("strategy_metrics")]
            benchmark = [v["total_return"] for v in get("benchmark_metrics")]
            wins = sum(a > b + 1e-10 for a, b in zip(returns, benchmark))
            exposures = get("exposure")
            output.append(
                {
                    "case": case,
                    "fee_multiple": multiple,
                    "count": len(group),
                    "errors": len(group) - len(good),
                    "wins": wins,
                    "median_return": float(np.median(returns)),
                    "median_hold_return": float(np.median(benchmark)),
                    "median_excess": float(np.median(np.array(returns) - benchmark)),
                    "median_exposure": float(np.median(exposures)),
                    "median_orders": float(np.median([len(t) for t in get("trades")])),
                    "median_drawdown": float(
                        np.median(
                            [v["maximum_drawdown"] for v in get("strategy_metrics")]
                        )
                    ),
                    "nearly_always_invested": sum(e >= 0.95 for e in exposures),
                    "nearly_always_cash": sum(e <= 0.05 for e in exposures),
                    "passes_performance_gate": wins / len(group) >= 0.8
                    and len(good) == len(group),
                }
            )
    return output


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "plan.json").exists():
        raise SystemExit("Refusing to overwrite a frozen experiment")
    assets = json.loads(SNAPSHOT.read_text())
    old = {
        (r["asset"], r["case"], r["fee_multiple"]): r
        for r in json.loads(BASELINE.read_text())["results"]
        if r["policy"] == "directional_hmm"
    }
    sources = [
        "backend/investor/analysis/adaptive.py",
        "backend/investor/analysis/model.py",
        "backend/investor/analysis/research_legacy.py",
        "backend/investor/analysis/metrics.py",
        "scripts/backtest_hmm_adaptive.py",
    ]
    plan = {
        "design": "Three states; EW mean/std ratio span30; seeds17/41/83 selected by training likelihood; refit63 trailing1260; adverse dominant negative state exits irrespective of costs; favorable dominant positive state enters only if expected duration move covers roundtrip fees; middle holds.",
        "exploratory": True,
        "limitations": "Reused data, overlapping windows, survivor universe. Initial Air Liquide/ETH/GTT smoke results already examined. No claim of an untouched holdout or absence of overfitting. No P&L parameter search.",
        "fees": "50bps stock, 1bps crypto, then doubled; each buy/sell",
        "execution": "Signal at close t, execution close t+1, first return t+2; final liquidation; no stop, short, leverage or trade/exposure quota.",
        "gate": "80% net outperformance per window family and fee scenario; evaluated only, never forces transactions.",
        "data_sha256": digest(assets),
        "sources": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources
        },
    }
    (OUT / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    for source in sources:
        archive = OUT / "sources" / source
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes((ROOT / source).read_bytes())
    results, skipped = [], []
    for asset, rows in assets:
        for case, data, _ in windows(rows):
            for multiple in (1, 2):
                baseline = old.get((asset["id"], case, multiple))
                if baseline is None:
                    skipped.append([asset["id"], case, multiple])
                    continue
                assert digest(data) == baseline["data_sha256"]
                row = {
                    "asset": asset["id"],
                    "name": asset["name"],
                    "case": case,
                    "fee_multiple": multiple,
                }
                try:
                    result = adaptive.calculate(
                        asset, data, AnalysisRequest(**baseline["parameters"])
                    )
                    np.testing.assert_allclose(
                        result["benchmark_metrics"]["total_return"],
                        baseline["benchmark_metrics"]["total_return"],
                        atol=1e-12,
                    )
                    row.update(result=result, ledger_error=verify_ledger(result, data))
                except (ValueError, AssertionError) as exc:
                    row["error"] = str(exc)
                results.append(row)
        print(asset["id"], len(results), "cases", flush=True)
        (OUT / "progress.json").write_text(
            json.dumps({"completed": len(results), "last_asset": asset["id"]})
        )
    (OUT / "results.json").write_text(
        json.dumps({"results": results, "skipped": skipped}, allow_nan=False)
    )
    totals = summary(results)
    (OUT / "summary.json").write_text(json.dumps(totals, indent=2) + "\n")
    print(json.dumps(totals, indent=2), flush=True)


if __name__ == "__main__":
    main()
