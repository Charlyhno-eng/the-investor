"""Numerical risk invariants and real HTTP contracts; no network requests."""

import math
from datetime import date, timedelta
from itertools import pairwise

import numpy as np
import pytest
from fastapi.testclient import TestClient
from investor import db
from investor.api import app
from investor.comparison import INDEX
from investor.volatility import (
    buckets,
    converted,
    coordinates,
    markowitz_frontier,
    risk_map,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    days = [(date.today() - timedelta(days=120 - i)).isoformat() for i in range(120)]
    with db.connect() as c:
        for symbol in [INDEX, "EURUSD=X"]:
            c.execute(
                "INSERT INTO reference_imports VALUES (?,strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
                (symbol,),
            )
            c.executemany(
                "INSERT INTO reference_observations VALUES (?,?,?)",
                [
                    (
                        symbol,
                        d,
                        1.25
                        if symbol == "EURUSD=X"
                        else 100 * math.exp(i * 0.001 + 0.01 * math.sin(i)),
                    )
                    for i, d in enumerate(days)
                ],
            )
    return TestClient(app), days


def seed(days, asset_id="a", category="stock", sign=1, frequency="daily", unit="USD"):
    price = 100
    values = []
    for i, d in enumerate(days):
        price *= 1 + sign * 0.015 * math.sin(i)
        value = -0.8 + 0.1 * math.sin(i) if category == "bond" else price
        values.append((asset_id, d, value))
    db.save(
        [
            (
                asset_id,
                asset_id,
                category,
                "yield" if category == "bond" else "price",
                unit,
                frequency,
                "test",
                "https://example.com",
            )
        ],
        values,
        asset_id,
    )
    with db.connect() as c:
        c.executemany(
            "INSERT INTO price_observations VALUES (?,?,100)",
            [(asset_id, d) for d in days],
        )
    return values


def risk(client, holdings):
    response = client.post(
        "/api/portfolio/volatility",
        json={"holdings": [{"asset_id": k, "quantity": q} for k, q in holdings]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def point(result, identifier):
    return next(p for p in result["points"] if p["id"] == identifier)


def test_coordinates_known_mean_covariance_and_zero_risk():
    means = np.array([0.1, 0.2])
    covariance = np.array([[0.04, -0.04], [-0.04, 0.04]])
    a, mix = coordinates([[1, 0], [0.5, 0.5]], means, covariance)
    assert a == pytest.approx({"return": 10, "volatility": 20, "sharpe": 0.5})
    assert mix["return"] == pytest.approx(15)
    assert mix["volatility"] == 0
    assert mix["sharpe"] is None


@pytest.mark.parametrize("category", ["stock", "crypto", "commodity"])
def test_each_asset_matches_aligned_sample_and_always_has_benchmark(client, category):
    http, days = client
    values = seed(days, category=category)
    result = http.get("/api/assets/a/volatility").json()
    assert result["status"] == "ready"
    assert result["annualization"] == 252  # All categories use benchmark sessions.
    assert result["currency"] == "EUR"
    assert result["end"] == days[-1]
    assert result["observations"] == 119
    changes = np.diff([v[2] for v in values]) / np.array([v[2] for v in values[:-1]])
    a = point(result, "a")
    assert a["return"] == pytest.approx(changes.mean() * 252 * 100)
    assert a["volatility"] == pytest.approx(changes.std(ddof=1) * math.sqrt(252) * 100)
    assert point(result, "sp500")["kind"] == "benchmark"
    assert len(result["points"]) == 2
    assert len(result["frontier"]) >= 1
    assert not {"cloud", "minimum", "tangent"} & result.keys()
    assert result == http.get("/api/assets/a/volatility").json()
    assert http.get("/api/assets/a/volatility?years=0").status_code == 422
    assert http.get("/api/assets/absent/volatility").status_code == 404


def test_bond_and_empty_portfolio_keep_benchmark_without_fabricated_returns(client):
    http, days = client
    seed(days, category="bond")
    for result in [
        http.get("/api/assets/a/volatility").json(),
        risk(http, [("a", 1)]),
        risk(http, []),
    ]:
        assert result["status"] == "ready"
        assert [p["id"] for p in result["points"]] == ["sp500"]
        assert result["frontier"] == []
    assert risk(http, [("a", 1)])["excluded"][0]["id"] == "a"


def test_portfolio_uses_only_holdings_and_has_one_point_per_asset(client):
    http, days = client
    seed(days, "a", sign=1)
    seed(days, "b", sign=-1)
    combined = risk(http, [("a", 1), ("b", 1)])
    assert [p["weight"] for p in combined["positions"]] == [0.5, 0.5]
    assert {p["id"] for p in combined["points"]} == {"a", "b", "sp500"}
    assert combined["frontier_assets"] == ["a", "b"]
    assert combined["frontier"][0]["volatility"] < 1e-5
    # A comparator must not influence the holdings' opportunity frontier.
    with db.connect() as c:
        c.execute(
            "UPDATE reference_observations SET value=value*2 WHERE symbol=? AND date=?",
            (INDEX, days[-1]),
        )
    assert risk(http, [("a", 1), ("b", 1)])["frontier"] == combined["frontier"]
    alone = risk(http, [("a", 1)])
    assert alone["frontier"] == []
    assert alone["frontier_assets"] == ["a"]


def test_markowitz_matches_analytic_minimum_and_target_return_qp():
    means = np.array([0.08, 0.12, 0.20])
    covariance = np.diag([0.04, 0.09, 0.16])
    upper, lower = markowitz_frontier(means, covariance)
    inverse = np.linalg.inv(covariance)
    minimum_weights = inverse @ np.ones(3) / np.sum(inverse)
    minimum = coordinates(minimum_weights, means, covariance)[0]
    assert upper[0] == pytest.approx(minimum)
    assert lower[0] == pytest.approx(minimum)
    assert upper[-1]["return"] == pytest.approx(20)
    assert lower[-1]["return"] == pytest.approx(8)
    # Closed-form equality-constrained solution applies whenever its weights are positive.
    constraints = np.vstack([np.ones(3), means])
    for p in upper + lower:
        target = np.array([1, p["return"] / 100])
        w = (
            inverse
            @ constraints.T
            @ np.linalg.solve(constraints @ inverse @ constraints.T, target)
        )
        if np.min(w) >= 0:
            assert p["volatility"] == pytest.approx(
                coordinates(w, means, covariance)[0]["volatility"], abs=1e-5
            )
    assert all(
        a["return"] < b["return"] and a["volatility"] <= b["volatility"] + 1e-6
        for a, b in pairwise(upper)
    )


@pytest.mark.parametrize(
    "means,covariance",
    [
        (np.array([0.1, 0.2]), np.array([[0.04, 0], [0, 0.09]])),
        (np.array([-0.2, -0.1]), np.array([[0.04, 0.04], [0.04, 0.04]])),
        (np.array([0.1, 0.1]), np.array([[0.04, 0.04], [0.04, 0.04]])),
        (np.array([0.0, 0.0]), np.zeros((2, 2))),
    ],
)
def test_two_asset_frontier_degenerate_and_negative_returns(means, covariance):
    upper, lower = markowitz_frontier(means, covariance)
    assert all(
        math.isfinite(p["volatility"]) and math.isfinite(p["return"])
        for p in upper + lower
    )
    for p in upper + lower:
        if np.ptp(means) > 0:
            w = (p["return"] / 100 - means[1]) / (means[0] - means[1])
            assert -0.000001 <= w <= 1.000001
            assert p["volatility"] == pytest.approx(
                coordinates([w, 1 - w], means, covariance)[0]["volatility"], abs=1e-6
            )
        else:
            assert len(upper) == 1
            assert lower == []


def test_currency_dates_and_short_history(client):
    http, days = client
    seed(days)
    first = risk(http, [("a", 1)])
    with db.connect() as c:
        c.executemany(
            "UPDATE reference_observations SET value=? WHERE symbol='EURUSD=X' AND date=?",
            [(1.2 * math.exp(0.02 * math.sin(i)), d) for i, d in enumerate(days)],
        )
        c.execute(
            "DELETE FROM reference_observations WHERE symbol=? AND date=?",
            (INDEX, days[30]),
        )
    second = risk(http, [("a", 1)])
    assert point(first, "a")["volatility"] != pytest.approx(
        point(second, "a")["volatility"]
    )
    assert second["observations"] == 118
    # Identical EUR return series for the detail and a one-asset portfolio.
    assert point(second, "a") == point(http.get("/api/assets/a/volatility").json(), "a")
    with db.connect() as c:
        c.execute("DELETE FROM observations WHERE asset_id='a' AND date<?", (days[-5],))
    assert risk(http, [("a", 1)])["status"] == "insufficient"


def test_monthly_completed_months_and_selected_period():
    today = date.today()
    months = []
    for i in range(60):
        index = today.year * 12 + today.month - 60 + i
        months.append(f"{index // 12}-{index % 12 + 1:02d}-01")
    history = {
        d: 100 * math.exp(i * 0.002 + 0.01 * math.sin(i)) for i, d in enumerate(months)
    }
    assets = [{"id": "m", "name": "Monthly", "frequency": "monthly"}]
    full = risk_map(assets, [history], history, 3)
    zoom = risk_map(assets, [history], history, 1)
    assert full["frequency"] == "monthly"
    assert full["annualization"] == 12
    assert full["end"][:7] < today.isoformat()[:7]
    assert zoom["observations"] >= 12
    assert zoom["observations"] < full["observations"]
    assert point(zoom, "m")["return"] != point(full, "m")["return"]
    assert buckets({"2025-01-03": 2, "2025-01-20": 3}, True) == {"2025-01-31": 3}


def test_missing_reference_pending_and_duplicate_validation(client):
    http, days = client
    seed(days)
    with db.connect() as c:
        c.execute("DELETE FROM reference_imports WHERE symbol=?", (INDEX,))
    assert risk(http, [("a", 1)])["status"] == "pending"
    assert http.get("/api/assets/a/volatility").json()["status"] == "pending"
    with db.connect() as c:
        assert (
            c.execute(
                "SELECT count(*) FROM import_jobs WHERE symbol=?", (INDEX,)
            ).fetchone()[0]
            == 1
        )
    assert (
        http.post(
            "/api/portfolio/volatility",
            json={"holdings": [{"asset_id": "a", "quantity": 1}] * 2},
        ).status_code
        == 422
    )


def test_fx_uses_no_future_and_expires_after_seven_days():
    assert converted(
        {"2025-01-02": 100, "2025-01-10": 100}, None, {"2025-01-01": 2, "2025-01-11": 4}
    ) == {"2025-01-02": 50}
    assert converted({"2025-01-01": 100}, None, {"2025-01-02": 2}) == {}


def test_frontier_with_all_positions_locked_collapses_to_actual_portfolio(client):
    http, days = client
    a = seed(days, "a")
    b = seed(days, "b", sign=-1)
    response = http.post(
        "/api/portfolio/volatility",
        json={
            "holdings": [
                {"asset_id": "a", "quantity": 3},
                {"asset_id": "b", "quantity": 1},
            ],
            "locked_asset_ids": ["a", "b"],
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert len(result["frontier"]) == 1
    assert result["lower_frontier"] == []
    prices = np.array([[v[2] for v in values] for values in (a, b)]).T
    changes = np.diff(prices, axis=0) / prices[:-1]
    expected = changes @ [0.75, 0.25]
    assert result["frontier"][0]["volatility"] == pytest.approx(
        expected.std(ddof=1) * np.sqrt(252) * 100
    )
