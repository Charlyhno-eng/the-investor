"""Verify adopted v6 against the frozen historical-Sharpe research candidate.

PYTHONPATH=backend:scripts .venv/bin/python scripts/verify_sp500_sharpe.py
Private SQLite copy; all pre-adoption research reports remain unchanged.
"""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
from study_sp500_deep_search import evaluate

from investor import db
from investor.portfolio import etf_switch
from investor.portfolio.sp500_simulation import Sp500SimulationRequest, simulate_history
from investor.portfolio.validation import ValidationRequest, portfolio_validation

OUT = Path("data/backtests/sp500-sharpe-production-verification.json")
VERSION = "slow_defensive_sharpe_v6"


def check(actual, expected):
    for metric, value in expected.items():
        if value is None:
            assert actual[metric] is None, metric
        else:
            np.testing.assert_allclose(
                actual[metric],
                value,
                rtol=0,
                atol=1e-6 if metric == "cost_eur" else 1e-9,
                err_msg=metric,
            )


def check_books(result):
    assert result["status"] == "ready", result
    sleeves = result["final_portfolio"]["sleeves"]
    assert [s["id"] for s in sleeves] == ["slow", "defensive"]
    assert all(s["cash"] >= -1e-6 and s["quantity"] >= 0 for s in sleeves)
    np.testing.assert_allclose(
        sum(s["cash"] for s in sleeves),
        result["final_portfolio"]["cash"],
        atol=1e-6,
        rtol=0,
    )
    assert all(t["sleeve"] in {"slow", "defensive"} for t in result["transactions"])
    assert all(
        t["execution"] > t["signal"] >= result["start"] for t in result["transactions"]
    )
    assert result["equity"][0]["strategy"] == 100


def main():
    assert etf_switch.VERSION == VERSION, "Verifier is frozen to adopted v6"
    archived = json.loads(Path("data/backtests/sp500-sharpe-history.json").read_text())
    candidate = archived["frozen_config"]
    assert candidate == dict(
        family="regression_joint",
        passive=0,
        regression=dict(
            entry="daily_cross",
            exit="level1.5",
            cadence="monthly",
            warm=True,
            floor=0.1,
            slow_share=0.75,
            defensive_exit=1.5,
        ),
    )
    report = dict(
        version=VERSION,
        policy=etf_switch.protocol(),
        cases={},
        archived_research="sp500-sharpe-history.json",
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro",
                uri=True,
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        report["snapshot_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' AND o.date<='2026-11-13' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        p = np.array([r[1] for r in rows])
        assert np.array_equal(p, [r[2] for r in rows])
        original = db.DATA_DIR
        db.DATA_DIR = Path(directory)
        try:
            cases = [(y, fee, 1) for y in [1, 3, 5, 10] for fee in [0.0012, 0, 0.0024]]
            for years, fee, delay in cases:
                period = [f"{2026 - years}-11-13", days[-1]]
                expected = evaluate(days, p, [candidate], period, fee=fee, delay=delay)[
                    2
                ]
                request = ValidationRequest(
                    asset_ids=["yf-psp5.pa"],
                    mode="etf_switch",
                    years=years,
                    whole_shares=True,
                    fee_rate=fee,
                    start_date=date.fromisoformat(period[0]),
                    end_date=date.fromisoformat(period[1]),
                )
                result = portfolio_validation(request)
                check_books(result)
                check(result["metrics"]["strategy"], expected)
                frozen = None
                if fee == 0.0012 and delay == 1:
                    frozen = archived["historical"][str(years)][2]
                elif fee == 0.0024 and str(years) in archived["stress"]["double_fees"]:
                    frozen = archived["stress"]["double_fees"][str(years)][2]
                if frozen is not None:
                    check(result["metrics"]["strategy"], frozen)
                report["cases"][f"{years}y_fee{fee}_delay{delay}"] = result["metrics"][
                    "strategy"
                ]
        finally:
            db.DATA_DIR = original
        for years, first_seed in [(5, 1820000), (10, 1830000)]:
            for offset in [0, 1, 42]:
                seed = first_seed + offset
                result = simulate_history(
                    rows, Sp500SimulationRequest(years=years, seed=seed)
                )
                assert result["status"] == "ready", result
                comparison = result["comparison"]
                check_books(comparison)
                for j, key in [(0, "benchmark"), (2, "strategy")]:
                    check(
                        comparison["metrics"][key],
                        archived["audit"][str(years)]["paths"][offset][j],
                    )
                report["cases"][f"synthetic{years}y_seed{seed}"] = comparison[
                    "metrics"
                ]["strategy"]
    OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(len(report["cases"]), "cases match frozen research:", OUT)


if __name__ == "__main__":
    main()
