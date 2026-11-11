"""Verify conditional shocks, joint uncertainty and honest missing-data behavior."""

import math

import numpy as np
import pytest

from investor.db import connect
from investor.simulation.router import FACTORS, changes, fit, month_shift


@pytest.fixture
def stress_client(client):
    api, _ = client
    from datetime import date

    months = []
    month = "2007-01"
    while month < date.today().isoformat()[:7]:
        months.append(month)
        month = month_shift(month, 1)
    rng = np.random.default_rng(9)
    returns = rng.normal(0, 0.04, (len(months), len(FACTORS)))
    levels = 100 * np.exp(np.cumsum(returns, axis=0))
    # Two identical EUR assets test preservation of residual dependence.
    asset = 100 * np.exp(
        np.cumsum(returns[:, 0] - returns[:, -1] + rng.normal(0, 0.02, len(months)))
    )
    with connect() as c:
        for j, symbol in enumerate(FACTORS):
            c.execute("DELETE FROM reference_observations WHERE symbol=?", (symbol,))
            c.execute(
                "INSERT OR REPLACE INTO reference_imports VALUES (?,strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
                (symbol,),
            )
            c.executemany(
                "INSERT INTO reference_observations VALUES (?,?,?)",
                [
                    (symbol, m + "-28", float(levels[i, j]))
                    for i, m in enumerate(months)
                ],
            )
        for identifier in ("one", "two"):
            c.execute(
                "INSERT INTO assets(id,name,category,metric,unit,frequency,source,source_url) VALUES (?,?,'stock','price','EUR','daily','test','https://example.com')",
                (identifier, identifier),
            )
            c.executemany(
                "INSERT INTO observations VALUES (?,?,?)",
                [
                    (identifier, m + "-28", float(asset[i]))
                    for i, m in enumerate(months)
                ],
            )
            c.execute(
                "INSERT INTO price_observations VALUES (?,?,?)",
                (identifier, months[-1] + "-28", float(asset[-1])),
            )
    return api


def run(api, holdings=None, **kwargs):
    return api.post(
        "/api/simulation/run",
        json={
            "holdings": holdings
            if holdings is not None
            else [{"asset_id": "one", "quantity": 2}],
            **kwargs,
        },
    )


def test_all_scenarios_finite_and_reproducible(stress_client):
    api = stress_client
    for scenario in api.get("/api/simulation/scenarios").json():
        response = run(api, scenario=scenario["id"])
        assert response.status_code == 200
        r = response.json()
        assert r["status"] == "ready"
        assert len(r["equity"]) == 13
        assert r["equity"][0]["central"] == pytest.approx(r["total"])
        for p in r["equity"]:
            assert 0 < p["p05"] <= p["p50"] <= p["p95"]
            assert math.isfinite(p["central"])
        assert sum(p["contribution"] for p in r["positions"]) == pytest.approx(
            r["metrics"]["return"]
        )
        assert r == run(api, scenario=scenario["id"]).json()


def test_identical_assets_keep_joint_dependence(stress_client):
    single = run(stress_client).json()
    pair = run(
        stress_client,
        [{"asset_id": "one", "quantity": 1}, {"asset_id": "two", "quantity": 1}],
    ).json()
    for a, b in zip(single["equity"], pair["equity"], strict=True):
        for key in ("central", "p05", "p50", "p95"):
            assert a[key] == pytest.approx(b[key])


def test_missing_scenario_data_never_fabricated(stress_client):
    with connect() as c:
        c.execute(
            "DELETE FROM reference_observations WHERE symbol='HYG' AND date LIKE '2020-03%'"
        )
    r = run(stress_client).json()
    assert r["status"] == "insufficient"
    assert "HYG" in r["message"]


def test_partial_coverage_is_explicit(stress_client):
    with connect() as c:
        c.execute("DELETE FROM observations WHERE asset_id='two' AND date<'2025-01-01'")
    r = run(
        stress_client,
        [{"asset_id": "one", "quantity": 1}, {"asset_id": "two", "quantity": 1}],
    ).json()
    assert r["status"] == "ready"
    assert r["coverage"] == pytest.approx(0.5)
    assert r["excluded"][0]["id"] == "two"


def test_validation_and_empty_portfolio(stress_client):
    assert run(stress_client, months=13).status_code == 422
    assert run(stress_client, scenario="invented").status_code == 422
    assert run(stress_client, [{"asset_id": "one", "quantity": -1}]).status_code == 422
    assert (
        run(stress_client, [{"asset_id": "one", "quantity": 1}] * 2).status_code == 422
    )
    assert run(stress_client, []).json()["status"] == "insufficient"


def test_returns_do_not_bridge_missing_months():
    assert changes({"2020-01": 100, "2020-03": 50}) == {}
    assert month_shift("2020-01", -1) == "2019-12"


def test_fit_stable_with_collinear_factors():
    x = np.ones((36, 7))
    assert np.isfinite(fit(x, np.ones((36, 2)))).all()


def test_fx_uses_past_observation_and_limits_staleness(stress_client):
    from investor.simulation.router import eur_monthly

    with connect() as c:
        asset = c.execute("SELECT * FROM assets WHERE id='one'").fetchone()
        c.execute("DELETE FROM observations WHERE asset_id='one'")
        c.executemany(
            "INSERT INTO observations VALUES ('one',?,100)",
            [("2020-01-15",), ("2020-02-20",)],
        )
        c.execute("DELETE FROM reference_observations WHERE symbol='EURUSD=X'")
        c.executemany(
            "INSERT INTO reference_observations VALUES ('EURUSD=X',?,?)",
            [("2020-01-14", 2), ("2020-01-16", 4), ("2020-02-01", 3)],
        )
        result = eur_monthly(c, asset, "USD")
        assert result == {"2020-01": 50}


def test_blocks_only_use_contiguous_months():
    from investor.simulation.router import contiguous_recent

    assert contiguous_recent(["2020-01", "2020-03", "2020-04"]) == [
        "2020-03",
        "2020-04",
    ]
    assert contiguous_recent([]) == []


def test_watchlist_matches_individual_simulation(stress_client):
    body = {"asset_ids": ["one", "two", "missing"], "scenario": "covid"}
    response = stress_client.post("/api/simulation/watchlist", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "ready"
    assert len(result["results"]) == 2
    single = run(stress_client, [{"asset_id": "one", "quantity": 1}]).json()
    assert result["results"][0] == single
    assert result["excluded"][0]["id"] == "missing"


def test_ai_scenario_uses_observed_tech_factor(stress_client):
    result = run(stress_client, scenario="ai").json()
    assert result["status"] == "ready"
    assert result["historical_start"] == "2021-12"
    assert any(f["symbol"] == "QQQ" for f in result["factors"])
    assert "hypothétique" in result["scenario"]["description"]
