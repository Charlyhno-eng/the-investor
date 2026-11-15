"""Whole-core research overlay, neutral control and next-close gap tests."""

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import study_sp500_drawdown_overlay as overlay  # noqa: E402


def sample():
    days = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(650)]
    p = 100 * np.exp(np.cumsum(np.random.default_rng(91).normal(0.0004, 0.014, 650)))
    return days, p


@pytest.mark.parametrize("delay", [1, 2])
def test_overlay_reference_and_neutral_candidate_reproduce_original_v5(
    monkeypatch, delay
):
    days, p = sample()
    c = dict(floor=0.25, multiple=1.5, rebound=0.06, cap=0.5, step=5)
    monkeypatch.setattr(
        overlay, "caps", lambda days, p, cs, period: np.ones((len(cs), len(p)))
    )
    rows = overlay.evaluate(days, p, [c], [days[320], days[-1]], delay=delay)
    original = overlay.engine.evaluate(days, p, [], [days[320], days[-1]], delay=delay)
    for metric in rows[0]:
        assert rows[0][metric] == pytest.approx(original[0][metric], abs=1e-9)
        assert rows[1][metric] == pytest.approx(original[1][metric], abs=1e-9)
        assert rows[2][metric] == pytest.approx(original[1][metric], abs=1e-9)


def test_caps_and_three_book_equity_ignore_future():
    days, p = sample()
    configs = overlay.grid()
    full = overlay.caps(days, p, configs, [days[320], days[-1]])
    cut = overlay.caps(days[:500], p[:500], configs, [days[320], days[499]])
    np.testing.assert_array_equal(full[:, :500], cut)
    f, ff = overlay.passive(days, p, full, [days[320], days[-1]])
    c, _ = overlay.passive(days[:500], p[:500], cut, [days[320], days[499]])
    np.testing.assert_allclose(f[:180], c, atol=1e-9, rtol=0)
    assert np.all(ff >= 0)


def test_cap_reduction_executes_after_gap_not_at_signal_price():
    days, p = sample()
    p[:] = 100
    p[326:] = 30
    targets = np.ones((1, len(p)))
    targets[:, 325:] = 0.25
    curve, fees = overlay.passive(days, p, targets, [days[320], days[327]], fee=0)
    assert fees[0] == 0
    assert curve[5, 0] == 3500
    assert curve[6, 0] == pytest.approx(1050)
    assert curve[7, 0] == pytest.approx(1050)


def test_active_caps_use_signal_day_and_separate_sleeve_budgets():
    days = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(7)]
    p = np.full(7, 100.0)
    scores = np.full(7, 2.0)
    features = (
        {60: (scores, scores), 18: (scores, scores)},
        {w: p for w in [50, 100, 200]},
        np.zeros(7),
    )
    targets = np.ones((1, 7))
    targets[:, :2] = 0.1
    result = overlay.engine.common.regression.simulate(
        days,
        p,
        p,
        features,
        [overlay.engine.common.BASE],
        [days[0], days[-1]],
        initial_capital=6500,
        fee=0.0012,
        exposure_caps=targets,
        keep_curve=True,
    )
    assert result["trace"][0]["units"] == [[4.0, 1.0]]
    assert result["trace"][1]["units"] == [[4.0, 1.0]]
    assert result["trace"][2]["units"] == [[12.0, 4.0]]
    assert result["metrics"][0]["fees"] == pytest.approx(16 * 100 * 0.0012)
