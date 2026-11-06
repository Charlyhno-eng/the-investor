import pytest
from fastapi.testclient import TestClient
from investor import db, market
from investor.api import app


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    return TestClient(app)


def test_queue_deduplication_completed_import_and_offline_consultation(
    local, monkeypatch
):
    calls = []

    def load(symbol, category):
        calls.append(symbol)
        db.save(
            [
                (
                    "yf-aapl",
                    "Apple",
                    "stock",
                    "price",
                    "USD",
                    "daily",
                    "yahoo",
                    "https://example.com",
                )
            ],
            [("yf-aapl", "2020-01-01", 100)],
            "yahoo:AAPL",
        )
        return "yf-aapl"

    monkeypatch.setattr(market, "import_symbol", load)
    first = local.post(
        "/api/asset-imports", json={"symbol": "aapl", "category": "stock"}
    )
    assert first.status_code == 202
    job = first.json()
    assert job["status"] == "queued" and not calls
    assert (
        local.post(
            "/api/asset-imports", json={"symbol": "AAPL", "category": "stock"}
        ).json()["id"]
        == job["id"]
    )
    assert market.process_one()
    assert calls == ["AAPL"]
    assert local.get(f"/api/asset-imports/{job['id']}").json()["status"] == "completed"
    assert local.get("/api/assets/yf-aapl/history").json()[0]["value"] == 100
    assert (
        local.post(
            "/api/asset-imports", json={"symbol": "AAPL", "category": "stock"}
        ).json()["asset_id"]
        == "yf-aapl"
    )
    assert not market.process_one()


def test_failed_import_retry_and_symbol_validation(local, monkeypatch):
    def fail(*args):
        raise RuntimeError("Provider unavailable")

    monkeypatch.setattr(market, "import_symbol", fail)
    job = local.post("/api/asset-imports", json={"symbol": "INVALID"}).json()
    market.process_one()
    result = local.get(f"/api/asset-imports/{job['id']}").json()
    assert result["status"] == "failed" and result["error"]
    retried = local.post("/api/asset-imports", json={"symbol": "INVALID"}).json()
    assert retried["id"] != job["id"]
    assert (
        local.post("/api/asset-imports", json={"symbol": "../../tmp"}).status_code
        == 422
    )
    assert (
        local.post(
            "/api/asset-imports", json={"symbol": "AAPL", "category": "crypto"}
        ).status_code
        == 422
    )
    assert local.get("/api/asset-imports/9999").status_code == 404


def test_yahoo_type_validation_and_archiving(local, monkeypatch):
    from types import SimpleNamespace

    import pandas as pd

    frame = pd.DataFrame(
        {"Close": [100, 101], "Adj Close": [80, 81], "Dividends": [0, 0.25]},
        index=pd.to_datetime(["2020-01-01", "2020-01-02"]),
    )
    ticker = SimpleNamespace(
        get_info=lambda: {"country": "France"},
        history=lambda **kwargs: frame,
        get_history_metadata=lambda: {
            "instrumentType": "EQUITY",
            "currency": "EUR",
            "longName": "Example",
        },
    )
    monkeypatch.setattr(market.yf, "Ticker", lambda symbol: ticker)
    assert market.import_symbol("EX.PA", "stock") == "yf-ex.pa"
    assert local.get("/api/assets").json()[0]["unit"] == "EUR"
    assert local.get("/api/assets").json()[0]["country"] == "France"
    ticker.get_info = dict
    market.update_country(ticker, "yf-ex.pa")
    assert local.get("/api/assets").json()[0]["country"] == "France"
    assert len(list((db.DATA_DIR / "raw").glob("*.csv"))) == 1
    assert len(list((db.DATA_DIR / "raw").glob("*.json"))) == 1
    with pytest.raises(ValueError, match="Cryptomonnaie absente"):
        market.import_symbol("EX.PA", "crypto")
    assert len(local.get("/api/assets").json()) == 1
    result = local.get("/api/assets/yf-ex.pa/dividends").json()
    assert result["events"] == [
        {"time": "2020-01-02", "amount": 0.25, "yield_percent": 0.25}
    ]
    assert local.get("/api/assets/yf-ex.pa/history").json()[0]["value"] == 80
    assert result["coverage"]["first_date"] == "2020-01-01"
    # Provider correction replaces the window, including deletion of an old event.
    frame["Dividends"] = [0.5, 0]
    market.import_symbol("EX.PA", "stock")
    assert local.get("/api/assets/yf-ex.pa/dividends").json()["events"] == [
        {"time": "2020-01-01", "amount": 0.5, "yield_percent": None}
    ]
    frame["Dividends"] = [float("nan"), 0]
    with pytest.raises(ValueError, match="Dividende invalide"):
        market.import_symbol("EX.PA", "stock")
    assert (
        local.get("/api/assets/yf-ex.pa/dividends").json()["events"][0]["amount"] == 0.5
    )
    assert local.get("/api/assets/missing/dividends").status_code == 404


