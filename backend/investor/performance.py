"""Observed portfolio comparison and constrained, retrospective allocation.

Both allocations use constant weights on observed dates, optionally reserving
cash before inception. Objectives: Sharpe, variance, compounded performance
and exact compounded maximum drawdown. No forecast is generated.
"""

import itertools
from datetime import date, timedelta
from typing import Literal

import numpy as np
from fastapi import HTTPException
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

from investor.db import connect
from investor.portfolio import PortfolioRequest, portfolio
from investor.volatility import buckets, load_histories


class PerformanceRequest(PortfolioRequest):
    mode: Literal["balanced", "volatility", "performance", "drawdown"] = "balanced"
    history: Literal["common", "extended"] = "common"


def optimize_weights(returns, current, mode="balanced"):
    """Long-only historical objectives; compounded drawdown uses convex cuts."""
    count = len(current)
    if count == 1:
        return current.copy()
    cap = 0.35 if count >= 3 else 1.0
    # An existing concentrated portfolio is a comparator, not a feasible solver seed.
    initial_weights = (
        current.copy() if np.max(current) <= cap else np.full(count, 1 / count)
    )
    covariance = np.atleast_2d(np.cov(returns, rowvar=False, ddof=1))
    scaled = covariance / max(float(np.max(np.diag(covariance))), 1e-12)
    means = returns.mean(axis=0)
    budget = {
        "type": "eq",
        "fun": lambda w: w.sum() - 1,
        "jac": lambda w: np.ones(count),
    }

    def solve(fun, jac, initial=initial_weights, constraints=None, bounds=None):
        with threadpool_limits(limits=1, user_api="blas"):
            result = minimize(
                fun,
                initial,
                jac=jac,
                bounds=bounds if bounds is not None else [(0, cap)] * count,
                constraints=constraints if constraints is not None else [budget],
                method="SLSQP",
                options={"ftol": 1e-12, "maxiter": 1500},
            )
        if not result.success or not np.all(np.isfinite(result.x)):
            raise HTTPException(
                503, "L’optimisation n’a pas convergé. Réessayez sur une autre période."
            )
        return result.x

    def minimum_variance():
        return solve(lambda w: float(w @ scaled @ w), lambda w: 2 * scaled @ w)

    if mode == "volatility":
        weights = minimum_variance()
    elif mode == "performance":
        # Maximizing log wealth is a concave maximization on the simplex.
        scale = max(float(np.max(np.abs(means))), 1e-4)
        weights = solve(
            lambda w: -float(np.log1p(returns @ w).mean()) / scale,
            lambda w: -(returns / (1 + returns @ w)[:, None]).mean(axis=0) / scale,
        )
    elif mode == "balanced":
        minimum = minimum_variance()
        best_mean = np.zeros(count)
        remaining = 1.0
        for i in np.argsort(-means):
            best_mean[i] = min(cap, remaining)
            remaining -= best_mean[i]
            if remaining <= 1e-12:
                break
        if means @ best_mean > 1e-12:
            # Positive Sharpe: min y'Σy subject to μ'y=1, y>=0, then w=y/sum(y).
            normalized = means / max(float(np.max(np.abs(means))), 1e-12)
            initial = best_mean / (normalized @ best_mean)
            allocation = solve(
                lambda y: float(y @ scaled @ y),
                lambda y: 2 * scaled @ y,
                initial=initial,
                constraints=[
                    {
                        "type": "eq",
                        "fun": lambda y: float(normalized @ y - 1),
                        "jac": lambda y: normalized,
                    },
                    {
                        "type": "ineq",
                        "fun": lambda y: cap * y.sum() - y,
                        "jac": lambda y: cap * np.ones((count, count)) - np.eye(count),
                    },
                ],
                bounds=[(0, None)] * count,
            )
            weights = allocation / allocation.sum()
        else:
            # For nonpositive means the best defined ratio is attained at a vertex;
            # include the zero-risk solution, whose zero mean has neutral utility.
            candidates = [initial_weights, minimum, best_mean]

            def score(w):
                risk = float(np.sqrt(max(0, w @ covariance @ w)))
                mean = float(means @ w)
                return (
                    mean / risk
                    if risk > 1e-12
                    else (0 if abs(mean) < 1e-12 else -np.inf)
                )

            if cap == 1:
                candidates.extend(np.eye(count))
            else:
                incumbent = max(candidates, key=score)
                incumbent_score = score(incumbent)
                # Vertices of the 35%-capped simplex: 35%, 35%, 30%.
                # Evaluate the third component in vector form for each pair.
                diagonal = np.diag(covariance)
                rest = 1 - 2 * cap
                for i, j in itertools.combinations(range(count), 2):
                    variances = (
                        cap**2 * (diagonal[i] + diagonal[j] + 2 * covariance[i, j])
                        + rest**2 * diagonal
                        + 2 * cap * rest * (covariance[i] + covariance[j])
                    )
                    risks = np.sqrt(np.maximum(variances, 0))
                    means_at_vertices = cap * (means[i] + means[j]) + rest * means
                    scores = np.divide(
                        means_at_vertices,
                        risks,
                        out=np.full(count, -np.inf),
                        where=risks > 1e-12,
                    )
                    scores[(risks <= 1e-12) & (np.abs(means_at_vertices) < 1e-12)] = 0
                    scores[[i, j]] = -np.inf
                    k = int(np.argmax(scores))
                    if k not in (i, j) and scores[k] > incumbent_score:
                        incumbent = np.zeros(count)
                        incumbent[[i, j, k]] = [cap, cap, rest]
                        incumbent_score = float(scores[k])
                candidates.append(incumbent)
            weights = max(candidates, key=score)
    elif mode == "drawdown":
        weights = _minimum_drawdown(returns, initial_weights, solve, cap)
    else:
        raise ValueError("Mode d’optimisation inconnu")
    if np.max(weights) > cap + 1e-7 or np.min(weights) < -1e-7:
        raise HTTPException(503, "Le plafond de concentration n’a pas été respecté.")
    weights = np.clip(weights, 0, cap)
    if not np.isfinite(weights.sum()) or abs(weights.sum() - 1) > 1e-7:
        raise HTTPException(503, "Pondérations invalides après optimisation.")
    weights /= weights.sum()
    if np.max(weights) > cap + 1e-8:
        raise HTTPException(503, "Le plafond de concentration n’a pas été respecté.")
    return weights


