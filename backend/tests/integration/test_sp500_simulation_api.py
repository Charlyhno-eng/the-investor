"""Synthetic paths stay out of the historical observations and strategy settings."""

import pytest
from sp500_support import historical_rows

from investor import db
from investor.portfolio import etf_switch


def test_simulation_api_and_no_database_mutation(client):
    http, _ = client
    rows = historical_rows()
    with db.connect() as c:
        c.execute(
            "INSERT INTO assets(id,name,category,metric,unit,frequency,source,source_url) VALUES('yf-psp5.pa','PSP5','etf','price','EUR','daily','test','test')"
        )
        c.executemany(
            "INSERT INTO observations VALUES(?,?,?)",
            [("yf-psp5.pa", d, p) for d, p, _ in rows],
        )
        c.executemany(
            "INSERT INTO price_observations VALUES(?,?,?)",
            [("yf-psp5.pa", d, raw) for d, _, raw in rows],
        )
    payload = dict(years=1, seed=45)
    a = http.post("/api/portfolio/sp500-simulation", json=payload)
    assert a.status_code == 200, a.text
    result = a.json()
    assert result["status"] == "ready", result
    assert result["comparison"]["protocol"]["etf_switch"] == etf_switch.protocol()
    assert http.post("/api/portfolio/sp500-simulation", json=payload).json() == result
    with db.connect() as c:
        stored = [
            tuple(r)
            for r in c.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            )
        ]
    assert stored == rows
    for invalid in [
        dict(years=2),
        dict(seed=-1),
        dict(seed=2**32),
        dict(fee_rate=0.2),
        dict(initial_capital=0),
    ]:
        assert (
            http.post("/api/portfolio/sp500-simulation", json=invalid).status_code
            == 422
        )


def test_simulation_api_missing_ese_explains_required_history(client):
    http, _ = client
    response = http.post("/api/portfolio/sp500-simulation", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient"


def test_batch_stream_matches_single_simulations_and_exposes_no_curves(client):
    import json

    from investor.portfolio.sp500_simulation import BatchSummary

    test_simulation_api_and_no_database_mutation(client)
    http, _ = client
    payload = dict(years=1, seed=2**32 - 1, count=3)
    response = http.post("/api/portfolio/sp500-simulation/batch", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    snapshots = [json.loads(line) for line in response.text.splitlines()]
    assert [r["completed"] for r in snapshots] == [0, 1, 2, 3]
    assert snapshots[-1]["status"] == "complete"
    expected = BatchSummary()
    for seed in (2**32 - 1, 0, 1):
        single = http.post(
            "/api/portfolio/sp500-simulation", json=dict(years=1, seed=seed)
        ).json()
        expected.add(single["comparison"])
    reference = expected.snapshot(3, 2**32 - 1)
    for key, row in reference["metrics"].items():
        for name, value in row.items():
            actual = snapshots[-1]["metrics"][key][name]
            if name.endswith("_mean") and value is not None:
                assert actual == pytest.approx(value, rel=1e-10, abs=1e-9)
            else:
                assert actual == value
    assert "equity" not in response.text
    for count in (0, -1, 10001, 1.5):
        assert (
            http.post(
                "/api/portfolio/sp500-simulation/batch", json=dict(count=count)
            ).status_code
            == 422
        )


def test_batch_missing_history_reports_error_without_claiming_complete(client):
    import json

    http, _ = client
    response = http.post("/api/portfolio/sp500-simulation/batch", json=dict(count=1000))
    snapshots = [json.loads(line) for line in response.text.splitlines()]
    assert snapshots[-1]["status"] == "error"
    assert snapshots[-1]["completed"] == 0
    assert "cinq ans" in snapshots[-1]["message"]
