"""Numerical risk invariants and real HTTP contracts; no network requests."""

import math

import numpy as np
import pytest
from support import point, seed

from investor import db
from investor.assets.comparison import INDEX


def risk(client, holdings):
    response = client.post(
        "/api/portfolio/volatility",
        json={"holdings": [{"asset_id": k, "quantity": q} for k, q in holdings]},
    )
    assert response.status_code == 200, response.text
    return response.json()


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
