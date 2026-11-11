"""Valuation of current quantities and correlations of aligned USD returns."""

import math
from datetime import date, timedelta
from typing import Literal

import numpy as np
from fastapi import HTTPException
from pydantic import BaseModel, Field

from investor.assets.comparison import ensure_prices, ensure_references
from investor.db import connect


class Holding(BaseModel):
    asset_id: str = Field(min_length=1, max_length=120)
    quantity: float = Field(ge=0, le=1e15, allow_inf_nan=False)


class PortfolioRequest(BaseModel):
    locked_asset_ids: list[str] = Field(default_factory=list, max_length=1000)
    holdings: list[Holding] = Field(max_length=1000)
    years: int = Field(default=3, ge=1, le=20)
    include_benchmark: bool = False
    include_correlation: bool = True
    currency: Literal["EUR"] = "EUR"


def portfolio(request: PortfolioRequest):
    if len({h.asset_id for h in request.holdings}) != len(request.holdings):
        raise HTTPException(422, "Un actif ne peut figurer qu’une fois.")
    with connect() as connection:
        assets, excluded, symbols = [], [], set()
        pending = False
        for holding in request.holdings:
            if holding.quantity <= 0:
                continue
            asset = connection.execute(
                "SELECT * FROM assets WHERE id=?", (holding.asset_id,)
            ).fetchone()
            if not asset:
                raise HTTPException(404, "Actif introuvable : " + holding.asset_id)
            if asset["category"] == "bond":
                excluded.append(
                    {
                        "id": asset["id"],
                        "name": asset["name"],
                        "reason": "Taux souverain : aucun prix de titre disponible.",
                    }
                )
                continue
            currency = (
                asset["unit"]
                if asset["category"] in ("stock", "etf", "currency")
                else "USD"
            )
            if currency == "GBp":
                currency = "GBP"
            if currency != "USD":
                symbols.add(f"{currency}USD=X")
            if asset["category"] in ("stock", "etf"):
                pending = ensure_prices(connection, asset) or pending
            assets.append((asset, holding.quantity, currency))
        if assets and request.currency != "USD":
            symbols.add(f"{request.currency}USD=X")
        if assets and request.include_correlation and request.include_benchmark:
            symbols.add("^SP500TR")
        pending = (
            ensure_references(connection, sorted(symbols), allow_cached=True) or pending
        )
        if pending:
            return {"status": "pending"}
        positions, histories = [], []
        cutoff = (
            date.today() - timedelta(days=int(request.years * 365.25))
        ).isoformat()
        exchange_histories = {}
        for asset, quantity, currency in assets:
            if (
                request.include_correlation
                and currency != "USD"
                and currency not in exchange_histories
            ):
                exchange_histories[currency] = dict(
                    connection.execute(
                        "SELECT date,value FROM reference_observations WHERE symbol=?",
                        (f"{currency}USD=X",),
                    ).fetchall()
                )
            fx = exchange_histories.get(currency)
            multiplier = 0.01 if asset["unit"] == "GBp" else 1
            if request.include_correlation:
                adjusted = connection.execute(
                    "SELECT date,value FROM observations WHERE asset_id=? AND date>=? ORDER BY date",
                    (asset["id"], cutoff),
                ).fetchall()
                values = {
                    r["date"]: r["value"]
                    * multiplier
                    * (fx[r["date"]] if fx is not None else 1)
                    for r in adjusted
                    if r["value"] > 0 and (fx is None or r["date"] in fx)
                }
                histories.append(
                    (asset, {d: v for d, v in values.items() if math.isfinite(v)})
                )
            # A rate or index point is not a tradable unit and cannot be valued as shares.
            if asset["category"] == "commodity" and "2010=100" in asset["unit"]:
                excluded.append(
                    {
                        "id": asset["id"],
                        "name": asset["name"],
                        "reason": "Indice : pas de valeur monétaire par unité (corrélation disponible).",
                    }
                )
                continue
            table = (
                "price_observations"
                if asset["category"] in ("stock", "etf")
                else "observations"
            )
            row = connection.execute(
                f"SELECT date,value FROM {table} WHERE asset_id=? ORDER BY date DESC LIMIT 1",
                (asset["id"],),
            ).fetchone()
            if not row or row["value"] <= 0:
                excluded.append(
                    {
                        "id": asset["id"],
                        "name": asset["name"],
                        "reason": "Prix actuel indisponible.",
                    }
                )
                continue
            rate = 1.0
            if currency != "USD":
                fx_row = connection.execute(
                    "SELECT value FROM reference_observations WHERE symbol=? AND date=?",
                    (f"{currency}USD=X", row["date"]),
                ).fetchone()
                if (
                    fx_row is None
                    or not math.isfinite(fx_row["value"])
                    or fx_row["value"] <= 0
                ):
                    excluded.append(
                        {
                            "id": asset["id"],
                            "name": asset["name"],
                            "reason": "Change absent à la date du dernier prix.",
                        }
                    )
                    continue
                rate = fx_row["value"]
            price = row["value"] * multiplier * rate
            # Banque mondiale reports cents for some series.
            if asset["category"] == "commodity" and "cents" in asset["unit"]:
                price /= 100
            value = price * quantity
            if not math.isfinite(value):
                raise HTTPException(422, "Valeur de position trop grande.")
            exchange_rate, fx_date = 1.0, None
            if request.currency != "USD":
                # FX markets close on weekends; use a known rate, never a future one.
                fx_row = connection.execute(
                    "SELECT date,value FROM reference_observations "
                    "WHERE symbol=? AND date<=? AND date>=date(?,'-7 days') "
                    "AND value>0 ORDER BY date DESC LIMIT 1",
                    (f"{request.currency}USD=X", row["date"], row["date"]),
                ).fetchone()
                if fx_row is None or not math.isfinite(fx_row["value"]):
                    excluded.append(
                        {
                            "id": asset["id"],
                            "name": asset["name"],
                            "reason": f"Change {request.currency} indisponible à la date du prix (7 jours maximum).",
                        }
                    )
                    continue
                exchange_rate, fx_date = fx_row["value"], fx_row["date"]
            converted = value / exchange_rate
            if not math.isfinite(converted):
                raise HTTPException(422, "Valeur de position trop grande.")
            positions.append(
                {
                    "id": asset["id"],
                    "name": asset["name"],
                    "quantity": quantity,
                    "price_usd": price,
                    "value_usd": value,
                    "price": price / exchange_rate,
                    "value": converted,
                    "fx_date": fx_date,
                    "date": row["date"],
                }
            )
        total = sum(p["value"] for p in positions)
        for p in positions:
            p["weight"] = p["value"] / total if total > 0 else 0
        if histories and request.include_benchmark:
            benchmark = {
                r["date"]: r["value"]
                for r in connection.execute(
                    "SELECT date,value FROM reference_observations WHERE symbol='^SP500TR' AND date>=? AND value>0 ORDER BY date",
                    (cutoff,),
                )
                if math.isfinite(r["value"])
            }
            histories.insert(
                0,
                (
                    {"id": "^SP500TR", "name": "S&P 500", "frequency": "daily"},
                    benchmark,
                ),
            )
        monthly = any(a["frequency"] == "monthly" for a, _ in histories)
        if monthly:
            # Last actually observed price in each completed month; no forward fill.
            histories = [
                (
                    a,
                    {
                        d[:7]: v
                        for d, v in sorted(values.items())
                        if d[:7] < date.today().isoformat()[:7]
                    },
                )
                for a, values in histories
            ]
        common = (
            sorted(set.intersection(*(set(values) for _, values in histories)))
            if histories
            else []
        )
        returns = [
            np.diff(np.log([values[d] for d in common])) for _, values in histories
        ]
        count = max(0, len(common) - 1)
        minimum = 6 if monthly else 20
        # Compute valid pairs together: hundreds of assets must not trigger
        # hundreds of thousands of separate corrcoef/std calls.
        matrix = [[None] * len(returns) for _ in returns]
        valid = (
            [i for i, series in enumerate(returns) if np.std(series) >= 1e-12]
            if count >= minimum
            else []
        )
        if valid:
            coefficients = np.clip(
                np.atleast_2d(np.corrcoef([returns[i] for i in valid])), -1, 1
            )
            for i, values in zip(valid, coefficients.tolist(), strict=True):
                for j, value in zip(valid, values, strict=True):
                    matrix[i][j] = value
        return {
            "status": "ready",
            "currency": request.currency,
            "positions": positions,
            "total_usd": sum(p["value_usd"] for p in positions),
            "total": total,
            "excluded": excluded,
            "correlation": {
                "assets": [{"id": a["id"], "name": a["name"]} for a, _ in histories],
                "matrix": matrix,
                "observations": count,
                "minimum": minimum,
                "frequency": "monthly" if monthly else "daily",
                "start": common[0] if common else None,
                "end": common[-1] if common else None,
            }
            if request.include_correlation
            else None,
        }
