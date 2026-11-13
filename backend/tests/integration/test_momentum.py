"""Momentum API: shared universe, native currency, and missing data."""

import math
from datetime import date, timedelta

import pytest
from support import seed

from investor import db
from investor.assets.comparison import INDEX


def setup_history():
    end = date(2026, 11, 9)
    days = [(end - timedelta(days=1200 - i)).isoformat() for i in range(1201)]
    for identifier, category, unit in [
        ("airbus", "stock", "EUR"),
        ("peer", "stock", "EUR"),
        ("us", "stock", "USD"),
        ("taiwan", "stock", "TWD"),
        ("europe", "etf", "EUR"),
        ("short", "stock", "EUR"),
    ]:
        seed(
            days[-100:] if identifier == "short" else days,
            identifier,
            category,
            unit=unit,
        )
    with db.connect() as c:
        c.execute(
            "UPDATE observations SET value=100 * exp((julianday(date)-julianday('2024-08-31')) * 0.001) WHERE asset_id IN ('airbus','peer','us','taiwan')"
        )
        for symbol in [INDEX, "^FCHI", "EURUSD=X"]:
            c.executemany(
                "INSERT OR REPLACE INTO reference_observations VALUES (?,?,?)",
                [
                    (
                        symbol,
                        d,
                        100 * math.exp(i * 0.0003)
                        if symbol != "EURUSD=X"
                        else math.exp(i * 0.0001),
                    )
                    for i, d in enumerate(days)
                ],
            )
        c.execute(
            "INSERT OR REPLACE INTO reference_imports VALUES ('^FCHI',strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
        )
    return days


def test_all_currencies_use_native_returns_and_common_benchmark(client):
    api, _ = client
    setup_history()
    response = api.get("/api/assets/airbus/momentum")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["as_of"] == "2026-11-09"
    assert {s["id"] for s in data["universe"]} == {
        "airbus",
        "peer",
        "short",
        "us",
        "taiwan",
    }
    assert next(s for s in data["universe"] if s["id"] == "short")["scores"] is None
    assert [h["months"] for h in data["horizons"]] == [36, 12, 6]
    assert data["horizons"][0]["start"] == "2023-11-09"
    h = data["horizons"][1]
    duration = (date.fromisoformat(h["end"]) - date.fromisoformat(h["start"])).days
    assert h["relative_performance"] == pytest.approx(math.expm1(duration * 0.0007))
    scores = [s["scores"] for s in data["universe"] if s["scores"] is not None]
    assert len(scores) == 4
    assert all(score == pytest.approx(scores[0]) for score in scores)
    batch = api.get("/api/momentum").json()
    assert batch["universe"] == data["universe"]
    assert batch["as_of"] == data["as_of"]
    cac = api.get("/api/assets/taiwan/momentum?benchmark=%5EFCHI").json()
    assert cac["benchmark_name"] == "CAC 40 · hors dividendes"
    assert cac["universe"] == data["universe"]
    assert data["recent_return"] > 0
    assert data["drawdown"] == 0
    etf = api.get("/api/assets/airbus/momentum?benchmark=europe").json()
    assert etf["benchmark_name"] == "europe"
    assert api.get("/api/assets/airbus/momentum?benchmark=us").status_code == 422
    assert api.get("/api/assets/europe/momentum").status_code == 200
    assert api.get("/api/assets/missing/momentum").status_code == 404


def test_pending_reference_and_local_etf_fallback(client):
    api, _ = client
    setup_history()
    with db.connect() as c:
        c.execute("DELETE FROM reference_imports")
        c.execute("DELETE FROM reference_observations WHERE symbol=?", (INDEX,))
    data = api.get("/api/assets/airbus/momentum").json()
    assert data["status"] == "pending"
    # A local reference works without waiting for the S&P 500 worker.
    assert (
        api.get("/api/assets/airbus/momentum?benchmark=europe").json()["status"]
        == "ready"
    )


@pytest.mark.parametrize("asset_id,category", [("airbus", "stock"), ("europe", "etf")])
@pytest.mark.parametrize("symbol", [INDEX, "^FCHI"])
@pytest.mark.parametrize("job_status", ["queued", "running", "failed"])
def test_cached_momentum_remains_available_during_reference_refresh(
    client, asset_id, category, symbol, job_status
):
    api, _ = client
    setup_history()
    path = f"/api/assets/{asset_id}/momentum"
    expected = api.get(path, params={"benchmark": symbol}).json()
    with db.connect() as c:
        c.execute(
            "UPDATE reference_imports SET updated_at='2000-01-01T00:00:00Z' WHERE symbol=?",
            (symbol,),
        )
        c.execute(
            "INSERT INTO import_jobs(symbol,category,status) VALUES (?,'reference',?)",
            (symbol, job_status),
        )
    response = api.get(path, params={"benchmark": symbol})
    assert response.status_code == 200
    assert response.json() == expected
    batch = api.get("/api/momentum", params={"category": category, "benchmark": symbol})
    assert batch.status_code == 200
    assert batch.json()["status"] == "ready"
    assert batch.json()["universe"] == expected["universe"]
    with db.connect() as c:
        assert (
            c.execute(
                "SELECT COUNT(*) FROM import_jobs WHERE symbol=?", (symbol,)
            ).fetchone()[0]
            == 1
        )


