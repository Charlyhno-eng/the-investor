"""Observed portfolio comparison and constrained, retrospective allocation.

Constant-weight ratio allocations and an annually rebalanced equal allocation.
Legacy objectives remain accepted for API compatibility. No forecast is generated.
"""

import calendar
import itertools
from datetime import date, timedelta
from typing import Literal

import numpy as np
from fastapi import HTTPException
from pydantic import Field
from scipy.optimize import linprog, minimize
from threadpoolctl import threadpool_limits

from investor.db import connect
from investor.portfolio.service import PortfolioRequest, portfolio
from investor.portfolio.statistics import curve_metrics, factor_regression
from investor.portfolio.volatility import load_histories


class PerformanceRequest(PortfolioRequest):
    mode: Literal[
        "equal",
        "sortino",
        "sharpe",
        "calmar",
        "beta_sharpe",
        "balanced",
        "volatility",
        "downside",
        "performance",
        "drawdown",
        "correlation",
    ] = "equal"
    history: Literal["common", "extended"] = "common"
    fee_rate: float = Field(default=0.005, ge=0, le=0.1)


def optimize_weights(
    returns,
    current,
    mode="balanced",
    locked=None,
    *,
    betas=None,
    target_beta=None,
    elapsed_years=None,
):
    """Select positions and solve each support with hard 3% / cardinality bounds.

    Exhaust all supports up to eight assets. Larger universes use deterministic
    ranked supports and bounded exchange search; no global optimality claim.
    """
    if mode == "sharpe":
        mode = "balanced"
    count = len(current)
    locked = dict(locked or {})
    if len(locked) == count:
        if target_beta is not None and abs(float(betas @ current) - target_beta) > 1e-7:
            raise HTTPException(
                422, "Bêta cible incompatible avec les quantités verrouillées."
            )
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
        if target_beta is not None and abs(float(betas[0]) - target_beta) > 1e-7:
            raise HTTPException(422, "Bêta cible inaccessible avec cet actif.")
        return np.ones(1)
    covariance = np.atleast_2d(np.cov(returns, rowvar=False, ddof=1))
    means = returns.mean(axis=0)
    correlation = None
    if mode == "correlation":
        deviations = np.sqrt(np.diag(covariance))
        correlation = covariance / np.outer(deviations, deviations)

    def objective(w):
        if mode in {"sortino", "calmar", "beta_sharpe"}:
            return ratio_objective(returns @ w, mode, elapsed_years)
        if mode == "downside":
            return float(np.mean(np.minimum(returns @ w, 0) ** 2))
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
                betas=betas[selected] if betas is not None else None,
                target_beta=target_beta,
                elapsed_years=elapsed_years,
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
            or (
                target_beta is not None
                and abs(float(betas @ full) - target_beta) > 1e-7
            )
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
            else _optimize_support(
                returns,
                np.full(count, 1 / count),
                mode,
                cap,
                betas=betas,
                target_beta=target_beta,
                elapsed_years=elapsed_years,
            )
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


