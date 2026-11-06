from datetime import date, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient
from investor import db
from investor.analysis.metrics import metrics
from investor.analysis.model import features
from investor.analysis.schemas import AnalysisRequest
from investor.analysis.service import calculate
from investor.analysis.strategy import simulate
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
    _, whole = features(values, False, 3)
    _, prefix = features(values[:4], False, 3)
    np.testing.assert_allclose(whole[:3], prefix)


def test_hmm_future_changes_do_not_change_past_results(sample):
    asset, rows, request = sample
    first = calculate(asset, rows, request)
    revised = [dict(row) for row in rows]
    for i in range(780, 800):
        revised[i]["value"] *= 1.5
    second = calculate(asset, revised, request)
    assert first["states"] == second["states"]
    assert first["transition_matrix"] == second["transition_matrix"]
    assert first["regimes"][:280] == second["regimes"][:280]
    assert first["equity"][:281] == second["equity"][:281]
    assert request.max_trades is None or len(first["trades"]) <= request.max_trades
    assert all(
        np.isfinite(v) for v in first["strategy_metrics"].values() if v is not None
    )


def test_execution_lag_costs_and_trade_cap():
    request = AnalysisRequest(
        train_start="2000-01-01",
        train_end="2005-01-01",
        test_start="2006-01-01",
        test_end="2007-01-01",
        fee_bps=100,
        slippage_bps=0,
        min_hold=1,
        entry_confirmation=1,
        exit_confirmation=1,
        max_trades=2,
    )
    # A perfect bullish signal at bar 0 enters only at bar 1's close.
    probabilities = np.tile([0.0, 0.0, 1.0], (5, 1))
    changes = np.log1p([0.5, 0.5, 0.1, 0.1, 0.1])
    net, benchmark, trades, _positions = simulate(
        changes, probabilities, ["a", "b", "c", "d", "e"], 2, request, 252
    )
    assert net[0] == 0
    assert net[1] == pytest.approx(-0.01)
    assert net[2] == pytest.approx(0.1)
    assert net[-1] == pytest.approx(1.1 * 0.99 - 1)
    assert [t["side"] for t in trades] == ["buy", "sell"]
    assert trades[0]["time"] == "b" and trades[-1]["time"] == "e"
    assert benchmark[0] == pytest.approx(1.5 * 0.99 - 1)


def test_hysteresis_confirmation_minimum_holding_and_cap():
    request = AnalysisRequest(
        train_start="2000-01-01",
        train_end="2005-01-01",
        test_start="2006-01-01",
        test_end="2007-01-01",
        min_hold=6,
        entry_confirmation=2,
        exit_confirmation=2,
        max_trades=4,
    )
    probabilities = np.zeros((60, 3))
    probabilities[:, 2] = np.tile([1, 1, 0, 0, 0, 0], 10)
    net, _, trades, _ = simulate(
        np.zeros(60), probabilities, list(range(60)), 2, request, 252
    )
    assert len(trades) <= 4
    for buy, sell in zip(trades[::2], trades[1::2]):
        assert sell["time"] - buy["time"] >= 6 or sell["time"] == 59
    assert trades[0]["time"] >= 2
    assert net.sum() <= 0


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
    original = service.fit_model
    calls = []

    def spy(training):
        calls.append(len(training))
        return original(training)

    monkeypatch.setattr(service, "fit_model", spy)
    path = "/api/assets/sample/analysis"
    payload = request.model_dump(mode="json")
    first = local.post(path, json=payload)
    assert first.status_code == 200
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
    from investor.analysis import model

    model._fit_cached.cache_clear()
    original = model.GaussianHMM.fit
    calls = []

    def fit(self, x, *args, **kwargs):
        calls.append(len(x))
        return original(self, x, *args, **kwargs)

    monkeypatch.setattr(model.GaussianHMM, "fit", fit)
    asset, rows, request = sample
    first = calculate(asset, rows, request)
    assert len(calls) == 3
    changed = request.model_copy(update={"fee_bps": 50})
    second = calculate(asset, rows, changed)
    assert len(calls) == 3
    assert second["states"] == first["states"]
    assert second["regimes"] == first["regimes"]
    assert second["equity"] != first["equity"]
    revised = [dict(row) for row in rows]
    revised[-1]["value"] *= 1.5
    calculate(asset, revised, request)
    assert len(calls) == 3
    revised[200]["value"] *= 1.01
    calculate(asset, revised, request)
    assert len(calls) == 6
    assert model._fit_cached.cache_info().maxsize == 8
    model._fit_cached.cache_clear()


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


def test_momentum_uses_only_trailing_log_returns():
    returns = np.array([0.01, 0.02, -0.01, 0.03])
    prices = 100 * np.exp(np.r_[0, np.cumsum(returns)])
    changes, x = features(prices, False, 3)
    np.testing.assert_allclose(changes, returns)
    np.testing.assert_allclose(x[:, 1], [0.01, 0.03, 0.02, 0.04])


