"""Check native signal fidelity, causality and real next-close accounting."""

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import study_sp500_sigma_momentum as study  # noqa: E402

from investor.assets.momentum import analyze  # noqa: E402


def sample():
    dates = [date(2016, 1, 1) + timedelta(days=i) for i in range(3300)]
    dates = [d for d in dates if d.weekday() < 5]
    p = 100 * np.exp(
        np.cumsum(np.random.default_rng(32).normal(0.0003, 0.012, len(dates)))
    )
    return dates, p


def test_scores_equal_native_calendar_momentum():
    dates, p = sample()
    _, scores = study.signals([d.isoformat() for d in dates], p)
    for i in [50, 400, 850, 1300, len(p) - 1]:
        points = list(zip(dates[: i + 1], p[: i + 1], strict=True))
        for h in [6, 12, 36]:
            expected = analyze(points, dict(points), dates[i], h, include_rows=False)
            if "score" in expected:
                assert scores[str(h)][i] == pytest.approx(expected["score"], abs=1e-7)
            else:
                assert np.isnan(scores[str(h)][i])


def test_sigma_matches_original_calendar_regression():
    from study_sp500_regression import features

    dates, p = sample()
    days = [d.isoformat() for d in dates]
    z, _ = study.signals(days, p)
    native, _ = features(days, p)
    for h in [18, 60]:
        valid = np.isfinite(z[h])
        assert valid.sum() > 500
        np.testing.assert_allclose(z[h][valid], native[h][0][valid], atol=1e-7, rtol=0)


@pytest.mark.parametrize("delay", [1, 2])
def test_all_rules_ignore_future_and_keep_separate_initial_budgets(delay):
    dates, p = sample()
    days = [d.isoformat() for d in dates]
    cs = study.grid()
    period = [days[1500], days[-1]]
    full, _ = study.tactical(days, p, cs, period, delay=delay)
    cut, _ = study.tactical(
        days[:1900], p[:1900], cs, [days[1500], days[1899]], delay=delay
    )
    np.testing.assert_allclose(full[:400], cut, atol=1e-9, rtol=0)
    np.testing.assert_allclose(full[0], [10000 * (1 - c["active"]) for c in cs])


def test_next_close_uses_actual_gap_and_whole_units():
    dates, p = sample()
    days = [d.isoformat() for d in dates]
    p[1500:] = 100
    p[1501:] = 200
    c = {**study.grid()[0], "active": 0.65}
    # With a constant supplied target, verify execution ledger independently
    # of any particular signal rule (which can be defensive or aggressive).
    target = np.full((1, len(p)), 0.5)
    curve, fees = study.ORIGINAL_TACTICAL(
        days, p, [c], [days[1500], days[1501]], target_weights=target
    )
    shares = np.floor(0.5 * 3500 / (200 * (1 + 0.5 * 0.0012)))
    assert fees[0] == pytest.approx(shares * 200 * 0.0012)
    assert curve[:, 0] == pytest.approx([3500, 3500 - shares * 200 * 0.0012])
