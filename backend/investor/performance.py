"""Observed portfolio comparison and constrained, retrospective allocation.

Both allocations use constant weights on observed dates, optionally reserving
cash before inception. Objectives: Sharpe, variance, compounded performance,
exact compounded maximum drawdown and standardized correlation risk. No forecast is generated.
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
from investor.volatility import load_histories


class PerformanceRequest(PortfolioRequest):
    mode: Literal[
        "balanced", "volatility", "performance", "drawdown", "correlation"
    ] = "balanced"
    history: Literal["common", "extended"] = "common"


def factor_regression(returns, factor_returns, periods):
    """OLS intercept (annual decimal return) and slope (dimensionless).

    Both series are synchronous EUR simple returns. The reference rate is
    explicitly zero, as for the other risk-adjusted metrics in this panel.
    """
    if float(np.var(factor_returns, ddof=1)) <= 1e-16:
        return None, None
    design = np.column_stack((np.ones(len(factor_returns)), factor_returns))
    intercept, slope = np.linalg.lstsq(design, returns, rcond=None)[0]
    alpha = float(intercept * periods)
    return 0.0 if abs(alpha) < 1e-12 else alpha, float(slope)


def optimize_weights(returns, current, mode="balanced", locked=None):
    """Select positions and solve each support with hard 3% / cardinality bounds.

    Exhaust all supports up to eight assets. Larger universes use deterministic
    ranked supports and bounded exchange search; no global optimality claim.
    """
    count = len(current)
    locked = dict(locked or {})
    if len(locked) == count:
        return current.copy()
    cap = 0.35 if count >= 3 else 1.0
    floor = 0.03
    minimum = max((count + 1) // 2, 1 if locked else int(np.ceil(1 / cap - 1e-10)))
    maximum = min(count, len(locked) + int((1 - sum(locked.values()) + 1e-10) / floor))
    if minimum > maximum:
        raise HTTPException(
            422,
            "Contraintes incompatibles : la moitié des actifs doit être conservée avec au moins 3 % par position (33 positions maximum).",
        )
    if (
        mode == "correlation"
        and count > 1
        and np.any(np.std(returns, axis=0, ddof=1) <= 1e-12)
    ):
        raise HTTPException(
            422,
            "Corrélations non mesurables : un actif a une volatilité nulle sur cette période.",
        )
    if count == 1:
        return np.ones(1)
    covariance = np.atleast_2d(np.cov(returns, rowvar=False, ddof=1))
    means = returns.mean(axis=0)
    correlation = None
    if mode == "correlation":
        deviations = np.sqrt(np.diag(covariance))
        correlation = covariance / np.outer(deviations, deviations)

    def objective(w):
        if mode == "volatility":
            return float(w @ covariance @ w)
        if mode == "correlation":
            return float(w @ correlation @ w)
        changes = returns @ w
        if mode == "performance":
            return -float(np.log1p(changes).sum())
        if mode == "drawdown":
            logs = np.r_[0.0, np.cumsum(np.log1p(changes))]
            return float(np.max(np.maximum.accumulate(logs) - logs))
        risk = float(np.sqrt(max(0, w @ covariance @ w)))
        mean = float(means @ w)
        return (
            -mean / risk
            if risk > 1e-12
            else (0.0 if abs(mean) < 1e-12 else -np.sign(mean) * np.inf)
        )

    solved = {}

    def evaluate(support):
        support = tuple(sorted(support))
        if support in solved:
            return
        if not set(locked).issubset(support):
            return
        selected = np.array(support)
        fixed = {j: locked[i] for j, i in enumerate(selected) if i in locked}
        low = sum(fixed.values()) + floor * (len(selected) - len(fixed))
        high = sum(fixed.values()) + cap * (len(selected) - len(fixed))
        if low > 1 + 1e-10 or high < 1 - 1e-10:
            return
        try:
            weights = _optimize_support(
                returns[:, selected],
                np.full(len(selected), 1 / len(selected)),
                mode,
                cap,
                floor,
                fixed=fixed,
            )
        except HTTPException as error:
            if error.status_code != 503:
                raise
            solved[support] = None
            return
        full = np.zeros(count)
        full[selected] = weights
        if (
            not np.all(np.isfinite(full))
            or abs(full.sum() - 1) > 1e-8
            or any(
                full[i] > cap + 1e-8 or (full[i] > 1e-8 and full[i] < floor - 1e-8)
                for i in range(count)
                if i not in locked
            )
            or any(abs(full[i] - value) > 1e-8 for i, value in locked.items())
        ):
            raise HTTPException(
                503, "Les contraintes de pondération n’ont pas été respectées."
            )
        solved[support] = (objective(full), full)

    if count <= 8:
        for size in range(minimum, maximum + 1):
            for support in itertools.combinations(range(count), size):
                evaluate(support)
    else:
        relaxed = (
            current
            if locked
            else _optimize_support(returns, np.full(count, 1 / count), mode, cap)
        )
        rankings = [
            np.argsort(-relaxed, kind="stable"),
            np.argsort(-current, kind="stable"),
        ]
        for ranking in rankings:
            for size in range(minimum, maximum + 1):
                free = [int(i) for i in ranking if i not in locked]
                evaluate(list(locked) + free[: max(0, size - len(locked))])
        # Improve support membership, rather than only rounding a relaxed result.
        for _ in range(2):
            feasible = [
                (key, value) for key, value in solved.items() if value is not None
            ]
            if not feasible:
                break
            support, (_, incumbent) = min(feasible, key=lambda item: item[1][0])
            inside = sorted(
                (i for i in support if i not in locked), key=lambda i: incumbent[i]
            )[:3]
            outside = [i for i in rankings[0] if i not in support][:3]
            for remove, add in itertools.product(inside, outside):
                evaluate((set(support) - {remove}) | {int(add)})
    feasible = [value for value in solved.values() if value is not None]
    if not feasible:
        raise HTTPException(
            422 if locked else 503,
            "Contraintes incompatibles avec les quantités verrouillées. Déverrouillez un actif ou modifiez les quantités."
            if locked
            else "Aucune allocation admissible n’a convergé. Réessayez sur une autre période.",
        )
    weights = min(feasible, key=lambda item: item[0])[1]
    if np.count_nonzero(weights > 1e-8) < minimum:
        raise HTTPException(503, "Le nombre minimal de positions n’a pas été respecté.")
    return weights


def _optimize_support(returns, current, mode, cap, floor=0.0, fixed=None):
    """Long-only historical objectives; compounded drawdown uses convex cuts."""
    count = len(current)
    if count == 1:
        return current.copy()
    fixed = dict(fixed or {})
    lower = np.array([fixed.get(i, floor) for i in range(count)])
    upper = np.array([fixed.get(i, cap) for i in range(count)])
    initial_fixed = lower.copy()
    for i in range(count):
        extra = min(upper[i] - initial_fixed[i], max(0, 1 - initial_fixed.sum()))
        initial_fixed[i] += extra
    # An existing concentrated portfolio is a comparator, not a feasible solver seed.
    initial_weights = (
        current.copy()
        if np.max(current) <= cap and np.min(current) >= floor
        else np.full(count, 1 / count)
    )
    if fixed:
        initial_weights = initial_fixed
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
                bounds=bounds if bounds is not None else list(zip(lower, upper)),
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
    elif mode == "correlation":
        deviations = np.sqrt(np.diag(covariance))
        correlation = covariance / np.outer(deviations, deviations)
        weights = solve(
            lambda w: float(w @ correlation @ w), lambda w: 2 * correlation @ w
        )
    elif mode == "performance":
        # Maximizing log wealth is a concave maximization on the simplex.
        scale = max(float(np.max(np.abs(means))), 1e-4)
        weights = solve(
            lambda w: -float(np.log1p(returns @ w).mean()) / scale,
            lambda w: -(returns / (1 + returns @ w)[:, None]).mean(axis=0) / scale,
        )
    elif mode == "balanced":
        minimum = minimum_variance()
        best_mean = lower.copy()
        remaining = 1.0 - lower.sum()
        for i in np.argsort(-means):
            extra = min(upper[i] - lower[i], remaining)
            best_mean[i] += extra
            remaining -= extra
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
                        "fun": lambda y: upper * y.sum() - y,
                        "jac": lambda y: (
                            upper[:, None] * np.ones((count, count)) - np.eye(count)
                        ),
                    },
                    {
                        "type": "ineq",
                        "fun": lambda y: y - lower * y.sum(),
                        "jac": lambda y: (
                            np.eye(count) - lower[:, None] * np.ones((count, count))
                        ),
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

            # A nonpositive Sharpe reaches its maximum at a box-simplex vertex.
            # Vertices have all but at most one weight at the floor or cap.
            free = [i for i in range(count) if upper[i] - lower[i] > 1e-12]

            def vertices(start, vertex, remaining):
                if remaining <= 1e-10:
                    candidates.append(vertex.copy())
                    return
                for j in free:
                    if (
                        vertex[j] == lower[j]
                        and remaining <= upper[j] - lower[j] + 1e-10
                    ):
                        candidate = vertex.copy()
                        candidate[j] += remaining
                        candidates.append(candidate)
                for k in range(start, len(free)):
                    j = free[k]
                    span = upper[j] - lower[j]
                    if span <= remaining + 1e-10:
                        candidate = vertex.copy()
                        candidate[j] = upper[j]
                        vertices(k + 1, candidate, remaining - span)

            vertices(0, lower.copy(), 1 - lower.sum())
            weights = max(candidates, key=score)
    elif mode == "drawdown":
        weights = _minimum_drawdown(
            returns, initial_weights, solve, cap, floor, bounds=list(zip(lower, upper))
        )
    else:
        raise ValueError("Mode d’optimisation inconnu")
    if np.any(weights > upper + 1e-7) or np.any(weights < lower - 1e-7):
        raise HTTPException(503, "Le plafond de concentration n’a pas été respecté.")
    weights = np.clip(weights, lower, upper)
    if not np.isfinite(weights.sum()) or abs(weights.sum() - 1) > 1e-7:
        raise HTTPException(503, "Pondérations invalides après optimisation.")
    weights /= weights.sum()
    if np.any(weights > upper + 1e-8) or np.any(weights < lower - 1e-8):
        raise HTTPException(503, "Le plafond de concentration n’a pas été respecté.")
    return weights


def _minimum_drawdown(returns, current, solve, cap=1.0, floor=0.0, bounds=None):
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
            bounds=(bounds if bounds is not None else [(floor, cap)] * count)
            + [(0, None)],
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
    locked_asset_ids=(),
):
    non_daily = [a for a in assets if a["frequency"] != "daily"]
    if non_daily:
        return {
            "status": "insufficient",
            "message": "La comparaison et l’optimisation utilisent uniquement des cours journaliers. "
            "Un historique journalier est nécessaire pour : "
            + ", ".join(a["name"] for a in non_daily)
            + ".",
            "excluded": [
                {
                    "id": a["id"],
                    "name": a["name"],
                    "reason": "Historique journalier indisponible.",
                }
                for a in non_daily
            ],
        }
    # Keep every observed date: never downsample the portfolio or benchmark.
    histories = [dict(sorted(h.items())) for h in [*histories, benchmark]]
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
    minimum = 21
    if len(common) - 1 < minimum or any(
        sum(d in h for d in common) < minimum + 1 for h in histories[:-1]
    ):
        return {
            "status": "insufficient",
            "message": f"Il faut au moins {minimum} variations quotidiennes observées par actif sur cette période.",
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
    periods = 252
    current = np.array([p["weight"] for p in positions])
    locked = {
        i: current[i]
        for i, p in enumerate(positions)
        if p.get("id") in locked_asset_ids
    }
    recommended = (
        optimize_weights(returns[:, :-1], current, mode, locked) if optimize else None
    )
    strategies = {"portfolio": returns[:, :-1] @ current, "benchmark": returns[:, -1]}
    if recommended is not None:
        strategies["optimized"] = returns[:, :-1] @ recommended
    benchmark_returns = returns[:, -1]
    curves, metrics = {}, {}
    for key, changes in strategies.items():
        curve = np.r_[100.0, 100 * np.cumprod(1 + changes)]
        if not np.all(np.isfinite(curve)):
            raise HTTPException(
                422, "Les valeurs de cette série dépassent les limites du calcul."
            )
        curves[key] = curve
        elapsed_years = (
            date.fromisoformat(common[-1]) - date.fromisoformat(common[0])
        ).days / 365.25
        cagr = float((curve[-1] / 100) ** (1 / elapsed_years) - 1)
        downside = float(np.sqrt(np.mean(np.minimum(changes, 0) ** 2)))
        drawdown = float(np.min(curve / np.maximum.accumulate(curve) - 1))
        alpha, beta = factor_regression(changes, benchmark_returns, periods)
        metrics[key] = {
            "beta": beta,
            "alpha": alpha,
            "total_return": float(curve[-1] / 100 - 1),
            "cagr": cagr,
            "volatility": float(np.std(changes, ddof=1) * np.sqrt(periods)),
            "max_drawdown": drawdown,
            "sortino": float(changes.mean() / downside * np.sqrt(periods))
            if downside > 1e-12
            else None,
            "calmar": float(cagr / abs(drawdown)) if drawdown < -1e-12 else None,
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
        "frequency": "daily",
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
                "locked": p.get("id") in locked_asset_ids,
                "recommended_quantity": (
                    p["quantity"]
                    if p.get("id") in locked_asset_ids
                    else float(total * recommended[i] / p["price"])
                )
                if recommended is not None
                else None,
            }
            for i, p in enumerate(positions)
        ],
    }


def portfolio_performance(request: PerformanceRequest, optimize=False):
    if not set(request.locked_asset_ids).issubset(
        {h.asset_id for h in request.holdings}
    ):
        raise HTTPException(422, "Un actif verrouillé doit figurer dans les positions.")
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
        locked_asset_ids=request.locked_asset_ids,
    )
