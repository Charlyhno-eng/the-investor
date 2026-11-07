from contextlib import asynccontextmanager
from datetime import date
from threading import Event, Thread

from fastapi import FastAPI, HTTPException, Query

from investor.analysis.schemas import AnalysisRequest
from investor.analysis.service import analyze
from investor.db import connect
from investor.import_runner import consume_imports
from investor.market_api import router as market_router
from investor.market_catalog import REMOVED_CRYPTO
from investor.market_schemas import DividendStatusRequest
from investor.performance import PerformanceRequest
from investor.portfolio import PortfolioRequest, portfolio
from investor.regression import RegressionRequest, regression_deviations


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = Event()
    runner = Thread(
        target=consume_imports, args=(stop,), daemon=True, name="asset-imports"
    )
    runner.start()
    try:
        yield
    finally:
        stop.set()
        # Finish any in-flight transaction before shutting down.
        import asyncio

        await asyncio.to_thread(runner.join)


app = FastAPI(title="The Investor", version="0.1.0", lifespan=lifespan)
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
            {**dict(row), "is_dividend": bool(row["is_dividend"])}
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
        ]


@app.get("/api/assets/{asset_id}/dividends")
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


@app.patch("/api/assets/{asset_id}/dividend-status")
def dividend_status(asset_id: str, request: DividendStatusRequest):
    with connect() as db:
        asset = db.execute(
            "SELECT category FROM assets WHERE id=?", (asset_id,)
        ).fetchone()
        if not asset:
            raise HTTPException(404, "Actif introuvable")
        if asset["category"] != "stock":
            raise HTTPException(
                422, "Le marquage dividende concerne les actions uniquement"
            )
        db.execute(
            "UPDATE assets SET is_dividend=? WHERE id=?",
            (int(request.is_dividend), asset_id),
        )
    return {"id": asset_id, "is_dividend": request.is_dividend}


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


@app.get("/api/assets/{asset_id}/comparison")
def asset_comparison(
    asset_id: str,
    start: date | None = None,
    end: date | None = None,
    reinvest: bool = True,
):
    from investor.comparison import compare

    return compare(asset_id, start, end, reinvest)


@app.post("/api/portfolio/analytics")
def portfolio_analytics(request: PortfolioRequest):
    return portfolio(request)


@app.post("/api/portfolio/regression")
def portfolio_regression(request: RegressionRequest):
    return regression_deviations(request)


@app.get("/api/assets/{asset_id}/volatility")
def get_asset_volatility(asset_id: str, years: int = Query(default=3, ge=1, le=20)):
    from investor.volatility import asset_volatility

    return asset_volatility(asset_id, years)


@app.post("/api/portfolio/volatility")
def get_portfolio_volatility(request: PortfolioRequest):
    from investor.volatility import portfolio_volatility

    return portfolio_volatility(request)


@app.post("/api/portfolio/performance")
def get_portfolio_performance(request: PerformanceRequest):
    from investor.performance import portfolio_performance

    return portfolio_performance(request)


@app.post("/api/portfolio/optimize")
def optimize_portfolio(request: PerformanceRequest):
    from investor.performance import portfolio_performance

    return portfolio_performance(request, optimize=True)
