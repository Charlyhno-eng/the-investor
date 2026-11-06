from datetime import date, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient
from investor import db
from investor.analysis.metrics import metrics
from investor.analysis.model import features
from investor.analysis.schemas import AnalysisRequest
from investor.analysis.service import calculate
from investor.analysis.strategy import POLICIES, simulate
from investor.api import app


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    return TestClient(app)


@pytest.fixture
def sample():
    rng = np.random.default_rng(49)
    daily = rng.normal(np.tile([0.001, -0.001, 0.0004], 300)[:800], 0.014)
    values = 100 * np.exp(np.cumsum(daily))
    rows = [
        {"date": (date(2019, 1, 1) + timedelta(days=i)).isoformat(), "value": float(v)}
        for i, v in enumerate(values)
    ]
    request = AnalysisRequest(
        train_start=rows[0]["date"],
        train_end=rows[499]["date"],
        test_start=rows[500]["date"],
        test_end=rows[-1]["date"],
    )
    asset = {
        "id": "sample",
        "metric": "price",
        "category": "stock",
        "frequency": "daily",
    }
    return asset, rows, request


def test_features_are_causal():
    values = np.array([100, 101, 98, 97, 109, 120.0])
    _, whole = features(values, False)
    _, prefix = features(values[:4], False)
    np.testing.assert_allclose(whole[:3], prefix)


def test_hmm_future_changes_do_not_change_past_results(sample):
    asset, rows, request = sample
    first = calculate(asset, rows, request)
    revised = [dict(row) for row in rows]
    for i in range(780, 800):
        revised[i]["value"] *= 1.5
    second = calculate(asset, revised, request)
    assert first["states"] == second["states"]
    assert first["model_selection"] == second["model_selection"]
    assert first["transition_matrix"] == second["transition_matrix"]
    assert first["regimes"][:280] == second["regimes"][:280]
    assert first["equity"][:281] == second["equity"][:281]
    assert all(
        np.isfinite(v) for v in first["strategy_metrics"].values() if v is not None
    )


def test_execution_lag_and_symmetric_costs():
    request = AnalysisRequest(
        train_start="2000-01-01",
        train_end="2005-01-01",
        test_start="2006-01-01",
        test_end="2007-01-01",
        fee_bps=100,
    )
    # A perfect bullish signal at bar 0 enters only at bar 1's close.
    probabilities = np.tile([0.0, 0.0, 1.0], (5, 1))
    changes = np.log1p([0.5, 0.5, 0.1, 0.1, 0.1])
    net, benchmark, trades, _positions = simulate(
        changes,
        probabilities,
        ["a", "b", "c", "d", "e"],
        2,
        request,
        252,
        policy=POLICIES["daily_original"],
    )
    assert net[0] == 0
    assert net[1] == pytest.approx(-0.01)
    assert net[2] == pytest.approx(0.1)
    assert net[-1] == pytest.approx(1.1 * 0.99 - 1)
    assert [t["side"] for t in trades] == ["buy", "sell"]
    assert trades[0]["time"] == "b" and trades[-1]["time"] == "e"
    assert benchmark[0] == pytest.approx(1.5 * 0.99 - 1)


def test_metrics_known_drawdown_beta_alpha_and_degenerate_cases():
    returns = np.array([0.1, -0.2, 0.1, 0.04])
    result = metrics(returns, returns, 12, 0)
    assert result["maximum_drawdown"] == pytest.approx(0.2)
    assert result["beta"] == pytest.approx(1)
    assert result["alpha"] == pytest.approx(0)
    assert result["annualized_volatility"] == pytest.approx(
        np.std(returns, ddof=1) * np.sqrt(12)
    )
    constant = metrics(np.zeros(30), np.zeros(30), 252, 0)
    assert constant["sharpe"] is None and constant["sortino"] is None
    assert constant["calmar"] is None and constant["beta"] is None
    assert constant["maximum_drawdown"] == 0


def test_yields_only_produce_regimes(sample):
    asset, rows, request = sample
    asset["metric"] = "yield"
    rows = [dict(row, value=row["value"] / 100 - 1) for row in rows]
    result = calculate(asset, rows, request)
    assert result["mode"] == "regimes"
    assert result["strategy_metrics"] is None and not result["equity"]
    assert len(result["regimes"]) == 300


