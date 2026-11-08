"""Shared isolated portfolio data and API fixture."""

import math
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from investor import db
from investor.api import app
from investor.assets.comparison import INDEX


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


def point(result, identifier):
    return next(p for p in result["points"] if p["id"] == identifier)
