from datetime import date

from fastapi import FastAPI, HTTPException

from investor.analysis.schemas import AnalysisRequest
from investor.analysis.service import analyze
from investor.db import connect
from investor.market_api import router as market_router

app = FastAPI(title="The Investor", version="0.1.0")
app.include_router(market_router)


@app.post("/api/assets/{asset_id}/analysis")
def asset_analysis(asset_id: str, request: AnalysisRequest):
    return analyze(asset_id, request)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/assets")
def assets():
    with connect() as db:
        return [
            dict(row)
            for row in db.execute("""SELECT a.*, COUNT(o.date) AS points,
          MIN(o.date) AS first_date, MAX(o.date) AS last_date,
          (SELECT value FROM observations WHERE asset_id=a.id ORDER BY date DESC LIMIT 1) AS last_value
          FROM assets a JOIN observations o ON o.asset_id=a.id WHERE a.category != 'bond' OR a.country_code IS NOT NULL GROUP BY a.id ORDER BY a.category, a.name""")
        ]


@app.get("/api/assets/{asset_id}/history")
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


@app.get("/api/imports")
def imports():
    with connect() as db:
        return [
            dict(row) for row in db.execute("SELECT * FROM imports ORDER BY source")
        ]
