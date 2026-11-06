"""Research-engine invariants; none of these tests assert profitability."""

from datetime import date, timedelta

import numpy as np
import pytest
from hmmlearn.hmm import GaussianHMM
from investor.analysis import adaptive
from investor.analysis.diagnostics import switching_diagnostics
from investor.analysis.schemas import AnalysisRequest


def test_continuation_diagnostic_proves_unreachable_exit_without_forcing_trades():
    # Even a pure adverse-state belief cannot reach the required -0.5% cost.
    p = np.array([[1.0, 0], [0.6, 0.4], [0, 1.0]])
    result = switching_diagnostics(
        p,
        np.array([-0.001, 0.002]),
        np.array([-0.0012, 0.0057]),
        0.005,
        [1, 1, 0],
        0.3068,
        0.2999,
    )
    assert result["exit_reachable"] is False
    assert result["negative_dominant_observations"] == 2
    assert result["negative_dominant_while_held"] == 1
    assert result["negative_dominant_without_exit_while_held"] == 1
    assert result["exit_signal_observations"] == 0
    assert result["net_excess_return"] == pytest.approx(0.0069)
    # A state crossing the boundary makes exit possible, but not necessarily
    # observed: all beliefs below assign only 10% to that state.
    result = switching_diagnostics(
        np.tile([0.1, 0.9], (3, 1)),
        np.array([-0.001, 0.002]),
        np.array([-0.02, 0.01]),
        0.005,
        [1, 1, 0],
        0,
        0,
    )
    assert result["exit_reachable"] is True
    assert result["exit_signal_observations"] == 0


def test_adaptive_observation_is_a_causal_normalized_trend():
    changes = np.random.default_rng(7).normal(0.001, 0.01, 100)
    prices = np.exp(np.r_[0, changes.cumsum()])
    _, x, vol = adaptive.observations(prices)
    _, prefix, prefix_vol = adaptive.observations(prices[:72])
    np.testing.assert_array_equal(x[:71], prefix)
    np.testing.assert_array_equal(vol[:71], prefix_vol)
    assert np.isnan(x[:29]).all() and np.isfinite(x[29:]).all()
    alpha = 2 / 31
    i = 70
    weights = np.r_[(1 - alpha) ** i, alpha * (1 - alpha) ** np.arange(i - 1, -1, -1)]
    mean = weights @ changes[: i + 1]
    variance = weights @ ((changes[: i + 1] - mean) ** 2)
    assert vol[i] == pytest.approx(np.sqrt(variance))
    assert x[i, 0] == pytest.approx(mean / np.sqrt(variance))


def test_adverse_exit_is_never_vetoed_by_costs_and_middle_does_not_trade():
    p = np.eye(3)
    centers, persistence, vol = (
        np.array([-0.1, 0, 0.15]),
        np.array([0.95, 0.9, 0.95]),
        np.full(3, 0.01),
    )
    low = adaptive.targets(p, centers, persistence, vol, 50)
    high = adaptive.targets(p, centers, persistence, vol, 500)
    np.testing.assert_array_equal(low, [0, -1, 1])
    np.testing.assert_array_equal(high, [0, -1, -1])
    # Relative favorable state with negative trend must not buy.
    assert (
        adaptive.targets(p, np.array([-0.3, -0.2, -0.1]), persistence, vol, 0)[-1] == -1
    )