def _optimize_support(
    returns,
    current,
    mode,
    cap,
    floor=0.0,
    fixed=None,
    *,
    betas=None,
    target_beta=None,
    elapsed_years=None,
):
    """Long-only historical objectives; compounded drawdown uses convex cuts."""
    count = len(current)
    if count == 1:
        if target_beta is not None and abs(float(betas[0]) - target_beta) > 1e-7:
            raise HTTPException(503, "Bêta inaccessible sur cette sélection.")
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
                bounds=bounds
                if bounds is not None
                else list(zip(lower, upper, strict=True)),
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

    if mode in {"sortino", "calmar", "beta_sharpe"}:
        constraints = [budget]
        free = np.flatnonzero(upper - lower > 1e-12)
        independent_beta = (
            target_beta is not None and len(free) > 1 and np.ptp(betas[free]) >= 1e-10
        )
        if target_beta is not None:
            # Fixed quantities can make the beta equality redundant even when
            # the full vector of asset betas is not constant.
            if independent_beta:
                constraints.append(
                    {
                        "type": "eq",
                        "fun": lambda w: float(betas @ w - target_beta),
                        "jac": lambda w: betas,
                    }
                )
        matrix = np.ones((1, count))
        rhs = [1.0]
        if target_beta is not None:
            matrix = np.vstack((matrix, betas))
            rhs.append(target_beta)
        feasible = linprog(
            -means,
            A_eq=matrix,
            b_eq=rhs,
            bounds=list(zip(lower, upper, strict=True)),
            method="highs",
        )
        if not feasible.success:
            raise HTTPException(503, "Contraintes incompatibles sur cette sélection.")
        if len(free) <= 1 or (independent_beta and len(free) == 2):
            # The equalities already determine the only possible allocation.
            return feasible.x

        if mode != "calmar" and means @ feasible.x > 1e-12:
            # Positive Sortino / Sharpe: y=w/(normalized_mean @ w).
            # Minimize squared risk with normalized_mean @ y=1. This convex
            # problem avoids dividing by nearly zero downside or volatility.
            normalized = means / max(float(np.max(np.abs(means))), 1e-12)
            equalities = [normalized]
            targets = [1.0]
            rows = [np.eye(count)[i] - lower[i] for i in range(count) if i not in free]
            if independent_beta:
                rows.append(betas - target_beta)
            for row in rows:
                if np.linalg.matrix_rank(np.vstack([*equalities, row])) > len(
                    equalities
                ):
                    equalities.append(row)
                    targets.append(0.0)
            equality_matrix = np.array(equalities)
            bound_matrix = np.vstack(
                [
                    np.eye(count)[free] - lower[free, None],
                    upper[free, None] - np.eye(count)[free],
                ]
            )
            scale = max(float(np.max(np.mean(returns**2, axis=0))), 1e-12)

            def risk(y):
                if mode == "sortino":
                    return float(np.mean(np.minimum(returns @ y, 0) ** 2)) / scale
                return float(y @ scaled @ y)

            def risk_gradient(y):
                if mode == "sortino":
                    return (
                        2
                        * returns.T
                        @ np.minimum(returns @ y, 0)
                        / len(returns)
                        / scale
                    )
                return 2 * scaled @ y

            allocation = solve(
                risk,
                risk_gradient,
                initial=feasible.x / (normalized @ feasible.x),
                constraints=[
                    {
                        "type": "eq",
                        "fun": lambda y: equality_matrix @ y - targets,
                        "jac": lambda y: equality_matrix,
                    },
                    {
                        "type": "ineq",
                        "fun": lambda y: bound_matrix @ y,
                        "jac": lambda y: bound_matrix,
                    },
                ],
                bounds=[(0, None)] * count,
            )
            weights = allocation / allocation.sum()
        else:

            def objective(w):
                return ratio_objective(returns @ w, mode, elapsed_years)

            candidates = []
            for seed in [feasible.x, initial_weights, np.full(count, 1 / count)]:
                try:
                    candidate = solve(
                        objective, None, initial=seed, constraints=constraints
                    )
                    if abs(candidate.sum() - 1) < 1e-8 and (
                        target_beta is None
                        or abs(float(betas @ candidate) - target_beta) < 1e-7
                    ):
                        candidates.append(candidate)
                except HTTPException:
                    continue
            if not candidates:
                raise HTTPException(503, "L’optimisation du ratio n’a pas convergé.")
            weights = min(candidates, key=objective)
    elif mode == "downside":
        # Minimize shortfalls below zero, not dispersion around a negative mean.
        # Scaling preserves the optimum while keeping SLSQP tolerances meaningful.
        scale = max(float(np.max(np.mean(returns**2, axis=0))), 1e-12)
        weights = solve(
            lambda w: float(np.mean(np.minimum(returns @ w, 0) ** 2)) / scale,
            lambda w: 2 * returns.T @ np.minimum(returns @ w, 0) / len(returns) / scale,
        )
    elif mode == "volatility":
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
            returns,
            initial_weights,
            solve,
            cap,
            floor,
            bounds=list(zip(lower, upper, strict=True)),
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


def ratio_objective(changes, mode, elapsed_years=None):
    """Same ratio conventions as the displayed metrics; finite solver utility."""
    mean = float(changes.mean())
    if mode == "sortino":
        denominator = float(np.sqrt(np.mean(np.minimum(changes, 0) ** 2)))
        numerator = mean * np.sqrt(252)
    elif mode == "calmar":
        logs = np.r_[0.0, np.cumsum(np.log1p(changes))]
        denominator = float(-np.expm1(np.min(logs - np.maximum.accumulate(logs))))
        numerator = float(np.expm1(logs[-1] / (elapsed_years or len(changes) / 252)))
    else:
        denominator = float(changes.std(ddof=1))
        numerator = mean * np.sqrt(252)
    return -numerator / max(denominator, 1e-10)


