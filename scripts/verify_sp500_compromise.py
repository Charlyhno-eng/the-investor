"""Historical v2 verifier, superseded by verify_sp500_reentry.py for active v3.

Verify the former two-sleeve policy against its frozen audit on a private DB copy.

Run from the project root: PYTHONPATH=backend uv run python scripts/verify_sp500_compromise.py
This checks the implementation, not independent financial validation.
"""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

from investor import db
from investor.portfolio.validation import ValidationRequest, portfolio_validation


def main():
    audit = json.loads(Path("data/backtests/sp500-compromise-audit.json").read_text())
    source = json.loads(Path("data/backtests/sp500-return-drawdown.json").read_text())
    original = db.DATA_DIR
    results = {}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(original / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        snapshot = hashlib.sha256(path.read_bytes()).hexdigest()
        if snapshot != source["snapshot_sha256"]:
            raise ValueError("Snapshot changed; cannot compare to frozen research")
        db.DATA_DIR = Path(folder)
        try:
            for name, case in audit["results"].items():
                if name == "ten_years":
                    start, end = "2016-11-13", "2026-11-13"
                else:
                    span, year = map(int, name.replace("y_", "_").split("_"))
                    start, end = f"{year}-11-13", f"{year + span}-11-13"
                result = portfolio_validation(
                    ValidationRequest(
                        asset_ids=["yf-ese.pa"],
                        mode="etf_switch",
                        whole_shares=True,
                        start_date=date.fromisoformat(start),
                        end_date=date.fromisoformat(end),
                    )
                )
                if result["status"] != "ready":
                    raise ValueError(result)
                actual = result["metrics"]["strategy"]
                expected = case["metrics"]
                for key in ["cagr", "volatility", "sharpe", "max_drawdown"]:
                    if abs(actual[key] - expected[key]) > 1e-9:
                        raise ValueError(
                            f"{name} {key}: {actual[key]} != {expected[key]}"
                        )
                if abs(actual["cost_eur"] - expected["fees"]) > 1e-6:
                    raise ValueError(f"{name}: fees differ")
                final = result["final_portfolio"]
                if abs(final["total"] - expected["final_value"]) > 1e-6:
                    raise ValueError(f"{name}: final capital differs")
                if abs(final["cash"] - sum(s["cash"] for s in final["sleeves"])) > 1e-6:
                    raise ValueError(f"{name}: sleeve cash differs")
                results[name] = {
                    k: result[k]
                    for k in [
                        "start",
                        "end",
                        "metrics",
                        "transactions",
                        "protocol",
                        "final_portfolio",
                    ]
                }
                print(name, "matches", flush=True)
        finally:
            db.DATA_DIR = original
    output = Path("data/backtests/sp500-compromise-production-verification.json")
    output.write_text(
        json.dumps(
            {
                "snapshot_sha256": snapshot,
                "research_match": True,
                "results": results,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    print(f"Production matches all {len(results)} frozen research cases.", flush=True)


if __name__ == "__main__":
    main()
