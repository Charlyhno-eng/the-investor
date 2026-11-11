import pytest
from fastapi.testclient import TestClient

from investor import db
from investor.api import app
from investor.assets.comparison import INDEX
from investor.imports import service as market


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    return TestClient(app)


def seed(currency="USD", category="stock"):
    db.save(
        [
            (
                "test",
                "Test",
                category,
                "yield" if category == "bond" else "price",
                currency,
                "daily",
                "test",
                "https://example.com",
            )
        ],
        [
            ("test", "2020-01-02", 100),
            ("test", "2020-01-03", 100),
            ("test", "2020-01-04", 110),
            ("test", "2020-01-06", 120),
        ],
        "test",
    )


def reference(symbol, values):
    with db.connect() as connection:
        connection.executemany(
            "INSERT INTO reference_observations VALUES (?,?,?)",
            [(symbol, day, value) for day, value in values],
        )
        connection.execute(
            "INSERT INTO reference_imports VALUES (?,strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
            (symbol,),
        )


def test_total_return_uses_adjusted_prices_once_and_common_dates(local):
    seed()
    # An ex-dividend raw price drop is already corrected in adjusted observations.
    # These dividends must never be added to adjusted prices a second time.
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO dividends(asset_id,date,amount) VALUES ('test','2020-01-03',10)"
        )
    reference(INDEX, [("2020-01-02", 1000), ("2020-01-03", 1100), ("2020-01-06", 1200)])
    response = local.get("/api/assets/test/comparison?start=2020-01-02&end=2020-01-03")
    assert response.status_code == 200
    result = response.json()
    assert result["asset_return"] == 0
    assert result["index_return"] == pytest.approx(0.1)
    assert result["dividends_reinvested"]
    assert result["equity"][0] == {
        "time": "2020-01-02",
        "strategy": 100,
        "benchmark": 100,
    }
    result = local.get("/api/assets/test/comparison").json()
    assert [p["time"] for p in result["equity"]] == [
        "2020-01-02",
        "2020-01-03",
        "2020-01-06",
    ]
    assert result["asset_return"] == pytest.approx(0.2)


def test_fx_conversion_at_each_date(local):
    seed("EUR")
    reference(INDEX, [("2020-01-02", 1000), ("2020-01-03", 1100)])
    reference("EURUSD=X", [("2020-01-02", 1.1), ("2020-01-03", 1.2)])
    result = local.get("/api/assets/test/comparison").json()
    assert result["converted"]
    assert result["asset_return"] == pytest.approx(1.2 / 1.1 - 1)
    assert result["equity"][-1]["strategy"] == pytest.approx(100 * 1.2 / 1.1)


def test_missing_reference_is_queued_and_worker_imports_it(local, monkeypatch):
    seed()
    assert local.get("/api/assets/test/comparison").json() == {"status": "pending"}
    assert local.get("/api/assets/test/comparison").json() == {"status": "pending"}
    with db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM import_jobs").fetchone()[0] == 1

    def load(symbol):
        assert symbol == INDEX
        reference(symbol, [("2020-01-02", 1000), ("2020-01-03", 1100)])

    monkeypatch.setattr("investor.assets.comparison.import_reference", load)
    assert market.process_one()
    assert local.get("/api/assets/test/comparison").json()["status"] == "ready"
    assert len(local.get("/api/assets").json()) == 1


def test_invalid_ranges_bonds_and_missing_history(local):
    assert local.get("/api/assets/missing/comparison").status_code == 404
    seed(category="bond")
    assert local.get("/api/assets/test/comparison").status_code == 422
    assert (
        local.get(
            "/api/assets/test/comparison?start=2022-01-01&end=2020-01-01"
        ).status_code
        == 422
    )
    with db.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM import_jobs").fetchone()[0] == 0


def test_insufficient_common_dates_and_negative_prices(local):
    seed()
    reference(INDEX, [("2020-01-02", 1000), ("2020-01-03", 1100)])
    assert local.get("/api/assets/test/comparison?start=2020-01-04").status_code == 422
    with db.connect() as connection:
        connection.execute("UPDATE observations SET value=-1 WHERE date='2020-01-02'")
    assert local.get("/api/assets/test/comparison").status_code == 422


def test_price_and_reinvested_modes_are_distinct(local):
    seed()
    reference(INDEX, [("2020-01-02", 1000), ("2020-01-03", 1100)])
    reference("^GSPC", [("2020-01-02", 1000), ("2020-01-03", 950)])
    with db.connect() as connection:
        connection.executemany(
            "INSERT INTO price_observations VALUES (?,?,?)",
            [("test", "2020-01-02", 100), ("test", "2020-01-03", 90)],
        )
    prices = local.get(
        "/api/assets/test/comparison?reinvest=false&end=2020-01-03"
    ).json()
    reinvested = local.get(
        "/api/assets/test/comparison?reinvest=true&end=2020-01-03"
    ).json()
    assert prices["asset_return"] == pytest.approx(-0.1)
    assert prices["index_return"] == pytest.approx(-0.05)
    assert not prices["dividends_reinvested"]
    assert reinvested["asset_return"] == 0
    assert reinvested["index_return"] == pytest.approx(0.1)


