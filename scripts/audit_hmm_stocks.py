"""Read-only, exhaustive catalog audit of the production HMM at actual UI fees.

Every stock is included, with explicit errors and no performance-based exclusions.
"""

import argparse
import hashlib
import json
import sqlite3
import time
from pathlib import Path

from investor.analysis.evaluation import majority_acceptance
from investor.analysis.schemas import AnalysisRequest
from investor.analysis.service import VERSION, calculate


def universe(database):
    with sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        assets = db.execute(
            "SELECT * FROM assets WHERE category='stock' ORDER BY id"
        ).fetchall()
        return [
            (
                dict(asset),
                [
                    dict(row)
                    for row in db.execute(
                        "SELECT date,value FROM observations WHERE asset_id=? ORDER BY date",
                        (asset["id"],),
                    )
                ],
            )
            for asset in assets
        ]


def default_request(rows):
    if len(rows) < 3:
        raise ValueError("Insufficient price history")
    start = max(0, len(rows) - 252 * 8)
    cut = min(len(rows) - 2, start + int((len(rows) - start) * 0.7))
    return AnalysisRequest(
        train_start=rows[start]["date"],
        train_end=rows[cut]["date"],
        test_start=rows[cut + 1]["date"],
        test_end=rows[-1]["date"],
        fee_bps=50,
    )


def audit(database, output):
    entries = []
    catalog = universe(database)
    expected_assets = [asset["id"] for asset, _ in catalog]
    output.write_text(
        json.dumps(
            {
                "version": VERSION,
                "results": [],
                "acceptance": majority_acceptance([], expected_assets),
            },
            indent=2,
        )
        + "\n"
    )
    for asset, rows in catalog:
        started = time.monotonic()
        entry = {
            "asset_id": asset["id"],
            "name": asset["name"],
        }
        try:
            request = default_request(rows)
            selected = [
                r
                for r in rows
                if request.train_start.isoformat()
                <= r["date"]
                <= request.test_end.isoformat()
            ]
            entry.update(
                parameters=request.model_dump(mode="json"),
                data_sha256=hashlib.sha256(
                    json.dumps(selected, sort_keys=True).encode()
                ).hexdigest(),
            )
            result = calculate(asset, selected, request)
            entry.update(
                strategy=result["strategy_metrics"],
                benchmark=result["benchmark_metrics"],
                excess_return=result["strategy_metrics"]["total_return"]
                - result["benchmark_metrics"]["total_return"],
                exposure=result["exposure"],
                transactions=len(result["trades"]),
                states=result["states"],
                policy=result["policy"],
                model_selection=result["model_selection"],
                diagnostics=result["diagnostics"],
            )
        except Exception as exc:  # noqa: BLE001 - Audit must retain every failed asset.
            entry["error"] = f"{type(exc).__name__}: {exc}"
        entry["seconds"] = round(time.monotonic() - started, 3)
        entries.append(entry)
        print(
            json.dumps(
                {
                    k: entry.get(k)
                    for k in (
                        "asset_id",
                        "excess_return",
                        "exposure",
                        "transactions",
                        "error",
                        "seconds",
                    )
                }
            ),
            flush=True,
        )
        output.write_text(
            json.dumps(
                {
                    "version": VERSION,
                    "results": entries,
                    "acceptance": majority_acceptance(entries, expected_assets),
                },
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )
    return entries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/investor.sqlite3"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--assert-majority",
        action="store_true",
        help="Exit 1 unless the entire stock catalog passes the economic criterion",
    )
    args = parser.parse_args()
    entries = audit(args.database, args.output)
    receipt = json.loads(args.output.read_text())["acceptance"]
    print(json.dumps(receipt), flush=True)
    if args.assert_majority and not receipt["passed"]:
        raise SystemExit(1)
