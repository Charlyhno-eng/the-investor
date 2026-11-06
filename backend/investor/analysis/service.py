"""Orchestrate local analysis; versioned cache is invalidated by any data revision."""

import hashlib
import json
import threading

import numpy as np
from fastapi import HTTPException

from investor.analysis.metrics import equity, metrics
from investor.analysis.model import features, fit_model, forward_filter
from investor.analysis.strategy import simulate
from investor.db import connect

SLOTS = threading.BoundedSemaphore(1)  # Bound CPU/memory and BLAS thread configuration.
VERSION = "hmm-causal-2"


def analyze(asset_id, request):
    with connect() as db:
        asset = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if not asset:
            raise HTTPException(404, "Actif introuvable")
        rows = db.execute(
            "SELECT date,value FROM observations WHERE asset_id=? AND date>=? AND date<=? ORDER BY date",
            (asset_id, request.train_start.isoformat(), request.test_end.isoformat()),
        ).fetchall()
    key = hashlib.sha256(
        json.dumps(
            [
                VERSION,
                asset_id,
                dict(asset),
                request.model_dump(mode="json"),
                [(r["date"], r["value"]) for r in rows],
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    with connect() as db:
        cached = db.execute(
            "SELECT result FROM analysis_runs WHERE id=?", (key,)
        ).fetchone()
    if cached:
        return json.loads(cached["result"])
    if not SLOTS.acquire(blocking=False):
        raise HTTPException(
            429, "Une analyse est déjà en cours. Réessayez dans quelques instants."
        )
    try:
        result = calculate(dict(asset), rows, request)
        result["id"] = key
        with connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO analysis_runs(id,result) VALUES (?,?)",
                (key, json.dumps(result, allow_nan=False)),
            )
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        SLOTS.release()


def calculate(asset, rows, request):
    if len(rows) > 40000:
        raise ValueError("Maximum 40 000 observations par analyse.")
    if len(rows) < 2:
        raise ValueError("Historique insuffisant.")
    dates = np.array([r["date"] for r in rows])
    values = np.array([r["value"] for r in rows], dtype=float)
    is_yield = asset["metric"] == "yield"
    if not is_yield and np.any(values <= 0):
        raise ValueError(
            "Les rendements logarithmiques exigent des prix strictement positifs. Réduisez la période."
        )
    window = 3 if asset["frequency"] == "monthly" else 10
    changes, x = features(values, is_yield, window)
    dates = dates[1:]
    # Warm-up is past-only and removed from both fitting and scoring.
    train = (dates <= request.train_end.isoformat()) & (np.arange(len(dates)) >= window)
    test = (dates >= request.test_start.isoformat()) & (
        dates <= request.test_end.isoformat()
    )
    if train.sum() < 100 or test.sum() < 20:
        raise ValueError(
            "Sélectionnez au moins 100 variations d’entraînement après initialisation et 20 variations de test."
        )
    if np.std(changes[train]) < 1e-10:
        raise ValueError("La période d’entraînement est constante.")
    model, mean, scale, converged = fit_model(x[train])
    probabilities = forward_filter(model, (x - mean) / scale)
    state_means = model.means_[:, 0] * scale[0] + mean[0]
    order = np.argsort(state_means)
    labels = (
        ["Baisse des taux", "Stable", "Hausse des taux"]
        if is_yield
        else ["Défensif", "Intermédiaire", "Porteur"]
    )
    label_for = {int(state): labels[i] for i, state in enumerate(order)}
    test_prob = probabilities[test]
    test_dates = dates[test].tolist()
    test_changes = changes[test]
    regimes = [
        {
            "time": d,
            "state": label_for[int(np.argmax(p))],
            "probabilities": [float(p[s]) for s in order],
        }
        for d, p in zip(test_dates, test_prob)
    ]
    annualization = (
        12
        if asset["frequency"] == "monthly"
        else (365 if asset["category"] == "crypto" else 252)
    )
    notes = [
        "États filtrés avec les observations passées uniquement. Paramètres figés après la période 1."
    ]
    if not converged:
        notes.append(
            "Le meilleur ajustement n’a pas atteint le seuil de convergence : interpréter les régimes avec prudence."
        )
    if asset["frequency"] == "monthly":
        notes.append(
            "Observations mensuelles : la durée de détention et la confirmation sont exprimées en mois."
        )
    output = {
        "mode": "regimes" if is_yield else "backtest",
        "regimes": regimes,
        "states": [
            {
                "name": label_for[int(s)],
                "mean_change": float(state_means[s]),
                "persistence": float(model.transmat_[s, s]),
            }
            for s in order
        ],
        "transition_matrix": model.transmat_[order][:, order].tolist(),
        "train_points": int(train.sum()),
        "test_points": int(test.sum()),
        "periods_per_year": annualization,
        "warnings": notes,
        "actual_train": [str(dates[train][0]), str(dates[train][-1])],
        "actual_test": [test_dates[0], test_dates[-1]],
        "equity": [],
        "strategy_metrics": None,
        "benchmark_metrics": None,
        "trades": [],
        "exposure": None,
        "parameters": request.model_dump(mode="json"),
    }
    if is_yield:
        notes.append(
            "Analyse des variations du taux en points de pourcentage. Performance, alpha et bêta indisponibles : un taux n’est pas un prix négociable."
        )
        return output
    if asset["category"] == "commodity":
        notes.append(
            "Simulation sur prix spot ou indice mensuel : proxy de marché, sans roulement de futures, stockage ni exécution réelle."
        )
    # Pick the state with highest trained mean, only if it exceeds cash plus round-trip costs.
    cost = (request.fee_bps + request.slippage_bps) / 10000
    threshold = (
        np.log1p(request.risk_free_rate) / annualization + 2 * cost / request.min_hold
    )
    favorable = int(order[-1]) if state_means[order[-1]] > threshold else None
    if favorable is None:
        notes.append(
            "Aucun régime entraîné ne dépasse le seuil de rentabilité : stratégie en liquidités."
        )
        signal = np.zeros_like(test_prob)
        favorable = 0
    else:
        signal = test_prob
    net, benchmark, trades, positions = simulate(
        test_changes, signal, test_dates, favorable, request, annualization
    )
    # Benchmark starts at the close preceding the first test return, shared with strategy.
    first_index = int(np.flatnonzero(test)[0])
    baseline_date = rows[first_index]["date"]
    all_dates = [baseline_date] + test_dates
    output.update(
        {
            "equity": [
                {"time": d, "strategy": float(a * 100), "benchmark": float(b * 100)}
                for d, a, b in zip(all_dates, equity(net), equity(benchmark))
            ],
            "strategy_metrics": metrics(
                net, benchmark, annualization, request.risk_free_rate
            ),
            "benchmark_metrics": metrics(
                benchmark, benchmark, annualization, request.risk_free_rate
            ),
            "trades": trades,
            "exposure": float(np.mean(positions)),
        }
    )
    if not trades:
        notes.append(
            "Aucune transaction avec ces paramètres ; les ratios à dénominateur nul sont affichés comme indisponibles."
        )
    return output
