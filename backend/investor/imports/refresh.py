"""Durable, deduplicated refreshes shared by the API and optional worker."""

from investor import db
from investor.countries import COUNTRIES, series_for
from investor.imports.catalog import (
    COMMODITY_FUTURES,
    CRYPTO,
    CURRENCIES,
    ETF,
    REMOVED_ETF,
)


def schedule_refreshes(*, seed=False):
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        symbols = {}
        for row in connection.execute("SELECT * FROM assets"):
            if row["id"] in REMOVED_ETF:
                symbols["ESE.PA"] = ("etf", "yahoo:ESE.PA", 1)
                continue
            if row["source"] == "yahoo" and row["id"].startswith("yf-"):
                symbol = row["id"][3:].upper()
                if row["category"] != "crypto" or symbol in CRYPTO:
                    symbols[symbol] = (row["category"], f"yahoo:{symbol}", 1)
            elif row["country_code"] in COUNTRIES and row["source"] in (
                "oecd-fred",
                "tesouro-direto",
            ):
                code = row["country_code"]
                source = (
                    "tesouro-direto" if code == "BR" else f"fred:{series_for(code)}"
                )
                symbols[code] = ("sovereign", source, 1 if code == "BR" else 6)
        for symbol, (asset_id, *_rest) in COMMODITY_FUTURES.items():
            if (
                seed
                or connection.execute(
                    "SELECT 1 FROM assets WHERE id=?", (asset_id,)
                ).fetchone()
            ):
                symbols[symbol] = ("commodity", f"yahoo:{symbol}", 1)
        if seed:
            for category, catalogue in (
                ("crypto", CRYPTO),
                ("etf", ETF),
                ("currency", CURRENCIES),
            ):
                for symbol in catalogue:
                    symbols[symbol] = (category, f"yahoo:{symbol}", 1)
            for code in COUNTRIES:
                source = (
                    "tesouro-direto" if code == "BR" else f"fred:{series_for(code)}"
                )
                symbols[code] = ("sovereign", source, 1 if code == "BR" else 6)
        candidates = list(symbols.items()) + [
            (row["symbol"], ("reference", None, 1))
            for row in connection.execute("SELECT symbol FROM reference_imports")
        ]

        for symbol, (category, source, hours) in candidates:
            # Successful checks govern frequency, even when the exchange is closed.
            table, key, stamp = (
                ("reference_imports", "symbol", "updated_at")
                if category == "reference"
                else ("imports", "source", "completed_at")
            )
            if connection.execute(
                f"SELECT 1 FROM {table} WHERE {key}=? AND {stamp} > "
                "strftime('%Y-%m-%dT%H:%M:%SZ','now',?)",
                (symbol if source is None else source, f"-{hours} hours"),
            ).fetchone():
                continue
            # Back off after failures; restart and multiple consumers cannot bypass it.
            connection.execute(
                "INSERT INTO import_jobs(symbol,category) SELECT ?,? WHERE NOT EXISTS "
                "(SELECT 1 FROM import_jobs WHERE symbol=? AND "
                "(status IN ('queued','running') OR (category=? AND "
                "updated_at > strftime('%Y-%m-%dT%H:%M:%SZ','now','-5 minutes'))))",
                (symbol, category, symbol, category),
            )
