"""Portfolio paths and allocation constraints against independent calculations."""

import numpy as np
import pytest
from investor import db
from investor.comparison import INDEX
from investor.performance import comparison_data, optimize_weights
from test_volatility import seed

pytest_plugins = ["test_volatility"]


def request(
    http, optimize=False, holdings=None, years=3, mode="volatility", history="common"
):
    response = http.post(
        "/api/portfolio/optimize" if optimize else "/api/portfolio/performance",
        json={
            "holdings": holdings
            if holdings is not None
            else [{"asset_id": "a", "quantity": 3}, {"asset_id": "b", "quantity": 1}],
            "years": years,
            "mode": mode,
            "history": history,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_paths_weights_quantities_and_independent_benchmark(client):
    http, days = client
    a = seed(days, "a")
    b = seed(days, "b", sign=-1)
    base = request(http)
    assert base["status"] == "ready"
    assert "optimized" not in base["metrics"]
    assert "optimized" not in base["equity"][0]
    assert base["equity"][0] == {"time": days[0], "portfolio": 100, "benchmark": 100}
    prices = np.array([[v[2] for v in values] for values in (a, b)]).T
    returns = prices[1:] / prices[:-1] - 1
    current_changes = returns @ np.array([0.75, 0.25])
    expected = np.r_[100, 100 * np.cumprod(1 + current_changes)]
    assert [p["portfolio"] for p in base["equity"]] == pytest.approx(expected)
    assert base["metrics"]["portfolio"]["volatility"] == pytest.approx(
        current_changes.std(ddof=1) * np.sqrt(252)
    )
    optimized = request(http, True)
    weights = np.array([p["recommended_weight"] for p in optimized["positions"]])
    assert weights.sum() == pytest.approx(1)
    assert np.min(weights) >= 0
    assert weights == pytest.approx([0.5, 0.5], abs=1e-6)
    assert optimized["metrics"]["optimized"]["volatility"] < 1e-7
    assert (
        optimized["metrics"]["optimized"]["total_return"]
        >= base["metrics"]["portfolio"]["total_return"] - 1e-9
    )
    assert [(p["portfolio"], p["benchmark"]) for p in optimized["equity"]] == [
        (p["portfolio"], p["benchmark"]) for p in base["equity"]
    ]
    for p in optimized["positions"]:
        assert p["recommended_quantity"] * p["price"] == pytest.approx(
            320 * p["recommended_weight"]
        )
    with db.connect() as c:
        c.execute(
            "UPDATE reference_observations SET value=value*2 WHERE symbol=? AND date=?",
            (INDEX, days[-1]),
        )
    changed = request(http, True)
    assert [p["recommended_weight"] for p in changed["positions"]] == pytest.approx(
        weights
    )
    assert changed["metrics"]["benchmark"] != optimized["metrics"]["benchmark"]


@pytest.mark.parametrize("mode", ["balanced", "volatility", "performance", "drawdown"])
def test_optimizer_matches_dense_two_asset_search(mode):
    rng = np.random.default_rng(91)
    returns = rng.normal([0.001, 0.0003], [0.025, 0.007], (750, 2))
    current = np.array([0.7, 0.3])
    w = optimize_weights(returns, current, mode)
    grid = np.column_stack((np.linspace(0, 1, 3001), np.linspace(1, 0, 3001)))

    def objective(weights):
        changes = returns @ weights.T
        if changes.ndim == 1:
            changes = changes[:, None]
        logs = np.vstack(
            [np.zeros(changes.shape[1]), np.cumsum(np.log1p(changes), axis=0)]
        )
        if mode == "balanced":
            return -changes.mean(axis=0) / changes.std(axis=0, ddof=1)
        if mode == "volatility":
            return changes.var(axis=0, ddof=1)
        if mode == "performance":
            return -logs[-1]
        return np.max(np.maximum.accumulate(logs, axis=0) - logs, axis=0)

    assert objective(w)[0] <= np.min(objective(grid)) + 1e-7
    assert objective(w)[0] <= objective(current)[0] + 1e-8
    assert w.sum() == pytest.approx(1)
    assert w.min() >= 0


@pytest.mark.parametrize("case", ["single", "identical", "zero", "negative"])
def test_degenerate_and_negative_return_portfolios(case):
    rng = np.random.default_rng(2)
    changes = rng.normal(-0.002, 0.01, 200)
    returns = {
        "single": changes[:, None],
        "identical": np.column_stack([changes, changes]),
        "zero": np.zeros((200, 3)),
        "negative": np.column_stack([changes, -0.001 + changes * 0.2]),
    }[case]
    current = np.full(returns.shape[1], 1 / returns.shape[1])
    weights = optimize_weights(returns, current, "volatility")
    assert weights.sum() == pytest.approx(1)
    assert np.min(weights) >= 0
    assert np.var(returns @ weights) <= np.var(returns @ current) + 1e-10


def test_validation_missing_history_exclusions_and_pending(client):
    http, days = client
    seed(days, "a")
    seed(days, "b", category="bond")
    assert request(http)["status"] == "insufficient"
    assert request(http)["excluded"][0]["id"] == "b"
    assert request(http, holdings=[])["status"] == "insufficient"
    with db.connect() as c:
        c.execute("DELETE FROM observations WHERE asset_id='b'")
        c.execute("DELETE FROM price_observations WHERE asset_id='b'")
    seed(days[-5:], "b")
    assert request(http)["status"] == "insufficient"
    for endpoint in ["performance", "optimize"]:
        assert (
            http.post(
                f"/api/portfolio/{endpoint}",
                json={"holdings": [{"asset_id": "a", "quantity": 1}] * 2},
            ).status_code
            == 422
        )
        assert (
            http.post(
                f"/api/portfolio/{endpoint}",
                json={"holdings": [{"asset_id": "missing", "quantity": 1}]},
            ).status_code
            == 404
        )
    with db.connect() as c:
        c.execute("DELETE FROM reference_imports WHERE symbol=?", (INDEX,))
    assert (
        request(http, holdings=[{"asset_id": "a", "quantity": 1}])["status"]
        == "pending"
    )


def test_monthly_alignment_fx_and_one_asset(client):
    http, days = client
    seed(days, "a", unit="EUR")
    base = request(http, True, [{"asset_id": "a", "quantity": 1}])
    assert base["positions"][0]["recommended_weight"] == 1
    assert base["metrics"]["optimized"] == base["metrics"]["portfolio"]
    with db.connect() as c:
        c.execute(
            "UPDATE reference_observations SET value=2 WHERE symbol='EURUSD=X' AND date=?",
            (days[-1],),
        )
    fx = request(http, holdings=[{"asset_id": "a", "quantity": 1}])
    assert fx["metrics"]["portfolio"] == base["metrics"]["portfolio"]  # EUR asset
    assert fx["metrics"]["benchmark"] != base["metrics"]["benchmark"]
    months = [f"2024-{m:02d}-15" for m in range(1, 13)] + [
        f"2025-{m:02d}-15" for m in range(1, 13)
    ]
    history = {d: 100 + i * 2 for i, d in enumerate(months)}
    result = comparison_data(
        [{"frequency": "monthly"}],
        [history],
        history,
        [{"weight": 1, "value": 200, "price": 100}],
        3,
        True,
    )
    assert result["frequency"] == "monthly"
    assert result["observations"] == 23
    assert result["metrics"]["benchmark"] == result["metrics"]["portfolio"]
    changes = np.diff(list(history.values())) / np.array(list(history.values())[:-1])
    assert result["metrics"]["portfolio"]["volatility"] == pytest.approx(
        changes.std(ddof=1) * np.sqrt(12)
    )


def test_extended_history_reserves_cash_before_inception_and_does_not_fill_gaps():
    from datetime import date, timedelta

    days = [
        (date(2026, 1, 1) - timedelta(days=900 - i)).isoformat() for i in range(900)
    ]
    old = {d: 100 + i * 0.1 for i, d in enumerate(days)}
    young = {d: 100 + i * 0.2 for i, d in enumerate(days[-150:])}
    assets = [
        {"id": "old", "name": "Old", "frequency": "daily"},
        {"id": "young", "name": "Young", "frequency": "daily"},
    ]
    positions = [{"weight": 0.5, "value": 100, "price": 100}] * 2
    short = comparison_data(assets, [old, young], old, positions, 1)
    long = comparison_data(assets, [old, young], old, positions, 3, history="extended")
    common = comparison_data(assets, [old, young], old, positions, 3)
    assert short["start"] == common["start"] == days[-150]
    assert long["start"] == days[0]
    assert long["cash_until"] == [{"id": "young", "name": "Young", "date": days[-150]}]
    # The young asset's reserved half stays cash, rather than inventing prices
    # or giving the old asset its weight. Entry occurs at its first known price.
    assert long["equity"][1]["portfolio"] == pytest.approx(100 * (1 + 0.5 * 0.001))
    prior, inception, active = long["equity"][749:752]
    assert inception["portfolio"] / prior["portfolio"] - 1 == pytest.approx(
        0.5 * (old[days[750]] / old[days[749]] - 1)
    )
    assert active["portfolio"] / inception["portfolio"] - 1 == pytest.approx(
        0.5 * (old[days[751]] / old[days[750]] - 1)
        + 0.5 * (young[days[751]] / young[days[750]] - 1)
    )
    del young[days[-50]]
    gap = comparison_data(assets, [old, young], old, positions, 3, history="extended")
    assert days[-50] not in [p["time"] for p in gap["equity"]]
    assert gap["observations"] == long["observations"] - 1


def test_metrics_reproduce_exact_drawdown_and_sharpe(client):
    http, days = client
    seed(days, "a")
    seed(days, "b", sign=-1)
    result = request(http, True, mode="drawdown")
    for key, metrics in result["metrics"].items():
        curve = np.array([p[key] for p in result["equity"]])
        changes = curve[1:] / curve[:-1] - 1
        assert metrics["max_drawdown"] == pytest.approx(
            np.min(curve / np.maximum.accumulate(curve) - 1)
        )
        if changes.std(ddof=1) > 1e-12:
            assert metrics["sharpe"] == pytest.approx(
                changes.mean() / changes.std(ddof=1) * np.sqrt(252)
            )
        else:
            assert metrics["sharpe"] is None
    assert result["mode"] == "drawdown"
    for field in [{"mode": "unknown"}, {"history": "invented"}]:
        assert (
            http.post(
                "/api/portfolio/optimize", json={"holdings": [], **field}
            ).status_code
            == 422
        )


@pytest.mark.parametrize("mode", ["balanced", "volatility", "performance", "drawdown"])
@pytest.mark.parametrize("case", ["positive", "negative", "zero"])
def test_all_modes_enforce_concentration_even_when_current_portfolio_is_concentrated(
    mode, case
):
    rng = np.random.default_rng(13)
    returns = rng.normal(
        [0.003, 0.001, 0.0002, 0.0005], [0.02, 0.01, 0.015, 0.008], (200, 4)
    )
    if case == "negative":
        returns = -np.abs(returns)
    elif case == "zero":
        returns = np.zeros((200, 4))
    weights = optimize_weights(returns, np.array([1.0, 0.0, 0.0, 0.0]), mode)
    assert weights.sum() == pytest.approx(1)
    assert weights.min() >= 0
    assert weights.max() <= 0.35 + 1e-8
    assert np.count_nonzero(weights > 1e-8) >= 3


def test_performance_cap_is_part_of_the_optimum_and_two_assets_are_exempt():
    returns = np.tile([0.01, 0.005, 0.001], (100, 1))
    weights = optimize_weights(returns, np.array([1.0, 0.0, 0.0]), "performance")
    assert weights == pytest.approx([0.35, 0.35, 0.3], abs=1e-7)
    two = optimize_weights(returns[:, :2], np.array([0.5, 0.5]), "performance")
    assert two == pytest.approx([1.0, 0.0], abs=1e-7)
