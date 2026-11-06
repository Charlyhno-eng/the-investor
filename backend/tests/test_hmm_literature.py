"""Research integrity: rolling recalibration, chronology and exposure accounting."""

import importlib
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
from investor.analysis.schemas import AnalysisRequest
from investor.analysis.switching import simulate_switching


@pytest.fixture
def research(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    return importlib.import_module("hmm_regime_candidates")


def sample():
    rng = np.random.default_rng(7)
    drift = np.repeat([0.004, -0.004, 0.004, -0.004], 250)
    returns = drift + rng.normal(0, 0.006, len(drift))
    values = np.r_[100, 100 * np.exp(np.cumsum(returns))]
    dates = np.array(
        [
            (date(2019, 1, 2) + timedelta(days=i)).isoformat()
            for i in range(len(returns))
        ]
    )
    request = AnalysisRequest(
        train_start="2019-01-01",
        train_end=dates[599],
        test_start=dates[600],
        test_end=dates[-1],
        fee_bps=50,
    )
    return returns, values, dates, request


def test_ewm_features_match_explicit_past_weights_and_prefixes(research):
    returns, values, _, _ = sample()
    changes, x = research.ewm_observations(values)
    np.testing.assert_allclose(changes, returns, atol=1e-14)
    assert np.isnan(x[:29]).all()
    _, prefix = research.ewm_observations(values[:400])
    np.testing.assert_allclose(prefix, x[:399], equal_nan=True)
    alpha = 2 / 31
    for i in (29, 200, 500):
        weights = alpha * (1 - alpha) ** np.arange(i, -1, -1)
        weights[0] = (1 - alpha) ** i
        mean = weights @ returns[: i + 1]
        variance = weights @ ((returns[: i + 1] - mean) ** 2)
        np.testing.assert_allclose(x[i], [mean, np.sqrt(variance)], atol=1e-13)


def test_recalibrations_never_see_signal_bar_or_rewrite_past(research, monkeypatch):
    _, values, dates, request = sample()
    _, x = research.ewm_observations(values)
    original = research.fit
    seen = []

    def spy(training):
        seen.append(training.copy())
        return original(training)

    monkeypatch.setattr(research, "fit", spy)
    first = research.candidate_signals(x, dates, request)
    assert len(seen) == 7  # Initial calibration and six 63-bar refreshes.
    np.testing.assert_allclose(seen[0], x[29:600])
    for i, training in enumerate(seen[1:], 1):
        np.testing.assert_allclose(training, x[29 : 600 + 63 * i])
    for signal in first.values():
        for calibration in signal["calibrations"]:
            assert calibration["calibration_end"] < calibration["first_signal"]
    changed_values = values.copy()
    changed_values[851:] *= 1.5
    _, revised = research.ewm_observations(changed_values)
    second = research.candidate_signals(revised, dates, request)
    for name in research.CANDIDATES:
        np.testing.assert_array_equal(
            first[name]["value"][:250], second[name]["value"][:250]
        )
        np.testing.assert_array_equal(
            first[name]["probability"][:250], second[name]["probability"][:250]
        )
    # Even the frozen model must detect both directions on never-fitted data.
    signal = first["ewm_frozen_pesr"]["value"]
    assert np.mean(signal[40:140] > 0) > 0.9
    assert np.mean(signal[220:350] < 0) > 0.9


def test_failed_refresh_carries_model_and_records_actual_training_dates(
    research, monkeypatch
):
    _, values, dates, request = sample()
    _, x = research.ewm_observations(values)
    original = research.fit
    calls = 0

    def failing(training):
        nonlocal calls
        calls += 1
        if calls in (3, 4):
            raise ValueError("Synthetic failed calibration")
        return original(training)

    monkeypatch.setattr(research, "fit", failing)
    result = research.candidate_signals(x, dates, request)["ewm_rolling_cost"]
    audit = result["calibrations"]
    assert audit[2]["failure"] == audit[3]["failure"] == "Synthetic failed calibration"
    assert (
        audit[1]["calibration_end"]
        == audit[2]["calibration_end"]
        == audit[3]["calibration_end"]
    )
    assert audit[4]["calibration_end"] > audit[3]["calibration_end"]
    assert np.isfinite(result["value"]).all()


def test_research_execution_matches_production_clock_and_measures_earned_exposure(
    research,
):
    _, _, _, request = sample()
    request = request.model_copy(update={"fee_bps": 100})
    p = np.eye(2)[[0, 0, 1, 1, 0, 0, 0]]
    advantage = np.array([0.02, -0.02])
    cost = -np.log(0.99)
    changes = np.log1p([0.5, 0.5, 0.1, 0.1, 0.1, 0.1, 0.1])
    dates = [str(i) for i in range(7)]
    old = simulate_switching(
        changes, p, dates, request, advantage, cost, np.array([True, False])
    )
    new = research.execute(changes, dates, p @ advantage, cost, p[:, 0], 100)
    np.testing.assert_allclose(old[0], new[0])
    np.testing.assert_allclose(old[1], new[1])
    assert old[2] == new[2]
    np.testing.assert_array_equal(new[3], [0, *old[3][:-1]])
    # Exposure is held at the beginning of each return, including final exit.
    assert new[3].tolist() == [0, 0, 1, 1, 0, 0, 1]


def test_benchmark_gate_cannot_pass_with_inert_exposure_or_losses(research):
    benchmark = importlib.import_module("backtest_hmm_literature")

    def case(exposure, excess):
        return {
            "case": "test",
            "fee_multiple": 1,
            "policy": "current_hmm",
            "excess_return": excess,
            "exposure": exposure,
            "strategy_metrics": {"total_return": 0.1 + excess, "maximum_drawdown": 0.1},
            "benchmark_metrics": {"total_return": 0.1},
            "trades": [1, 2],
        }

    assert not benchmark.aggregate([case(0.99, 0.01) for _ in range(10)])[0][
        "passes_gate"
    ]
    assert not benchmark.aggregate([case(0, 0.01) for _ in range(10)])[0]["passes_gate"]
    assert not benchmark.aggregate([case(0.6, -0.01) for _ in range(10)])[0][
        "passes_gate"
    ]
    assert benchmark.aggregate([case(0.6, 0.01) for _ in range(10)])[0]["passes_gate"]


def test_volatility_filter_is_causal_across_retraining_and_maps_actual_variance(
    research,
):
    module = importlib.import_module("backtest_hmm_volatility")
    changes, _, dates, request = sample()
    first, probability, audit = module.risk_signals(changes, dates, request, True)
    revised = changes.copy()
    revised[850:] += 0.2
    second, changed_probability, _ = module.risk_signals(revised, dates, request, True)
    np.testing.assert_array_equal(first[:250], second[:250])
    np.testing.assert_array_equal(probability[:250], changed_probability[:250])
    assert len(audit) == 7
    for calibration in audit:
        assert calibration["calibration_end"] < calibration["first_signal"]
        calm = calibration["calm_state"]
        assert calibration["volatility"][calm] == min(calibration["volatility"])
    np.testing.assert_allclose(first, probability - 0.5)
