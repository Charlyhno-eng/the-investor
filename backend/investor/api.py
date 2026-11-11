"""Application assembly and import worker lifecycle."""

import asyncio
from contextlib import asynccontextmanager
from threading import Event, Thread

from fastapi import FastAPI

from investor.assets.router import router as assets_router
from investor.imports.router import router as imports_router
from investor.imports.runner import consume_imports
from investor.portfolio.router import router as portfolio_router
from investor.simulation.router import router as simulation_router


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
        await asyncio.to_thread(runner.join)


app = FastAPI(title="The Investor", version="0.1.0", lifespan=lifespan)
app.include_router(assets_router)
app.include_router(imports_router)
app.include_router(portfolio_router)
app.include_router(simulation_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
