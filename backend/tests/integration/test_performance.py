"""Portfolio paths and allocation constraints against independent calculations."""

from datetime import date

import numpy as np
import pytest
from support import seed

from investor import db
from investor.assets.comparison import INDEX


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


def test_daily_alignment_fx_and_one_asset(client):
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


def test_alpha_beta_unavailable_for_flat_benchmark(client):
    http, days = client
    seed(days, "a", unit="EUR")
    with db.connect() as c:
        c.execute(
            "UPDATE reference_observations SET value=100 WHERE symbol=?", (INDEX,)
        )
        c.execute("UPDATE reference_observations SET value=1 WHERE symbol='EURUSD=X'")
    result = request(http, holdings=[{"asset_id": "a", "quantity": 1}])
    for key, metrics in result["metrics"].items():
        assert metrics["alpha"] is None
        assert metrics["beta"] == (1.0 if key == "benchmark" else None)


@pytest.mark.parametrize("history", ["common", "extended"])
@pytest.mark.parametrize(
    "mode", ["balanced", "volatility", "performance", "drawdown", "correlation"]
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
            zip(adjusted, days, strict=True),
        )
        connection.executemany(
            "UPDATE price_observations SET value=? WHERE asset_id='a' AND date=?",
            zip(raw, days, strict=True),
        )
        connection.executemany(
            "UPDATE observations SET value=? WHERE asset_id='b' AND date=?",
            [(100 * (1 + 0.00001 * np.sin(i)), day) for i, day in enumerate(days)],
        )
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
    b_prices = 100 * (1 + 0.00001 * np.sin(np.arange(len(days))))
    returns = np.column_stack((reinvested, b_prices[1:] / b_prices[:-1] - 1))
    expected_current = np.r_[100.0, 100 * np.cumprod(1 + returns @ current)]
    expected_optimized = np.r_[100.0, 100 * np.cumprod(1 + returns @ weights)]
    assert [p["weight"] for p in base["positions"]] == pytest.approx(current)
    assert [p["portfolio"] for p in base["equity"]] == pytest.approx(expected_current)
    assert [p["portfolio"] for p in optimized["equity"]] == pytest.approx(
        expected_current
    )
    assert [p["optimized"] for p in optimized["equity"]] == pytest.approx(
        expected_optimized
    )
    for i in (30, 70):
        assert (
            abs(
                optimized["equity"][i]["portfolio"]
                / optimized["equity"][i - 1]["portfolio"]
                - 1
            )
            < 1e-4
        )
    assert raw[-1] < raw[0]  # Price-only performance would wrongly report a loss.
    assert base["metrics"]["portfolio"]["total_return"] > 0
    if mode == "performance":
        assert weights == pytest.approx([1, 0], abs=1e-6)


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize("history", ["common", "extended"])
def test_monthly_asset_never_downsamples_the_daily_portfolio(client, optimize, history):
    http, days = client
    seed(days, "a")
    seed(days, "b", frequency="monthly", category="commodity")
    result = request(http, optimize, history=history)
    assert result["status"] == "insufficient"
    assert "cours journaliers" in result["message"]
    assert result["excluded"] == [
        {"id": "b", "name": "b", "reason": "Historique journalier indisponible."}
    ]
    assert "equity" not in result


@pytest.mark.parametrize(
    "mode", ["balanced", "volatility", "performance", "drawdown", "correlation"]
)
def test_daily_curves_preserve_intramonth_drawdown_and_last_session(client, mode):
    http, days = client
    seed(days, "a")
    prices = np.full(len(days), 100.0)
    # A sharp, fully recovered loss inside one month disappears in month-end data.
    trough = next(i for i in range(10, len(days) - 1) if days[i][8:10] == "15")
    prices[trough] = 50
    prices[-1] = 110
    with db.connect() as connection:
        connection.executemany(
            "UPDATE observations SET value=? WHERE asset_id='a' AND date=?",
            zip(prices, days, strict=True),
        )
    holdings = [{"asset_id": "a", "quantity": 1}]
    base = request(http, holdings=holdings)
    result = request(http, True, holdings=holdings, mode=mode)
    assert result["frequency"] == "daily"
    assert result["observations"] == len(days) - 1
    assert [p["time"] for p in result["equity"]] == days
    changes = prices[1:] / prices[:-1] - 1
    for key in ("portfolio", "optimized"):
        assert [p[key] for p in result["equity"]] == pytest.approx(prices)
        assert result["metrics"][key]["max_drawdown"] == pytest.approx(-0.5)
        assert result["metrics"][key]["volatility"] == pytest.approx(
            changes.std(ddof=1) * np.sqrt(252)
        )
    assert base["equity"] == [
        {k: v for k, v in p.items() if k != "optimized"} for p in result["equity"]
    ]


@pytest.mark.parametrize(
    "mode", ["balanced", "volatility", "performance", "drawdown", "correlation"]
)
def test_api_retains_exact_locked_quantity(client, mode):
    http, days = client
    seed(days, "a")
    seed(days, "b", sign=-1)
    result = http.post(
        "/api/portfolio/optimize",
        json={
            "holdings": [
                {"asset_id": "a", "quantity": 3},
                {"asset_id": "b", "quantity": 1},
            ],
            "locked_asset_ids": ["a"],
            "mode": mode,
        },
    )
    assert result.status_code == 200, result.text
    positions = result.json()["positions"]
    assert positions[0]["recommended_quantity"] == 3
    assert positions[0]["recommended_weight"] == pytest.approx(0.75)
