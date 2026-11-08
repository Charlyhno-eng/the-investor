from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from investor import db
from investor.api import app
from investor.ingest import parse_world_bank
from openpyxl import Workbook


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    return TestClient(app)


def seed():
    db.save(
        [
            (
                "gold",
                "Gold",
                "commodity",
                "price",
                "$/oz",
                "monthly",
                "test",
                "https://example.com",
            )
        ],
        [("gold", "2020-01-01", 1500), ("gold", "2020-02-01", 1600)],
        "test",
    )


def test_idempotent_import_and_correction(local):
    seed()
    seed()
    db.save(
        [
            (
                "gold",
                "Gold",
                "commodity",
                "price",
                "$/oz",
                "monthly",
                "test",
                "https://example.com",
            )
        ],
        [("gold", "2020-02-01", 1610)],
        "test",
    )
    assert local.get("/api/assets").json()[0]["points"] == 2
    assert local.get("/api/assets/gold/history").json()[-1]["value"] == 1610


def test_local_history_filters_and_errors(local, monkeypatch):
    seed()
    # API consultation must work without any provider access.
    import httpx

    def offline(*args, **kwargs):
        raise AssertionError("External request during consultation")

    monkeypatch.setattr(httpx.Client, "send", offline)
    from datetime import date

    from investor.api import assets, history

    assert len(assets()) == 1
    assert history("gold", date(2020, 2, 1)) == [
        {"time": "2020-02-01", "value": 1600.0}
    ]


def test_http_errors_and_empty_import_preserves_history(local):
    seed()
    assert local.get("/api/assets/missing/history").status_code == 404
    assert (
        local.get(
            "/api/assets/gold/history?start=2021-01-01&end=2020-01-01"
        ).status_code
        == 422
    )
    assert local.get("/api/assets/gold/history?start=invalid").status_code == 422
    with pytest.raises(ValueError):
        db.save([], [], "test")
    assert len(local.get("/api/assets/gold/history").json()) == 2


def test_world_bank_parser_missing_and_negative_values():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Monthly Prices"
    for row in [
        ("Historical prices",),
        ("", "Gold", "Oil"),
        ("", "$/oz", "$/bbl"),
        ("2020M01", 1500, 60),
        ("2020M02", "..", -10),
        ("2020M03", float("inf"), None),
    ]:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    assets, points = parse_world_bank(stream.getvalue())
    assert len(assets) == 2
    assert points == [
        ("wb-gold", "2020-01-01", 1500.0),
        ("wb-oil", "2020-01-01", 60.0),
        ("wb-oil", "2020-02-01", -10.0),
    ]


def test_bonds_are_listed_by_country_and_legacy_maturities_preserved(local):
    db.save(
        [
            (
                "DGS2",
                "Trésor US · 2 ans",
                "bond",
                "yield",
                "%",
                "daily",
                "fred",
                "https://fred.stlouisfed.org/series/DGS2",
            )
        ],
        [("DGS2", "2020-01-01", 1.5)],
        "legacy",
    )
    db.save(
        [
            (
                "FR10",
                "France",
                "bond",
                "yield",
                "%",
                "monthly",
                "oecd-fred",
                "https://example.com",
            )
        ],
        [("FR10", "2020-01-01", -0.1)],
        "fr",
        country_code="FR",
        benchmark_years=10,
    )
    listed = local.get("/api/assets").json()
    assert [a["name"] for a in listed] == ["France"]
    assert listed[0]["country_code"] == "FR"
    assert listed[0]["benchmark_years"] == 10
    assert local.get("/api/assets/DGS2/history").json() == [
        {"time": "2020-01-01", "value": 1.5}
    ]


def test_fred_parser_rejects_missing_schema_and_skips_gaps():
    from investor.ingest import parse_fred

    data = b"observation_date,FR10\n2020-01-01,-0.1\n2020-02-01,.\n2020-03-01,1.2\n"
    assert parse_fred(data, "FR10") == [
        ("FR10", "2020-01-01", -0.1),
        ("FR10", "2020-03-01", 1.2),
    ]
    with pytest.raises(ValueError):
        parse_fred(b"<html>Unavailable</html>", "FR10")
    with pytest.raises(ValueError):
        parse_fred(b"observation_date,FR10\ninvalid,2\n", "FR10")


def test_country_import_continues_after_failure(local, monkeypatch):
    from investor import ingest

    monkeypatch.setattr(ingest, "COUNTRIES", {"FR": "France", "DE": "Allemagne"})

    def download(url, extension):
        if "FRM156N" in url:
            raise RuntimeError("Provider unavailable")
        return b"observation_date,IRLTLT01DEM156N\n2020-01-01,-0.1\n"

    monkeypatch.setattr(ingest, "download", download)
    with pytest.raises(RuntimeError, match="France"):
        ingest.fred()
    assert local.get("/api/assets").json()[0]["name"] == "Allemagne"


def test_existing_database_migration(local):
    import sqlite3

    with sqlite3.connect(db.DATA_DIR / "investor.sqlite3") as connection:
        connection.execute(
            "CREATE TABLE assets (id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, metric TEXT NOT NULL, unit TEXT NOT NULL, frequency TEXT NOT NULL, source TEXT NOT NULL, source_url TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO assets VALUES ('old','Old','commodity','price','$','monthly','test','https://example.com')"
        )
    with db.connect() as connection:
        row = dict(
            connection.execute("SELECT * FROM assets WHERE id=?", ("old",)).fetchone()
        )
    assert row["name"] == "Old"
    assert row["country_code"] is None


def test_bond_year_ranking(local):
    for code, values in [("FR", [50, 2, 4]), ("US", [0, 4, 6]), ("JP", [1])]:
        dates = (
            ["2024-10-01", "2024-11-01", "2025-10-01"]
            if code != "JP"
            else ["2020-01-01"]
        )
        db.save(
            [
                (
                    code,
                    code,
                    "bond",
                    "yield",
                    "%",
                    "monthly",
                    "test",
                    "https://example.com",
                )
            ],
            [(code, d, v) for d, v in zip(dates, values)],
            "test",
            country_code=code,
            benchmark_years=10,
        )
    rows = local.get("/api/assets").json()
    assert [r["id"] for r in rows] == ["US", "FR", "JP"]
    assert rows[0]["year_average_yield"] == 5
    assert rows[1]["year_average_yield"] == 3
    assert rows[0]["year_yield_samples"] == 2
    assert rows[2]["year_average_yield"] is None
    assert rows[0]["bond_ranking_date"] == "2025-10-01"
    assert local.get("/api/assets/FR/dividends").status_code == 422
