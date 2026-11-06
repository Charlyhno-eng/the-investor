import pytest
from fastapi.testclient import TestClient
from investor import db, market
from investor.api import app
from investor.comparison import INDEX


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

    monkeypatch.setattr("investor.comparison.import_reference", load)
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
