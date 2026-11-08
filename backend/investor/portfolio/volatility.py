"""Markowitz minimum-variance frontier on aligned historical EUR returns."""

import calendar
import math
from bisect import bisect_right
from datetime import date, timedelta

import numpy as np
from fastapi import HTTPException
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

from investor.assets.comparison import INDEX, ensure_references
from investor.db import connect
from investor.portfolio.service import PortfolioRequest, portfolio


def buckets(values, monthly):
    if not monthly:
        return dict(sorted(values.items()))
    result = {}
    for d, value in sorted(values.items()):
        if d[:7] < date.today().isoformat()[:7]:
            y, m = map(int, d[:7].split("-"))
            result[f"{d[:7]}-{calendar.monthrange(y, m)[1]:02d}"] = value
    return result


def observations(connection, asset):
    return {
        r["date"]: r["value"]
        for r in connection.execute(
            "SELECT date,value FROM observations WHERE asset_id=? ORDER BY date",
            (asset["id"],),
        )
        if math.isfinite(r["value"]) and r["value"] > 0
    }


def reference(connection, symbol):
    return {
        r["date"]: r["value"]
        for r in connection.execute(
            "SELECT date,value FROM reference_observations WHERE symbol=? AND value>0 ORDER BY date",
            (symbol,),
        )
        if math.isfinite(r["value"])
    }


def converted(values, fx, euro):
    """Use only FX known on the observation date, with a seven-day limit."""
    euro_dates = sorted(euro)
    fx_dates = sorted(fx) if fx is not None else []

    def rate(series, dates, day):
        i = bisect_right(dates, day) - 1
        if i < 0 or (date.fromisoformat(day) - date.fromisoformat(dates[i])).days > 7:
            return None
        return series[dates[i]]

    result = {}
    for d, value in values.items():
        eur = rate(euro, euro_dates, d)
        usd = 1 if fx is None else rate(fx, fx_dates, d)
        if eur and usd:
            result[d] = value * usd / eur
    return result


def coordinates(weights, means, covariance):
    weights = np.atleast_2d(weights)
    returns = weights @ means
    risks = np.sqrt(
        np.maximum(np.einsum("ij,jk,ik->i", weights, covariance, weights), 0)
    )
    return [
        {
            "return": float(r * 100),
            "volatility": float(v * 100),
            "sharpe": float(r / v) if v > 1e-12 else None,
        }
        for r, v in zip(returns, risks, strict=True)
    ]


def markowitz_frontier(means, covariance):
    """Long-only QP: min wᵀΣw, 1ᵀw=1, μᵀw=target.

    Return the efficient upper branch and the inefficient lower branch separately.
    No inverse or random allocations: singular covariance matrices are supported.
    """
    count = len(means)
    if count < 2:
        return [], []
    covariance = np.asarray(covariance, dtype=float)
    scaled = covariance / max(float(np.max(np.diag(covariance))), 1e-12)
    budget = {
        "type": "eq",
        "fun": lambda w: w.sum() - 1,
        "jac": lambda w: np.ones(count),
    }

    def solve(initial, constraints):
        with threadpool_limits(limits=1, user_api="blas"):
            result = minimize(
                lambda w: float(w @ scaled @ w),
                initial,
                jac=lambda w: 2 * scaled @ w,
                bounds=[(0, 1)] * count,
                constraints=constraints,
                method="SLSQP",
                options={"ftol": 1e-12, "maxiter": 500},
            )
        if (
            not result.success
            or not np.all(np.isfinite(result.x))
            or abs(result.x.sum() - 1) > 1e-7
            or np.min(result.x) < -1e-7
            or any(abs(c["fun"](result.x)) > 1e-7 for c in constraints)
        ):
            raise HTTPException(
                503,
                "Le calcul de la frontière de Markowitz n’a pas convergé. Réessayez.",
            )
        return result.x

    minimum = solve(np.full(count, 1 / count), [budget])
    minimum_return = float(means @ minimum)
    spread = float(np.ptp(means))
    if spread < 1e-10:
        # Equal expected returns: the efficient set collapses to the minimum-risk point.
        return coordinates(minimum, means, covariance), []
    normalized_means = (means - means.min()) / spread

    def branch(endpoint):
        targets = np.linspace(minimum_return, float(endpoint), 81)
        allocations = [minimum]
        for target in targets[1:]:
            normalized_target = float((target - means.min()) / spread)
            extreme = int(
                np.argmax(means) if endpoint > minimum_return else np.argmin(means)
            )
            alpha = (target - minimum_return) / (means[extreme] - minimum_return)
            initial = (1 - alpha) * minimum + alpha * np.eye(count)[extreme]
            constraint = {
                "type": "eq",
                "fun": lambda w, t=normalized_target: float(normalized_means @ w - t),
                "jac": lambda w: normalized_means,
            }
            # For two assets the two equalities determine weights analytically.
            allocation = initial if count == 2 else solve(initial, [budget, constraint])
            allocations.append(allocation)
        return coordinates(allocations, means, covariance)

    upper = (
        branch(means.max())
        if means.max() - minimum_return > 1e-10
        else coordinates(minimum, means, covariance)
    )
    lower = branch(means.min()) if minimum_return - means.min() > 1e-10 else []
    return upper, lower