def test_cached_momentum_queues_refresh_and_still_checks_reference_dates(client):
    api, _ = client
    setup_history()
    with db.connect() as c:
        c.execute("DELETE FROM reference_imports WHERE symbol=?", (INDEX,))
    data = api.get("/api/assets/airbus/momentum").json()
    assert data["status"] == "ready"
    assert all("score" in h for h in data["horizons"])
    with db.connect() as c:
        assert c.execute("SELECT symbol,status FROM import_jobs").fetchall()[0][:] == (
            INDEX,
            "queued",
        )
        # Cached does not mean usable: old endpoints must never invent a score.
        c.execute(
            "DELETE FROM reference_observations WHERE symbol=? AND date > '2026-09-01'",
            (INDEX,),
        )
    old = api.get("/api/assets/airbus/momentum").json()
    assert old["status"] == "ready"
    assert all("error" in h for h in old["horizons"])
    assert all(s["scores"] is None for s in old["universe"])


def test_stale_stock_not_ranked(client):
    api, _ = client
    setup_history()
    with db.connect() as c:
        c.execute(
            "DELETE FROM observations WHERE asset_id='peer' AND date > '2026-10-30'"
        )
    data = api.get("/api/assets/airbus/momentum").json()
    assert next(s for s in data["universe"] if s["id"] == "peer")["scores"] is None


def test_other_currency_etf_can_be_selected_without_fx_data(client):
    api, _ = client
    setup_history()
    seed(
        [(date(2024, 8, 31) + timedelta(days=i)).isoformat() for i in range(1201)],
        "usd-etf",
        "etf",
        unit="USD",
    )
    with db.connect() as c:
        c.execute("DELETE FROM reference_imports")
        c.execute("DELETE FROM reference_observations")
    response = api.get("/api/assets/taiwan/momentum?benchmark=usd-etf")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert len(response.json()["universe"]) == 5


def test_crypto_uses_separate_universe_daily_dates_and_local_bitcoin(client):
    api, _ = client
    days = setup_history()
    for identifier in ("yf-btc-usd", "yf-eth-usd"):
        seed(days, identifier, "crypto")
    with db.connect() as c:
        c.execute("UPDATE assets SET name='Bitcoin' WHERE id='yf-btc-usd'")
        c.execute(
            "UPDATE observations SET value=100 * exp((julianday(date)-julianday('2024-08-31')) * 0.001) WHERE asset_id='yf-btc-usd'"
        )
        c.execute(
            "UPDATE observations SET value=100 * exp((julianday(date)-julianday('2024-08-31')) * 0.002) WHERE asset_id='yf-eth-usd'"
        )
        c.execute("DELETE FROM reference_imports")
        # Stock dates must not shift the crypto analysis date.
        c.execute("INSERT INTO observations VALUES ('airbus','2026-11-10',100)")
    response = api.get("/api/assets/yf-eth-usd/momentum")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["category"] == "crypto"
    assert data["as_of"] == "2026-11-09"
    assert data["benchmark_name"] == "Bitcoin"
    assert {s["id"] for s in data["universe"]} == {"yf-btc-usd", "yf-eth-usd"}
    assert all(s["scores"] is not None for s in data["universe"])
    horizon = data["horizons"][1]
    assert horizon["end"] == "2026-10-09"
    assert horizon["observations"] == 335
    assert any(
        date.fromisoformat(row["time"]).weekday() == 6 for row in horizon["rows"]
    )
    assert (
        api.get("/api/momentum?category=crypto").json()["universe"] == data["universe"]
    )
    own = api.get("/api/assets/yf-btc-usd/momentum").json()
    assert all(h["relative_performance"] == pytest.approx(0) for h in own["horizons"])
    alternate = api.get("/api/assets/yf-btc-usd/momentum?benchmark=yf-eth-usd").json()
    assert all(h["relative_performance"] < 0 for h in alternate["horizons"])
    with db.connect() as c:
        c.execute(
            "UPDATE observations SET value=value/10 WHERE asset_id='yf-eth-usd' AND date > '2026-10-09'"
        )
        assert c.execute("SELECT COUNT(*) FROM import_jobs").fetchone()[0] == 0
    crashed = api.get("/api/assets/yf-eth-usd/momentum").json()
    assert crashed["universe"] == data["universe"]
    assert crashed["recent_return"] < data["recent_return"]
    assert api.get("/api/momentum?category=etf").status_code == 200


