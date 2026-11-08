"""Portfolio paths and allocation constraints against independent calculations."""

from datetime import date

import numpy as np
import pytest
from investor import db
from investor.comparison import INDEX
from investor.performance import comparison_data, factor_regression, optimize_weights
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


@pytest.mark.parametrize(
    "mode", ["balanced", "volatility", "performance", "drawdown", "diversification"]
)
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
        if mode == "diversification":
            return -(weights @ returns.std(axis=0, ddof=1)) / changes.std(
                axis=0, ddof=1
            )
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
    # The EUR asset is unchanged, but alpha and beta follow the EUR benchmark.
    for key, value in base["metrics"]["portfolio"].items():
        if key not in {"alpha", "beta"}:
            assert fx["metrics"]["portfolio"][key] == value
    assert fx["metrics"]["portfolio"]["beta"] != base["metrics"]["portfolio"]["beta"]
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
    benchmark = np.array([p["benchmark"] for p in result["equity"]])
    market_changes = benchmark[1:] / benchmark[:-1] - 1
    for key, metrics in result["metrics"].items():
        curve = np.array([p[key] for p in result["equity"]])
        changes = curve[1:] / curve[:-1] - 1
        assert metrics["max_drawdown"] == pytest.approx(
            np.min(curve / np.maximum.accumulate(curve) - 1)
        )
        beta = np.cov(changes, market_changes, ddof=1)[0, 1] / np.var(
            market_changes, ddof=1
        )
        assert metrics["beta"] == pytest.approx(beta)
        assert metrics["alpha"] == pytest.approx(
            (changes.mean() - beta * market_changes.mean()) * 252, abs=1e-12
        )
        years = (
            date.fromisoformat(result["end"]) - date.fromisoformat(result["start"])
        ).days / 365.25
        cagr = (curve[-1] / curve[0]) ** (1 / years) - 1
        assert metrics["cagr"] == pytest.approx(cagr)
        downside = np.sqrt(np.mean(np.minimum(changes, 0) ** 2))
        if downside > 1e-12:
            assert metrics["sortino"] == pytest.approx(
                changes.mean() / downside * np.sqrt(252)
            )
        else:
            assert metrics["sortino"] is None
        if metrics["max_drawdown"] < -1e-12:
            assert metrics["calmar"] == pytest.approx(
                cagr / abs(metrics["max_drawdown"])
            )
        else:
            assert metrics["calmar"] is None
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


@pytest.mark.parametrize(
    "mode", ["balanced", "volatility", "performance", "drawdown", "diversification"]
)
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


def test_alpha_beta_unavailable_for_flat_benchmark(client):
    http, days = client
    seed(days, "a", unit="EUR")
    with db.connect() as c:
        c.execute(
            "UPDATE reference_observations SET value=100 WHERE symbol=?", (INDEX,)
        )
        c.execute("UPDATE reference_observations SET value=1 WHERE symbol='EURUSD=X'")
    result = request(http, holdings=[{"asset_id": "a", "quantity": 1}])
    for metrics in result["metrics"].values():
        assert metrics["alpha"] is None
        assert metrics["beta"] is None


@pytest.mark.parametrize("beta", [-1.3, 0.0, 0.7, 2.4])
@pytest.mark.parametrize("periods", [12, 252])
def test_factor_regression_recovers_intercept_and_signed_beta(beta, periods):
    factor = np.array([-0.02, 0.01, 0.03, -0.01, 0.005])
    intercept = 0.0004
    alpha, slope = factor_regression(intercept + beta * factor, factor, periods)
    assert alpha == pytest.approx(intercept * periods)
    assert slope == pytest.approx(beta, abs=1e-12)
    assert factor_regression(factor, factor, periods) == pytest.approx((0, 1))
    assert factor_regression(factor, np.zeros(5), periods) == (None, None)


