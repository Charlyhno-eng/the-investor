"""Independent accounting and temporal checks for the isolated research harness."""

import importlib
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from investor.portfolio.validation import ValidationRequest


@pytest.fixture
def research(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    return importlib.import_module("study_quantitative_strategies")


def synthetic():
    dates = []
    day = date(2015, 1, 1)
    while day <= date(2022, 12, 30):
        if day.weekday() < 5:
            dates.append(day.isoformat())
        day += timedelta(days=1)
    assets, histories, raw, payouts = [], [], [], []
    for j in range(6):
        crypto = j == 4
        assets.append(
            {
                "id": f"asset-{j}",
                "name": f"Asset {j}",
                "category": "crypto" if crypto else "stock",
                "frequency": "daily",
            }
        )
        h, r, p = {}, {}, {}
        for i, d in enumerate(dates):
            if j == 5 and d < "2019-01-02":
                continue
            price = (50 + 20 * j) * np.exp(
                (0.0003 - j * 0.00004) * i + 0.12 * np.sin(i / (23 + j * 7))
            )
            r[d] = float(price)
            h[d] = float(price * np.exp(0.00005 * i)) if not crypto else float(price)
            if not crypto and i and d[:7] != dates[i - 1][:7]:
                p[d] = 0.2
        histories.append(h)
        raw.append(r)
        payouts.append(p)
    return {
        "assets": assets,
        "histories": histories,
        "benchmark": histories[0],
        "execution_histories": raw,
        "cash_distributions": payouts,
    }


def request(**kwargs):
    return ValidationRequest(
        asset_ids=[f"asset-{j}" for j in range(6)],
        start_date="2018-01-02",
        end_date="2022-12-30",
        whole_shares=True,
        **kwargs,
    )


@pytest.mark.parametrize(
    "policy", ["equal_monthly", "variance_managed", "time_series_momentum"]
)
def test_quant_research_independent_ledger_and_late_listing(research, policy):
    inputs = synthetic()
    req = request()
    result = research.simulate(inputs, req, policy)
    assert result["transactions"] > 0
    assert research.audit_ledger(inputs, req, result)
    assert all(t["signal"] < t["execution"] for t in result["journal"])
    assert all(
        t["signal"] >= "2022-01-02"
        for t in result["journal"]
        if t["asset_id"] == "asset-5"
    )
    assert sum(t["fee"] for t in result["journal"]) == pytest.approx(
        result["metrics"]["cost_eur"]
    )
    broken = deepcopy(result)
    broken["equity"][-1]["value"] += 20
    with pytest.raises(ValueError, match="Independent NAV"):
        research.audit_ledger(inputs, req, broken)


@pytest.mark.parametrize("policy", ["variance_managed", "time_series_momentum"])
def test_quant_research_future_prices_do_not_change_earlier_decisions(research, policy):
    inputs = synthetic()
    before = research.simulate(inputs, request(), policy)
    changed = deepcopy(inputs)
    cutoff = "2021-06-15"
    for histories in (changed["histories"], changed["execution_histories"]):
        for history in histories:
            for day in history:
                if day >= cutoff:
                    history[day] *= 3.0
    after = research.simulate(changed, request(), policy)
    assert [a for a in before["allocations"] if a["signal"] < cutoff] == [
        a for a in after["allocations"] if a["signal"] < cutoff
    ]
    assert [p for p in before["equity"] if p["time"] < cutoff] == [
        p for p in after["equity"] if p["time"] < cutoff
    ]
    assert before["final_value"] != after["final_value"]


def test_quant_research_position_caps_and_intended_cash_reserve(research):
    assert research.capped_weights(np.array([10.0, 1, 0])).tolist() == pytest.approx(
        [0.25, 0.25, 0]
    )
    weights = research.capped_weights(np.array([100, 5, 4, 3, 2, 1]))
    assert weights.sum() == pytest.approx(1)
    assert weights.max() <= 0.25
    inputs = synthetic()
    # A common daily shock forces an intentional cash reserve, even after rounding.
    for histories in (inputs["histories"], inputs["execution_histories"]):
        for history in histories:
            for i, day in enumerate(history):
                history[day] *= 1.07 if i % 2 else 0.93
    req = request()
    result = research.simulate(inputs, req, "variance_managed")
    assert research.audit_ledger(inputs, req, result)
    assert any(sum(a["weights"]) < 0.75 for a in result["allocations"])
    assert result["metrics"]["market_exposure"] < 1
