"""Orchestrate local analysis; versioned cache is invalidated by any data revision."""

import hashlib
import json
import threading
from itertools import pairwise

import numpy as np
from fastapi import HTTPException

from investor.analysis.basic import fit_cached, simulate
from investor.analysis.metrics import equity, metrics
from investor.analysis.model import forward_filter
from investor.db import connect

SLOTS = threading.BoundedSemaphore(1)  # Bound CPU/memory and BLAS thread configuration.
VERSION = "hmm-two-state-dominant-filtered-live-v3"


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
    changes = np.diff(np.log(values))
    x = changes[:, None]
    row_dates = [str(r["date"]) for r in rows]
    if any(a >= b for a, b in pairwise(row_dates)):
        raise ValueError("Les dates doivent être uniques et strictement croissantes.")
    dates = np.array(row_dates[1:])
    train = (
        (np.array(row_dates[:-1]) >= request.train_start.isoformat())
        & (dates > request.train_start.isoformat())
        & (dates <= request.train_end.isoformat())
    )
    test = (dates >= request.test_start.isoformat()) & (
        dates <= request.test_end.isoformat()
    )
    if train.sum() < 100 or test.sum() < 20:
        raise ValueError(
            "Sélectionnez au moins 100 variations d’entraînement et 20 variations de test."
        )
    if np.std(changes[train]) < 1e-10:
        raise ValueError("La période d’entraînement est constante.")
    model, mean, scale, seed = fit_cached(changes[train])
    selection = {
        "method": "fixed_two_states_training_likelihood",
        "selected_states": 2,
        "regimes_supported": True,
        "validation_points": 0,
        "validation_scores": {},
        "baseline_score": None,
        "seed": seed,
    }
    converged = model.monitor_.converged
    probabilities = forward_filter(model, (x - mean) / scale)
    # Filter across any gap without fitting on it or opening positions there.
    test_prob = probabilities[test]
    log_means = model.means_[:, 0] * scale + mean
    volatility = np.sqrt(model.covars_[:, 0, 0]) * scale
    order = np.argsort(log_means)
    names = ["Autre · moyenne inférieure", "Haussier · moyenne supérieure"]
    labels = {int(state): name for state, name in zip(order, names)}
    test_dates = dates[test].tolist()
    test_indices = np.flatnonzero(test)
    first_index = int(test_indices[0])
    if first_index == 0:
        raise ValueError("Une observation précédant le test est requise.")
    bullish = int(np.argmax(log_means))
    beliefs = probabilities[first_index - 1 : test_indices[-1] + 1]
    net, benchmark, orders, positions = simulate(
        changes[test], beliefs, bullish, request.fee_bps
    )
    trades = [
        {
            "time": test_dates[t["index"]],
            "side": t["side"],
            "probability": float(beliefs[t["index"], bullish])
            if t["index"] < len(test_dates) - 1
            else None,
            "reason": "final_liquidation"
            if t["index"] == len(test_dates) - 1
            else "regime",
        }
        for t in orders
    ]
    annualization = 365 if asset["category"] == "crypto" else 252
    all_dates = [rows[first_index]["date"]] + test_dates
    notes = [
        "HMM à exactement deux états : une seule observation, le rendement logarithmique terminé. Trois initialisations comparées par vraisemblance d’entraînement uniquement.",
        "Paramètres figés après l’entraînement. Probabilités filtrées causalement, sans lissage ; les données entre entraînement et test mettent à jour le filtre sans réajuster les paramètres.",
        "Investi lorsque l’état à moyenne entraînée supérieure est dominant, en liquidités sinon. Les frais sont prélevés sur les ordres ; ils ne bloquent ni les achats ni les ventes.",
        "Signal en clôture, exécution à la clôture suivante. Le dernier signal précédant le test peut être exécuté à sa première clôture. Frais identiques à chaque achat et vente, liquidation finale comprise ; liquidités non rémunérées, hors glissement et impôts.",
        "Les états décrivent des distributions de rendement, pas des phases de hausse ou de baisse certaines. Une meilleure densité prédictive ne démontre pas un avantage de trading.",
    ]
    if log_means[bullish] <= 0:
        notes.append(
            "L’état dit haussier a la moyenne la plus élevée, mais cette moyenne d’entraînement n’est pas positive."
        )
    if not converged:
        notes.append(
            "L’ajustement retenu n’a pas atteint le seuil de convergence ; interpréter les régimes avec prudence."
        )
    if not trades:
        notes.append(
            "Aucune transaction : l’état haussier n’a pas dominé aux clôtures exécutables de cette période."
        )
    strategy_metrics = metrics(net, benchmark, annualization, 0)
    benchmark_metrics = metrics(benchmark, benchmark, annualization, 0)
    held = np.r_[0, np.asarray(positions[:-1])]
    negative = log_means[np.argmax(beliefs[:-1], axis=1)] < 0
    exit_signals = np.argmax(beliefs[:-1], axis=1) != bullish
    diagnostics = {
        "entry_reachable": True,
        "exit_reachable": True,
        "entry_signal_observations": int((~exit_signals).sum()),
        "exit_signal_observations": int(exit_signals.sum()),
        "negative_states": int((log_means < 0).sum()),
        "negative_dominant_observations": int(negative.sum()),
        "negative_dominant_while_held": int((negative & (held == 1)).sum()),
        "negative_dominant_without_exit_while_held": int(
            (negative & ~exit_signals & (held == 1)).sum()
        ),
        "net_excess_return": strategy_metrics["total_return"]
        - benchmark_metrics["total_return"],
        "nearly_always_invested": bool(held.mean() >= 0.95),
        "nearly_always_cash": bool(held.mean() <= 0.05),
    }
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
        "model_version": VERSION,
        "diagnostics": diagnostics,
        "policy": {
            "review": "daily",
            "signal": "hmm_dominant_higher_mean_state",
            "entry_threshold": 0.5,
            "exit_threshold": 0.5,
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
