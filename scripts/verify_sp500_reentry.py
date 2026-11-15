"""Historical v3 recovery verifier, superseded by verify_sp500_warm_state.py.

Run: PYTHONPATH=backend uv run python scripts/verify_sp500_reentry.py
Implementation equivalence only, not prospective financial validation.
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
    frozen = json.loads(Path("data/backtests/sp500-next-iteration.json").read_text())
    index = frozen["audit_index"]
    expected_config = dict(
        exit="level",
        recovery="rebound0",
        floor=0.25,
        slow_share=0.75,
        weekly=False,
        scope="slow",
    )
    if frozen["configs"][index] != expected_config:
        raise ValueError("Frozen candidate is not the explicitly adopted policy")
    cases = {
        k: (period, frozen["results"][k]["candidates"][index])
        for k, period in {
            "train": ["2018-09-17", "2020-12-31"],
            "validation": ["2021-01-04", "2023-12-29"],
            "later": ["2024-01-02", "2026-11-13"],
            "five_years": ["2021-11-13", "2026-11-13"],
            "ten_years": ["2016-11-13", "2026-11-13"],
        }.items()
    }
    for span in [3, 5]:
        for year in range(2016, 2027 - span):
            name = f"{span}y_{year}"
            cases[name] = (
                [f"{year}-11-13", f"{year + span}-11-13"],
                frozen["rolling"][name]["candidate"],
            )
    original = db.DATA_DIR
    results = {}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(original / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as source,
            sqlite3.connect(path) as dest,
        ):
            source.backup(dest)
        fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
        if fingerprint != frozen["snapshot_sha256"]:
            raise ValueError(
                "Snapshot differs from frozen research; do not compare different inputs"
            )
        db.DATA_DIR = Path(folder)
        try:
            for name, (period, expected) in cases.items():
                result = portfolio_validation(
                    ValidationRequest(
                        asset_ids=["yf-ese.pa"],
                        mode="etf_switch",
                        whole_shares=True,
                        start_date=date.fromisoformat(period[0]),
                        end_date=date.fromisoformat(period[1]),
                    )
                )
                if result["status"] != "ready":
                    raise ValueError(result)
                actual = result["metrics"]["strategy"]
                for key in ["cagr", "volatility", "sharpe", "max_drawdown"]:
                    if abs(actual[key] - expected[key]) > 1e-9:
                        raise ValueError((name, key, actual[key], expected[key]))
                if abs(actual["cost_eur"] - expected["fees"]) > 1e-6:
                    raise ValueError((name, "fees"))
                final = result["final_portfolio"]
                if abs(final["total"] - expected["final_value"]) > 1e-6:
                    raise ValueError((name, "final_value"))
                if abs(final["cash"] - sum(s["cash"] for s in final["sleeves"])) > 1e-6:
                    raise ValueError((name, "sleeve_cash"))
                results[name] = {
                    k: result[k]
                    for k in [
                        "start",
                        "end",
                        "metrics",
                        "protocol",
                        "final_portfolio",
                        "transactions",
                    ]
                }
                print(name, "matches", flush=True)
        finally:
            db.DATA_DIR = original
    output = Path("data/backtests/sp500-reentry-production-verification.json")
    output.write_text(
        json.dumps(
            dict(snapshot_sha256=fingerprint, research_match=True, results=results),
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    print(f"Production matches all {len(results)} frozen research cases.", flush=True)


if __name__ == "__main__":
    main()
