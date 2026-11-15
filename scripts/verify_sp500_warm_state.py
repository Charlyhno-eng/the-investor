"""Verify the explicitly adopted warm-state policy on a private SQLite backup.

Run: PYTHONPATH=backend uv run python scripts/verify_sp500_warm_state.py
Frozen research equivalence only; not a prospective financial validation.
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
    frozen = json.loads(Path("data/backtests/sp500-three-years.json").read_text())
    audit = json.loads(Path("data/backtests/sp500-three-years-audit.json").read_text())
    config = dict(entry="daily_cross", exit="level1.5", cadence="monthly", warm=True)
    index = frozen["selected_index"]
    if frozen["selected"] != config or audit["candidate"] != config:
        raise ValueError("Frozen research is not the explicitly adopted policy")
    cases = {
        name: (period, frozen["results"][name][index])
        for name, period in frozen["periods"].items()
    }
    for span in [3, 5]:
        for year in range(2016, 2027 - span):
            name = f"{span}y_{year}"
            cases[name] = (
                [f"{year}-11-13", f"{year + span}-11-13"],
                frozen["rolling"][name][index],
            )
    cases["one_year"] = (["2025-11-13", "2026-11-13"], audit["one_year"][1])
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
        if (
            fingerprint != frozen["snapshot_sha256"]
            or fingerprint != audit["snapshot_sha256"]
        ):
            raise ValueError("Snapshot differs from the frozen research")
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
                if (
                    result["protocol"]["etf_switch"]["version"]
                    != "slow_defensive_warm_state_v4"
                ):
                    raise ValueError("Unexpected production policy")
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
                    raise ValueError((name, "cash"))
                if abs(result["equity"][0]["strategy"] - 100) > 1e-9:
                    raise ValueError((name, "Initial capital contains prior gains"))
                if any(
                    t["signal"] < result["start"] or t["execution"] <= t["signal"]
                    for t in result["transactions"]
                ):
                    raise ValueError((name, "Backdated transaction"))
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
    output = Path("data/backtests/sp500-warm-state-production-verification.json")
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
