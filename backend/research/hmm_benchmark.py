"""Reproducible exploratory search; reads market SQLite without writing to it.

Run: PYTHONPATH=backend .venv/bin/python backend/research/hmm_benchmark.py
Selection is completed and saved before the final window is evaluated.
"""

import argparse
import hashlib
import itertools
import json
import logging
import sqlite3
import warnings
from datetime import UTC, datetime
from pathlib import Path

import hmmlearn
import numpy as np
import scipy
from hmmlearn import _hmmc
from hmmlearn.hmm import GaussianHMM
from investor.analysis.metrics import metrics
from investor.analysis.model import features, fit_model, forward_filter
from investor.analysis.schemas import AnalysisRequest
from investor.analysis.strategy import simulate
from scipy.special import logsumexp
from threadpoolctl import threadpool_limits

MODELS = {
    "current": (10, 2, "diag", None, False),
    "momentum5": (5, 2, "diag", None, False),
    "momentum20": (20, 2, "diag", None, False),
    "returns_only": (10, 2, "diag", None, True),
    "full_covariance": (10, 2, "full", None, False),
    "three_states": (10, 3, "diag", None, False),
    "rolling504": (10, 2, "diag", 504, False),
    "rolling1008": (10, 2, "diag", 1008, False),
}
RULES = list(itertools.product((0.65, 0.8, 0.9), (0.35, 0.5), (1, 3, 5), (1, 3, 5)))
BASELINE = ("current", (0.8, 0.5, 5, 3))


def read_assets(database):
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        # A single read transaction provides a consistent snapshot across assets.
        db.execute("BEGIN")
        assets = []
        for asset in db.execute(
            "SELECT * FROM assets WHERE category IN ('stock','crypto') ORDER BY id"
        ).fetchall():
            rows = db.execute(
                "SELECT date,value FROM observations WHERE asset_id=? ORDER BY date",
                (asset["id"],),
            ).fetchall()
            if len(rows) < 1024:
                raise ValueError(f"Insufficient history: {asset['id']}")
            dates, values = zip(*[(r["date"], r["value"]) for r in rows[-2016:]])
            values = np.asarray(values, dtype=float)
            if not np.isfinite(values).all() or np.any(values <= 0):
                raise ValueError(f"Invalid prices: {asset['id']}")
            assets.append(
                {"asset": dict(asset), "dates": list(dates), "values": values}
            )
        if not assets:
            raise ValueError("No stocks or cryptocurrencies in the database")
    return assets


def fit(training, states, covariance):
    if states == 2 and covariance == "diag":
        return fit_model(training)
    mean = training.mean(axis=0)
    scale = np.maximum(training.std(axis=0), 1e-8)
    normalized = (training - mean) / scale
    candidates = []
    for seed in (17, 41, 83):
        model = GaussianHMM(
            n_components=states,
            covariance_type=covariance,
            n_iter=150,
            tol=1e-4,
            min_covar=1e-3,
            random_state=seed,
            implementation="scaling",
        )
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                model.fit(normalized)
            score = model.score(normalized)
            history = model.monitor_.history
            delta = history[-1] - history[-2] if len(history) > 1 else np.inf
            converged = bool(np.isfinite(delta) and -0.01 <= delta < model.tol)
            if np.isfinite(score) and np.isfinite(model.covars_).all():
                candidates.append((score, model, converged))
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            continue
    if not candidates:
        raise ValueError("No valid initialization")
    _, model, converged = max(candidates, key=lambda item: item[0])
    return model, mean, scale, converged


def prepare(data, model_name, start, stop):
    window, states, covariance, rolling, returns_only = MODELS[model_name]
    # Slice before computing features: no observation after this fold is read.
    changes, x = features(data["values"][: stop + 1], False, window)
    momentum = x[:, 1].copy()
    if returns_only:
        x = x[:, :1]
    train_start = max(window, start - rolling) if rolling else window
    model, mean, scale, converged = fit(x[train_start:start], states, covariance)
    # Expanding variants preserve the application's exact filtering history.
    filter_start = train_start if rolling else 0
    observations = (x[filter_start:] - mean) / scale
    if covariance == "diag":
        probabilities = forward_filter(model, observations)
    else:
        emission = model._compute_log_likelihood(observations)
        likelihood = np.exp(emission - emission.max(axis=1, keepdims=True))
        try:
            _, probabilities, _ = _hmmc.forward_scaling(
                model.startprob_, model.transmat_, likelihood
            )
        except ValueError:
            _, lattice = _hmmc.forward_log(model.startprob_, model.transmat_, emission)
            probabilities = np.exp(lattice - logsumexp(lattice, axis=1, keepdims=True))
    means = model.means_[:, 0] * scale[0] + mean[0]
    favorable = int(np.argmax(means))
    if means[favorable] <= 0:
        probabilities = np.zeros_like(probabilities)
    return {
        "changes": changes[start:stop],
        "probabilities": probabilities[start - filter_start :],
        "dates": data["dates"][start + 1 : stop + 1],
        "favorable": favorable,
        "entry_allowed": momentum[start:stop] > 0,
        "converged": bool(converged),
        "iterations": model.monitor_.iter,
        "train_points": start - train_start,
    }