def risk_map(assets, histories, benchmark, years, *, portfolio_view=False, locked=None):
    monthly = any(a["frequency"] == "monthly" for a in assets)
    histories = [buckets(h, monthly) for h in histories] + [buckets(benchmark, monthly)]
    common = sorted(set.intersection(*(set(h) for h in histories)))
    if common:
        cutoff = (
            date.fromisoformat(common[-1]) - timedelta(days=int(years * 365.25))
        ).isoformat()
        common = [d for d in common if d >= cutoff]
    minimum = 12 if monthly else 21
    if len(common) - 1 < minimum:
        return {
            "status": "insufficient",
            "message": f"Il faut au moins {minimum} variations {'mensuelles' if monthly else 'quotidiennes'} communes avec le S&P 500 sur cette période.",
        }
    prices = np.array([[h[d] for d in common] for h in histories])
    returns = np.diff(prices, axis=1) / prices[:, :-1]
    periods = 12 if monthly else 252
    means = returns.mean(axis=1) * periods
    covariance = np.atleast_2d(np.cov(returns, ddof=1)) * periods
    count = len(histories)
    individual = coordinates(np.eye(count), means, covariance)
    points = [
        {"id": a["id"], "name": a["name"], "kind": "asset", **p}
        for a, p in zip(assets, individual[:-1], strict=True)
    ]
    points.append(
        {"id": "sp500", "name": "S&P 500", "kind": "benchmark", **individual[-1]}
    )
    # The benchmark is a comparator, not a hidden addition to portfolio holdings.
    universe_means = means[:-1] if portfolio_view else means
    universe_covariance = covariance[:-1, :-1] if portfolio_view else covariance
    if locked:
        fixed = np.array([locked.get(i, 0) for i in range(len(assets))])
        free = [i for i in range(len(assets)) if i not in locked]
        if not free:
            frontier, lower_frontier = (
                coordinates(fixed, universe_means, universe_covariance),
                [],
            )
        else:
            # Every free-allocation vertex includes exactly the same locked holdings.
            vertices = np.tile(fixed, (len(free), 1))
            vertices[np.arange(len(free)), free] = 1 - fixed.sum()
            reduced_means = vertices @ universe_means
            reduced_covariance = vertices @ universe_covariance @ vertices.T
            frontier, lower_frontier = (
                markowitz_frontier(reduced_means, reduced_covariance)
                if len(free) > 1
                else (coordinates([1], reduced_means, reduced_covariance), [])
            )
    else:
        frontier, lower_frontier = (
            markowitz_frontier(universe_means, universe_covariance)
            if assets
            else ([], [])
        )
    return {
        "status": "ready",
        "currency": "EUR",
        "frequency": "monthly" if monthly else "daily",
        "annualization": periods,
        "observations": len(common) - 1,
        "start": common[0],
        "end": common[-1],
        "points": points,
        "frontier": frontier,
        "lower_frontier": lower_frontier,
        "frontier_assets": [a["id"] for a in assets]
        + ([] if portfolio_view or not assets else ["sp500"]),
    }


def load_histories(connection, assets):
    """Shared EUR total-return histories, with no interpolation or future FX.

    Stocks use observations (Yahoo Adj Close, distributions reinvested), never
    price_observations (raw share valuation). Do not add dividends again.
    """
    currencies = [
        a["unit"] if a["category"] in ("stock", "etf", "currency") else "USD"
        for a in assets
    ]
    currencies = ["GBP" if c == "GBp" else c for c in currencies]
    symbols = {INDEX, "EURUSD=X"} | {f"{c}USD=X" for c in currencies if c != "USD"}
    if ensure_references(connection, sorted(symbols)):
        return None
    euro = reference(connection, "EURUSD=X")
    histories = [
        converted(
            observations(connection, a),
            None if c == "USD" else reference(connection, f"{c}USD=X"),
            euro,
        )
        for a, c in zip(assets, currencies, strict=True)
    ]
    return histories, converted(reference(connection, INDEX), None, euro)


def load_map(connection, assets, years, *, portfolio_view=False, locked=None):
    loaded = load_histories(connection, assets)
    if loaded is None:
        return {"status": "pending"}
    histories, benchmark = loaded
    return risk_map(
        assets,
        histories,
        benchmark,
        years,
        portfolio_view=portfolio_view,
        locked=locked,
    )


def asset_volatility(asset_id, years=3):
    with connect() as connection:
        asset = connection.execute(
            "SELECT * FROM assets WHERE id=?", (asset_id,)
        ).fetchone()
        if not asset:
            raise HTTPException(404, "Actif introuvable")
        if asset["metric"] == "yield":
            # Keep a real benchmark visible without misrepresenting a yield as a price return.
            result = load_map(connection, [], years)
            return {
                **result,
                "excluded": [
                    {
                        "id": asset["id"],
                        "name": asset["name"],
                        "reason": "Taux souverain : aucun prix obligataire pour calculer un rendement comparable au S&P 500.",
                    }
                ],
            }
        return load_map(connection, [asset], years)


def portfolio_volatility(request: PortfolioRequest):
    valuation = portfolio(request)
    if valuation["status"] == "pending":
        return valuation
    positions = valuation["positions"]
    with connect() as connection:
        assets = [
            connection.execute("SELECT * FROM assets WHERE id=?", (p["id"],)).fetchone()
            for p in positions
        ]
        result = load_map(
            connection,
            assets,
            request.years,
            portfolio_view=True,
            locked={
                i: p["weight"]
                for i, p in enumerate(positions)
                if p["id"] in request.locked_asset_ids
            },
        )
    return {**result, "positions": positions, "excluded": valuation["excluded"]}