@pytest.mark.parametrize("category", ["stock", "crypto", "etf", "commodity"])
def test_comparison_metrics_use_the_same_selected_dates_and_currency(local, category):
    import numpy as np

    seed("EUR" if category in ("stock", "etf") else "USD", category)
    days = ["2020-01-02", "2020-01-03", "2020-01-06"]
    reference(INDEX, list(zip(days, [1000, 900, 990], strict=True)))
    if category in ("stock", "etf"):
        reference("EURUSD=X", list(zip(days, [1.1, 1.2, 1.15], strict=True)))
    response = local.get("/api/assets/test/comparison?start=2020-01-02&end=2020-01-06")
    assert response.status_code == 200
    result = response.json()
    assert result["annualization"] == 252
    assert result["observations"] == 2
    # Independent formulas applied to the displayed base-100 curve, including FX.
    prices = np.array([point["strategy"] for point in result["equity"]])
    changes = prices[1:] / prices[:-1] - 1
    market = np.array([-0.1, 0.1])
    mean = float(sum(changes) / 2)
    deviation = float(np.sqrt(sum((changes - mean) ** 2)))
    downside = float(np.sqrt(sum(min(r, 0) ** 2 for r in changes) / 2))
    cagr = float((prices[-1] / prices[0]) ** (365.25 / 4) - 1)
    drawdown = min(prices / np.maximum.accumulate(prices) - 1)
    metrics = result["metrics"]["portfolio"]
    assert metrics["cagr"] == pytest.approx(cagr)
    assert metrics["volatility"] == pytest.approx(deviation * np.sqrt(252))
    assert metrics["downside_volatility"] == pytest.approx(downside * np.sqrt(252))
    assert metrics["max_drawdown"] == pytest.approx(drawdown)
    assert metrics["sharpe"] == pytest.approx(mean / deviation * np.sqrt(252))
    assert metrics["sortino"] == (
        pytest.approx(mean / downside * np.sqrt(252)) if downside else None
    )
    assert metrics["calmar"] == (
        pytest.approx(cagr / abs(drawdown)) if drawdown else None
    )
    assert metrics["beta"] == pytest.approx(
        sum((changes - mean) * (market - market.mean()))
        / sum((market - market.mean()) ** 2)
    )
    assert result["metrics"]["benchmark"]["beta"] == 1
    # Changing the period also changes the metric sample, never the whole history.
    short = local.get("/api/assets/test/comparison?end=2020-01-03").json()
    assert short["observations"] == 1
    assert short["metrics"]["portfolio"]["volatility"] is None
    assert short["metrics"]["portfolio"]["sharpe"] is None
    assert short["metrics"]["portfolio"]["beta"] is None
    assert short["metrics"]["portfolio"]["cagr"] != metrics["cagr"]


def test_constant_comparison_has_no_undefined_ratios_in_json(local):
    seed()
    with db.connect() as connection:
        connection.execute("UPDATE observations SET value=100")
    reference(INDEX, [("2020-01-02", 1000), ("2020-01-03", 1000), ("2020-01-06", 1000)])
    result = local.get("/api/assets/test/comparison").json()
    for metrics in result["metrics"].values():
        assert metrics["cagr"] == 0
        assert metrics["volatility"] == 0
        assert metrics["downside_volatility"] == 0
        assert metrics["max_drawdown"] == 0
        assert metrics["sharpe"] is None
        assert metrics["sortino"] is None
        assert metrics["calmar"] is None


def test_monthly_commodity_metrics_use_twelve_observations_per_year(local):
    import math

    seed(category="commodity")
    days = ["2020-01-02", "2020-02-03", "2020-03-02"]
    with db.connect() as connection:
        connection.execute("UPDATE assets SET frequency='monthly'")
        connection.execute("DELETE FROM observations")
        connection.executemany(
            "INSERT INTO observations VALUES ('test',?,?)",
            list(zip(days, [100, 110, 99], strict=True)),
        )
    reference(INDEX, list(zip(days, [1000, 1050, 997.5], strict=True)))
    result = local.get("/api/assets/test/comparison").json()
    assert result["frequency"] == "monthly"
    assert result["annualization"] == 12
    assert result["metrics"]["portfolio"]["volatility"] == pytest.approx(
        math.sqrt(0.02) * math.sqrt(12)
    )
    assert result["metrics"]["portfolio"]["max_drawdown"] == pytest.approx(-0.1)
    assert result["metrics"]["portfolio"]["beta"] == pytest.approx(2)
