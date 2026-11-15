"""Compare adopted 65/35 production against frozen independent research cases.

PYTHONPATH=backend:scripts uv run python scripts/verify_sp500_core35.py
Private SQLite snapshot, historical and seeded app paths, archived studies untouched.
"""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
from study_sp500_broader_compromise import evaluate

from investor import db
from investor.portfolio import etf_switch
from investor.portfolio.sp500_simulation import Sp500SimulationRequest, simulate_history
from investor.portfolio.validation import ValidationRequest, portfolio_validation

OUT = Path("data/backtests/sp500-core35-production-verification.json")


def check(actual, expected):
    for metric in expected:
        tolerance = 1e-6 if metric == "cost_eur" else 1e-9
        np.testing.assert_allclose(
            actual[metric], expected[metric], rtol=0, atol=tolerance, err_msg=metric
        )


def main():
    assert etf_switch.VERSION == "core35_slow_defensive_v5", (
        "Archived v5 verifier; use verify_sp500_sharpe.py for v6"
    )
    archived = json.loads(
        Path("data/backtests/sp500-broader-compromise.json").read_text()
    )
    assert archived["chosen"] == dict(family="hybrid", passive=0.35)
    report = dict(
        version=etf_switch.VERSION,
        policy=etf_switch.protocol(),
        cases={},
        archived_research="sp500-broader-compromise.json",
    )
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        report["snapshot_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        prices = np.array([r[1] for r in rows])
        original = db.DATA_DIR
        db.DATA_DIR = Path(folder)
        try:
            for years in [1, 3, 5, 10]:
                period = [f"{2026 - years}-11-13", days[-1]]
                for fee in [0.0012, 0, 0.0024]:
                    expected = evaluate(
                        days, prices, [archived["chosen"]], period, fee=fee
                    )[2]
                    result = portfolio_validation(
                        ValidationRequest(
                            asset_ids=["yf-psp5.pa"],
                            mode="etf_switch",
                            years=years,
                            whole_shares=True,
                            fee_rate=fee,
                            start_date=date.fromisoformat(period[0]),
                            end_date=date.fromisoformat(period[1]),
                        )
                    )
                    assert result["status"] == "ready", result
                    check(result["metrics"]["strategy"], expected)
                    if fee == 0.0012 and str(years) in archived["historical"]:
                        check(
                            result["metrics"]["strategy"],
                            archived["historical"][str(years)][2],
                        )
                    sleeves = result["final_portfolio"]["sleeves"]
                    assert [s["id"] for s in sleeves] == [
                        "slow",
                        "defensive",
                        "passive",
                    ]
                    assert all(s["cash"] >= -1e-6 for s in sleeves)
                    passive = [
                        t for t in result["transactions"] if t["sleeve"] == "passive"
                    ]
                    assert len(passive) == 1 and passive[0]["side"] == "buy"
                    assert passive[0]["reason"] == "etf_passive_sp500"
                    report["cases"][f"{years}y_fee{fee}"] = result["metrics"][
                        "strategy"
                    ]
        finally:
            db.DATA_DIR = original
        # Exact frozen research draws: no recomputed candidate selection.
        for years, seeds in [
            (5, [130000, 130001, 130042]),
            (10, [140000, 140001, 140042]),
        ]:
            for seed in seeds:
                result = simulate_history(
                    rows, Sp500SimulationRequest(years=years, seed=seed)
                )
                assert result["status"] == "ready", result
                offset = seed - (130000 if years == 5 else 140000)
                expected = archived["audit"][str(years)]["paths"][offset][2]
                check(result["comparison"]["metrics"]["strategy"], expected)
                report["cases"][f"synthetic{years}y_seed{seed}"] = result["comparison"][
                    "metrics"
                ]["strategy"]
    OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(len(report["cases"]), "cases match independent research:", OUT)


if __name__ == "__main__":
    main()
