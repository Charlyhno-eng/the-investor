"""Read-only asset library and historical data endpoints."""

from datetime import date

from fastapi import APIRouter, HTTPException

from investor.assets.metadata import enrich_asset, visible_asset
from investor.db import connect
from investor.imports.catalog import REMOVED_CRYPTO

router = APIRouter(prefix="/api", tags=["assets"])


@router.get("/assets")
def assets():
    with connect() as db:
        return [
            enrich_asset(db, row)
            for row in db.execute(
                """
          WITH ranking AS (
            SELECT MAX(o.date) AS end_date FROM observations o JOIN assets a ON a.id=o.asset_id
            WHERE a.category='bond' AND a.country_code IS NOT NULL
          ), annual AS (
            SELECT o.asset_id, AVG(o.value) AS average_yield, COUNT(*) AS samples
            FROM observations o JOIN assets a ON a.id=o.asset_id CROSS JOIN ranking r
            WHERE a.category='bond' AND o.date > date(r.end_date, '-1 year')
            GROUP BY o.asset_id
          )
          SELECT a.*, COUNT(o.date) AS points,
            MIN(o.date) AS first_date, MAX(o.date) AS last_date,
            (SELECT value FROM observations WHERE asset_id=a.id ORDER BY date DESC LIMIT 1) AS last_value,
            y.average_yield AS year_average_yield, COALESCE(y.samples,0) AS year_yield_samples,
            r.end_date AS bond_ranking_date
          FROM assets a JOIN observations o ON o.asset_id=a.id
          LEFT JOIN annual y ON y.asset_id=a.id CROSS JOIN ranking r
          WHERE (a.category != 'bond' OR a.country_code IS NOT NULL)
            AND a.id NOT IN (?, ?)
          GROUP BY a.id ORDER BY a.category, y.average_yield DESC, a.name
          """,
                REMOVED_CRYPTO,
            )
            if visible_asset(row)
        ]


@router.get("/assets/{asset_id}/dividends")
def dividends(asset_id: str):
    with connect() as db:
        asset = db.execute(
            "SELECT category,unit FROM assets WHERE id=?", (asset_id,)
        ).fetchone()
        if not asset:
            raise HTTPException(404, "Actif introuvable")
        if asset["category"] != "stock":
            raise HTTPException(422, "Les dividendes concernent les actions uniquement")
        coverage = db.execute(
            "SELECT * FROM dividend_imports WHERE asset_id=?", (asset_id,)
        ).fetchone()
        events = [
            dict(row)
            for row in db.execute(
                "SELECT date AS time,amount,yield_percent FROM dividends WHERE asset_id=? ORDER BY date",
                (asset_id,),
            )
        ]
        return {
            "currency": asset["unit"],
            "coverage": dict(coverage) if coverage else None,
            "events": events,
        }


@router.get("/assets/{asset_id}/history")
def history(asset_id: str, start: date | None = None, end: date | None = None):
    if start and end and start > end:
        raise HTTPException(422, "La date de début doit précéder la date de fin")
    start_value = start.isoformat() if start else None
    end_value = end.isoformat() if end else None
    with connect() as db:
        if not db.execute("SELECT 1 FROM assets WHERE id=?", (asset_id,)).fetchone():
            raise HTTPException(404, "Actif introuvable")
        return [
            dict(row)
            for row in db.execute(
                "SELECT date AS time,value FROM observations WHERE asset_id=? AND (? IS NULL OR date>=?) AND (? IS NULL OR date<=?) ORDER BY date",
                (asset_id, start_value, start_value, end_value, end_value),
            )
        ]


@router.get("/assets/{asset_id}/comparison")
def asset_comparison(
    asset_id: str,
    start: date | None = None,
    end: date | None = None,
    reinvest: bool = True,
):
    from investor.assets.comparison import compare

    return compare(asset_id, start, end, reinvest)
