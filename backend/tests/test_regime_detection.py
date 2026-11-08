from datetime import date, timedelta

import numpy as np
import pytest
from fastapi import HTTPException
from investor import db
from investor.analysis.detection import RegimeRequest, detect
from pydantic import ValidationError


def test_test_period_does_not_fit_model_or_rewrite_earlier_regimes(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    rng = np.random.default_rng(17)
    returns = rng.normal(np.tile([-0.012, -0.002, 0.003, 0.015], 125), 0.008)
    prices = 100 * np.exp(np.cumsum(returns))
    days = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(500)]
    db.save(
        [
            (
                "a",
                "Test",
                "stock",
                "price",
                "USD",
                "daily",
                "test",
                "https://example.com",
            )
        ],
        [("a", day, float(value)) for day, value in zip(days, prices)],
        "test",
    )

    def request(end):
        return RegimeRequest(
            train_start=days[0],
            train_end=days[349],
            test_start=days[370],
            test_end=days[end],
        )

    first = detect("a", request(420))
    with db.connect() as connection:
        connection.execute(
            "UPDATE observations SET value=value*3 WHERE asset_id='a' AND date>?",
            (days[420],),
        )
    extended = detect("a", request(499))
    assert first["points"] == extended["points"][: len(first["points"])]
    assert len(first["states"]) == 4
    assert len({s["name"] for s in first["states"]}) == 4
    for state in first["states"]:
        assert state["name"].startswith(
            "Hausse"
            if state["mean"] > 0
            else "Baisse"
            if state["mean"] < 0
            else "Stable"
        )
        assert "volatilité" in state["name"]
    assert [s["name"] for s in first["states"]] == [
        s["name"] for s in extended["states"]
    ]
    assert first["train_observations"] == 349
    assert first["actual_test"] == [days[370], days[420]]
    assert all(
        0 <= p["state"] < 4 and 0 <= p["confidence"] <= 1 for p in extended["points"]
    )
    assert sum(s["probability"] for s in extended["states"]) == pytest.approx(1)
    assert sum(s["next_probability"] for s in extended["states"]) == pytest.approx(1)
    assert [(s["mean"], s["volatility"]) for s in first["states"]] == [
        (s["mean"], s["volatility"]) for s in extended["states"]
    ]
    assert [s["mean"] for s in first["states"]] == sorted(
        s["mean"] for s in first["states"]
    )
    with pytest.raises(HTTPException, match="252"):
        detect(
            "a",
            RegimeRequest(
                train_start=days[0],
                train_end=days[100],
                test_start=days[200],
                test_end=days[250],
            ),
        )


def test_periods_must_be_disjoint_and_chronological():
    with pytest.raises(ValidationError):
        RegimeRequest(
            train_start="2020-01-01",
            train_end="2021-01-01",
            test_start="2020-12-01",
            test_end="2022-01-01",
        )
