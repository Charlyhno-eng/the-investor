"""Verify grouped research allocation and capped self-financing orders."""

import importlib
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def study(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    return importlib.import_module("study_three_optimizations")


def test_groups_do_not_reward_duplicate_assets(study):
    rng = np.random.default_rng(42)
    x, y = rng.normal(size=(2, 252))
    returns = np.column_stack([x, x, y])
    np.testing.assert_allclose(study.grouped_weights(returns), [0.25, 0.25, 0.5])
    assert study.grouped_weights(returns[:, :1])[0] == 1


def test_capped_orders_preserve_cash_fees_and_whole_shares(study):
    values = np.array([30.0, 0.0, 0.0])
    after, cash = study.capped_orders(
        values,
        70.0,
        [0.0, -3.0, -2.5],
        0.005,
        group_labels=np.array([0, 0, 1]),
        unit_prices=np.ones(3),
        whole=np.ones(3, dtype=bool),
        entry_z=2,
        funding_min_z=0.3,
    )
    assert after[:2].sum() <= 40 + 1e-9
    assert after[1] >= 10
    assert cash >= 0
    np.testing.assert_allclose(after, np.round(after))
    assert after.sum() + cash + np.abs(after - values).sum() * 0.005 == pytest.approx(
        100
    )


def test_overweight_group_does_not_block_exits(study):
    after, cash = study.capped_orders(
        np.array([60.0, 0.0]),
        40.0,
        [3.0, -3.0],
        0.005,
        group_labels=np.array([0, 0]),
        unit_prices=np.ones(2),
        whole=np.ones(2, dtype=bool),
        entry_z=2,
        exits=[True, False],
    )
    assert after[0] == 0
    assert after.sum() <= 40 + 1e-9
    assert cash >= 0


@pytest.mark.parametrize(
    "candidate,mode",
    [("group_allocation", "volatility"), ("group_cap", "mean_reversion")],
)
def test_future_prices_do_not_change_past_trades(study, candidate, mode):
    from copy import deepcopy

    from test_quantitative_research import request, synthetic

    inputs = synthetic()
    req = request(
        mode=mode,
        reversion_entry_z=0.5,
        reversion_exit_z=2,
        reversion_exit_mode="trailing_z",
        reversion_trailing_gap=1,
        reversion_funding_min_z=0.3,
    )
    first = study.engine(candidate)(**inputs, request=req)
    changed = deepcopy(inputs)
    for key in ("histories", "execution_histories"):
        for history in changed[key]:
            for day in history:
                if day >= "2021-01-01":
                    history[day] *= 1.5
    second = study.engine(candidate)(**changed, request=req)
    assert first["status"] == second["status"] == "ready"
    a = [t for t in first["transactions"] if t["execution"] < "2021-01-01"]
    b = [t for t in second["transactions"] if t["execution"] < "2021-01-01"]
    assert a
    assert a == b
