"""Validation API: shared EUR data loader, benchmark choice and failure states."""

from datetime import date, timedelta

import pytest
from support import seed

from investor import db
from investor.assets.comparison import INDEX


def test_validation_api_with_fx_and_local_benchmark(client):
    http, _ = client
    start = date.today() - timedelta(days=6 * 366)
    days = [
        (start + timedelta(days=i)).isoformat()
        for i in range(6 * 366 + 1)
        if (start + timedelta(days=i)).weekday() < 5
    ]
    seed(days, "a", unit="EUR")
    seed(days, "b", sign=-1, category="etf")
    with db.connect() as c:
        for symbol in (INDEX, "EURUSD=X"):
            c.execute("DELETE FROM reference_observations WHERE symbol=?", (symbol,))
            c.executemany(
                "INSERT INTO reference_observations VALUES (?,?,?)",
                [
                    (
                        symbol,
                        d,
                        (1.05 + i * 0.00001)
                        if symbol == "EURUSD=X"
                        else (100 + i * 0.05),
                    )
                    for i, d in enumerate(days)
                ],
            )
    payload = {"asset_ids": ["a", "b"], "years": 1}
    response = http.post("/api/portfolio/validation", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "ready", result
    assert result["benchmark_name"].startswith("S&P 500")
    assert result["completed_quarters"] >= 3
    assert result["assets"] == [{"id": "a", "name": "a"}, {"id": "b", "name": "b"}]
    local = http.post(
        "/api/portfolio/validation", json={**payload, "benchmark_asset_id": "b"}
    ).json()
    assert local["status"] == "ready"
    assert local["benchmark_name"] == "b"
    assert local["metrics"]["benchmark"] != result["metrics"]["benchmark"]
    whole = http.post(
        "/api/portfolio/validation",
        json={**payload, "whole_shares": True, "benchmark_asset_id": "b"},
    ).json()
    assert whole["status"] == "ready", whole
    assert whole["parameters"]["whole_shares"] is True
    assert whole["transactions"]
    assert all(isinstance(t["quantity"], int) for t in whole["transactions"])
    assert all(
        isinstance(p["quantity"], int) for p in whole["final_portfolio"]["positions"]
    )
    seed(days, "coin", category="crypto")
    seed(days, "gold", category="commodity")
    seed(days, "yield", category="bond")
    mixed = http.post(
        "/api/portfolio/validation",
        json={
            "asset_ids": ["a", "b", "coin", "gold", "yield"],
            "mode": "mean_reversion",
            "years": 1,
        },
    ).json()
    assert mixed["status"] == "ready", mixed
    assert any("b : retour à la moyenne non appliqué" in n for n in mixed["notices"])
    assert any("yield : aucun cours exploitable" in n for n in mixed["notices"])
    for aid in ("b", "gold"):
        orders = [t for t in mixed["transactions"] if t["asset_id"] == aid]
        assert len(orders) == 1 and orders[0]["side"] == "buy"
        position = next(
            p for p in mixed["final_portfolio"]["positions"] if p["id"] == aid
        )
        assert position["quantity"] == pytest.approx(orders[0]["quantity"])
    assert (
        next(p for p in mixed["final_portfolio"]["positions"] if p["id"] == "yield")[
            "quantity"
        ]
        == 0
    )
    # No dependence on current share prices: this endpoint uses adjusted history.
    with db.connect() as c:
        c.execute("DELETE FROM price_observations")
    assert http.post("/api/portfolio/validation", json=payload).json() == result
    # A historical run stays reproducible while an hourly reference refresh is
    # queued or failed, as long as the same historical quotes remain available.
    with db.connect() as c:
        c.execute("UPDATE reference_imports SET updated_at='2000-01-01T00:00:00Z'")
    assert http.post("/api/portfolio/validation", json=payload).json() == result
    with db.connect() as c:
        c.execute("UPDATE import_jobs SET status='failed' WHERE category='reference'")
    assert http.post("/api/portfolio/validation", json=payload).json() == result


def test_validation_request_errors_and_missing_data(client):
    http, days = client
    seed(days, "a")
    for payload in [
        {"asset_ids": []},
        {"asset_ids": ["a", "a"]},
        {"asset_ids": ["a"], "fee_rate": -0.1},
        {"asset_ids": ["a"], "years": 2},
        {"asset_ids": ["a"], "mode": "unknown"},
        {"asset_ids": ["a"], "initial_capital": 0},
        {"asset_ids": ["a"], "reversion_entry_z": 0},
        {"asset_ids": ["a"], "reversion_exit_z": -1},
        {"asset_ids": ["a"], "reversion_exit_mode": "unknown"},
        {"asset_ids": ["a"], "reversion_trailing_gap": 0},
        {"asset_ids": ["a"], "reversion_funding_min_z": -0.5},
        {"asset_ids": ["a"], "start_date": "2025-01-01", "end_date": "2024-01-01"},
        {"asset_ids": [str(i) for i in range(21)]},
    ]:
        assert http.post("/api/portfolio/validation", json=payload).status_code == 422
    assert (
        http.post(
            "/api/portfolio/validation", json={"asset_ids": ["unknown"]}
        ).status_code
        == 404
    )
    seed(days, "bond", category="bond")
    assert (
        http.post("/api/portfolio/validation", json={"asset_ids": ["bond"]}).status_code
        == 422
    )
    payload = {"asset_ids": ["a"]}
    result = http.post("/api/portfolio/validation", json=payload).json()
    assert result["status"] == "insufficient"
    assert "trois ans" in result["message"]
    with db.connect() as c:
        c.execute("DELETE FROM reference_imports WHERE symbol=?", (INDEX,))
        c.execute("DELETE FROM reference_observations WHERE symbol=?", (INDEX,))
    assert (
        http.post("/api/portfolio/validation", json=payload).json()["status"]
        == "pending"
    )


def test_mean_reversion_accepts_non_stock_universe(client):
    http, days = client
    seed(days, "fund", category="etf")
    response = http.post(
        "/api/portfolio/validation",
        json={"asset_ids": ["fund"], "mode": "mean_reversion"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient"
    assert "trois ans" in response.json()["message"]
