"""Orchestrate local analysis; versioned cache is invalidated by any data revision."""

import hashlib
import json
import threading

import numpy as np
from fastapi import HTTPException

from investor.analysis.diagnostics import switching_diagnostics
from investor.analysis.metrics import equity, metrics
from investor.analysis.model import forward_filter
from investor.analysis.regimes import fit_regimes, observations
from investor.analysis.switching import simulate_switching, switching_values
from investor.db import connect

SLOTS = threading.BoundedSemaphore(1)  # Bound CPU/memory and BLAS thread configuration.
VERSION = "hmmlearn-directional-return-validation-switching-diagnostics-v3"


def analyze(asset_id, request):
    with connect() as db:
        asset = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if not asset:
            raise HTTPException(404, "Actif introuvable")
        if asset["category"] not in ("stock", "crypto"):
            raise HTTPException(
                422,
                "L’analyse HMM est réservée aux actions et cryptomonnaies ; "
                "elle n’est pas disponible pour les matières premières et obligations.",
            )
        rows = db.execute(
            "SELECT date,value FROM observations WHERE asset_id=? AND date>=? AND date<=? ORDER BY date",
            (asset_id, request.train_start.isoformat(), request.test_end.isoformat()),
        ).fetchall()
    request = resolve_fees(dict(asset), request)
    key = hashlib.sha256(
        json.dumps(
            [
                VERSION,
                asset_id,
                dict(asset),
                request.model_dump(mode="json"),
                [dict(r) for r in rows],
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


def resolve_fees(asset, request):
    if request.fee_bps is None:
        return request.model_copy(
            update={"fee_bps": 1 if asset["category"] == "crypto" else 50}
        )
    return request


def calculate(asset, rows, request, *, policy=None):
    request = resolve_fees(asset, request)
    if policy is not None or asset["metric"] == "yield":
        from investor.analysis.legacy import calculate as legacy

        return legacy(asset, rows, request, policy=policy)
    if len(rows) > 40000:
        raise ValueError("Maximum 40 000 observations par analyse.")
    if len(rows) < 2:
        raise ValueError("Historique insuffisant.")
    values = np.array([r["value"] for r in rows], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Les observations doivent être finies.")
    if np.any(values <= 0):
        raise ValueError(
            "Les rendements logarithmiques exigent des prix strictement positifs."
        )
    changes, x = observations(values)
    dates = np.array([r["date"] for r in rows[1:]])
    valid = np.isfinite(x).all(axis=1)
    train = (
        valid
        & (dates > request.train_start.isoformat())
        & (dates <= request.train_end.isoformat())
    )
    test = (dates >= request.test_start.isoformat()) & (
        dates <= request.test_end.isoformat()
    )
    if train.sum() < 100 or test.sum() < 20:
        raise ValueError(
            "Sélectionnez au moins 100 variations d’entraînement après les 20 observations de contexte, et 20 variations de test."
        )
    if np.std(changes[train]) < 1e-10:
        raise ValueError("La période d’entraînement est constante.")
    model, mean, scale, converged, selection = fit_regimes(x[train])
    selected = x[valid][:, selection["observable_columns"]]
    probabilities = forward_filter(model, (selected - mean) / scale)
    # Valid context begins before the test. This index keeps the filter's past
    # observations (including any gap between training and testing) intact.
    test_prob = probabilities[test[valid]]
    log_means = model.means_[:, 0] * scale[0] + mean[0]
    volatility = np.sqrt(model.covars_[:, 0, 0]) * scale[0]
    order = np.argsort(log_means)
    names = ["Baisse" if log_means[order[0]] < 0 else "Hausse modérée"]
    if len(order) == 3:
        names.append("Transition")
    names.append("Hausse" if log_means[order[-1]] > 0 else "Baisse modérée")
    labels = {int(state): name for state, name in zip(order, names)}
    test_dates = dates[test].tolist()
    advantage, cost = switching_values(model, log_means, request.fee_bps)
    net, benchmark, trades, positions = simulate_switching(
        changes[test], test_prob, test_dates, request, advantage, cost, log_means > 0
    )
    annualization = 365 if asset["category"] == "crypto" else 252
    first_index = int(np.flatnonzero(test)[0])
    all_dates = [rows[first_index]["date"]] + test_dates
    notes = [
        "HMM directionnel sur rendement logarithmique, avec contexte optionnel de moyenne et volatilité des 20 dernières variations. Le contexte est une observation du modèle, sans filtre technique supplémentaire.",
        "Deux ou trois états, avec ou sans contexte, choisis selon la densité prédictive du prochain rendement sur les derniers 20 % de l’entraînement, puis ajustement sur tout l’entraînement. Aucun gain de test ne sélectionne le modèle.",
        "Probabilités filtrées avec le passé uniquement. Paramètres figés après l’entraînement ; les régimes sont classés par rendement moyen estimé, et non par volatilité.",
        "Décisions quotidiennes long/liquidités par valeur de continuation du HMM, frais identiques à chaque achat et vente. Aucun stop de drawdown, quota de transactions ou délai de détention imposé.",
        "Signal en clôture, ordre à la clôture suivante. Frais inclus, hors glissement et impôts ; liquidités non rémunérées. La politique utilise une approximation des états cachés par leurs probabilités filtrées.",
        "Le contexte glissant crée une dépendance entre observations : les probabilités sont des scores de modèle, sans garantie de calibration. Ces régimes ne garantissent pas une prévision des rendements.",
    ]
    if not converged:
        notes.append(
            "L’ajustement retenu n’a pas atteint le seuil de convergence ; interpréter les régimes avec prudence."
        )
    if not trades:
        notes.append(
            "Aucune transaction : le modèle ne prévoit pas un avantage suffisant après frais."
        )
    strategy_metrics = metrics(net, benchmark, annualization, 0)
    benchmark_metrics = metrics(benchmark, benchmark, annualization, 0)
    diagnostics = switching_diagnostics(
        test_prob,
        log_means,
        advantage,
        cost,
        positions,
        strategy_metrics["total_return"],
        benchmark_metrics["total_return"],
    )
    if not diagnostics["exit_reachable"]:
        notes.append(
            "Aucune sortie de régime n’est possible avec les paramètres appris et cette règle de continuation : même une probabilité de 100 % dans l’un des états ne franchit pas le seuil de vente. Seule la liquidation finale peut vendre. Ce résultat ne valide pas une stratégie de changements de régime."
        )
    if diagnostics["nearly_always_invested"]:
        notes.append(
            "Exposition supérieure ou égale à 95 % : cette simulation reste proche de l’achat-conservation. Ce seuil est un diagnostic ; il ne force aucune transaction."
        )
    return {
        "mode": "backtest",
        "regimes": [
            {
                "time": d,
                "state": labels[int(np.argmax(p))],
                "probabilities": [float(p[s]) for s in order],
            }
            for d, p in zip(test_dates, test_prob)
        ],
        "states": [
            {
                "name": labels[int(s)],
                "mean_change": float(np.expm1(log_means[s])),
                "persistence": float(model.transmat_[s, s]),
                "volatility": float(volatility[s]),
            }
            for s in order
        ],
        "transition_matrix": model.transmat_[order][:, order].tolist(),
        "model_selection": selection,
        "diagnostics": diagnostics,
        "policy": {
            "review": "daily",
            "signal": "hmm_cost_switching",
            "transaction_target": None,
            "position_stop": None,
        },
        "train_points": int(train.sum()),
        "test_points": int(test.sum()),
        "periods_per_year": annualization,
        "warnings": notes,
        "actual_train": [str(dates[train][0]), str(dates[train][-1])],
        "actual_test": [test_dates[0], test_dates[-1]],
        "equity": [
            {"time": d, "strategy": float(a * 100), "benchmark": float(b * 100)}
            for d, a, b in zip(all_dates, equity(net), equity(benchmark))
        ],
        "strategy_metrics": strategy_metrics,
        "benchmark_metrics": benchmark_metrics,
        "trades": trades,
        "exposure": float(np.mean(positions)),
        "positions": [
            {"time": d, "position": int(p)} for d, p in zip(test_dates, positions)
        ],
        "parameters": request.model_dump(mode="json"),
    }
