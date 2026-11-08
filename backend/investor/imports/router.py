"""Local durable import queue and cached stock discovery."""

from fastapi import APIRouter, HTTPException, Query

from investor.db import connect
from investor.imports.catalog import CRYPTO
from investor.imports.schemas import ImportRequest
from investor.imports.search import search_stocks

router = APIRouter(prefix="/api")


@router.post("/asset-imports", status_code=202)
def enqueue(request: ImportRequest):
    symbol = request.symbol.upper()
    if request.category == "crypto" and symbol not in CRYPTO:
        raise HTTPException(422, "Crypto non prise en charge.")
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        asset = db.execute(
            "SELECT id,category FROM assets WHERE id=?", ("yf-" + symbol.lower(),)
        ).fetchone()
        if asset:
            if asset["category"] != request.category:
                raise HTTPException(422, "Ce symbole existe dans une autre catégorie.")
            return {"status": "completed", "asset_id": asset["id"], "id": None}
        job = db.execute(
            "SELECT * FROM import_jobs WHERE symbol=? AND status IN ('queued','running')",
            (symbol,),
        ).fetchone()
        if job:
            if job["category"] != request.category:
                raise HTTPException(
                    422,
                    "Ce symbole est déjà en cours d’import dans une autre catégorie.",
                )
            return dict(job)
        pending = db.execute(
            "SELECT COUNT(*) FROM import_jobs WHERE status IN ('queued','running')"
        ).fetchone()[0]
        if pending >= 50:
            raise HTTPException(429, "La file d’import est pleine.")
        cursor = db.execute(
            "INSERT INTO import_jobs(symbol,category) VALUES (?,?)",
            (symbol, request.category),
        )
        return dict(
            db.execute(
                "SELECT * FROM import_jobs WHERE id=?", (cursor.lastrowid,)
            ).fetchone()
        )


@router.get("/asset-imports/{job_id}")
def import_status(job_id: int):
    with connect() as db:
        job = db.execute("SELECT * FROM import_jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        raise HTTPException(404, "Import introuvable")
    return dict(job)


@router.get("/stocks/search")
def stock_search(q: str = Query(min_length=2, max_length=80)):
    if len(q.strip()) < 2:
        raise HTTPException(422, "Saisissez au moins deux caractères.")
    return search_stocks(q)


@router.get("/imports")
def imports():
    with connect() as db:
        return [
            dict(row) for row in db.execute("SELECT * FROM imports ORDER BY source")
        ]
