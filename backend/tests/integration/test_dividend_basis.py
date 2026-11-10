"""Price charts and total return use distinct provider columns, exactly once."""

from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from investor import db
from investor.api import app
from investor.imports import service


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    return TestClient(app)


@pytest.mark.parametrize("category,kind", [("stock", "EQUITY"), ("etf", "ETF")])
def test_provider_to_chart_and_comparison(local, monkeypatch, category, kind):
    # A 10 cash distribution reduces Close from 100 to 90. Adj Close already
    # neutralizes that distribution; adding the cash again would invent a gain.
    frame = pd.DataFrame(
        {"Close": [100, 90, 99], "Adj Close": [90, 90, 99], "Dividends": [0, 10, 0]},
        index=pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"]),
    )

    def history(**kwargs):
        assert kwargs["auto_adjust"] is False
        assert kwargs["actions"] is True
        return frame

    monkeypatch.setattr(
        service.yf,
        "Ticker",
        lambda _: SimpleNamespace(
            history=history,
            get_info=dict,
            get_history_metadata=lambda: {"instrumentType": kind, "currency": "USD"},
        ),
    )
    service.import_symbol("TEST", category)
    with db.connect() as connection:
        for symbol in ("^GSPC", "^SP500TR"):
            connection.executemany(
                "INSERT INTO reference_observations VALUES (?,?,?)",
                [(symbol, day.date().isoformat(), 100) for day in frame.index],
            )
            connection.execute(
                "INSERT INTO reference_imports VALUES (?,strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
                (symbol,),
            )
    for reinvest, expected in [(False, [100, 90, 99]), (True, [90, 90, 99])]:
        query = f"reinvest={str(reinvest).lower()}"
        chart = local.get(f"/api/assets/yf-test/history?{query}")
        assert chart.status_code == 200
        assert [p["value"] for p in chart.json()] == expected
        result = local.get(f"/api/assets/yf-test/comparison?{query}").json()
        assert result["asset_return"] == pytest.approx(expected[-1] / expected[0] - 1)
        assert result["dividends_reinvested"] is reinvest
        partial = local.get(
            f"/api/assets/yf-test/history?{query}&start=2020-01-03&end=2020-01-03"
        ).json()
        assert partial == [{"time": "2020-01-03", "value": expected[1]}]
    # Historical analytics keep their adjusted API default.
    assert local.get("/api/assets/yf-test/history").json()[0]["value"] == 90
    frame.drop(columns="Adj Close", inplace=True)
    with pytest.raises(ValueError, match="Clôtures ajustées absentes"):
        service.import_symbol("TEST", category)
    assert local.get("/api/assets/yf-test/history").json()[0]["value"] == 90


def test_missing_price_history_never_falls_back_to_adjusted(local):
    db.save(
        [
            (
                "yf-old",
                "Old",
                "stock",
                "price",
                "USD",
                "daily",
                "yahoo",
                "https://example.com",
            )
        ],
        [("yf-old", "2020-01-02", 90)],
        "test",
    )
    for _ in range(2):
        response = local.get("/api/assets/yf-old/history?reinvest=false")
        assert response.status_code == 503
        assert "hors dividendes" in response.json()["detail"]
    with db.connect() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM import_jobs WHERE symbol='OLD' AND status='queued'"
            ).fetchone()[0]
            == 1
        )
    assert local.get("/api/assets/yf-old/history?reinvest=true").json() == [
        {"time": "2020-01-02", "value": 90}
    ]
