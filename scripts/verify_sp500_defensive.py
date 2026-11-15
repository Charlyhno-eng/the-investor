"""Historical defensive_v1 verifier (superseded by verify_sp500_compromise.py).

Requires the defensive_v1 production implementation; not for the active v2 policy.
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
    report = json.loads(
        Path("data/backtests/sp500-defensive-refinement.json").read_text()
    )
    original = db.DATA_DIR
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(original / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        if hashlib.sha256(path.read_bytes()).hexdigest() != report["snapshot_sha256"]:
            raise ValueError("Snapshot changed")
        db.DATA_DIR = Path(folder)
        results = {}
        try:
            for name, start in [
                ("full", "2018-09-17"),
                ("one_year", "2025-11-13"),
                ("three_years", "2023-11-13"),
                ("five_years", "2021-11-15"),
                ("ten_years", "2016-11-14"),
            ]:
                result = portfolio_validation(
                    ValidationRequest(
                        asset_ids=["yf-ese.pa"],
                        mode="etf_switch",
                        whole_shares=True,
                        start_date=date.fromisoformat(start),
                        end_date=date(2026, 11, 13),
                    )
                )
                if result["status"] != "ready":
                    raise ValueError(result)
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
                print(
                    name,
                    result["metrics"]["strategy"]["cagr"],
                    result["metrics"]["strategy"]["volatility"],
                    flush=True,
                )
            actual = results["full"]["metrics"]["strategy"]
            expected = report["baseline_full"]
            for key in ["cagr", "volatility", "sharpe", "max_drawdown"]:
                if abs(actual[key] - expected[key]) > 1e-9:
                    raise ValueError(
                        f"{key}: engine {actual[key]} != research {expected[key]}"
                    )
            if abs(actual["cost_eur"] - expected["fees"]) > 1e-6:
                raise ValueError("Fees differ")
            results["research_match"] = True
            output = Path("data/backtests/sp500-defensive-production-verification.json")
            output.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n")
        finally:
            db.DATA_DIR = original
    print("Production matches frozen research.", flush=True)


if __name__ == "__main__":
    main()