def test_crypto_missing_bitcoin_queues_reference_and_never_uses_sp500(client):
    api, _ = client
    days = setup_history()
    seed(days, "yf-eth-usd", "crypto")
    assert api.get("/api/assets/yf-eth-usd/momentum").json()["status"] == "pending"
    with db.connect() as c:
        jobs = c.execute("SELECT symbol,category FROM import_jobs").fetchall()
        assert [tuple(job) for job in jobs] == [("BTC-USD", "reference")]
        c.execute(
            "INSERT INTO reference_imports VALUES ('BTC-USD',strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
        )
        c.executemany(
            "INSERT INTO reference_observations VALUES ('BTC-USD',?,100)",
            [(d,) for d in days],
        )
    data = api.get("/api/momentum?category=crypto").json()
    assert data["status"] == "ready"
    assert data["benchmark_name"] == "Bitcoin"
    assert data["universe"][0]["scores"] is not None


def test_hyperliquid_partial_history_is_rankable_without_fabricating_36_months(client):
    api, _ = client
    days = setup_history()
    seed(days, "yf-btc-usd", "crypto")
    seed(days[-707:], "yf-hype32196-usd", "crypto")
    data = api.get("/api/assets/yf-hype32196-usd/momentum").json()
    hype = next(s for s in data["universe"] if s["id"] == "yf-hype32196-usd")
    assert hype["scores"][0] is None
    assert all(isinstance(score, float) for score in hype["scores"][1:])
    assert hype["partial"] is True
    assert hype["available_horizons"] == [12, 6]
    assert hype["reason"] is None
    assert "error" in data["horizons"][0]
    assert data["horizons"][1]["end"] == "2026-10-09"
    assert (
        api.get("/api/momentum?category=crypto").json()["universe"] == data["universe"]
    )
    with db.connect() as c:
        c.execute(
            "DELETE FROM observations WHERE asset_id='yf-hype32196-usd' AND date > '2026-10-30'"
        )
    stale = api.get("/api/assets/yf-hype32196-usd/momentum").json()
    assert (
        next(s for s in stale["universe"] if s["id"] == "yf-hype32196-usd")["scores"]
        is None
    )


def test_bitcoin_reference_import_accepts_crypto_provider_type(client, monkeypatch):
    from types import SimpleNamespace

    import pandas as pd

    from investor.assets.comparison import import_reference

    frame = pd.DataFrame(
        {"Close": [100.0, 101.0]}, index=pd.to_datetime(["2026-11-07", "2026-11-08"])
    )
    ticker = SimpleNamespace(
        history=lambda **_: frame,
        get_history_metadata=lambda: {"instrumentType": "CRYPTOCURRENCY"},
    )
    monkeypatch.setattr("investor.assets.comparison.yf.Ticker", lambda _: ticker)
    import_reference("BTC-USD")
    with db.connect() as c:
        assert (
            c.execute(
                "SELECT COUNT(*) FROM reference_observations WHERE symbol='BTC-USD'"
            ).fetchone()[0]
            == 2
        )
        assert (
            c.execute(
                "SELECT COUNT(*) FROM reference_imports WHERE symbol='BTC-USD'"
            ).fetchone()[0]
            == 1
        )


def test_etf_matches_stock_math_and_has_its_own_universe_and_partial_scores(client):
    api, _ = client
    days = setup_history()
    seed(days, "etf-peer", "etf")
    seed(days[-707:], "etf-short", "etf")
    with db.connect() as c:
        c.execute(
            "UPDATE observations SET value=100 * exp((julianday(date)-julianday('2024-08-31')) * 0.001) WHERE asset_id='europe'"
        )
        c.execute("INSERT INTO observations VALUES ('airbus','2026-11-10',100)")
    response = api.get("/api/assets/europe/momentum")
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "etf"
    assert data["as_of"] == "2026-11-09"
    assert data["benchmark_name"] == "S&P 500 · dividendes réinvestis"
    assert {s["id"] for s in data["universe"]} == {"europe", "etf-peer", "etf-short"}
    assert all("score" in h for h in data["horizons"])
    assert api.get("/api/momentum?category=etf").json()["universe"] == data["universe"]
    short = next(s for s in data["universe"] if s["id"] == "etf-short")
    assert short["scores"][0] is None and short["partial"]
    assert short["available_horizons"] == [12, 6]
    # Align dates again to compare the exact same formula and adjusted series.
    with db.connect() as c:
        c.execute(
            "DELETE FROM observations WHERE asset_id='airbus' AND date='2026-11-10'"
        )
    stock = api.get("/api/assets/airbus/momentum").json()
    assert data["horizons"] == stock["horizons"]
    alternate = api.get("/api/assets/europe/momentum?benchmark=etf-peer").json()
    assert alternate["benchmark_name"] == "etf-peer"
    assert api.get("/api/assets/europe/momentum?benchmark=airbus").status_code == 422
    own = api.get("/api/assets/europe/momentum?benchmark=europe").json()
    assert all(h["relative_performance"] == pytest.approx(0) for h in own["horizons"])
