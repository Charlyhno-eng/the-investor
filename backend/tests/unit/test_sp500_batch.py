"""Batch arithmetic, decisions and ordered summaries against full production."""

import asyncio
import json

import numpy as np
import pytest
from sp500_support import historical_rows

from investor.portfolio import sp500_simulation as simulation
from investor.portfolio.sp500_batch import CHUNK_SIZE, PreparedBatch, _rebalance
from investor.portfolio.validation import rebalance


@pytest.mark.parametrize("years", [1, 3, 5, 10])
@pytest.mark.parametrize(
    "whole,capital,fee,trim",
    [
        (True, 10000, 0.0012, 0),
        (False, 12345.67, 0.0012, 0),
        (True, 1, 0, 1),
        (False, 1000000, 0.1, 1),
    ],
)
def test_vectorized_metrics_match_full_engine(years, whole, capital, fee, trim):
    rows = historical_rows()
    if trim:
        rows = rows[:-trim]
    request = simulation.Sp500SimulationRequest(
        years=years, whole_shares=whole, initial_capital=capital, fee_rate=fee
    )
    seeds = [0, 42, 2**32 - 1]
    batch = PreparedBatch(simulation.prepare_history(rows, years), request)
    results = batch.simulate(seeds)
    actual_summary, expected_summary = (
        simulation.BatchSummary(),
        simulation.BatchSummary(),
    )
    for seed, actual in zip(seeds, results, strict=True):
        expected = simulation.simulate_history(
            rows, request.model_copy(update={"seed": seed})
        )
        assert actual["status"] == expected["status"] == "ready"
        for key in ("benchmark", "strategy"):
            for metric in simulation.BATCH_METRICS:
                a = actual["comparison"]["metrics"][key][metric]
                e = expected["comparison"]["metrics"][key][metric]
                if e is None or metric == "positive_quarters":
                    assert a == e, (key, metric)
                else:
                    assert a == pytest.approx(e, rel=1e-10, abs=1e-9), (key, metric)
        actual_summary.add(actual["comparison"])
        expected_summary.add(expected["comparison"])
    for metric, row in actual_summary.snapshot(3, 0)["metrics"].items():
        expected = expected_summary.snapshot(3, 0)["metrics"][metric]
        for key in ("valid", "benchmark_wins", "strategy_wins", "ties"):
            assert row[key] == expected[key], metric


def test_vectorized_rebalance_matches_production_for_sales_purchases_and_cash():
    rng = np.random.default_rng(190)
    values, cash = rng.uniform(0, 1000, (2, 100))
    target = rng.choice([0, 0.1, 1], 100)
    for fee in (0, 0.0012, 0.1):
        actual, remaining = _rebalance(values, cash, target, fee)
        for j in range(len(values)):
            expected = rebalance(
                np.array([values[j]]), cash[j], np.array([target[j]]), fee
            )
            assert actual[j] == expected[0][0]
            assert remaining[j] == expected[1]


def test_group_size_and_order_do_not_change_independent_paths():
    request = simulation.Sp500SimulationRequest(years=1)
    prepared = PreparedBatch(simulation.prepare_history(historical_rows(), 1), request)
    grouped = prepared.simulate([42, 0, 1])
    for seed, actual in zip([42, 0, 1], grouped, strict=True):
        solo = prepared.simulate([seed])[0]
        for key in ("benchmark", "strategy"):
            assert actual["comparison"]["metrics"][key] == pytest.approx(
                solo["comparison"]["metrics"][key], rel=1e-10, abs=1e-9
            )


def test_sparse_history_keeps_production_eligibility_error():
    rows = historical_rows()[::3]
    request = simulation.Sp500SimulationRequest(years=1)
    source = simulation.prepare_history(rows, 1)
    assert source["status"] == "ready"
    actual = PreparedBatch(source, request).simulate([42])[0]
    expected = simulation.simulate_history(
        rows, request.model_copy(update={"seed": 42})
    )
    assert actual == expected
    assert actual["status"] == "insufficient"


def test_stream_chunks_keep_seed_wrap_prefixes_and_stop_with_bounded_work(monkeypatch):
    monkeypatch.setattr(simulation, "load_simulation_history", historical_rows)
    calls = []

    def simulate(self, seeds):
        calls.append(seeds)
        return [
            {
                "status": "ready",
                "comparison": {"metrics": {"benchmark": {}, "strategy": {}}},
            }
            for _ in seeds
        ]

    monkeypatch.setattr(PreparedBatch, "simulate", simulate)

    async def collect():
        snapshots = []

        async def disconnected():
            return bool(snapshots and snapshots[-1]["completed"] == 3)

        async for line in simulation.stream_sp500_batch(
            simulation.Sp500BatchRequest(count=10000, seed=2**32 - 1), disconnected
        ):
            snapshots.append(json.loads(line))
        return snapshots

    snapshots = asyncio.run(collect())
    assert [s["completed"] for s in snapshots] == [0, 1, 2, 3]
    assert calls == [[2**32 - 1], list(range(CHUNK_SIZE))]


def test_failure_keeps_prefix_without_skipping_a_path(monkeypatch):
    monkeypatch.setattr(simulation, "load_simulation_history", historical_rows)

    def simulate(self, seeds):
        return [
            {
                "status": "ready",
                "comparison": {"metrics": {"benchmark": {}, "strategy": {}}},
            }
            if seed < 2
            else {"status": "insufficient", "message": "Parcours invalide"}
            for seed in seeds
        ]

    monkeypatch.setattr(PreparedBatch, "simulate", simulate)

    async def collect():
        async def connected():
            return False

        return [
            json.loads(line)
            async for line in simulation.stream_sp500_batch(
                simulation.Sp500BatchRequest(count=100, seed=0), connected
            )
        ]

    snapshots = asyncio.run(collect())
    assert [s["completed"] for s in snapshots] == [0, 1, 2, 2]
    assert snapshots[-1] == {
        "status": "error",
        "completed": 2,
        "message": "Parcours invalide",
    }
