"""Verify the production policy against frozen historical and simulated PSP5 books."""

import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path

import numpy as np

from investor import db
from investor.portfolio.sp500_simulation import (
    Sp500BatchRequest,
    Sp500SimulationRequest,
    simulate_history,
    stream_sp500_batch,
)
from investor.portfolio.validation import ValidationRequest, portfolio_validation


async def check_batch(archive):
    async def disconnected():
        return False

    req = Sp500BatchRequest(
        strategy="downside", years=5, count=archive["count"], seed=archive["seed"]
    )
    async for line in stream_sp500_batch(req, disconnected):
        result = json.loads(line)
    assert result["status"] == "complete" and result["completed"] == archive["count"]
    for key, index in [
        ("sharpe", 0),
        ("cagr", 1),
        ("max_drawdown", 2),
        ("volatility", 3),
        ("cost_eur", 4),
    ]:
        row = result["metrics"][key]
        np.testing.assert_allclose(
            [row["strategy_mean"], row["benchmark_mean"]],
            [archive["mean"][-1][index], archive["mean"][0][index]],
            rtol=0,
            atol=1e-8,
        )
    assert (
        result["metrics"]["sharpe"]["strategy_wins"]
        == archive["paired"]["passive"]["sharpe"]["wins"]
    )
    assert result["joint_wins"] == archive["paired"]["passive"]["joint"]
    print("Verified", result["completed"], "paired production simulations", flush=True)


def main():
    archive = json.loads(Path("data/backtests/pea-agreement-1000.json").read_text())
    history = json.loads(Path("data/backtests/pea-sharpe-hybrid.json").read_text())
    idx = history["frozen"].index(["agreement", 0.25, 32, 1, 0.05])
    with tempfile.TemporaryDirectory() as tmp:
        with (
            sqlite3.connect(
                f"file:{db.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
            ) as src,
            sqlite3.connect(Path(tmp) / "investor.sqlite3") as dest,
        ):
            src.backup(dest)
            # Freeze to the audited dates even if the user's catalogue has grown.
            for table in ("observations", "price_observations"):
                dest.execute(
                    f"DELETE FROM {table} WHERE asset_id=? AND date>?",
                    ("yf-psp5.pa", archive["source"][1]),
                )
            rows = dest.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p USING(asset_id,date) WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
        original = db.DATA_DIR
        try:
            db.DATA_DIR = Path(tmp)
            for years in (1, 3, 5, 10):
                result = portfolio_validation(
                    ValidationRequest(
                        mode="psp5_downside",
                        asset_ids=["yf-psp5.pa"],
                        years=years,
                        whole_shares=True,
                    )
                )
                metrics = result["metrics"]["strategy"]
                np.testing.assert_allclose(
                    [
                        metrics[k]
                        for k in (
                            "sharpe",
                            "cagr",
                            "max_drawdown",
                            "volatility",
                            "cost_eur",
                        )
                    ],
                    history["history"][str(years)][idx][:5],
                    atol=1e-8,
                    rtol=0,
                )
            for i in (0, 17, 999):
                result = simulate_history(
                    rows,
                    Sp500SimulationRequest(
                        strategy="downside", years=5, seed=archive["seed"] + i
                    ),
                )
                metrics = result["comparison"]["metrics"]["strategy"]
                np.testing.assert_allclose(
                    [
                        metrics[k]
                        for k in (
                            "sharpe",
                            "cagr",
                            "max_drawdown",
                            "volatility",
                            "cost_eur",
                        )
                    ],
                    archive["paths"][i][-1][:5],
                    atol=1e-8,
                    rtol=0,
                )
            print(
                "Verified four historical horizons and three simulated paths",
                flush=True,
            )
            asyncio.run(check_batch(archive))
        finally:
            db.DATA_DIR = original


if __name__ == "__main__":
    main()
