"""Evaluate the predeclared review criteria against every stored simulation."""

import hashlib
import json
import sqlite3
import tempfile
from bisect import bisect_left
from datetime import date
from pathlib import Path

import numpy as np
from audit_validation import UNIVERSES
from study_quantitative_strategies import PERIODS, load_inputs
from study_risk_allocations_review import OUTPUT, PROTOCOL, allocator

from investor import db
from investor.portfolio import performance, validation
from investor.portfolio.validation import align, maturities

report = json.loads(OUTPUT.read_text())
results = report["results"]
objectives = {}
unmeasurable = {}
cases = {}
production_checks = []
with tempfile.TemporaryDirectory() as folder:
    with (
        sqlite3.connect(
            f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
        ) as src,
        sqlite3.connect(Path(folder) / "investor.sqlite3") as dst,
    ):
        src.backup(dst)
    digest = hashlib.sha256(
        (Path(folder) / "investor.sqlite3").read_bytes()
    ).hexdigest()
    if digest != report["snapshot_sha256"]:
        raise RuntimeError(
            "Database changed since the simulations; regenerate the study before summarizing."
        )
    original = db.DATA_DIR
    db.DATA_DIR = Path(folder)
    try:
        for universe in PROTOCOL["universes"]:
            for period, (start, end) in PERIODS.items():
                req = validation.ValidationRequest(
                    asset_ids=UNIVERSES[universe],
                    whole_shares=True,
                    rebalance_tolerance=0.03,
                    start_date=date.fromisoformat(start),
                    end_date=date.fromisoformat(end),
                )
                inputs = load_inputs(req)
                histories = inputs["histories"]
                daily = [(min(h), h) for h in histories if h]
                days = sorted(
                    d
                    for d in inputs["benchmark"]
                    if d <= end and all((d < s or d in h for s, h in daily))
                )
                prices = np.column_stack([align(h, days) for h in histories])
                prices = np.where(np.isfinite(prices), prices, 1)
                mature = maturities(histories, days)
                for fee in PROTOCOL["fees"]:
                    production_request = req.model_copy(
                        update={
                            "mode": "correlation",
                            "fee_rate": fee,
                            "whole_shares": True,
                            "rebalance_tolerance": 0.03,
                        }
                    )
                    production = validation.validation_data(
                        **inputs, request=production_request
                    )
                    expected = results[
                        f"{universe}:{period}:correlation:continuous:{fee}"
                    ]
                    assert production["status"] == expected["status"] == "ready", (
                        universe,
                        period,
                        fee,
                        production.get("message"),
                    )
                    for metric in ("volatility", "cagr", "sharpe", "cost_eur"):
                        np.testing.assert_allclose(
                            production["metrics"]["strategy"][metric],
                            expected["metrics"]["strategy"][metric],
                            rtol=1e-6,
                            atol=1e-6,
                        )
                    np.testing.assert_allclose(
                        [f["weights"] for f in production["folds"]],
                        [f["weights"] for f in expected["folds"]],
                        atol=1e-6,
                    )
                    production_checks.append(f"{universe}:{period}:{fee}")
                    prefix = f"{universe}:{period}:correlation:"
                    base = results[f"{prefix}baseline:{fee}"]
                    basefolds = {f["signal"]: f for f in base["folds"]}
                    for variant in (
                        PROTOCOL["candidates"] + PROTOCOL["correlation_extra"]
                    ):
                        result = results[f"{prefix}{variant}:{fee}"]
                        ratios = []
                        pair = []
                        for f in result["folds"]:
                            lo = bisect_left(days, f["train_start"])
                            hi = days.index(f["train_end"])
                            selected = mature[hi]
                            x = (prices[lo + 1 : hi + 1] / prices[lo:hi] - 1)[
                                :, selected
                            ]
                            corr = np.atleast_2d(np.corrcoef(x, rowvar=False))
                            w = np.array(f["weights"])[selected]
                            b = np.array(basefolds[f["signal"]]["weights"])[selected]
                            denominator = float(b @ corr @ b)
                            if denominator > 1e-12:
                                ratios.append(float(w @ corr @ w / denominator))
                            else:
                                unmeasurable[variant] = unmeasurable.get(variant, 0) + 1
                            if universe == "journal_14":
                                pair.append(float(f["weights"][7] + f["weights"][11]))
                        if ratios:
                            objectives.setdefault(variant, []).append(
                                float(np.median(ratios))
                            )
                        if (
                            universe == "journal_14"
                            and period == "five_years"
                            and (fee == 0.005)
                        ):
                            cases[variant] = {
                                "pair_weights": pair,
                                "pair_both_zero": sum(w < 1e-08 for w in pair),
                            }
    finally:
        db.DATA_DIR = original
