"""Research bookkeeping: future isolation, delayed orders and independent cash."""

import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import study_sp500_drawdown_frontier as study  # noqa: E402
import study_sp500_drawdown_reversal as reversal  # noqa: E402


def sample():
    days = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(650)]
    p = 100 * np.exp(np.cumsum(np.random.default_rng(29).normal(0.0003, 0.013, 650)))
    return days, p


@pytest.mark.parametrize("delay", [1, 2])
def test_all_families_ignore_future_prices_and_future_executions(delay):
    days, p = sample()
    configs = study.grid() + reversal.grid()
    full, fees = study.tactical(days, p, configs, [days[320], days[-1]], delay=delay)
    cut, _ = study.tactical(
        days[:500], p[:500], configs, [days[320], days[499]], delay=delay
    )
    np.testing.assert_allclose(full[:180], cut, atol=1e-9, rtol=0)
    np.testing.assert_allclose(full[0], [10000 * (1 - c["active"]) for c in configs])
    assert np.all(fees >= 0)


def test_next_close_gap_whole_units_and_real_budget():
    days, _ = sample()
    p = np.full(650, 100.0)
    p[321:] = 200
    c = dict(
        family="shrunk_growth", prior=0.08, shrink=0.25, floor=0.5, step=5, active=0.65
    )
    curve, fees = study.tactical(days, p, [c], [days[320], days[321]])
    # The signal sees100, order executes200, with a separate3500EUR budget.
    units = np.floor(3500 / (200 * 1.0012))
    assert curve[:, 0] == pytest.approx([3500, 3500 - units * 200 * 0.0012])
    assert fees[0] == pytest.approx(units * 200 * 0.0012)


def test_parallel_sampling_preserves_seed_results_and_order():
    days, prices = sample()
    cs = [study.grid()[0], reversal.grid()[0]]
    tasks = [(days, prices, cs, 1, seed) for seed in [32, 33]]
    sequential = list(map(study.sampled_case, tasks))
    with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn")) as pool:
        parallel = list(pool.map(study.sampled_case, tasks))
    assert parallel == sequential
