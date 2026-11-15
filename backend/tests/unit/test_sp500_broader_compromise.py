"""Research books: exact capital budgets, next-close risk and prefix causality."""

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import study_sp500_broader_compromise as study  # noqa: E402


def sample():
    days = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(7)]
    p = np.array([100.0, 100.0, 100.0, 100.0, 100.0, 80.0, 60.0])
    return days, p


def test_drawdown_budget_is_not_a_guaranteed_floor():
    days, p = sample()
    c = dict(family="insurance", protection=0.8, multiple=5, ratchet=True)
    result = study.ledger(days, p, [c], [days[0], days[-1]], fee=0, trace=True)
    assert result["curve"][-1, 0] == pytest.approx(6000)
    assert result["trace"][-1]["execution"] == days[6]
    assert result["trace"][-1]["units"] == [35]
    assert result["metrics"]["max_drawdown"][0] == pytest.approx(-0.4)


def test_constant_allocation_uses_integer_units_and_initial_fee():
    days, p = sample()
    c = dict(family="constant", weight=0.8, step=0)
    result = study.ledger(days, p, [c], [days[0], days[-1]], trace=True)
    assert result["trace"][0]["execution"] == days[1]
    units = np.floor(0.8 * 10000 / (100 * (1 + 0.8 * 0.0012)))
    assert result["trace"][0]["units"] == [units]
    final = 10000 - units * 100 * 1.0012 + units * 60
    assert result["curve"][-1, 0] == pytest.approx(final)
    assert result["fees"][0] == pytest.approx(units * 100 * 0.0012)


def test_removing_future_prices_preserves_every_book_prefix():
    days = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(600)]
    p = 100 * np.exp(np.cumsum(np.random.default_rng(19).normal(0.0003, 0.015, 600)))
    cs = [c for c in study.grid() if c["family"] != "hybrid"]
    full = study.ledger(days, p, cs, [days[320], days[-1]])
    cut = study.ledger(days[:500], p[:500], cs, [days[320], days[499]])
    np.testing.assert_allclose(full["curve"][:180], cut["curve"], atol=1e-9)


def test_variable_initial_capital_is_real_book_budget():
    days, p = sample()
    scores = np.full(7, 2.0)
    features = (
        {60: (scores, scores), 18: (scores, scores)},
        {w: p for w in [50, 100, 200]},
        np.zeros(7),
    )
    r = study.common.regression.simulate(
        days,
        p,
        p,
        features,
        [study.common.BASE] * 2,
        [days[0], days[-1]],
        fee=0.0012,
        initial_capital=np.array([10000.0, 6500.0]),
        keep_curve=True,
    )
    assert r["curve"][0] == [10000, 6500]
    # Separate slow/defensive orders are rounded within each initial pocket.
    for j, capital in enumerate([10000, 6500]):
        expected = [
            np.floor(capital * share * 0.25 / (100 * (1 + 0.25 * 0.0012)))
            for share in [0.75, 0.25]
        ]
        assert r["trace"][0]["units"][j] == expected
        assert r["curve"][1][j] == pytest.approx(capital - sum(expected) * 100 * 0.0012)


def test_full_hybrid_uses_6500_and_3500_euro_books(monkeypatch):
    days, p = sample()
    scores = np.full(7, 2.0)
    f = (
        {60: (scores, scores), 18: (scores, scores)},
        {w: p for w in [50, 100, 200]},
        np.zeros(7),
    )
    monkeypatch.setattr(study.common.regression.previous, "prepare", lambda days, p: f)
    rows = study.evaluate(
        days, p, [dict(family="hybrid", passive=0.35)], [days[0], days[-1]]
    )
    # Active: 12 slow +4 defensive; passive:34 units. All three entries pay fees.
    assert rows[2]["cost_eur"] == pytest.approx(50 * 100 * 0.0012)
    assert rows[2]["total_return"] == pytest.approx(
        (10000 - 50 * 100 * 1.0012 + 50 * 60) / 10000 - 1
    )