def test_binary_model_and_executed_positions(sample):
    asset, rows, request = sample
    rng = np.random.default_rng(73)
    # Both directions are present in training and test, with sustained trends.
    returns = np.repeat([0.006, -0.006, 0.006, -0.006], 200)
    returns += rng.normal(0, 0.001, len(returns))
    values = 100 * np.exp(np.cumsum(returns))
    revised = [dict(row, value=float(v)) for row, v in zip(rows, values)]
    result = calculate(asset, revised, request)
    assert [s["name"] for s in result["states"]] == ["Neutre / baisse", "Hausse"]
    assert np.array(result["transition_matrix"]).shape == (2, 2)
    assert all(len(p["probabilities"]) == 2 for p in result["regimes"])
    assert len(result["positions"]) == result["test_points"]
    position = 0
    trades = {t["time"]: t for t in result["trades"]}
    for p in result["positions"]:
        if p["time"] in trades:
            position = int(trades[p["time"]]["side"] == "buy")
        assert p["position"] == position
    assert any(p["position"] == 1 for p in result["positions"][:80])
    assert all(p["position"] == 0 for p in result["positions"][150:])
    assert result["positions"][-1]["position"] == 0


def test_no_buy_when_both_trained_states_lose_money(sample, monkeypatch):
    from types import SimpleNamespace

    from investor.analysis import service

    asset, rows, request = sample
    fake = SimpleNamespace(
        means_=np.array([[-0.02, -0.1], [-0.01, -0.05]]),
        transmat_=np.array([[0.9, 0.1], [0.1, 0.9]]),
    )
    monkeypatch.setattr(
        service, "fit_model", lambda x: (fake, np.zeros(2), np.ones(2), True)
    )
    monkeypatch.setattr(
        service, "forward_filter", lambda m, x: np.tile([0, 1.0], (len(x), 1))
    )
    result = calculate(asset, rows, request)
    assert result["trades"] == []
    assert all(p["position"] == 0 for p in result["positions"])
    assert result["strategy_metrics"]["total_return"] == 0


def test_strategy_confirms_exit_as_well_as_entry():
    request = AnalysisRequest(
        train_start="2000-01-01",
        train_end="2001-01-01",
        test_start="2002-01-01",
        test_end="2003-01-01",
        entry_confirmation=3,
        exit_confirmation=3,
    )
    p = np.array([[0, 1.0]] * 4 + [[1.0, 0]] * 6)
    _, _, trades, _ = simulate(
        np.zeros(len(p)), p, list(range(len(p))), 1, request, 252
    )
    assert trades[0]["time"] == 3
    assert trades[1]["time"] == 7
    assert request.max_trades is None


def test_nonpositive_momentum_blocks_bullish_model(sample, monkeypatch):
    from types import SimpleNamespace

    from investor.analysis import service

    asset, rows, request = sample
    revised = [
        dict(r, value=100 * np.exp(-i * 0.001 + 0.0001 * np.sin(i)))
        for i, r in enumerate(rows)
    ]
    fake = SimpleNamespace(
        means_=np.array([[-0.01, -0.1], [0.01, 0.1]]),
        transmat_=np.array([[0.9, 0.1], [0.1, 0.9]]),
    )
    monkeypatch.setattr(
        service, "fit_model", lambda x: (fake, np.zeros(2), np.ones(2), True)
    )
    monkeypatch.setattr(
        service, "forward_filter", lambda m, x: np.tile([0.0, 1.0], (len(x), 1))
    )
    result = calculate(asset, revised, request)
    assert not result["trades"]


def test_confirmation_reduces_churn_and_costs(sample):
    request = sample[2].model_copy(
        update={"entry_confirmation": 2, "exit_confirmation": 2}
    )
    p = np.array([[0.0, 1.0]] * 5 + [[1.0, 0.0], [0.0, 1.0]] * 10)
    net, _, trades, _ = simulate(
        np.zeros(len(p)), p, list(range(len(p))), 1, request, 252
    )
    fast, _, frequent, _ = simulate(
        np.zeros(len(p)),
        p,
        list(range(len(p))),
        1,
        request.model_copy(update={"entry_confirmation": 1, "exit_confirmation": 1}),
        252,
    )
    assert len(trades) == 2
    assert len(frequent) > len(trades)
    assert np.prod(1 + net) > np.prod(1 + fast)


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


@pytest.mark.parametrize("entry,exit,buy_at,sell_at", [(5, 3, 5, 12), (2, 6, 2, 15)])
def test_independent_entry_and_exit_confirmations(sample, entry, exit, buy_at, sell_at):
    request = sample[2].model_copy(
        update={"entry_confirmation": entry, "exit_confirmation": exit}
    )
    bullish = np.array([0.9] * 9 + [0.1] * 8)
    probabilities = np.column_stack((1 - bullish, bullish))
    _, _, trades, _ = simulate(
        np.zeros(17), probabilities, list(range(17)), 1, request, 252
    )
    assert [(t["side"], t["time"]) for t in trades] == [
        ("buy", buy_at),
        ("sell", sell_at),
    ]


def test_interrupted_entry_and_exit_confirmation_streaks_reset(sample):
    bullish = np.array(
        [0.9] * 4 + [0.6] + [0.9] * 5 + [0.1] * 2 + [0.6] + [0.1] * 3 + [0.6] * 3
    )
    probabilities = np.column_stack((1 - bullish, bullish))
    _, _, trades, _ = simulate(
        np.zeros(len(bullish)),
        probabilities,
        list(range(len(bullish))),
        1,
        sample[2],
        252,
    )
    assert [(t["side"], t["time"]) for t in trades] == [("buy", 10), ("sell", 16)]