def test_removed_crypto_are_hidden_and_cannot_be_reimported(local):
    from investor.market_catalog import CRYPTO

    for symbol in ("ADA-USD", "XRP-USD", "BTC-USD"):
        asset_id = "yf-" + symbol.lower()
        db.save(
            [
                (
                    asset_id,
                    symbol,
                    "crypto",
                    "price",
                    "USD",
                    "daily",
                    "yahoo",
                    "https://example.com",
                )
            ],
            [(asset_id, "2025-01-01", 100)],
            "test:" + symbol,
        )
    assert [a["id"] for a in local.get("/api/assets").json()] == ["yf-btc-usd"]
    for symbol in ("ADA-USD", "XRP-USD"):
        assert symbol not in CRYPTO
        assert (
            local.post(
                "/api/asset-imports", json={"symbol": symbol, "category": "crypto"}
            ).status_code
            == 422
        )
        with pytest.raises(ValueError, match="absente du catalogue"):
            market.import_symbol(symbol, "crypto")
    # Removal from the catalogue does not erase archived price histories.
    assert local.get("/api/assets/yf-ada-usd/history").json()[0]["value"] == 100


def test_dividends_distinguish_pending_from_known_zero(local):
    asset = (
        "stock",
        "Stock",
        "stock",
        "price",
        "USD",
        "daily",
        "test",
        "https://example.com",
    )
    db.save([asset], [("stock", "2025-01-01", 100)], "test")
    assert local.get("/api/assets/stock/dividends").json()["coverage"] is None
    db.save(
        [asset],
        [("stock", "2025-01-01", 100)],
        "test",
        dividends=[],
        dividend_coverage=("stock", "2025-01-01", "2025-01-01"),
    )
    result = local.get("/api/assets/stock/dividends").json()
    assert result["events"] == []
    assert result["coverage"]["last_date"] == "2025-01-01"


def test_stock_search_names_filtering_cache_and_local_fallback(local, monkeypatch):
    from types import SimpleNamespace

    from investor import stock_search

    stock_search._cache.clear()
    calls = []

    def search(query, **kwargs):
        calls.append(query)
        return SimpleNamespace(
            quotes=[
                {
                    "symbol": "AAPL",
                    "longname": "Apple Inc.",
                    "quoteType": "EQUITY",
                    "exchDisp": "NASDAQ",
                },
                {"symbol": "SPY", "quoteType": "ETF"},
                {"symbol": "BAD/URL", "quoteType": "EQUITY"},
            ]
        )

    monkeypatch.setattr(stock_search.yf, "Search", search)
    result = local.get("/api/stocks/search", params={"q": "Apple"}).json()
    assert result["results"] == [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "imported": False,
        }
    ]
    local.get("/api/stocks/search", params={"q": "apple"})
    assert calls == ["Apple"]
    assert local.get("/api/stocks/search", params={"q": " "}).status_code == 422
    db.save(
        [
            (
                "yf-aapl",
                "Apple",
                "stock",
                "price",
                "USD",
                "daily",
                "yahoo",
                "https://example.com",
            )
        ],
        [("yf-aapl", "2020-01-01", 100)],
        "test",
    )
    assert local.get("/api/stocks/search", params={"q": "Apple"}).json()["results"][0][
        "imported"
    ]

    def fail(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(stock_search.yf, "Search", fail)
    stock_search._cache.clear()
    fallback = local.get("/api/stocks/search", params={"q": "Apple"}).json()
    assert fallback["warning"] and fallback["results"][0]["imported"]
    assert local.get("/api/stocks/search", params={"q": "Unknown"}).status_code == 503


def test_api_consumes_import_queue_without_bulk_worker(local, monkeypatch):
    from threading import Event

    imported = Event()

    def load(symbol, category):
        imported.set()
        return "yf-test"

    monkeypatch.setattr(market, "import_symbol", load)
    with TestClient(app) as client:
        job = client.post("/api/asset-imports", json={"symbol": "TEST"}).json()
        assert imported.wait(3), "API should process the queued import automatically"
    assert local.get(f"/api/asset-imports/{job['id']}").json()["status"] == "completed"


def test_abandoned_import_recovers_without_resetting_active_download(
    local, monkeypatch
):
    active = local.post("/api/asset-imports", json={"symbol": "ACTIVE"}).json()
    stale = local.post("/api/asset-imports", json={"symbol": "STALE"}).json()
    with db.connect() as connection:
        connection.execute("UPDATE import_jobs SET status='running'")
        connection.execute(
            "UPDATE import_jobs SET updated_at='2000-01-01T00:00:00Z' WHERE id=?",
            (stale["id"],),
        )
    calls = []

    def load(symbol, category):
        calls.append(symbol)
        return "yf-stale"

    monkeypatch.setattr(market, "import_symbol", load)
    assert market.process_one()
    assert calls == ["STALE"]
    assert not market.process_one()
    assert local.get(f"/api/asset-imports/{active['id']}").json()["status"] == "running"
