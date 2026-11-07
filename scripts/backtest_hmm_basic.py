"""Evaluate exactly two regimes, higher mean / other, with no trading filter.

No test-set selection. Every stock, UI defaults and annual 2024/2025/2026,
0 and 50 bps per order. Same execution/benchmark conventions as the catalog audit.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import median

from audit_hmm_stocks import default_request, universe
from investor.analysis.basic import SEEDS, VERSION, evaluate
from investor.analysis.evaluation import majority_acceptance
from investor.analysis.schemas import AnalysisRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/investor.sqlite3"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assert-majority", action="store_true")
    args = parser.parse_args()
    catalog = universe(args.database)
    expected = [asset["id"] for asset, _ in catalog]
    entries = []
    protocol = {
        "version": VERSION,
        "states": 2,
        "observable": "daily_log_return",
        "decision": "long_if_highest_training_mean_state_has_dominant_filtered_probability_else_cash",
        "seeds_by_training_likelihood": SEEDS,
        "fees_bps": [0, 50],
        "execution": "next_close",
        "refitting": False,
        "test_selection": False,
        "model_count_selection": False,
    }
    for asset, full in catalog:
        defaults = default_request(full)
        periods = [("interface_default", defaults)]
        for year in (2024, 2025, 2026):
            periods.append(
                (
                    f"annual_{year}",
                    AnalysisRequest(
                        train_start=max(full[0]["date"], f"{year - 5}-01-01"),
                        train_end=f"{year - 1}-12-31",
                        test_start=f"{year}-01-01",
                        test_end=min(f"{year}-12-31", full[-1]["date"]),
                        fee_bps=50,
                    ),
                )
            )
        for case, request in periods:
            rows = [
                r
                for r in full
                if request.train_start.isoformat()
                <= r["date"]
                <= request.test_end.isoformat()
            ]
            base = {
                "asset_id": asset["id"],
                "name": asset["name"],
                "case": case,
                "parameters": request.model_dump(mode="json"),
                "data_sha256": hashlib.sha256(
                    json.dumps(rows, sort_keys=True).encode()
                ).hexdigest(),
            }
            try:
                results = evaluate(rows, request)
                entries.extend({**base, **r} for r in results)
                print(
                    json.dumps(
                        {
                            "asset_id": asset["id"],
                            "case": case,
                            "outcomes": [
                                {
                                    k: r[k]
                                    for k in (
                                        "fee_bps",
                                        "excess_return",
                                        "transactions",
                                    )
                                }
                                for r in results
                            ],
                        }
                    ),
                    flush=True,
                )
            except (ValueError, ArithmeticError) as exc:
                entries.extend(
                    {**base, "fee_bps": fee, "error": str(exc)} for fee in (0, 50)
                )
            args.output.write_text(
                json.dumps(
                    {"protocol": protocol, "results": entries},
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            )
    summary = []
    for case in ("interface_default", "annual_2024", "annual_2025", "annual_2026"):
        for fee in (0, 50):
            group = [r for r in entries if r["case"] == case and r["fee_bps"] == fee]
            valid = [r for r in group if "error" not in r]
            summary.append(
                {
                    "case": case,
                    "fee_bps": fee,
                    "acceptance": majority_acceptance(group, expected),
                    "median_excess_return": median(r["excess_return"] for r in valid),
                    "median_transactions": median(r["transactions"] for r in valid),
                }
            )
    args.output.write_text(
        json.dumps(
            {"protocol": protocol, "summary": summary, "results": entries},
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w") as stream:
        fields = [
            "asset_id",
            "name",
            "case",
            "fee_bps",
            "strategy_return",
            "benchmark_return",
            "excess_return",
            "transactions",
            "exposure",
            "regime_exits",
            "bullish_mean_positive",
            "data_sha256",
            "error",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for r in entries:
            writer.writerow(
                {
                    **{
                        key: r.get(key)
                        for key in fields
                        if key not in ("strategy_return", "benchmark_return")
                    },
                    "strategy_return": r.get("strategy", {}).get("total_return"),
                    "benchmark_return": r.get("benchmark", {}).get("total_return"),
                }
            )
    print(json.dumps(summary, indent=2), flush=True)
    gate = next(
        r["acceptance"]
        for r in summary
        if r["case"] == "interface_default" and r["fee_bps"] == 50
    )
    if args.assert_majority and not gate["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