def test_orders_are_next_close_and_reentry_is_not_locked(research_sample):
    request = research_sample[2].model_copy(update={"fee_bps": 100})
    changes = np.log1p([0.5, 0.5, 0.1, -0.1, 0.2, 0.2, 0.2])
    action = np.array([1, 0, 1, -1, 0, 1, 1])
    p = np.tile([0, 0, 1.0], (len(action), 1))
    net, market, trades, positions, exposure = adaptive.simulate(
        changes,
        list(range(7)),
        action,
        p,
        request,
    )
    assert [(t["time"], t["side"]) for t in trades] == [
        (1, "buy"),
        (2, "sell"),
        (3, "buy"),
        (5, "sell"),
    ]
    assert net[0] == 0 and net[1] == pytest.approx(-0.01)
    assert net[2] == pytest.approx(1.1 * 0.99 - 1)
    assert net[3] == pytest.approx(-0.01)  # New buy at close, no same-day loss.
    assert positions == [0, 1, 0, 1, 1, 0, 0]
    assert exposure == pytest.approx(3 / 7)
    assert market[0] == pytest.approx(1.5 * 0.99 - 1)


@pytest.fixture
def research_sample():
    changes = np.random.default_rng(59).normal(0.0005, 0.015, 650)
    prices = np.exp(np.r_[0, changes.cumsum()]) * 100
    rows = [
        {"date": str(date(2020, 1, 1) + timedelta(days=i)), "value": float(v)}
        for i, v in enumerate(prices)
    ]
    request = AnalysisRequest(
        train_start=rows[0]["date"],
        train_end=rows[299]["date"],
        test_start=rows[300]["date"],
        test_end=rows[-1]["date"],
        fee_bps=50,
    )
    return {"category": "stock", "metric": "price"}, rows, request


def fitted(training, permutation=(0, 1, 2)):
    order = np.array(permutation)
    model = GaussianHMM(n_components=3, covariance_type="full", init_params="")
    model.startprob_ = np.array([0.3, 0.2, 0.5])[order]
    model.transmat_ = np.array(
        [[0.95, 0.04, 0.01], [0.05, 0.9, 0.05], [0.01, 0.04, 0.95]]
    )[order][:, order]
    model.means_ = np.array([[-1.0], [0], [1.0]])[order]
    model.covars_ = np.array([[[0.3]], [[0.4]], [[0.3]]])[order]
    return model, training.mean(axis=0), np.maximum(training.std(axis=0), 1e-8), True


def test_rolling_calibration_does_not_repaint_past_and_aligns_state_ids(
    research_sample, monkeypatch
):
    asset, rows, request = research_sample
    monkeypatch.setattr(adaptive, "fit_regimes", fitted)
    original = adaptive.calculate(asset, rows, request)
    assert len(original["calibrations"]) == 6
    assert all(c["train_end"] < c["first_signal"] for c in original["calibrations"])
    assert original["calibrations"][0]["train_end"] <= request.train_end.isoformat()
    revised = [dict(r) for r in rows]
    for row in revised[470:]:
        row["value"] *= 3
    updated = adaptive.calculate(asset, revised, request)
    assert original["regimes"][:170] == updated["regimes"][:170]
    assert original["equity"][:171] == updated["equity"][:171]
    assert original["calibrations"][:3] == updated["calibrations"][:3]
    monkeypatch.setattr(adaptive, "fit_regimes", lambda x: fitted(x, (2, 0, 1)))
    permuted = adaptive.calculate(asset, rows, request)
    np.testing.assert_allclose(
        [r["probabilities"] for r in original["regimes"]],
        [r["probabilities"] for r in permuted["regimes"]],
        atol=1e-12,
    )
    assert original["positions"] == permuted["positions"]


def test_failed_refresh_keeps_last_model_and_audits_failure(
    research_sample, monkeypatch
):
    calls = []

    def fit(training):
        calls.append(len(training))
        if len(calls) == 2:
            raise ValueError("Refresh unavailable")
        return fitted(training)

    monkeypatch.setattr(adaptive, "fit_regimes", fit)
    result = adaptive.calculate(*research_sample)
    c = result["calibrations"]
    assert c[1]["failure"] == "Refresh unavailable"
    assert c[0]["train_end"] == c[1]["train_end"]
    assert c[2]["failure"] is None and c[2]["train_end"] > c[0]["train_end"]
    assert all(sum(r["probabilities"]) == pytest.approx(1) for r in result["regimes"])
