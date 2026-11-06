"""Local total-return comparisons. Provider requests run in the import worker."""

import math
import re
from datetime import date

import yfinance as yf
from fastapi import HTTPException

from investor import db

INDEX = "^SP500TR"


def import_reference(symbol):
    if symbol not in (INDEX, "^GSPC") and not re.fullmatch(r"[A-Z]{3}USD=X", symbol):
        raise ValueError("Référence non prise en charge")
    yf.set_tz_cache_location(str(db.DATA_DIR / "provider-cache"))
    ticker = yf.Ticker(symbol)
    frame = ticker.history(period="max", interval="1d", auto_adjust=False, timeout=30)
    metadata = ticker.get_history_metadata()
    expected = "INDEX" if symbol in (INDEX, "^GSPC") else "CURRENCY"
    if frame.empty or metadata.get("instrumentType") != expected:
        raise ValueError("Référence absente ou de type incorrect")
    rows = [
        (symbol, stamp.date().isoformat(), float(value))
        for stamp, value in frame["Close"].items()
        if math.isfinite(float(value)) and value > 0
    ]
    if not rows:
        raise ValueError("Référence sans observations valides")
    with db.connect() as connection:
        connection.executemany(
            "INSERT OR REPLACE INTO reference_observations VALUES (?,?,?)", rows
        )
        connection.execute(
            "INSERT OR REPLACE INTO reference_imports VALUES (?,strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
            (symbol,),
        )


def compare(
    asset_id: str,
    start: date | None = None,
    end: date | None = None,
    reinvest: bool = True,
):
    if start and end and start > end:
        raise HTTPException(422, "La date de début doit précéder la date de fin")
    with db.connect() as connection:
        asset = connection.execute(
            "SELECT * FROM assets WHERE id=?", (asset_id,)
        ).fetchone()
        if not asset:
            raise HTTPException(404, "Actif introuvable")
        if asset["metric"] == "yield" or asset["category"] == "bond":
            raise HTTPException(
                422, "Une série de taux ne mesure pas une performance totale."
            )
        currency = asset["unit"] if asset["category"] == "stock" else "USD"
        multiplier = 0.01 if currency == "GBp" else 1
        if currency == "GBp":
            currency = "GBP"
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise HTTPException(422, "Devise de l’actif non prise en charge.")
        index = INDEX if reinvest else "^GSPC"
        symbols = [index] + ([f"{currency}USD=X"] if currency != "USD" else [])
        if ensure_references(connection, symbols):
            return {"status": "pending"}
        lower = start.isoformat() if start else "0001-01-01"
        upper = end.isoformat() if end else "9999-12-31"
        table = "observations"
        if asset["category"] == "stock" and not reinvest:
            if ensure_prices(connection, asset):
                return {"status": "pending"}
            table = "price_observations"
        observations = connection.execute(
            f"SELECT date,value FROM {table} WHERE asset_id=? AND date>=? AND date<=? ORDER BY date",
            (asset_id, lower, upper),
        ).fetchall()
        refs = {
            row["date"]: row["value"]
            for row in connection.execute(
                "SELECT date,value FROM reference_observations WHERE symbol=?", (index,)
            )
        }
        fx = (
            None
            if currency == "USD"
            else {
                row["date"]: row["value"]
                for row in connection.execute(
                    "SELECT date,value FROM reference_observations WHERE symbol=?",
                    (symbols[1],),
                )
            }
        )
        aligned = [
            (
                row["date"],
                row["value"] * multiplier * (fx[row["date"]] if fx is not None else 1),
                refs[row["date"]],
            )
            for row in observations
            if row["date"] in refs and (fx is None or row["date"] in fx)
        ]
        if len(aligned) < 2:
            raise HTTPException(
                422, "Pas assez de dates communes sur cette période (deux au minimum)."
            )
        if any(
            not math.isfinite(a) or a <= 0 or not math.isfinite(b) or b <= 0
            for _, a, b in aligned
        ):
            raise HTTPException(
                422, "La comparaison nécessite des prix strictement positifs."
            )
        base_asset, base_index = aligned[0][1:]
        return {
            "status": "ready",
            "currency": "USD",
            "equity": [
                {
                    "time": day,
                    "strategy": a / base_asset * 100,
                    "benchmark": b / base_index * 100,
                }
                for day, a, b in aligned
            ],
            "asset_return": aligned[-1][1] / base_asset - 1,
            "index_return": aligned[-1][2] / base_index - 1,
            "start": aligned[0][0],
            "end": aligned[-1][0],
            "converted": currency != "USD",
            "dividends_reinvested": reinvest and asset["category"] == "stock",
            "reinvest": reinvest,
            "price_proxy": asset["category"] == "commodity",
        }


def ensure_references(connection, symbols):
    pending = False
    for symbol in symbols:
        available = connection.execute(
            "SELECT 1 FROM reference_imports WHERE symbol=? AND updated_at > strftime('%Y-%m-%dT%H:%M:%SZ','now','-1 day')",
            (symbol,),
        ).fetchone()
        if available:
            continue
        job = connection.execute(
            "SELECT status,updated_at FROM import_jobs WHERE symbol=? AND category='reference' ORDER BY id DESC LIMIT 1",
            (symbol,),
        ).fetchone()
        if job and job["status"] == "failed":
            # A new request can retry after a short provider cooldown.
            recent = connection.execute(
                "SELECT ? > strftime('%Y-%m-%dT%H:%M:%SZ','now','-5 minutes')",
                (job["updated_at"],),
            ).fetchone()[0]
            if recent:
                raise HTTPException(
                    503,
                    "Une référence de marché ou un taux de change est indisponible. Réessayez dans quelques minutes.",
                )
        if not job or job["status"] not in ("queued", "running"):
            connection.execute(
                "INSERT INTO import_jobs(symbol,category) SELECT ?, 'reference' WHERE NOT EXISTS (SELECT 1 FROM import_jobs WHERE symbol=? AND status IN ('queued','running'))",
                (symbol, symbol),
            )
        pending = True
    return pending


def ensure_prices(connection, asset):
    if connection.execute(
        "SELECT 1 FROM price_observations WHERE asset_id=? LIMIT 1", (asset["id"],)
    ).fetchone():
        return False
    if not asset["id"].startswith("yf-"):
        raise HTTPException(422, "Prix hors dividendes indisponibles pour cet actif.")
    symbol = asset["id"][3:].upper()
    job = connection.execute(
        "SELECT status,updated_at FROM import_jobs WHERE symbol=? ORDER BY id DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    if (
        job
        and job["status"] == "failed"
        and connection.execute(
            "SELECT ? > strftime('%Y-%m-%dT%H:%M:%SZ','now','-5 minutes')",
            (job["updated_at"],),
        ).fetchone()[0]
    ):
        raise HTTPException(
            503, "Prix hors dividendes indisponibles. Réessayez dans quelques minutes."
        )
    connection.execute(
        "INSERT INTO import_jobs(symbol,category) SELECT ?,'stock' WHERE NOT EXISTS (SELECT 1 FROM import_jobs WHERE symbol=? AND status IN ('queued','running'))",
        (symbol, symbol),
    )
    return True
