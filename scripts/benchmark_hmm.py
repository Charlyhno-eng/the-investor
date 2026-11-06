"""Read-only evaluation; never use these test outcomes to tune the model.

Run: PYTHONPATH=backend .venv/bin/python scripts/benchmark_hmm.py --output /tmp/hmm.json
"""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from investor.analysis.schemas import AnalysisRequest
from investor.analysis.service import VERSION, calculate

ASSETS = (
    "yf-aapl",
    "yf-msft",
    "yf-nvda",
    "yf-ai.pa",
    "yf-mc.pa",
    "yf-btc-usd",
    "yf-eth-usd",
    "yf-sol-usd",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/investor.sqlite3"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("calendar", "split"), default="calendar")
    args = parser.parse_args()
    results, skipped = [], []
    with sqlite3.connect(f"{args.database.resolve().as_uri()}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        for aid in ASSETS:
            asset = db.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone()
            if asset is None:
                skipped.append({"asset": aid, "reason": "absent"})
                continue
            periods = (
                ((2015, 2020), (2017, 2022), (2019, 2024))
                if args.mode == "split"
                else ((2015, 2021), (2017, 2023), (2019, 2025), (2020, 2026))
            )
            for start, end in periods:
                rows = [
                    dict(r)
                    for r in db.execute(
                        "SELECT date,value FROM observations WHERE asset_id=? AND date>=? AND date<=? ORDER BY date",
                        (
                            aid,
                            f"{start}-01-01",
                            (
                                f"{end}-01-01"
                                if args.mode == "split"
                                else f"{end - 1}-12-31"
                            ),
                        ),
                    )
                ]
                if len(rows) < 500:
                    skipped.append(
                        {
                            "asset": aid,
                            "start": start,
                            "end": end,
                            "reason": "less than 500 prices",
                        }
                    )
                    continue
                if args.mode == "split":
                    cut = int(len(rows) * 0.7)
                else:
                    cut = max(
                        i for i, r in enumerate(rows) if r["date"] < f"{end - 1}-01-01"
                    )
                fingerprint = hashlib.sha256(
                    json.dumps(rows, sort_keys=True).encode()
                ).hexdigest()
                for fee in (10,) if args.mode == "split" else (0, 10, 50):
                    request = AnalysisRequest(
                        train_start=rows[0]["date"],
                        train_end=rows[cut]["date"],
                        test_start=rows[cut + 1]["date"],
                        test_end=rows[-1]["date"],
                        fee_bps=fee,
                    )
                    result = calculate(dict(asset), rows, request)
                    results.append(
                        {
                            "asset": aid,
                            "data_sha256": fingerprint,
                            "parameters": request.model_dump(mode="json"),
                            "actual_train": result["actual_train"],
                            "actual_test": result["actual_test"],
                            "strategy": result["strategy_metrics"],
                            "benchmark": result["benchmark_metrics"],
                            "trades": len(result["trades"]),
                            "exposure": result["exposure"],
                            "states": result["states"],
                            "warnings": result["warnings"],
                        }
                    )
    args.output.write_text(
        json.dumps(
            {
                "version": VERSION,
                "mode": args.mode,
                "results": results,
                "skipped": skipped,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    print(f"{len(results)} evaluations; {len(skipped)} skipped; {args.output}")


if __name__ == "__main__":
    main()
