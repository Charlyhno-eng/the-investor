import sqlite3

from investor.assets.metadata import enrich_asset, visible_asset
from investor.ingest import parse_brazil


def test_dividend_threshold_includes_zero_payment_years_and_ignores_manual_flag():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        "CREATE TABLE dividend_imports(asset_id,first_date,last_date); CREATE TABLE dividends(asset_id,date,yield_percent);"
    )
    db.execute("INSERT INTO dividend_imports VALUES ('a','2023-01-01','2026-11-08')")
    row = {"id": "a", "category": "stock", "is_dividend": True}
    assert enrich_asset(db, row)["is_dividend"] is False
    db.execute("INSERT INTO dividends VALUES ('a','2025-02-01',12)")
    assert enrich_asset(db, row)["is_dividend"] is False
    db.execute("INSERT INTO dividends VALUES ('a','2024-02-01',3)")
    result = enrich_asset(db, row)
    assert result["is_dividend"] is True
    assert result["dividend_average_yield"] == 5


def test_missing_dividend_yield_does_not_fabricate_a_high_yield():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        "CREATE TABLE dividend_imports(asset_id,first_date,last_date); CREATE TABLE dividends(asset_id,date,yield_percent);"
    )
    db.execute("INSERT INTO dividend_imports VALUES ('a','2025-01-01','2026-01-01')")
    db.execute("INSERT INTO dividends VALUES ('a','2025-02-01',NULL)")
    assert (
        enrich_asset(db, {"id": "a", "category": "stock"})["dividend_average_yield"]
        is None
    )


def test_brazil_uses_nominal_treasury_yield_nearest_ten_year_maturity():
    payload = (
        b"Tipo Titulo;Data Base;Data Vencimento;Taxa Compra Manha\n"
        b"Tesouro Prefixado;01/01/2026;01/01/2036;13,5\n"
        b"Tesouro Prefixado;01/01/2026;01/01/2029;14,2\n"
        b"Tesouro IPCA+;01/01/2026;01/01/2036;7,0\n"
    )
    assert parse_brazil(payload) == [("br-tesouro-prefixado", "2026-01-01", 13.5)]
    assert visible_asset({"category": "bond", "country_code": "BR"})
