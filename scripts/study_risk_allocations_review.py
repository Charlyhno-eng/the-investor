"""Predeclared risk-allocation review, frozen SQLite copy, no user DB writes."""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
from audit_validation import UNIVERSES
from fastapi import HTTPException
from scipy.optimize import minimize
from study_quantitative_strategies import PERIODS, load_inputs

from investor import db
from investor.portfolio import performance, validation
from investor.portfolio.research import shrunk_covariance

OUTPUT = Path("data/backtests/risk-allocations-review.json")
PROTOCOL = {
    "universes": ["journal_14", "actions_11", "crypto_4"],
    "periods": PERIODS,
    "fees": [0.005, 0.01],
    "initial_capital": 10000,
    "whole_shares": True,
    "cadence": "quarterly, three-year eligibility, 3 percentage-point trading band",
    "candidates": ["baseline", "continuous", "recent_252", "ewma_63", "oas_fixed"],
    "correlation_extra": ["representative_080", "squared_correlation"],
    "criterion_before_results": "Risk objective first: median realized volatility ratio <=0.95 versus baseline for volatility; median normalized correlation objective <=1.01 and positive aggregate AIR+SAF weights in synthetic paired-sector example for correlation. Both: volatility no more than 5% worse in at least 75% of cases, median CAGR loss <=0.005, median Sharpe loss <=0.03, summed fees <=1.10x baseline. No change selected just for largest return. All cases including failures are retained. No parameter retuning.",
    "limitations": "Previously examined historical windows, survivorship/selection bias. This study is retrospective. OAS reevaluated because covariance override was not propagated to each inner support solve; unlike the earlier faulty implementation, regularization now affects all weights. Representative method differs from rejected equal-group allocation: one representative per complete-link cluster, globally optimized unequal budgets, cap adapted only when feasibility requires it.",
}


def solve(matrix, cap=0.35):
    n = len(matrix)
    if n == 1:
        return np.ones(1)
    cap = max(cap, 1 / n)
    matrix = matrix / max(float(np.max(np.diag(matrix))), 1e-12)
    result = minimize(
        lambda w: float(w @ matrix @ w),
        np.full(n, 1 / n),
        jac=lambda w: 2 * matrix @ w,
        bounds=[(0, cap)] * n,
        constraints=[
            {"type": "eq", "fun": lambda w: w.sum() - 1, "jac": lambda w: np.ones(n)}
        ],
        method="SLSQP",
        options={"ftol": 1e-12, "maxiter": 1500},
    )
    if not result.success:
        raise HTTPException(503, "Research allocation did not converge")
    return result.x


def allocator(variant):
    def allocate(returns, current, mode, **kwargs):
        x = returns[-252:] if variant == "recent_252" else returns
        covariance = np.atleast_2d(np.cov(x, rowvar=False, ddof=1))
        if variant == "oas_fixed":
            covariance = shrunk_covariance(x)
        if variant == "ewma_63":
            x = x[-504:]
            p = np.exp2(np.arange(len(x)) / 63)
            p /= p.sum()
            centered = x - p @ x
            covariance = (centered * p[:, None]).T @ centered / (1 - p @ p)
        matrix = covariance
        if mode == "correlation":
            sd = np.sqrt(np.diag(covariance))
            matrix = covariance / np.outer(sd, sd)
        if variant == "squared_correlation":
            matrix = matrix**2
        if variant == "representative_080":
            groups = []
            for j in np.argsort(-current, kind="stable"):
                group = next(
                    (g for g in groups if all(matrix[j, k] >= 0.8 for k in g)), None
                )
                if group is None:
                    groups.append([int(j)])
                else:
                    group.append(int(j))
            representatives = []
            for group in groups:
                outside = [k for k in range(len(current)) if k not in group]
                representatives.append(
                    min(
                        group,
                        key=lambda j: (
                            float(matrix[j, outside].mean()) if outside else 0,
                            -current[j],
                            j,
                        ),
                    )
                )
            target = np.zeros(len(current))
            idx = np.array(representatives)
            target[idx] = solve(matrix[np.ix_(idx, idx)])
            return target
        return solve(matrix)

    return allocate


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    report = {"protocol": PROTOCOL, "results": {}}
    OUTPUT.write_text(json.dumps(report, indent=2))
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(copy) as dst,
        ):
            src.backup(dst)
        report["snapshot_sha256"] = hashlib.sha256(copy.read_bytes()).hexdigest()
        original_dir = db.DATA_DIR
        db.DATA_DIR = Path(folder)
        # Without an override, propagating the same empirical covariance is
        # numerically identical to the pre-review baseline.
        try:
            for universe in PROTOCOL["universes"]:
                for period, (start, end) in PERIODS.items():
                    request = validation.ValidationRequest(
                        asset_ids=UNIVERSES[universe],
                        start_date=date.fromisoformat(start),
                        end_date=date.fromisoformat(end),
                        whole_shares=True,
                        rebalance_tolerance=0.03,
                    )
                    inputs = load_inputs(request)
                    for mode in ("volatility", "correlation"):
                        variants = PROTOCOL["candidates"] + (
                            PROTOCOL["correlation_extra"]
                            if mode == "correlation"
                            else []
                        )
                        for variant in variants:
                            # OAS fixed uses current production constraints, isolates the propagation fix.
                            method = (
                                performance.optimize_weights
                                if variant == "baseline"
                                else performance.optimize_weights
                                if variant == "oas_fixed"
                                else allocator(variant)
                            )
                            if variant == "oas_fixed" and mode == "correlation":
                                method = allocator(variant)

                            def legacy_constraints(
                                returns, current, mode, _method=method, **kwargs
                            ):
                                kwargs.pop("continuous_correlation", None)
                                return _method(returns, current, mode, **kwargs)

                            for fee in PROTOCOL["fees"]:
                                req = request.model_copy(
                                    update={
                                        "mode": mode,
                                        "fee_rate": fee,
                                        "regularize_covariance": variant == "oas_fixed",
                                    }
                                )
                                with patch.object(
                                    validation, "optimize_weights", legacy_constraints
                                ):
                                    result = validation.validation_data(
                                        **inputs, request=req
                                    )
                                key = f"{universe}:{period}:{mode}:{variant}:{fee}"
                                report["results"][key] = {
                                    k: result[k]
                                    for k in (
                                        "status",
                                        "message",
                                        "metrics",
                                        "parameters",
                                        "folds",
                                        "final_portfolio",
                                    )
                                    if k in result
                                }
                                print(key, result["status"], flush=True)
                                OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
        finally:
            db.DATA_DIR = original_dir


if __name__ == "__main__":
    main()