def _minimum_drawdown(returns, current, solve, cap=1.0):
    """Cutting-plane epigraph of max peak-to-trough log loss (convex).

    Every interval loss is convex in w. Add the actual worst interval until
    the epigraph lower bound meets the exact compounded path drawdown.
    """
    count = len(current)

    def worst(w):
        logwealth = np.r_[0.0, np.cumsum(np.log1p(returns @ w))]
        peaks = np.maximum.accumulate(logwealth)
        trough = int(np.argmax(peaks - logwealth))
        peak = int(np.argmax(logwealth[: trough + 1]))
        return float(peaks[trough] - logwealth[trough]), (peak, trough)

    weights = current.copy()
    cuts = []
    bound = 0.0
    for _ in range(150):
        loss, interval = worst(weights)
        if loss - bound <= 1e-8:
            return weights
        if interval in cuts:
            break
        cuts.append(interval)

        def constraints(x):
            logs = np.log1p(returns @ x[:-1])
            return np.array([x[-1] + logs[a:b].sum() for a, b in cuts])

        def gradients(x):
            gradients = returns / (1 + returns @ x[:-1])[:, None]
            return np.array([np.r_[gradients[a:b].sum(axis=0), 1] for a, b in cuts])

        x = solve(
            lambda x: float(x[-1]),
            lambda x: np.r_[np.zeros(count), 1.0],
            initial=np.r_[weights, loss],
            constraints=[
                {
                    "type": "eq",
                    "fun": lambda x: x[:-1].sum() - 1,
                    "jac": lambda x: np.r_[np.ones(count), 0],
                },
                {"type": "ineq", "fun": constraints, "jac": gradients},
            ],
            bounds=[(0, cap)] * count + [(0, None)],
        )
        weights, bound = x[:-1], float(x[-1])
        if constraints(x).min() < -1e-7:
            break
    raise HTTPException(
        503,
        "La minimisation du drawdown n’a pas convergé. Réduisez la période ou réessayez.",
    )