def test_period_validation_and_history_minimums(sample):
    asset, rows, request = sample
    with pytest.raises(ValueError, match="ordonnées"):
        AnalysisRequest(**{**request.model_dump(), "test_start": request.train_end})
    with pytest.raises(ValueError, match="100 variations"):
        calculate(asset, rows[:80], request)
    rows[0]["value"] = -1
    with pytest.raises(ValueError, match="positifs"):
        calculate(asset, rows, request)


def test_analysis_cache_and_data_revision(local, sample, monkeypatch):
    from investor.analysis import service

    _asset, rows, request = sample
    db.save(
        [
            (
                "sample",
                "Sample",
                "stock",
                "price",
                "USD",
                "daily",
                "test",
                "https://example.com",
            )
        ],
        [("sample", r["date"], r["value"]) for r in rows],
        "test",
    )
    original = service.fit_regimes
    calls = []

    def spy(training):
        calls.append(len(training))
        return original(training)

    monkeypatch.setattr(service, "fit_regimes", spy)
    path = "/api/assets/sample/analysis"
    payload = request.model_dump(mode="json")
    first = local.post(path, json=payload)
    assert first.status_code == 200
    assert first.json()["parameters"]["fee_bps"] == 50
    assert "exit_reachable" in first.json()["diagnostics"]
    assert (
        local.post(
            path, json={k: v for k, v in payload.items() if k != "fee_bps"}
        ).json()
        == first.json()
    )
    assert local.post(path, json=payload).json() == first.json()
    assert len(calls) == 1
    with db.connect() as connection:
        connection.execute(
            "UPDATE observations SET value=value*1.01 WHERE asset_id='sample' AND date=?",
            (rows[-1]["date"],),
        )
    updated = local.post(path, json=payload)
    assert updated.status_code == 200
    assert updated.json()["id"] != first.json()["id"] and len(calls) == 2
    assert local.post("/api/assets/missing/analysis", json=payload).status_code == 404
    assert local.post(path, json={**payload, "fee_bps": -1}).status_code == 422
    assert (
        local.post(
            path, json={**payload, "test_start": payload["train_start"]}
        ).status_code
        == 422
    )


@pytest.mark.parametrize("category", ["commodity", "bond"])
def test_unsupported_categories_rejected_before_cache_and_fit(
    local, sample, monkeypatch, category
):
    from investor.analysis import service

    _, _, request = sample
    db.save(
        [
            (
                "unsupported",
                "Unsupported",
                category,
                "price",
                "USD",
                "daily",
                "test",
                "https://example.com",
            )
        ],
        [("unsupported", "2020-01-01", 100)],
        "test",
    )
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO analysis_runs(id,result) VALUES (?,?)",
            ("old-result", '{"legacy":true}'),
        )

    def unexpected_fit(*args):
        pytest.fail("Unsupported assets must be rejected before model fitting")

    monkeypatch.setattr(service, "fit_regimes", unexpected_fit)

    # A cache hit would be returned if the eligibility check were moved below hashing.
    class LegacyHash:
        def hexdigest(self):
            return "old-result"

    monkeypatch.setattr(service.hashlib, "sha256", lambda *args: LegacyHash())
    response = local.post(
        "/api/assets/unsupported/analysis", json=request.model_dump(mode="json")
    )
    assert response.status_code == 422
    assert "réservée aux actions et cryptomonnaies" in response.json()["detail"]


def test_scaled_filter_matches_prefix_posteriors():
    from hmmlearn.hmm import GaussianHMM
    from investor.analysis.model import forward_filter

    model = GaussianHMM(n_components=3, covariance_type="diag", init_params="")
    model.startprob_ = np.array([0.2, 0.5, 0.3])
    model.transmat_ = np.array([[0.9, 0.05, 0.05], [0.1, 0.8, 0.1], [0.05, 0.05, 0.9]])
    model.means_ = np.array([[-1.0, 0.5], [0.0, 1.0], [1.0, 2.0]])
    model.covars_ = np.array([[0.5, 0.2], [0.5, 0.5], [0.5, 1.0]])
    x = np.random.default_rng(4).normal(size=(30, 2))
    filtered = forward_filter(model, x)
    expected = np.array([model.predict_proba(x[:i])[-1] for i in range(1, 31)])
    np.testing.assert_allclose(filtered, expected, atol=1e-12)
    np.testing.assert_allclose(filtered.sum(axis=1), 1.0)