def annual_equal_returns(returns, dates, fee_rate=0.005, first_dates=None):
    """Buy equal stakes, let them drift, then rebalance on each anniversary.

    Fees apply to both traded legs. Solve the self-financing target value,
    including the initial purchase; no fictional sale at the final observation.
    """
    count = returns.shape[1]
    first_dates = first_dates or [dates[0]] * count
    active = np.array([first <= dates[0] for first in first_dates])
    values = np.full(count, 1 / count) / (1 + fee_rate * active)
    start = date.fromisoformat(dates[0])
    next_year = start.year + 1
    changes = []
    for i, row in enumerate(returns):
        previous = 1.0 if i == 0 else float(values.sum())
        values *= 1 + row
        day = date.fromisoformat(dates[i + 1])
        available = np.array([first <= dates[i + 1] for first in first_dates])
        values[available & ~active] /= 1 + fee_rate
        active = available
        anniversary = date(
            next_year,
            start.month,
            min(start.day, calendar.monthrange(next_year, start.month)[1]),
        )
        if day >= anniversary and i < len(returns) - 1:
            wealth = float(values.sum())
            low, high = 0.0, wealth
            for _ in range(50):
                net = (low + high) / 2
                if net + fee_rate * np.abs(net / count - values)[active].sum() > wealth:
                    high = net
                else:
                    low = net
            values[:] = (low + high) / 2 / count
            next_year = day.year + 1
        changes.append(float(values.sum()) / previous - 1)
    return np.array(changes)


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
    fee_rate=0.005,
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
                d < first or d in h
                for first, h in zip(first_dates, histories[:-1], strict=True)
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
    recommended = None
    allocations, unavailable = {}, {}
    strategies = {"portfolio": returns[:, :-1] @ current, "benchmark": returns[:, -1]}
    elapsed_years = (
        date.fromisoformat(common[-1]) - date.fromisoformat(common[0])
    ).days / 365.25
    if optimize:
        if mode == "equal":
            recommended = np.full(len(current), 1 / len(current))
            if any(abs(recommended[i] - value) > 1e-8 for i, value in locked.items()):
                raise HTTPException(
                    422,
                    "L’équipondération est incompatible avec les quantités verrouillées. Déverrouillez les actifs concernés.",
                )
            strategies["optimized"] = annual_equal_returns(
                returns[:, :-1], common, fee_rate, first_dates
            )
        elif mode == "beta_sharpe":
            betas = np.array(
                [
                    factor_regression(returns[:, i], returns[:, -1], periods)[1]
                    for i in range(len(current))
                ]
            )
            for digit in (3, 4, 5, 6, 7):
                key = f"beta_0{digit}"
                try:
                    if any(value is None for value in betas):
                        raise HTTPException(
                            422,
                            "Bêta non mesurable : le S&P 500 ne varie pas sur cette période.",
                        )
                    weights = optimize_weights(
                        returns[:, :-1],
                        current,
                        mode,
                        locked,
                        betas=betas.astype(float),
                        target_beta=digit / 10,
                        elapsed_years=elapsed_years,
                    )
                    allocations[key] = weights.tolist()
                    strategies[key] = returns[:, :-1] @ weights
                except HTTPException as error:
                    unavailable[key] = (
                        "Cible non obtenue : contraintes incompatibles ou optimisation sans convergence."
                        if error.status_code == 503
                        else error.detail
                    )
        else:
            recommended = optimize_weights(
                returns[:, :-1], current, mode, locked, elapsed_years=elapsed_years
            )
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
        metrics[key] = curve_metrics(
            curve,
            changes,
            benchmark_returns,
            elapsed_years,
            periods,
            benchmark=key == "benchmark",
        )
    total = sum(p["value"] for p in positions)
    return {
        "status": "ready",
        "currency": "EUR",
        "mode": mode if optimize else None,
        "history": history,
        "requested_start": cutoff,
        "cash_until": [
            {"id": a["id"], "name": a["name"], "date": first}
            for a, first in zip(assets, first_dates, strict=True)
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
        "allocations": allocations,
        "unavailable": unavailable,
        "fee_rate": fee_rate if mode == "equal" and optimize else None,
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
    valuation = portfolio(request.model_copy(update={"include_correlation": False}))
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
        fee_rate=request.fee_rate,
    )
