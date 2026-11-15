"""Audit synthetic tails and current-policy execution on a private local snapshot.

Run: PYTHONPATH=backend uv run python scripts/verify_sp500_simulation.py
These frequencies describe this generator, not future market probabilities.
"""

import argparse
import json
import sqlite3
import tempfile
import time
from datetime import date
from pathlib import Path

import numpy as np

from investor import db
from investor.portfolio import etf_switch
from investor.portfolio.sp500_simulation import (
    BatchSummary,
    Sp500SimulationRequest,
    future_sessions,
    sampled_returns,
    simulate_history,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-count", type=int, default=1000)
    options = parser.parse_args()
    if not 1 <= options.batch_count <= 10000:
        parser.error("batch-count doit être entre 1 et 10000")
    with tempfile.TemporaryDirectory() as directory:
        copy = Path(directory) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as source,
            sqlite3.connect(copy) as destination,
        ):
            source.backup(destination)
        with sqlite3.connect(copy) as connection:
            rows = connection.execute(
                "SELECT o.date,o.value,p.value FROM observations o LEFT JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
    prices = np.array([r[1] for r in rows])
    increments = np.diff(np.log(prices))
    report = dict(
        version=etf_switch.VERSION,
        source_asset_id="yf-psp5.pa",
        fee_rate=0.0012,
        source_start=rows[0][0],
        source_end=rows[-1][0],
        source_observations=len(rows),
        note="Generator diagnostics, never estimates of future market probabilities.",
        tails={},
        comparisons=[],
    )
    for years in [1, 3, 5, 10]:
        length = len(future_sessions(date.fromisoformat(rows[-1][0]), years))
        drawdowns = []
        for seed in range(200):
            nav = np.exp(np.r_[0, np.cumsum(sampled_returns(increments, length, seed))])
            drawdowns.append(float((nav / np.maximum.accumulate(nav) - 1).min()))
        report["tails"][str(years)] = dict(
            draws=200,
            at_least_30pct_drawdown=sum(d <= -0.3 for d in drawdowns),
            min_drawdown=min(drawdowns),
            max_drawdown=max(drawdowns),
        )
    assert 0 < report["tails"]["5"]["at_least_30pct_drawdown"] < 200
    for years in [1, 5, 10]:
        for seed in [0, 1, 42]:
            started = time.monotonic()
            result = simulate_history(
                rows, Sp500SimulationRequest(years=years, seed=seed)
            )
            assert result["status"] == "ready", result
            r = result["comparison"]
            assert r["protocol"]["etf_switch"] == etf_switch.protocol()
            assert r["start"] == rows[-1][0]
            assert r["equity"][0]["benchmark"] == r["equity"][0]["strategy"] == 100
            assert all(
                t["signal"] >= r["start"] and t["execution"] > t["signal"]
                for t in r["transactions"]
            )
            assert r["final_portfolio"]["cash"] >= 0
            assert all(
                np.isfinite(v)
                for m in r["metrics"].values()
                for v in m.values()
                if v is not None
            )
            report["comparisons"].append(
                dict(
                    years=years,
                    seed=seed,
                    elapsed_seconds=time.monotonic() - started,
                    metrics=r["metrics"],
                    protocol=r["protocol"]["etf_switch"],
                )
            )
    summary = BatchSummary()
    started = time.monotonic()
    for seed in range(options.batch_count):
        result = simulate_history(rows, Sp500SimulationRequest(years=5, seed=seed))
        assert result["status"] == "ready", (seed, result)
        assert result["comparison"]["fee_rate"] == 0.0012
        summary.add(result["comparison"])
        for row in summary.metrics.values():
            assert (
                row["valid"]
                == row["benchmark_wins"] + row["strategy_wins"] + row["ties"]
            )
        if (seed + 1) % 100 == 0:
            print(f"{seed + 1}/{options.batch_count} paired paths checked", flush=True)
    report["batch"] = summary.snapshot(options.batch_count, 0)
    report["batch_elapsed_seconds"] = time.monotonic() - started
    output = Path("data/backtests/sp500-sharpe-simulation-verification.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report["tails"], indent=2))
    print("9 production-engine scenarios verified.", output)


if __name__ == "__main__":
    main()
