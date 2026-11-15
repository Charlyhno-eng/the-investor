"""Research-only risk allocation must absorb shocks before next-close execution."""

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import study_sp500_ratio_tradeoff as study  # noqa: E402


def test_risk_signal_cannot_sell_before_the_following_close(monkeypatch):
    days = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(7)]
    prices = np.array([100.0, 100.0, 100.0, 100.0, 100.0, 80.0, 60.0])
    monkeypatch.setattr(
        study,
        "risk_weights",
        lambda p, cs: np.array([[1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0]]),
    )
    result = study.risk_run(
        days, prices, [dict(family="risk")], [days[0], days[-1]], fee=0.0012
    )
    units = np.floor(10000 / (100 * 1.0012))
    final_cash = 10000 - units * 100 * 1.0012 + units * 60 * 0.9988
    assert result["total_return"][0] == pytest.approx(final_cash / 10000 - 1)
    assert result["cost_eur"][0] == pytest.approx(units * 160 * 0.0012)
    assert result["max_drawdown"][0] < -0.39


def test_risk_features_do_not_use_future_shock():
    p = 100 * np.exp(np.cumsum(np.random.default_rng(7).normal(0.0003, 0.01, 600)))
    configs = [c for c in study.grid() if c["family"] == "risk"]
    expected = study.risk_weights(p[:400], configs)
    p[400:] *= 10
    np.testing.assert_allclose(
        expected, study.risk_weights(p, configs)[:, :400], equal_nan=True
    )