def test_diversification_uses_covariance_and_handles_a_zero_risk_seed():
    rng = np.random.default_rng(21)
    returns = rng.normal(0, [0.01, 0.03], (2000, 2))
    current = np.array([0.5, 0.5])
    weights = optimize_weights(returns, current, "diversification")
    inverse_volatility = 1 / returns.std(axis=0, ddof=1)
    expected = inverse_volatility / inverse_volatility.sum()
    assert weights == pytest.approx(expected, abs=1e-5)
    shifted = optimize_weights(returns + [0.005, -0.003], current, "diversification")
    assert shifted == pytest.approx(weights, abs=1e-7)
    with_cash = np.column_stack((np.zeros(2000), returns[:, 0]))
    weights = optimize_weights(with_cash, np.array([1.0, 0.0]), "diversification")
    assert np.all(np.isfinite(weights))
    assert weights.sum() == pytest.approx(1)


def test_removed_model_endpoints_are_unavailable(client):
    http, _ = client
    for suffix in ("regime", "analysis"):
        assert http.get(f"/api/assets/a/{suffix}").status_code == 404
        assert http.post(f"/api/assets/a/{suffix}", json={}).status_code == 404
    from investor.api import app

    assert not any(
        "regime" in path or "analysis" in path for path in app.openapi()["paths"]
    )
    with db.connect() as c:
        assert (
            c.execute(
                "SELECT name FROM sqlite_master WHERE name='analysis_runs'"
            ).fetchone()
            is None
        )


@pytest.mark.parametrize("history", ["common", "extended"])
@pytest.mark.parametrize(
    "mode", ["balanced", "volatility", "performance", "drawdown", "diversification"]
)
def test_dividends_reinvested_in_current_and_optimized_curves(client, history, mode):
    """Two cash distributions: compare against an independent share ledger.

    Raw prices fall on ex-dividend dates. Reinvesting the distribution buys
    more shares, while adjusted prices already include that reinvestment.
    The separate dividends table must never credit those payouts a second time.
    """
    http, days = client
    seed(days, "a")
    seed(days, "b")
    price, shares = 100.0, 1.0
    raw, wealth, dividends = [], [], []
    for i, day in enumerate(days):
        if i in (30, 70):
            payout = price * 0.1
            price -= payout
            dividends.append(("a", day, payout))
            shares += shares * payout / price
        elif i:
            price *= 1.001
        raw.append(price)
        wealth.append(shares * price)
    # Adj Close is scaled to the final raw close; its ratios track total return.
    adjusted = np.array(wealth) * raw[-1] / wealth[-1]
    with db.connect() as connection:
        connection.executemany(
            "UPDATE observations SET value=? WHERE asset_id='a' AND date=?",
            zip(adjusted, days),
        )
        connection.executemany(
            "UPDATE price_observations SET value=? WHERE asset_id='a' AND date=?",
            zip(raw, days),
        )
        connection.execute("UPDATE observations SET value=100 WHERE asset_id='b'")
        connection.executemany(
            "INSERT INTO dividends(asset_id,date,amount) VALUES (?,?,?)", dividends
        )
    base = request(http, history=history)
    optimized = request(http, True, mode=mode, history=history)
    # Current weights use actual share prices, not dividend-adjusted past prices.
    current = np.array([3 * raw[-1], 100.0])
    current /= current.sum()
    weights = np.array([p["recommended_weight"] for p in optimized["positions"]])
    reinvested = np.array(wealth[1:]) / wealth[:-1] - 1
    expected_current = np.r_[100.0, 100 * np.cumprod(1 + current[0] * reinvested)]
    expected_optimized = np.r_[100.0, 100 * np.cumprod(1 + weights[0] * reinvested)]
    assert [p["weight"] for p in base["positions"]] == pytest.approx(current)
    assert [p["portfolio"] for p in base["equity"]] == pytest.approx(expected_current)
    assert [p["portfolio"] for p in optimized["equity"]] == pytest.approx(
        expected_current
    )
    assert [p["optimized"] for p in optimized["equity"]] == pytest.approx(
        expected_optimized
    )
    for i in (30, 70):
        assert optimized["equity"][i]["portfolio"] == pytest.approx(
            optimized["equity"][i - 1]["portfolio"]
        )
    assert raw[-1] < raw[0]  # Price-only performance would wrongly report a loss.
    assert base["metrics"]["portfolio"]["total_return"] > 0
    if mode == "performance":
        assert weights == pytest.approx([1, 0], abs=1e-6)
