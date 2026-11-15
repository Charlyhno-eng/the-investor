"""Time the old full engine and the batch stream on a private SQLite snapshot.

Run: PYTHONPATH=backend .venv/bin/python scripts/benchmark_sp500_batch.py --count 10000
The audit compares fixed seeds, never searches for favorable financial results.
"""

import argparse
import asyncio
import json
import math
import sqlite3
import tempfile
import time
from pathlib import Path

from investor import db
from investor.portfolio import etf_switch
from investor.portfolio import sp500_simulation as simulation


async def timed_stream(rows, count, years):
    original = simulation.load_simulation_history
    simulation.load_simulation_history = lambda: rows

    async def connected():
        return False

    started = time.perf_counter()
    final = None
    try:
        async for line in simulation.stream_sp500_batch(
            simulation.Sp500BatchRequest(count=count, years=years, seed=0), connected
        ):
            final = json.loads(line)
            if final["status"] == "error":
                raise AssertionError(final)
    finally:
        simulation.load_simulation_history = original
    assert final["completed"] == count and final["status"] == "complete"
    return time.perf_counter() - started, final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count", type=int, default=1000, choices=range(1, 10001), metavar="N"
    )
    parser.add_argument("--reference-count", type=int, default=32)
    parser.add_argument("--years", type=int, default=5, choices=(1, 3, 5, 10))
    parser.add_argument("--output", type=Path)
    options = parser.parse_args()
    if not 1 <= options.reference_count <= 10000:
        parser.error("reference-count must be between 1 and 10000")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dest,
        ):
            src.backup(dest)
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o "
                "LEFT JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date "
                "WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
    expected = simulation.BatchSummary()
    started = time.perf_counter()
    for seed in range(options.reference_count):
        result = simulation.simulate_history(
            rows, simulation.Sp500SimulationRequest(years=options.years, seed=seed)
        )
        assert result["status"] == "ready", result
        expected.add(result["comparison"])
    reference_seconds = time.perf_counter() - started
    fast_seconds, fast = asyncio.run(
        timed_stream(rows, options.reference_count, options.years)
    )
    max_difference = 0.0
    for metric, row in expected.snapshot(options.reference_count, 0)["metrics"].items():
        for key, value in row.items():
            actual = fast["metrics"][metric][key]
            if key.endswith("_mean") and value is not None:
                assert math.isclose(actual, value, rel_tol=1e-10, abs_tol=1e-9), (
                    metric,
                    key,
                    actual,
                    value,
                )
                max_difference = max(max_difference, abs(actual - value))
            else:
                assert actual == value, (metric, key, actual, value)
    batch_seconds, final = asyncio.run(timed_stream(rows, options.count, options.years))
    report = dict(
        version=etf_switch.VERSION,
        source_start=rows[0][0],
        source_end=rows[-1][0],
        source_observations=len(rows),
        years=options.years,
        reference_count=options.reference_count,
        reference_seconds=reference_seconds,
        optimized_same_count_seconds=fast_seconds,
        same_count_speedup=reference_seconds / fast_seconds,
        max_mean_absolute_difference=max_difference,
        exact_win_tie_valid_counts=True,
        batch_count=options.count,
        batch_seconds=batch_seconds,
        full_engine_extrapolated_seconds=reference_seconds
        / options.reference_count
        * options.count,
        note="Local software timing and equivalence audit, not financial validation.",
        final=final,
    )
    output = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if options.output:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        options.output.write_text(output)
    print(output)


if __name__ == "__main__":
    main()