rng = np.random.default_rng(554)
n = 14
corr = np.full((n, n), 0.45)
np.fill_diagonal(corr, 1)
corr[:2, 2:] = 0.05
corr[2:, :2] = 0.05
corr[0, 1] = corr[1, 0] = 0.98
q, _ = np.linalg.qr(rng.normal(size=(1200, n)) - 0)
q -= q.mean(0)
q, _ = np.linalg.qr(q)
x = q @ np.linalg.cholesky(corr).T
synthetic = {}
for variant in PROTOCOL["candidates"] + PROTOCOL["correlation_extra"]:
    method = (
        performance.optimize_weights if variant == "baseline" else allocator(variant)
    )
    w = method(x, np.full(n, 1 / n), "correlation")
    synthetic[variant] = {"pair_weight": float(w[:2].sum()), "weights": w.tolist()}
summary = {}
for mode in ["volatility", "correlation"]:
    for variant in PROTOCOL["candidates"][1:] + (
        PROTOCOL["correlation_extra"] if mode == "correlation" else []
    ):
        pairs = [
            (v, results[k.replace(":" + variant + ":", ":baseline:")])
            for k, v in results.items()
            if f":{mode}:{variant}:" in k
        ]
        pairs = [
            (v["metrics"]["strategy"], b["metrics"]["strategy"])
            for v, b in pairs
            if v["status"] == b["status"] == "ready"
        ]
        ratios = [v["volatility"] / b["volatility"] for v, b in pairs]
        cagr = float(np.median([v["cagr"] - b["cagr"] for v, b in pairs]))
        sharpe = float(np.median([v["sharpe"] - b["sharpe"] for v, b in pairs]))
        fees = sum((v["cost_eur"] for v, b in pairs)) / sum(
            (b["cost_eur"] for v, b in pairs)
        )
        robustness = float(np.mean(np.array(ratios) <= 1.05))
        med = float(np.median(ratios))
        objective = (
            float(np.median(objectives[variant])) if mode == "correlation" else None
        )
        passes = (
            (
                med <= 0.95
                if mode == "volatility"
                else objective <= 1.01 and synthetic[variant]["pair_weight"] > 0
            )
            and robustness >= 0.75
            and (cagr >= -0.005)
            and (sharpe >= -0.03)
            and (fees <= 1.1)
            and (len(pairs) == 24)
        )
        summary[f"{mode}:{variant}"] = {
            "cases": len(pairs),
            "median_volatility_ratio": med,
            "volatility_robustness_fraction": robustness,
            "median_cagr_delta": cagr,
            "median_sharpe_delta": sharpe,
            "aggregate_fee_ratio": fees,
            "median_correlation_objective_ratio": objective,
            "passes": bool(passes),
        }
report["review"] = {
    "summary": summary,
    "production_continuous_equivalence": production_checks,
    "correlation_unmeasurable_cash_folds": unmeasurable,
    "synthetic_pair": synthetic,
    "journal_14_five_years_pair": cases,
}
OUTPUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
print(json.dumps(report["review"], indent=2))