def test_training_cache_reuses_fit_for_simulation_and_test_changes(sample, monkeypatch):
    from investor.analysis import regimes

    regimes._fit_cached.cache_clear()
    original = regimes._fit
    calls = []

    def fit(training, count):
        calls.append((len(training), count))
        return original(training, count)

    monkeypatch.setattr(regimes, "_fit", fit)
    asset, rows, request = sample
    first = calculate(asset, rows, request)
    fitted = len(calls)
    assert fitted >= 3  # Two internal validation models and the final refit.
    changed = request.model_copy(update={"fee_bps": 100})
    second = calculate(asset, rows, changed)
    assert len(calls) == fitted
    assert second["states"] == first["states"]
    assert second["regimes"] == first["regimes"]
    revised = [dict(row) for row in rows]
    revised[-1]["value"] *= 1.5
    calculate(asset, revised, request)
    assert len(calls) == fitted
    revised[200]["value"] *= 1.01
    calculate(asset, revised, request)
    assert len(calls) > fitted
    assert regimes._fit_cached.cache_info().maxsize == 8
    regimes._fit_cached.cache_clear()


def test_forward_filter_extreme_observations_and_zero_transitions():
    from hmmlearn.hmm import GaussianHMM
    from investor.analysis.model import forward_filter

    model = GaussianHMM(n_components=3, covariance_type="diag", init_params="")
    model.startprob_ = np.array([1.0, 0.0, 0.0])
    model.transmat_ = np.eye(3)
    model.means_ = np.array([[-100.0, 0.0], [0.0, 0.0], [100.0, 0.0]])
    model.covars_ = np.ones((3, 2))
    # The most likely emission is unreachable: scaled densities underflow for
    # the only reachable state. Log-space fallback must keep its probability 1.
    x = np.array([[100.0, 0.0], [-100.0, 0.0]])
    probabilities = forward_filter(model, x)
    np.testing.assert_allclose(probabilities, [[1, 0, 0], [1, 0, 0]])
    assert np.isfinite(probabilities).all()
    assert forward_filter(model, np.empty((0, 2))).shape == (0, 3)


def test_comparison_curves_match_reported_net_returns(sample):
    result = calculate(*sample)
    curve = result["equity"]
    assert curve[0]["strategy"] == curve[0]["benchmark"] == 100
    assert curve[0]["time"] < result["actual_test"][0]
    assert len(curve) == result["test_points"] + 1
    assert curve[-1]["strategy"] == pytest.approx(
        100 * (1 + result["strategy_metrics"]["total_return"])
    )
    assert curve[-1]["benchmark"] == pytest.approx(
        100 * (1 + result["benchmark_metrics"]["total_return"])
    )


def test_observable_is_simple_return_without_momentum():
    prices = np.array([100, 110, 99, 118.8])
    changes, x = features(prices, False)
    np.testing.assert_allclose(x[:, 0], [0.1, -0.1, 0.2])
    np.testing.assert_allclose(np.expm1(changes), x[:, 0])
    assert x.shape == (3, 1)


def test_regimes_are_ordered_by_training_return(sample):
    result = calculate(*sample)
    count = len(result["states"])
    means = [s["mean_change"] for s in result["states"]]
    assert means == sorted(means)
    assert count in (2, 3)
    assert np.array(result["transition_matrix"]).shape == (count, count)
    for row in result["regimes"]:
        assert len(row["probabilities"]) == count
        assert sum(row["probabilities"]) == pytest.approx(1)
    position = 0
    trades = {t["time"]: t for t in result["trades"]}
    for row in result["positions"]:
        if row["time"] in trades:
            position = int(trades[row["time"]]["side"] == "buy")
        assert row["position"] == position
    assert result["positions"][-1]["position"] == 0


def test_full_covariance_filter_matches_causal_prefixes():
    from hmmlearn.hmm import GaussianHMM
    from investor.analysis.model import forward_filter

    m = GaussianHMM(n_components=2, covariance_type="full", init_params="")
    m.startprob_ = np.array([0.5, 0.5])
    m.transmat_ = np.array([[0.97, 0.03], [0.1, 0.9]])
    m.means_ = np.array([[0.001], [-0.005]])
    m.covars_ = np.array([[[0.0001]], [[0.0025]]])
    x = np.array([[0.01], [-0.08], [0.06], [0.001], [0.002]])
    expected = np.array([m.predict_proba(x[:i])[-1] for i in range(1, len(x) + 1)])
    np.testing.assert_allclose(forward_filter(m, x), expected, atol=1e-12)


