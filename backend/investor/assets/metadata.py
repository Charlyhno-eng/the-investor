"""Derived library metadata; the API never contacts a market provider."""

from datetime import date

from investor.countries import COUNTRIES
from investor.imports.catalog import COMMODITIES, COMMODITY_FUTURES


def history_revision(db, row):
    asset = dict(row)
    source = asset["source"]
    if source == "yahoo":
        symbol = next(
            (s for s, values in COMMODITY_FUTURES.items() if values[0] == asset["id"]),
            asset["id"][3:].upper(),
        )
        source = f"yahoo:{symbol}"
    elif source == "oecd-fred":
        source = f"fred:{asset['id']}"
    imported = db.execute(
        "SELECT completed_at FROM imports WHERE source=?", (source,)
    ).fetchone()
    return f"{imported[0] if imported else ''}:{asset.pop('reference_updated_at', None) or ''}"


def enrich_asset(db, row):
    asset = dict(row)
    asset["is_dividend"] = False
    asset["dividend_average_yield"] = None
    if asset["category"] == "stock":
        coverage = db.execute(
            "SELECT * FROM dividend_imports WHERE asset_id=?", (asset["id"],)
        ).fetchone()
        if coverage:
            end_year = date.fromisoformat(coverage["last_date"]).year
            annual = []
            for year in range(end_year - 3, end_year):
                start, end = f"{year}-01-01", f"{year}-12-31"
                if coverage["first_date"] <= start and coverage["last_date"] >= end:
                    events = db.execute(
                        "SELECT yield_percent FROM dividends WHERE asset_id=? AND date BETWEEN ? AND ?",
                        (asset["id"], start, end),
                    ).fetchall()
                    if all(e["yield_percent"] is not None for e in events):
                        annual.append(sum(e["yield_percent"] for e in events))
            if annual:
                asset["dividend_average_yield"] = sum(annual) / len(annual)
                asset["is_dividend"] = asset["dividend_average_yield"] > 4
    return asset


def visible_asset(row):
    if row["category"] == "commodity":
        return row["id"] in COMMODITIES and row["frequency"] == "daily"
    if row["category"] == "bond":
        return row["country_code"] in COUNTRIES
    return True
