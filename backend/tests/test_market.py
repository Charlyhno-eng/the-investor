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
        {"Close": [100, 101]}, index=pd.to_datetime(["2020-01-01", "2020-01-02"])
    )
    ticker = SimpleNamespace(
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
    assert len(list((db.DATA_DIR / "raw").glob("*.csv"))) == 1
    assert len(list((db.DATA_DIR / "raw").glob("*.json"))) == 1
    with pytest.raises(ValueError, match="catégorie incompatible"):
        market.import_symbol("EX.PA", "crypto")
    assert len(local.get("/api/assets").json()) == 1
