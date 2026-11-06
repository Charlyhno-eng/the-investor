"""Small cached discovery requests; price histories remain local and queued."""

import re
from threading import Lock
from time import monotonic

import yfinance as yf
from fastapi import HTTPException

from investor.db import connect

_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = Lock()


def search_stocks(query: str):
    key = query.strip().casefold()
    with connect() as db:
        local = [
            {
                "symbol": row["id"][3:].upper(),
                "name": row["name"],
                "exchange": "Bibliothèque locale",
                "imported": True,
            }
            for row in db.execute(
                "SELECT id,name FROM assets WHERE category='stock' AND source='yahoo'"
            )
        ]
    matches = [
        item
        for item in local
        if key in item["name"].casefold() or key in item["symbol"].casefold()
    ]
    try:
        with _lock:
            cached = _cache.get(key)
            if cached and monotonic() - cached[0] < 300:
                results = cached[1]
            else:
                quotes = yf.Search(
                    query.strip(),
                    max_results=12,
                    news_count=0,
                    lists_count=0,
                    timeout=8,
                ).quotes
                results = []
                for quote in quotes:
                    symbol = quote.get("symbol", "")
                    if quote.get("quoteType") != "EQUITY" or not re.fullmatch(
                        r"[A-Za-z0-9][A-Za-z0-9.\-]{0,23}", symbol
                    ):
                        continue
                    results.append(
                        {
                            "symbol": symbol,
                            "name": quote.get("longname")
                            or quote.get("shortname")
                            or symbol,
                            "exchange": quote.get("exchDisp")
                            or quote.get("exchange")
                            or "",
                        }
                    )
                if len(_cache) >= 128:
                    _cache.pop(next(iter(_cache)))
                _cache[key] = (monotonic(), results)
    except Exception as exc:
        if matches:
            return {
                "results": matches,
                "warning": "Recherche en ligne indisponible. Résultats de votre bibliothèque.",
            }
        raise HTTPException(
            503,
            "La recherche est indisponible. Réessayez ou saisissez un symbole exact.",
        ) from exc
    imported = {item["symbol"] for item in local}
    merged = {
        item["symbol"]: {**item, "imported": item["symbol"] in imported}
        for item in results
    }
    for item in matches:
        merged.setdefault(item["symbol"], item)
    return {"results": list(merged.values()), "warning": None}
