import math
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from investor import db
from investor.api import app


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    with db.connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO reference_imports VALUES ('EURUSD=X',strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
        )
        connection.executemany(
            "INSERT INTO reference_observations VALUES ('EURUSD=X',?,1.25)",
            [
                (day,)
                for day in [
                    "2025-09-25",
                    *[
                        (date.today() - timedelta(days=i)).isoformat()
                        for i in range(45)
                    ],
                ]
            ],
        )
    return TestClient(app)


def seed(asset_id, sign=1, raw=100, category="stock"):
    points = []
    value = 100.0
    for i in range(35):
        value *= math.exp(sign * 0.01 * math.sin(i))
        day = (date.today() - timedelta(days=40 - i)).isoformat()
        points.append((asset_id, day, value))
    db.save(
        [
            (
                asset_id,
                asset_id,
                category,
                "yield" if category == "bond" else "price",
                "USD",
                "daily",
                "test",
                "https://example.com",
            )
        ],
        points,
        "test:" + asset_id,
    )
    with db.connect() as connection:
        connection.executemany(
            "INSERT INTO price_observations VALUES (?,?,?)",
            [(p[0], p[1], raw) for p in points],
        )


def test_valuation_uses_current_unadjusted_prices_and_correlations_use_returns(local):
    seed("a", raw=20)
    seed("b", sign=-1, raw=40)
    r = local.post(
        "/api/portfolio/analytics",
        json={
            "holdings": [
                {"asset_id": "a", "quantity": 2},
                {"asset_id": "b", "quantity": 1},
            ]
        },
    ).json()
    assert r["status"] == "ready"
    assert r["total_usd"] == 80
    assert r["currency"] == "EUR"
    assert r["total"] == 64
    assert [p["weight"] for p in r["positions"]] == [0.5, 0.5]
    assert r["correlation"]["observations"] == 34
    assert r["correlation"]["matrix"][0][0] == pytest.approx(1)
    assert r["correlation"]["matrix"][0][1] == pytest.approx(-1)
    assert r["correlation"]["matrix"][1][0] == pytest.approx(-1)


def test_constant_series_and_missing_overlap_are_null(local):
    seed("a", sign=0)
    seed("b")
    r = local.post(
        "/api/portfolio/analytics",
        json={
            "holdings": [
                {"asset_id": "a", "quantity": 0.5},
                {"asset_id": "b", "quantity": 2},
            ]
        },
    ).json()
    assert r["correlation"]["matrix"][0] == [None, None]
    with db.connect() as connection:
        connection.execute("DELETE FROM observations WHERE asset_id='b'")
    r = local.post(
        "/api/portfolio/analytics",
        json={
            "holdings": [
                {"asset_id": "a", "quantity": 0.5},
                {"asset_id": "b", "quantity": 2},
            ]
        },
    ).json()
    assert r["correlation"]["observations"] == 0
    assert r["correlation"]["matrix"] == [[None, None], [None, None]]


def test_invalid_quantities_duplicates_and_rate_exclusion(local):
    seed("bond", category="bond")
    assert (
        local.post(
            "/api/portfolio/analytics",
            json={"holdings": [{"asset_id": "bond", "quantity": -1}]},
        ).status_code
        == 422
    )
    assert (
        local.post(
            "/api/portfolio/analytics",
            json={"holdings": [{"asset_id": "bond", "quantity": 1}] * 2},
        ).status_code
        == 422
    )
    r = local.post(
        "/api/portfolio/analytics",
        json={"holdings": [{"asset_id": "bond", "quantity": 1}]},
    ).json()
    assert r["positions"] == []
    assert r["excluded"][0]["id"] == "bond"
    assert (
        local.post("/api/portfolio/analytics", json={"holdings": []}).json()[
            "total_usd"
        ]
        == 0
    )


