"""One fixed policy, local diagnostics only; no selection on these known periods."""

import csv
import hashlib
import json
import sqlite3
from pathlib import Path

from investor.analysis.bars import enrich_rows
from investor.analysis.schemas import AnalysisRequest
from investor.analysis.service import calculate
from investor.analysis.strategy import POLICIES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/backtests/hmm-reentry"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "results.json"
    if target.exists():
        raise SystemExit("Refusing to overwrite existing diagnostics.")
    plan = {
        "policy": "Daily predicted HMM return with cost-amortized bands, no transaction count target. Resting trailing 10% net stop per position, gap fill at open, fresh bullish recovery reentry.",
        "parameters_chosen_from_results": False,
        "period": "Train 2015-2021, test 2022-2025 continuously; these periods are already consumed research data, not an untouched holdout.",
        "fees_bps": [0, 10, 50],
        "compare": ["previous_weekly_latch", "reentry_cost_band"],
        "scope": "Every stock/crypto in local catalog with >=101 training prices.",
        "screenshot_case": "GTT, same default 2016 most recent observations / 70% split as frontend.",
        "model": "Unchanged two-state Gaussian HMM; no new seed/hyperparameter search.",
        "sources": {},
    }
    for module in ["model", "strategy", "reentry", "bars", "service", "metrics"]:
        p = ROOT / f"backend/investor/analysis/{module}.py"
        plan["sources"][module] = hashlib.sha256(p.read_bytes()).hexdigest()
    (OUT / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    results, skipped = [], []
    with sqlite3.connect(
        f"file:{ROOT / 'data/investor.sqlite3'}?mode=ro", uri=True
    ) as db:
        db.row_factory = sqlite3.Row
        for asset in db.execute(
            "SELECT * FROM assets WHERE category IN ('stock','crypto') ORDER BY id"
        ).fetchall():
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT date,value FROM observations WHERE asset_id=? AND date>=? AND date<=? ORDER BY date",
                    (asset["id"], "2015-01-01", "2025-12-31"),
                )
            ]
            if sum(r["date"] <= "2021-12-31" for r in rows) < 101:
                skipped.append(asset["id"])
                continue
            windows = [
                (
                    "continuous",
                    rows,
                    {
                        "train_start": rows[0]["date"],
                        "train_end": "2021-12-31",
                        "test_start": "2022-01-01",
                        "test_end": "2025-12-31",
                    },
                )
            ]
            if asset["id"] == "yf-gtt.pa":
                screen = [
                    dict(r)
                    for r in db.execute(
                        "SELECT date,value FROM observations WHERE asset_id=? ORDER BY date",
                        (asset["id"],),
                    )
                ][-2016:]
                cut = int(len(screen) * 0.7)
                windows.append(
                    (
                        "screenshot",
                        screen,
                        {
                            "train_start": screen[0]["date"],
                            "train_end": screen[cut]["date"],
                            "test_start": screen[cut + 1]["date"],
                            "test_end": screen[-1]["date"],
                        },
                    )
                )
            for case, window, period in windows:
                history = enrich_rows(asset["id"], window)
                digest = hashlib.sha256(
                    json.dumps(history, sort_keys=True).encode()
                ).hexdigest()
                for name, policy in [
                    ("previous_weekly_latch", POLICIES["weekly_hmm"]),
                    ("reentry_cost_band", None),
                ]:
                    for fee in plan["fees_bps"]:
                        request = AnalysisRequest(**period, fee_bps=fee)
                        result = calculate(dict(asset), history, request, policy=policy)
                        results.append(
                            dict(
                                case=case,
                                asset=asset["id"],
                                policy=name,
                                fee_bps=fee,
                                data_sha256=digest,
                                parameters=request.model_dump(mode="json"),
                                **{
                                    k: result[k]
                                    for k in [
                                        "actual_test",
                                        "strategy_metrics",
                                        "benchmark_metrics",
                                        "trades",
                                        "equity",
                                        "exposure",
                                        "risk_control",
                                    ]
                                },
                            )
                        )
    target.write_text(
        json.dumps(
            {"plan": plan, "skipped": skipped, "results": results}, allow_nan=False
        )
        + "\n"
    )
    with (OUT / "summary.csv").open("w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "case",
                "asset",
                "policy",
                "fee_bps",
                "net_return",
                "market_return",
                "max_drawdown",
                "orders",
                "stops",
                "reentries",
                "gaps",
                "ohlc_points",
                "data_sha256",
            ]
        )
        for r in results:
            ev = r["risk_control"]["events"]
            writer.writerow(
                [
                    r["case"],
                    r["asset"],
                    r["policy"],
                    r["fee_bps"],
                    r["strategy_metrics"]["total_return"],
                    r["benchmark_metrics"]["total_return"],
                    r["strategy_metrics"]["maximum_drawdown"],
                    len(r["trades"]),
                    len(ev),
                    sum(e.get("reentered_at") is not None for e in ev),
                    sum(e.get("gap", False) for e in ev),
                    r["risk_control"].get("ohlc_points"),
                    r["data_sha256"],
                ]
            )
    print(len(results), "diagnostics; skipped", skipped)
    for r in results:
        if r["case"] == "screenshot" and r["fee_bps"] == 10:
            print(
                r["policy"],
                r["parameters"],
                r["strategy_metrics"],
                len(r["trades"]),
                r["risk_control"],
            )


if __name__ == "__main__":
    main()
