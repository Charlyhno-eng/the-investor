"""Causality, directional recovery, switching costs and absence of forced stops."""

from types import SimpleNamespace

import numpy as np
import pytest
from investor.analysis.model import forward_filter
from investor.analysis.regimes import fit_regimes, observations, predictive_return_score
from investor.analysis.schemas import AnalysisRequest
from investor.analysis.service import resolve_fees
from investor.analysis.switching import simulate_switching, switching_values


def request(fee=0):
    return AnalysisRequest(
        train_start="2000-01-01",
        train_end="2005-01-01",
        test_start="2006-01-01",
        test_end="2007-01-01",
        fee_bps=fee,
    )


def test_return_observations_have_no_future_padding_or_warmup():
    values = np.exp(np.cumsum(np.random.default_rng(5).normal(0, 0.02, 120)))
    _, whole = observations(values)
    _, prefix = observations(values[:70])
    np.testing.assert_allclose(prefix, whole[:69], equal_nan=True)
    assert whole.shape == (119, 1)
    assert np.isfinite(whole).all()
    np.testing.assert_allclose(whole[:, 0], np.diff(np.log(values)))


def test_hmm_recognizes_opposite_drifts_with_the_same_noise_level():
    rng = np.random.default_rng(7)
    drift = np.repeat([0.006, -0.006, 0.006, -0.006, 0.006, -0.006], 180)
    returns = drift + rng.normal(0, 0.006, len(drift))
    _, x = observations(np.r_[100, 100 * np.exp(np.cumsum(returns))])
    model, mean, scale, _, selection = fit_regimes(x[:720])
    p = forward_filter(model, (x[:, selection["observable_columns"]] - mean) / scale)
    estimated = model.means_[:, 0] * scale[0] + mean[0]
    # Last two segments were never fitted. Allow 30 observations of causal
    # detection delay after each change.
    for start, end, positive in [(750, 900, True), (930, 1080, False)]:
        expected = p[start:end] @ estimated
        assert np.mean((expected > 0) == positive) > 0.9
    assert selection["fit_points"] + selection["validation_points"] == 720
    assert selection["selected_states"] in (2, 3)


def test_validation_scores_next_return_density_from_past_only():
    from hmmlearn.hmm import GaussianHMM
    from scipy.stats import norm

    model = GaussianHMM(n_components=2, covariance_type="diag", init_params="")
    model.startprob_ = np.array([0.4, 0.6])
    model.transmat_ = np.array([[0.9, 0.1], [0.2, 0.8]])
    model.means_ = np.array([[-0.2, -0.5], [0.2, 0.5]])
    model.covars_ = np.array([[0.5, 0.4], [0.2, 0.3]])
    mean, scale = np.array([0.001, 2.0]), np.array([0.03, 0.4])
    x = np.random.default_rng(91).normal(size=(35, 2))
    observed = x * scale + mean
    expected = []
    for i in range(20, len(x)):
        prior = model.predict_proba(x[:i])[-1] @ model.transmat_
        density = norm.pdf(
            observed[i, 0],
            loc=model.means_[:, 0] * scale[0] + mean[0],
            scale=np.sqrt(model.covars_[:, 0, 0]) * scale[0],
        )
        expected.append(np.log(prior @ density))
    assert predictive_return_score(model, observed, mean, scale, 20) == pytest.approx(
        np.mean(expected)
    )


def test_finite_horizon_forecast_accounts_for_execution_delay_and_roundtrip_cost():
    model = SimpleNamespace(transmat_=np.array([[0.99, 0.01], [0.01, 0.99]]))
    means = np.array([0.01, -0.01])
    advantage, cost = switching_values(model, means, 50)
    # In the symmetric chain the signed drift decays by 0.98 each step.
    expected = means * sum(0.98**step for step in range(2, 7))
    np.testing.assert_allclose(advantage, expected)
    assert cost == pytest.approx(-2 * np.log(0.995))
    free, threshold = switching_values(model, means, 0)
    np.testing.assert_allclose(free, advantage)
    assert threshold == 0


def test_no_drawdown_stop_or_permanent_lock_even_after_large_loss():
    p = np.tile([1.0, 0.0], (7, 1))
    net, _, trades, positions = simulate_switching(
        np.log1p([0, 0, -0.5, 0, 0.1, 0, 0]),
        p,
        list(range(7)),
        request(),
        np.array([0.01, -0.01]),
        0.0,
        np.array([True, False]),
    )
    assert positions == [0, 1, 1, 1, 1, 1, 0]
    assert net[2] == pytest.approx(-0.5)
    assert [(t["time"], t["reason"]) for t in trades] == [
        (1, "regime"),
        (6, "final_liquidation"),
    ]


def test_finite_horizon_handles_periodic_transitions_without_iteration():
    model = SimpleNamespace(transmat_=np.array([[0.0, 1.0], [1.0, 0.0]]))
    advantage, cost = switching_values(
        model, np.array([0.01, -0.01]), (1 - np.exp(-0.01)) * 10000
    )
    np.testing.assert_allclose(advantage, [0.01, -0.01], atol=1e-10)
    assert cost == pytest.approx(0.02)


def test_regime_switch_and_reentry_are_executed_next_close():
    p = np.eye(2)[[0, 0, 1, 1, 0, 0, 0]]
    net, market, trades, positions = simulate_switching(
        np.log1p([0.5, 0.5, 0.1, 0.1, 0.1, 0.1, 0.1]),
        p,
        list(range(7)),
        request(100),
        np.array([0.02, -0.02]),
        -np.log(0.99),
        np.array([True, False]),
    )
    assert [(t["time"], t["side"]) for t in trades] == [
        (1, "buy"),
        (3, "sell"),
        (5, "buy"),
        (6, "sell"),
    ]
    assert net[0] == 0
    assert net[1] == pytest.approx(-0.01)
    assert net[3] == pytest.approx(1.1 * 0.99 - 1)
    assert net[5] == pytest.approx(-0.01)
    assert np.prod(1 + net) == pytest.approx(1.1**3 * 0.99**4)
    assert np.prod(1 + market) == pytest.approx(1.5**2 * 1.1**5 * 0.99**2)
    assert positions[-1] == 0


def test_costs_ignore_weak_flips_but_allow_all_strong_model_changes():
    p = np.eye(2)[[0, 0, 1, 0, 1, 0, 1, 1, 1, 0, 0, 0]]
    # Intermediate posteriors are uncertain, then the bearish regime is clear.
    p = p.astype(float)
    p[2:7] = [[0.49, 0.51], [0.51, 0.49], [0.49, 0.51], [0.51, 0.49], [0.49, 0.51]]
    args = (np.zeros(len(p)), p, list(range(len(p))), request())
    free = simulate_switching(
        *args, np.array([0.02, -0.02]), 0.0, np.array([True, False])
    )
    costed = simulate_switching(
        *args, np.array([0.02, -0.02]), 0.001, np.array([True, False])
    )
    assert len(costed[2]) < len(free[2])
    assert [(t["time"], t["side"]) for t in costed[2]] == [
        (1, "buy"),
        (8, "sell"),
        (10, "buy"),
        (11, "sell"),
    ]


@pytest.mark.parametrize("category, expected", [("stock", 50), ("crypto", 1)])
def test_default_fees_respect_asset_category_and_explicit_zero(category, expected):
    asset = {"category": category}
    omitted = request().model_copy(update={"fee_bps": None})
    assert resolve_fees(asset, omitted).fee_bps == expected
    assert resolve_fees(asset, request(0)).fee_bps == 0
    assert resolve_fees(asset, request(20)).fee_bps == 20
