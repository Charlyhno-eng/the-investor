"""User dividend classification persists independently of imported events."""

import pytest
from fastapi.testclient import TestClient
from investor import db
from investor.api import app


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    db.save(
        [
            (id_, id_, category, "price", "USD", "daily", "test", "https://example.com")
            for id_, category in (
                ("yf-test", "stock"),
                ("yf-other", "stock"),
                ("yf-btc-usd", "crypto"),
            )
        ],
        [(id_, "2024-01-01", 100) for id_ in ("yf-test", "yf-other", "yf-btc-usd")],
        "test",
    )
    return TestClient(app)


def test_dividend_flag_is_durable_reversible_and_survives_refresh_import(local):
    path = "/api/assets/yf-test/dividend-status"
    assert all(not r["is_dividend"] for r in local.get("/api/assets").json())
    assert local.patch(path, json={"is_dividend": True}).json() == {
        "id": "yf-test",
        "is_dividend": True,
    }
    # Reimporting quotes must preserve the user's classification.
    db.save(
        [
            (
                "yf-test",
                "Renamed",
                "stock",
                "price",
                "USD",
                "daily",
                "test",
                "https://example.com",
            )
        ],
        [("yf-test", "2024-01-02", 110)],
        "test",
    )
    fresh_client = TestClient(app)
    flagged = [r for r in fresh_client.get("/api/assets").json() if r["is_dividend"]]
    assert [r["id"] for r in flagged] == ["yf-test"]
    assert fresh_client.get("/api/assets/yf-test/dividends").json()["events"] == []
    assert fresh_client.patch(path, json={"is_dividend": False}).status_code == 200
    assert not any(r["is_dividend"] for r in local.get("/api/assets").json())


def test_dividend_flag_rejects_missing_non_stock_and_invalid_payloads(local):
    assert (
        local.patch(
            "/api/assets/missing/dividend-status", json={"is_dividend": True}
        ).status_code
        == 404
    )
    assert (
        local.patch(
            "/api/assets/yf-btc-usd/dividend-status", json={"is_dividend": True}
        ).status_code
        == 422
    )
    for payload in (
        {},
        {"is_dividend": "false"},
        {"is_dividend": 1},
        {"is_dividend": True, "other": True},
    ):
        assert (
            local.patch("/api/assets/yf-test/dividend-status", json=payload).status_code
            == 422
        )