def evaluate(prepared, rule, annualization, cost=15):
    entry, exit_, confirm_buy, confirm_sell = rule
    request = AnalysisRequest(
        train_start="2000-01-01",
        train_end="2001-01-01",
        test_start="2002-01-01",
        test_end="2003-01-01",
        entry_probability=entry,
        exit_probability=exit_,
        entry_confirmation=confirm_buy,
        exit_confirmation=confirm_sell,
        fee_bps=10,
        slippage_bps=cost - 10,
    )
    net, benchmark, trades, positions = simulate(
        prepared["changes"],
        prepared["probabilities"],
        prepared["dates"],
        prepared["favorable"],
        request,
        annualization,
        entry_allowed=prepared["entry_allowed"],
    )
    summary = metrics(net, benchmark, annualization, 0)
    summary.update(
        {
            "exposure": float(np.mean(positions)),
            "orders": len(trades),
            "orders_per_year": len(trades) * annualization / len(net),
        }
    )
    return summary, metrics(benchmark, benchmark, annualization, 0)


def utility(result):
    # Fixed before running: reward net return and Sharpe; penalize loss/exposure/churn.
    return float(
        0.35 * np.clip(result["sharpe"] or 0, -3, 3)
        + 0.35 * np.clip(result["annualized_return"], -1, 1)
        - 0.5 * result["maximum_drawdown"]
        - 0.15 * result["exposure"]
        - 0.001 * result["orders_per_year"]
    )


def score(results, assets):
    # Each asset's three folds count equally; each category receives half the weight.
    per_asset = [np.mean([utility(r) for r in folds]) for folds in results]
    stability = [np.std([utility(r) for r in folds]) for folds in results]
    return float(
        np.mean(
            [
                np.mean(
                    [
                        per_asset[i] - 0.15 * stability[i]
                        for i, a in enumerate(assets)
                        if a["asset"]["category"] == category
                    ]
                )
                for category in ("stock", "crypto")
                if any(a["asset"]["category"] == category for a in assets)
            ]
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/investor.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("docs/hmm-benchmark.json"))
    args = parser.parse_args()
    logging.getLogger("hmmlearn.base").setLevel(logging.ERROR)
    assets = read_assets(args.database)
    digest = hashlib.sha256()
    for data in assets:
        digest.update(
            json.dumps([data["asset"], data["dates"]], sort_keys=True).encode()
        )
        digest.update(data["values"].tobytes())
    candidates = [(model, rule) for model in MODELS for rule in RULES]
    validation = {str(c): [] for c in candidates}
    diagnostics = []
    with threadpool_limits(limits=1):
        for data in assets:
            n = len(data["values"]) - 1
            edges = [int(n * fraction) for fraction in (0.5, 0.6, 0.7, 0.8)]
            annualization = 365 if data["asset"]["category"] == "crypto" else 252
            for model_name in MODELS:
                prepared = [
                    prepare(data, model_name, a, b)
                    for a, b in itertools.pairwise(edges)
                ]
                diagnostics.append(
                    {
                        "asset": data["asset"]["id"],
                        "model": model_name,
                        "converged": [p["converged"] for p in prepared],
                        "iterations": [p["iterations"] for p in prepared],
                    }
                )
                for rule in RULES:
                    validation[str((model_name, rule))].append(
                        [evaluate(p, rule, annualization)[0] for p in prepared]
                    )
            print(f"Validation complete: {data['asset']['id']}", flush=True)
        ranking = sorted(
            [
                {
                    "model": model,
                    "rule": list(rule),
                    "score": score(validation[str((model, rule))], assets),
                }
                for model, rule in candidates
            ],
            key=lambda row: row["score"],
            reverse=True,
        )
        selected = ranking[0]
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "versions": {
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "hmmlearn": hmmlearn.__version__,
            },
            "data_sha256": digest.hexdigest(),
            "protocol": {
                "maximum_points": 2016,
                "validation_edges": [0.5, 0.6, 0.7, 0.8],
                "final_test": [0.8, 1.0],
                "cost_bps_per_order": 15,
                "stress_cost_bps_per_order": 30,
                "model_variants": MODELS,
                "rule_count": len(RULES),
                "candidate_count": len(candidates),
                "score": "mean by category(mean by asset(mean fold utility - 0.15 * std fold utility))",
                "utility": "0.35*clip(Sharpe,-3,3)+0.35*clip(CAGR,-1,1)-0.5*MDD-0.15*exposure-0.001*annual_orders",
                "seeds": [17, 41, 83],
                "max_iterations": 150,
                "caveat": "Exploratory: these historical data have already been inspected in earlier research.",
            },
            "selected_before_final_test": selected,
            "ranking": ranking,
            "validation_diagnostics": diagnostics,
            "assets": [],
        }
        # Persist the choice before accessing holdout prices for evaluation.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(f"Frozen selection: {selected}", flush=True)
        for data in assets:
            n = len(data["values"]) - 1
            start = int(n * 0.8)
            annualization = 365 if data["asset"]["category"] == "crypto" else 252
            result = {
                "id": data["asset"]["id"],
                "name": data["asset"]["name"],
                "category": data["asset"]["category"],
                "points": n + 1,
                "history": [data["dates"][0], data["dates"][-1]],
                "validation_windows": [
                    [data["dates"][int(n * a) + 1], data["dates"][int(n * b)]]
                    for a, b in ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8))
                ],
                "test": [data["dates"][start + 1], data["dates"][-1]],
            }
            for label, (model_name, rule) in {
                "baseline": BASELINE,
                "selected": (selected["model"], tuple(selected["rule"])),
            }.items():
                p = prepare(data, model_name, start, n)
                normal, benchmark = evaluate(p, rule, annualization)
                stress, _ = evaluate(p, rule, annualization, cost=30)
                result[label] = {
                    "normal": normal,
                    "stress": stress,
                    "converged": p["converged"],
                    "validation": validation[str((model_name, tuple(rule)))][
                        len(report["assets"])
                    ],
                }
                result["benchmark"] = benchmark
            report["assets"].append(result)
            print(f"Final test complete: {result['id']}", flush=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