def test_negative_predictive_return_does_not_buy_even_in_calm_regime(
    sample, monkeypatch
):
    from types import SimpleNamespace

    from investor.analysis import service

    fake = SimpleNamespace(
        means_=np.array([[-0.01, -0.01, -4], [0.1, 0.1, -2]]),
        covars_=np.array([[[0.0001]], [[0.01]]]),
        transmat_=np.array([[0.99, 0.01], [0.1, 0.9]]),
    )
    monkeypatch.setattr(
        service,
        "fit_regimes",
        lambda x: (
            fake,
            np.zeros(3),
            np.ones(3),
            True,
            {"observable_columns": [0, 1, 2]},
        ),
    )
    monkeypatch.setattr(
        service, "forward_filter", lambda m, x: np.tile([1.0, 0.0], (len(x), 1))
    )
    asset, rows, request = sample
    rows = [
        dict(r, value=100 * np.exp(i * 0.001 + 0.0001 * np.sin(i)))
        for i, r in enumerate(rows)
    ]
    result = calculate(asset, rows, request)
    assert result["trades"] == []
    assert result["exposure"] == 0


def test_regime_switch_executes_next_close_and_fee_is_same_on_both_sides(sample):
    request = sample[2].model_copy(update={"fee_bps": 100})
    # Calm at 0 buys at 1; extreme at 2 sells at 3.
    p = np.array([[1.0, 0], [1.0, 0], [0.0, 1], [0.0, 1], [1.0, 0], [1.0, 0], [1.0, 0]])
    net, benchmark, trades, positions = simulate(
        np.zeros(7),
        p,
        list(range(7)),
        0,
        request,
        252,
        policy=POLICIES["daily_original"],
    )
    assert [(t["time"], t["side"]) for t in trades] == [
        (1, "buy"),
        (3, "sell"),
        (5, "buy"),
        (6, "sell"),
    ]
    assert positions == [0, 1, 1, 0, 0, 1, 0]
    assert np.prod(1 + net) == pytest.approx(0.99**4)
    assert np.prod(1 + benchmark) == pytest.approx(0.99**2)


@pytest.mark.parametrize(
    "field",
    [
        "slippage_bps",
        "entry_probability",
        "exit_probability",
        "entry_confirmation",
        "exit_confirmation",
        "min_hold",
        "max_trades",
        "risk_free_rate",
    ],
)
def test_only_fees_are_configurable(sample, field):
    with pytest.raises(ValueError, match="Extra inputs"):
        AnalysisRequest(**sample[2].model_dump(), **{field: 1})


def test_higher_fees_preserve_hmm_and_no_stop_is_configured(sample):
    asset, rows, request = sample
    zero = calculate(asset, rows, request.model_copy(update={"fee_bps": 0}))
    high = calculate(asset, rows, request.model_copy(update={"fee_bps": 100}))
    assert high["regimes"] == zero["regimes"]
    assert high["states"] == zero["states"]
    assert "risk_control" not in high
    assert high["policy"]["position_stop"] is None
    assert zero["policy"]["position_stop"] is None


def test_unreachable_exit_is_reported_even_when_adverse_regime_is_detected(
    sample, monkeypatch
):
    from types import SimpleNamespace

    from investor.analysis import service

    # Parameters of the structural failure seen on Air Liquide: every pure
    # state's continuation stays above -cost, despite a negative state mean.
    model = SimpleNamespace(
        means_=np.array([[-0.00081365], [0.00086961]]),
        covars_=np.array([[[0.0004]], [[0.0001]]]),
        transmat_=np.array([[0.913911, 0.086089], [0.015879, 0.984121]]),
    )
    monkeypatch.setattr(
        service,
        "fit_regimes",
        lambda x: (model, np.zeros(1), np.ones(1), True, {"observable_columns": [0]}),
    )

    def beliefs(model, x):
        p = np.tile([0.0, 1.0], (len(x), 1))
        p[-100:] = [1.0, 0.0]
        return p

    monkeypatch.setattr(service, "forward_filter", beliefs)
    result = calculate(*sample)
    diagnostic = result["diagnostics"]
    assert diagnostic["exit_reachable"] is False
    assert diagnostic["negative_dominant_observations"] == 100
    assert diagnostic["negative_dominant_without_exit_while_held"] == 100
    assert (
        len(result["trades"]) == 2
        and result["trades"][-1]["reason"] == "final_liquidation"
    )
    assert any("Aucune sortie de régime" in note for note in result["warnings"])
    assert result["diagnostics"]["nearly_always_invested"] is True
