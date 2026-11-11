from datetime import date, timedelta

import numpy as np
import pytest
from support import seed

from investor import db


@pytest.mark.parametrize("category", ["stock", "etf"])
def test_five_year_deviation_matches_ols_of_log_prices_and_ignores_older_data(
    client, category
):
    http, _ = client
    days = [
        (date.today() - timedelta(days=3000 - i * 10)).isoformat() for i in range(300)
    ]
    values = seed(days, category=category)
    result = http.post("/api/portfolio/regression", json={"asset_ids": ["a"]}).json()[
        "positions"
    ][0]
    selected = [(d, v) for _, d, v in values if d >= result["start"]]
    x = np.array(
        [
            (date.fromisoformat(d) - date.fromisoformat(selected[0][0])).days
            for d, _ in selected
        ]
    )
    y = np.log([v for _, v in selected])
    slope, intercept = np.polyfit(x, y, 1)
    residuals = y - (intercept + slope * x)
    assert result["z"] == pytest.approx(
        residuals[-1] / np.sqrt(np.sum(residuals**2) / (len(y) - 2))
    )
    assert result["observations"] < len(days)
    assert result["end"] == days[-1]
    with db.connect() as c:
        c.execute(
            "UPDATE observations SET value=1 WHERE asset_id='a' AND date<?",
            (result["start"],),
        )
    assert (
        http.post("/api/portfolio/regression", json={"asset_ids": ["a"]}).json()[
            "positions"
        ][0]
        == result
    )


def test_insufficient_invalid_and_degenerate_regressions_return_no_fabricated_z(client):
    http, days = client
    seed(days[-5:], "short")
    seed(days, "flat")
    seed(days, "negative", category="bond")
    with db.connect() as c:
        c.execute("UPDATE observations SET value=100 WHERE asset_id='flat'")
    result = http.post(
        "/api/portfolio/regression",
        json={"asset_ids": ["short", "flat", "negative", "missing"]},
    ).json()
    assert len(result["positions"]) == 4
    assert all(p["z"] is None and p["reason"] for p in result["positions"])