def test_monthly_series_align_by_completed_month_and_indices_are_not_valued(local):
    assets = [
        (
            "stock",
            "Stock",
            "stock",
            "price",
            "USD",
            "daily",
            "test",
            "https://example.com",
        ),
        (
            "index",
            "Index",
            "commodity",
            "price",
            "(2010=100)",
            "monthly",
            "test",
            "https://example.com",
        ),
    ]
    points = []
    for month in range(1, 10):
        value = math.exp(month * 0.1 + math.sin(month) * 0.05) * 100
        points.extend(
            [
                ("stock", f"2025-{month:02d}-25", value),
                ("index", f"2025-{month:02d}-01", value),
            ]
        )
    db.save(assets, points, "test-monthly")
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO price_observations VALUES ('stock','2025-09-25',100)"
        )
    result = local.post(
        "/api/portfolio/analytics",
        json={
            "holdings": [
                {"asset_id": "stock", "quantity": 2},
                {"asset_id": "index", "quantity": 3},
            ],
            "years": 3,
        },
    ).json()
    assert result["correlation"]["frequency"] == "monthly"
    assert result["correlation"]["observations"] == 8
    assert result["correlation"]["matrix"][0][1] == pytest.approx(1)
    assert result["total_usd"] == 200
    assert result["excluded"][0]["id"] == "index"


def test_currency_conversion_uses_last_known_rate_not_a_future_rate(local):
    seed("a", raw=100)
    with db.connect() as connection:
        connection.execute("DELETE FROM reference_observations")
        last = connection.execute(
            "SELECT MAX(date) FROM price_observations"
        ).fetchone()[0]
        previous = (date.fromisoformat(last) - timedelta(days=2)).isoformat()
        future = (date.fromisoformat(last) + timedelta(days=1)).isoformat()
        connection.executemany(
            "INSERT INTO reference_observations VALUES (?,?,?)",
            [("EURUSD=X", previous, 1.25), ("EURUSD=X", future, 2)],
        )
        connection.execute(
            "INSERT OR REPLACE INTO reference_imports VALUES ('EURUSD=X',strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
        )
    body = {"holdings": [{"asset_id": "a", "quantity": 2}], "currency": "EUR"}
    result = local.post("/api/portfolio/analytics", json=body).json()
    assert result["currency"] == "EUR"
    assert result["total"] == 160
    assert result["total_usd"] == 200
    assert result["positions"][0]["value"] == 160
    assert result["positions"][0]["price"] == 80
    assert result["positions"][0]["fx_date"] == previous
    assert result["positions"][0]["weight"] == 1
    with db.connect() as connection:
        connection.execute(
            "DELETE FROM reference_observations WHERE date=?", (previous,)
        )
        connection.execute(
            "INSERT INTO reference_observations VALUES ('EURUSD=X',?,1.1)",
            ((date.fromisoformat(last) - timedelta(days=8)).isoformat(),),
        )
    result = local.post("/api/portfolio/analytics", json=body).json()
    assert result["positions"] == []
    assert "Change EUR indisponible" in result["excluded"][0]["reason"]
    body["currency"] = "USD"
    assert local.post("/api/portfolio/analytics", json=body).status_code == 422


def test_missing_display_currency_rate_is_queued_and_empty_portfolio_needs_no_rate(
    local,
):
    seed("a")
    with db.connect() as connection:
        connection.execute("DELETE FROM reference_imports")
        connection.execute("DELETE FROM reference_observations")
    body = {"holdings": [{"asset_id": "a", "quantity": 1}]}
    assert local.post("/api/portfolio/analytics", json=body).json() == {
        "status": "pending"
    }
    with db.connect() as connection:
        assert (
            connection.execute("SELECT symbol FROM import_jobs").fetchone()[0]
            == "EURUSD=X"
        )
    result = local.post(
        "/api/portfolio/analytics", json={"holdings": [], "currency": "EUR"}
    ).json()
    assert result["currency"] == "EUR"
    assert result["total"] == 0


def test_sp500_reference_is_in_correlation_without_becoming_a_position(local):
    seed("a")
    with db.connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO reference_imports VALUES ('^SP500TR',strftime('%Y-%m-%dT%H:%M:%SZ','now'))"
        )
        connection.execute(
            "INSERT INTO reference_observations SELECT '^SP500TR',date,value FROM observations WHERE asset_id='a'"
        )
    result = local.post(
        "/api/portfolio/analytics",
        json={
            "holdings": [{"asset_id": "a", "quantity": 2}],
            "include_benchmark": True,
        },
    ).json()
    assert result["status"] == "ready"
    assert [p["id"] for p in result["positions"]] == ["a"]
    assert [a["id"] for a in result["correlation"]["assets"]] == ["^SP500TR", "a"]
    assert result["correlation"]["matrix"][1][1] == pytest.approx(1)
    assert result["correlation"]["matrix"][0][1] == pytest.approx(1)
    assert result["total_usd"] == 200
