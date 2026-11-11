import pytest
from support import seed

from investor import db


def request(client, *holdings):
    return client.post(
        "/api/portfolio/prediction",
        json={"holdings": [{"asset_id": a, "quantity": q} for a, q in holdings]},
    )


def test_independent_histories_quantities_and_latest_eur_values(client):
    api, days = client
    seed(days, "a")
    seed(days[-10:], "young", category="crypto")
    data = request(api, ("a", 2), ("young", 3)).json()
    assert data["status"] == "ready"
    old, young = data["series"]
    assert len(old["points"]) == 120
    assert len(young["points"]) == 10
    assert old["value"] == pytest.approx(200 / 1.25)
    assert old["crypto"] is False and young["crypto"] is True
    assert data["current_total"] == pytest.approx(old["value"] + young["value"])
    doubled = request(api, ("a", 4), ("young", 6)).json()
    assert doubled["current_total"] == pytest.approx(data["current_total"] * 2)
    assert doubled["series"][0]["points"] == old["points"]


def test_first_quote_and_zero_holdings(client):
    api, days = client
    seed(days[-1:], "new", category="crypto")
    seed(days, "ignored", category="bond")
    data = request(api, ("new", 1), ("ignored", 0)).json()
    assert data["status"] == "ready"
    assert len(data["series"]) == 1
    assert len(data["series"][0]["points"]) == 1


def test_whole_portfolio_validation(client):
    api, days = client
    seed(days, "a")
    seed(days, "bond", category="bond")
    assert request(api, ("a", 1), ("bond", 1)).json()["status"] == "insufficient"
    assert "quantités" in request(api).json()["message"]
    seed(days, "monthly", category="commodity", frequency="monthly")
    assert "quotidien" in request(api, ("monthly", 1)).json()["message"]
    assert request(api, ("a", 1), ("a", 1)).status_code == 422
    assert request(api, ("missing", 1)).status_code == 404


def test_native_currency_history_is_not_fx_transformed(client):
    api, days = client
    values = seed(days, "a", unit="EUR")
    data = request(api, ("a", 2)).json()
    assert data["series"][0]["value"] == pytest.approx(200)
    assert [p["value"] for p in data["series"][0]["points"]] == [v[2] for v in values]
    with db.connect() as c:
        assert (
            c.execute(
                "SELECT count(*) FROM import_jobs WHERE symbol='^SP500TR'"
            ).fetchone()[0]
            == 0
        )