def comparison_data(
    assets,
    histories,
    benchmark,
    positions,
    years,
    optimize=False,
    mode="balanced",
    history="common",
):
    monthly = any(a["frequency"] == "monthly" for a in assets)
    histories = [buckets(h, monthly) for h in [*histories, benchmark]]
    if any(not h for h in histories):
        return {
            "status": "insufficient",
            "message": "Un actif ne dispose d’aucun historique comparable en EUR.",
        }
    latest = min(max(h) for h in histories)
    cutoff = (
        date.fromisoformat(latest) - timedelta(days=int(years * 365.25))
    ).isoformat()
    first_dates = [min(h) for h in histories[:-1]]
    if history == "extended":
        # Only cash before inception. Missing observations AFTER inception are
        # excluded, never converted into zero asset returns or forward-filled.
        common = [
            d
            for d in sorted(histories[-1])
            if cutoff <= d <= latest
            and all(
                d < first or d in h for first, h in zip(first_dates, histories[:-1])
            )
        ]
    else:
        common = [
            d
            for d in sorted(set.intersection(*(set(h) for h in histories)))
            if cutoff <= d <= latest
        ]
    minimum = 12 if monthly else 21
    if len(common) - 1 < minimum or any(
        sum(d in h for d in common) < minimum + 1 for h in histories[:-1]
    ):
        return {
            "status": "insufficient",
            "message": f"Il faut au moins {minimum} variations {'mensuelles' if monthly else 'quotidiennes'} observées par actif sur cette période.",
        }
    returns = np.array(
        [
            [
                h[right] / h[left] - 1 if left in h and right in h else 0.0
                for h in histories
            ]
            for left, right in itertools.pairwise(common)
        ]
    )
    periods = 12 if monthly else 252
    current = np.array([p["weight"] for p in positions])
    recommended = optimize_weights(returns[:, :-1], current, mode) if optimize else None
    strategies = {"portfolio": returns[:, :-1] @ current, "benchmark": returns[:, -1]}
    if recommended is not None:
        strategies["optimized"] = returns[:, :-1] @ recommended
    curves, metrics = {}, {}
    for key, changes in strategies.items():
        curve = np.r_[100.0, 100 * np.cumprod(1 + changes)]
        if not np.all(np.isfinite(curve)):
            raise HTTPException(
                422, "Les valeurs de cette série dépassent les limites du calcul."
            )
        curves[key] = curve
        metrics[key] = {
            "total_return": float(curve[-1] / 100 - 1),
            "volatility": float(np.std(changes, ddof=1) * np.sqrt(periods)),
            "max_drawdown": float(np.min(curve / np.maximum.accumulate(curve) - 1)),
            "sharpe": float(changes.mean() / changes.std(ddof=1) * np.sqrt(periods))
            if changes.std(ddof=1) > 1e-12
            else None,
        }
    total = sum(p["value"] for p in positions)
    return {
        "status": "ready",
        "currency": "EUR",
        "mode": mode if optimize else None,
        "history": history,
        "requested_start": cutoff,
        "cash_until": [
            {"id": a["id"], "name": a["name"], "date": first}
            for a, first in zip(assets, first_dates)
            if history == "extended" and first > common[0]
        ],
        "start": common[0],
        "end": common[-1],
        "frequency": "monthly" if monthly else "daily",
        "observations": len(common) - 1,
        "equity": [
            {"time": d, **{key: float(curve[i]) for key, curve in curves.items()}}
            for i, d in enumerate(common)
        ],
        "metrics": metrics,
        "positions": [
            {
                **p,
                "recommended_weight": float(recommended[i])
                if recommended is not None
                else None,
                "recommended_quantity": float(total * recommended[i] / p["price"])
                if recommended is not None
                else None,
            }
            for i, p in enumerate(positions)
        ],
    }


def portfolio_performance(request: PerformanceRequest, optimize=False):
    valuation = portfolio(request)
    if valuation["status"] == "pending":
        return valuation
    # Never silently optimize a subset and redistribute an excluded holding's value.
    if valuation["excluded"]:
        return {
            "status": "insufficient",
            "message": "La comparaison complète nécessite un prix monétaire et un historique pour chaque position détenue.",
            "excluded": valuation["excluded"],
        }
    positions = valuation["positions"]
    if not positions:
        return {
            "status": "insufficient",
            "message": "Renseignez vos quantités dans Positions pour comparer votre portefeuille au S&P 500.",
        }
    with connect() as connection:
        assets = [
            connection.execute("SELECT * FROM assets WHERE id=?", (p["id"],)).fetchone()
            for p in positions
        ]
        loaded = load_histories(connection, assets)
        if loaded is None:
            return {"status": "pending"}
    histories, benchmark = loaded
    return comparison_data(
        assets,
        histories,
        benchmark,
        positions,
        request.years,
        optimize,
        mode=request.mode,
        history=request.history,
    )
