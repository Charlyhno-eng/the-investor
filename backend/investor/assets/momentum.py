"""Descriptive multi-horizon momentum, using only local adjusted observations."""

import calendar
import math
from datetime import date, timedelta

import numpy as np
from fastapi import HTTPException

from investor.assets.comparison import INDEX, ensure_references
from investor.db import connect

HORIZONS = (36, 12, 6)


def months_before(day: date, months: int) -> date:
    total = day.year * 12 + day.month - 1 - months
    year, month = divmod(total, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def analyze(points, reference, as_of, months, *, include_rows=True):
    start, end = months_before(as_of, months), months_before(as_of, 1)
    # Exact shared dates, with at most seven calendar days of endpoint slippage.
    rows = [
        (d, v, reference[d]) for d, v in points if start <= d <= end and d in reference
    ]
    if (
        len(rows) < 60
        or (rows[0][0] - start).days > 7
        or (end - rows[-1][0]).days > 7
        or any(not math.isfinite(v) or v <= 0 for _, a, b in rows for v in (a, b))
        # A fortnight accommodates long exchange holidays (e.g. Taiwan).
        or any((b[0] - a[0]).days > 14 for a, b in zip(rows, rows[1:], strict=False))
    ):
        return {
            "months": months,
            "error": "Historique commun insuffisant ou discontinu.",
        }
    x = np.array([(d - rows[0][0]).days / 365.25 for d, _, _ in rows])
    y = np.log([v for _, v, _ in rows])
    centered = x - x.mean()
    slope = float(np.dot(centered, y - y.mean()) / np.dot(centered, centered))
    predicted = y.mean() + slope * centered
    residuals = y - predicted
    sse = float(np.dot(residuals, residuals))
    total = float(np.dot(y - y.mean(), y - y.mean()))
    r2 = max(0, min(1, 1 - sse / total)) if total > 1e-20 else 0
    sigma = math.sqrt(sse / (len(rows) - 2))
    duration = float(x[-1])
    log_return = math.log(rows[-1][1] / rows[0][1])
    relative_log = log_return - math.log(rows[-1][2] / rows[0][2])
    # Bounded signed components: a smooth decline cannot earn a bullish score.
    strength = (
        0.4 * math.tanh(log_return / duration / 0.3)
        + 0.3 * math.tanh(slope / 0.3)
        + 0.3 * math.tanh(relative_log / duration / 0.2)
    )
    quality = math.sqrt(r2) / (1 + sigma / 0.1)
    score = 50 + 50 * strength * quality
    return {
        "months": months,
        "start": rows[0][0].isoformat(),
        "end": rows[-1][0].isoformat(),
        "observations": len(rows),
        "performance": math.expm1(log_return),
        "annual_performance": math.expm1(log_return / duration),
        "annual_trend": math.expm1(slope),
        "slope": slope,
        "r2": r2,
        "sigma": sigma,
        "relative_performance": math.expm1(relative_log),
        "score": score,
        "rows": [
            {
                "time": d.isoformat(),
                "value": v,
                "trend": float(math.exp(p)),
                "residual": float(r),
            }
            for (d, v, _), p, r in zip(rows, predicted, residuals, strict=True)
        ]
        if include_rows
        else [],
    }


def momentum(asset_id=None, benchmark=None, category="stock"):
    """One date and benchmark per asset class, using native percentage returns."""
    with connect() as db:
        if asset_id is not None:
            asset = db.execute(
                "SELECT * FROM assets WHERE id=?", (asset_id,)
            ).fetchone()
            if not asset:
                raise HTTPException(404, "Actif introuvable")
            if asset["category"] not in ("stock", "crypto"):
                raise HTTPException(
                    422, "Le momentum concerne les actions et les cryptomonnaies"
                )
            category = asset["category"]
            if not db.execute(
                "SELECT 1 FROM observations WHERE asset_id=? LIMIT 1", (asset_id,)
            ).fetchone():
                raise HTTPException(422, "Aucun historique disponible")
        latest = db.execute(
            "SELECT MAX(o.date) FROM observations o JOIN assets a ON a.id=o.asset_id WHERE a.category=?",
            (category,),
        ).fetchone()[0]
        if latest is None:
            return {"status": "ready", "as_of": None, "universe": []}
        as_of = date.fromisoformat(latest)
        lower = months_before(as_of, max(HORIZONS)).isoformat()
        benchmarks = [
            dict(row)
            for row in db.execute(
                "SELECT id,name FROM assets WHERE category=? ORDER BY name",
                ("crypto" if category == "crypto" else "etf",),
            )
        ]
        symbol = benchmark or ("BTC-USD" if category == "crypto" else INDEX)
        if symbol == "BTC-USD" and category == "crypto":
            local_btc = db.execute(
                "SELECT id FROM assets WHERE category='crypto' AND id='yf-btc-usd'"
            ).fetchone()
            if local_btc:
                symbol = local_btc["id"]
        if symbol in (INDEX, "^FCHI", "BTC-USD"):
            if ensure_references(db, [symbol]):
                return {"status": "pending"}
            reference = {
                date.fromisoformat(r["date"]): r["value"]
                for r in db.execute(
                    "SELECT date,value FROM reference_observations WHERE symbol=? AND date>=? AND date<=?",
                    (symbol, lower, latest),
                )
            }
            reference_name = {
                INDEX: "S&P 500 · dividendes réinvestis",
                "^FCHI": "CAC 40 · hors dividendes",
                "BTC-USD": "Bitcoin",
            }[symbol]
        else:
            chosen = next((b for b in benchmarks if b["id"] == symbol), None)
            if chosen is None:
                raise HTTPException(422, "Référence momentum inconnue")
            reference = {
                date.fromisoformat(r["date"]): r["value"]
                for r in db.execute(
                    "SELECT date,value FROM observations WHERE asset_id=? AND date>=? AND date<=?",
                    (symbol, lower, latest),
                )
            }
            reference_name = chosen["name"]
        universe = []
        selected = {}
        for stock in db.execute(
            "SELECT id,name FROM assets WHERE category=? ORDER BY name", (category,)
        ).fetchall():
            points = [
                (date.fromisoformat(r["date"]), r["value"])
                for r in db.execute(
                    "SELECT date,value FROM observations WHERE asset_id=? AND date>=? AND date<=? ORDER BY date",
                    (stock["id"], lower, latest),
                )
            ]
            horizons = [
                analyze(
                    points, reference, as_of, h, include_rows=stock["id"] == asset_id
                )
                for h in HORIZONS
            ]
            eligible = bool(
                points
                and (as_of - points[-1][0]) <= timedelta(days=7)
                and any("score" in h for h in horizons)
            )
            reason = (
                None
                if eligible
                else (
                    "Dernière cotation trop ancienne."
                    if points and (as_of - points[-1][0]).days > 7
                    else "Aucun horizon exploitable parmi 36, 12 et 6 mois."
                )
            )
            universe.append(
                {
                    "id": stock["id"],
                    "name": stock["name"],
                    "scores": [h.get("score") for h in horizons] if eligible else None,
                    "reason": reason,
                    "partial": eligible and any("score" not in h for h in horizons),
                    "available_horizons": [
                        h["months"] for h in horizons if "score" in h
                    ]
                    if eligible
                    else [],
                }
            )
            if stock["id"] == asset_id:
                end = months_before(as_of, 1)
                prior = next((v for d, v in reversed(points) if d <= end), None)
                valid = [v for _, v in points if math.isfinite(v) and v > 0]
                selected = {
                    "horizons": horizons,
                    "recent_return": points[-1][1] / prior - 1
                    if prior and points
                    else None,
                    "drawdown": points[-1][1] / max(valid) - 1
                    if valid and points
                    else None,
                }
        return {
            "status": "ready",
            "category": category,
            "as_of": latest,
            "benchmark_name": reference_name,
            "universe": universe,
            **selected,
        }
