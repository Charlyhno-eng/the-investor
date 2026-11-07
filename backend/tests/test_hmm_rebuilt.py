"""Acceptance checks for the rebuilt engine, including absent and real regimes."""

from datetime import date, timedelta

import numpy as np
import pytest
from hmmlearn.hmm import GaussianHMM
from investor.analysis.model import forward_filter
from investor.analysis.regimes import fit_regimes
from investor.analysis.schemas import AnalysisRequest
from investor.analysis.service import VERSION, calculate
from investor.analysis.switching import simulate_switching


def test_single_gaussian_does_not_force_regimes():
    training = np.random.default_rng(42).normal(0.0002, 0.012, (1400, 1))
    model, _, _, converged, selection = fit_regimes(training)
    assert converged
    assert model.n_components == 1
    assert selection["regimes_supported"] is False
    assert selection["baseline_score"] == selection["validation_scores"]["1"]
    assert selection["folds"] == [
        {"fit_points": 840, "validation_points": 280},
        {"fit_points": 1120, "validation_points": 280},
    ]


def test_heldout_volatility_regimes_are_detected_without_directional_indicators():
    rng = np.random.default_rng(55)
    volatility = np.tile(np.repeat([0.003, 0.035], 160), 5)
    returns = rng.normal(0, volatility)[:, None]
    model, mean, scale, _, selection = fit_regimes(returns[:960])
    assert selection["regimes_supported"]
    p = forward_filter(model, (returns - mean) / scale)
    estimated_vol = np.sqrt(model.covars_[:, 0, 0]) * scale[0]
    forecast_vol = p @ estimated_vol
    assert forecast_vol[1140:1270].mean() > 3 * forecast_vol[980:1110].mean()


def test_log_filter_recovers_an_extremely_unlikely_state_after_later_evidence():
    model = GaussianHMM(n_components=2, covariance_type="full", init_params="")
    model.startprob_ = np.array([0.5, 0.5])
    model.transmat_ = np.eye(2)
    model.means_ = np.array([[-50.0], [50.0]])
    model.covars_ = np.ones((2, 1, 1))
    # First posterior underflows in ordinary probability space. Equal and
    # opposite evidence must nevertheless restore the original equal odds.
    p = forward_filter(model, np.array([[-50.0], [50.0]]))
    np.testing.assert_allclose(p[-1], [0.5, 0.5], atol=1e-12)


@pytest.mark.parametrize(
    "training",
    [
        np.ones((200, 1)),
        np.full((200, 1), np.nan),
        np.zeros((99, 1)),
        np.ones((200, 3)),
    ],
)
def test_invalid_training_is_rejected(training):
    with pytest.raises(ValueError):
        fit_regimes(training)


def test_unstable_hmms_fall_back_to_single_gaussian(monkeypatch):
    from investor.analysis import regimes

    original = regimes._fit

    def only_baseline(training, count):
        if count != 1:
            raise ValueError("Synthetic convergence failure")
        return original(training, count)

    monkeypatch.setattr(regimes, "_fit", only_baseline)
    regimes._fit_cached.cache_clear()
    model, _, _, _, selection = fit_regimes(
        np.random.default_rng(801).normal(size=(250, 1))
    )
    assert model.n_components == 1
    assert list(selection["validation_scores"]) == ["1"]
    regimes._fit_cached.cache_clear()


def test_signal_before_test_can_execute_at_first_test_close():
    request = AnalysisRequest(
        train_start="2020-01-01",
        train_end="2020-12-31",
        test_start="2021-01-01",
        test_end="2021-12-31",
        fee_bps=100,
    )
    net, _, trades, positions = simulate_switching(
        np.log1p([0.5, 0.1, 0.1]),
        np.tile([1.0, 0.0], (3, 1)),
        ["2021-01-01", "2021-01-02", "2021-01-03"],
        request,
        np.array([0.1, -0.1]),
        0.02,
        np.array([True, False]),
        initial_probability=np.array([1.0, 0.0]),
    )
    assert trades[0]["time"] == "2021-01-01"
    assert net[0] == pytest.approx(-0.01)  # First day's return precedes execution.
    assert net[1] == pytest.approx(0.1)
    assert net[2] == pytest.approx(1.1 * 0.99 - 1)
    assert positions == [1, 1, 0]


def fixture():
    rng = np.random.default_rng(123)
    values = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.01, 360)))
    rows = [
        {
            "date": (date(2020, 1, 1) + timedelta(days=i)).isoformat(),
            "value": float(value),
        }
        for i, value in enumerate(values)
    ]
    request = AnalysisRequest(
        train_start=rows[0]["date"],
        train_end=rows[219]["date"],
        test_start=rows[260]["date"],
        test_end=rows[-1]["date"],
        fee_bps=0,
    )
    return {"metric": "price", "category": "stock"}, rows, request


def test_shortening_test_preserves_all_prior_signals_and_orders():
    asset, rows, request = fixture()
    full = calculate(asset, rows, request)
    short = calculate(
        asset,
        rows[:320],
        request.model_copy(update={"test_end": date.fromisoformat(rows[319]["date"])}),
    )
    assert short["states"] == full["states"]
    assert short["model_selection"] == full["model_selection"]
    assert short["regimes"] == full["regimes"][:60]
    assert short["positions"][:-1] == full["positions"][:59]
    assert short["equity"][:-1] == full["equity"][:60]
    assert full["model_version"] == VERSION


def test_gap_updates_filter_without_becoming_training_data():
    asset, rows, request = fixture()
    first = calculate(asset, rows, request)
    changed = [dict(row) for row in rows]
    changed[240]["value"] *= 1.2
    second = calculate(asset, changed, request)
    assert first["states"] == second["states"]
    assert first["model_selection"] == second["model_selection"]
    assert first["train_points"] == 219
    assert first["test_points"] == 100


def test_duplicate_dates_are_rejected():
    asset, rows, request = fixture()
    rows[150]["date"] = rows[149]["date"]
    with pytest.raises(ValueError, match="strictement croissantes"):
        calculate(asset, rows, request)
