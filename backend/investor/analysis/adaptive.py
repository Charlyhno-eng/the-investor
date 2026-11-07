"""Causal trend-regime classification, rolling calibration and long/cash trading.

The observation is an exponentially weighted return/volatility ratio. Unlike
daily return density fitting, this explicitly describes persistent direction.
State indices are ordered anew at every calibration, never copied across fits.
"""

from functools import lru_cache

import numpy as np
from threadpoolctl import threadpool_limits

from investor.analysis.metrics import equity, metrics
from investor.analysis.model import forward_filter
from investor.analysis.research_legacy import _fit

SPAN, REFIT, LOOKBACK = 30, 63, 1260
NAMES = ("Défavorable", "Transition", "Favorable")


def observations(values):
    changes = np.diff(np.log(values))
    trend, volatility = np.full(len(changes), np.nan), np.full(len(changes), np.nan)
    if len(changes):
        alpha = 2 / (SPAN + 1)
        mean, variance = changes[0], 0.0
        for i, change in enumerate(changes):
            delta = change - mean
            mean += alpha * delta
            variance = (1 - alpha) * (variance + alpha * delta**2)
            if i >= SPAN - 1:
                volatility[i] = np.sqrt(max(variance, 1e-16))
                trend[i] = mean / volatility[i]
    return changes, trend[:, None], volatility


def fit_regimes(training):
    training = np.ascontiguousarray(training, dtype=np.float64)
    return _fit_cached(training.shape, training.tobytes())


@lru_cache(maxsize=128)
def _fit_cached(shape, data):
    training = np.frombuffer(data, dtype=np.float64).reshape(shape)
    with threadpool_limits(limits=1):
        return _fit(training, 3)


def targets(probabilities, centers, persistence, volatility, fee_bps):
    """Dominant adverse regime exits; costs never veto that exit.

    Middle-state ambiguity holds the current position. Entry additionally asks
    that the estimated move over the favorable state's mean duration covers
    an entry and exit fee. This is a heuristic for costs, not a promised return.
    A relative low state with positive drift is not called an absolute decline.
    """
    dominant = probabilities.argmax(axis=1)
    action = np.full(len(probabilities), -1, dtype=int)  # -1 means hold.
    action[(dominant == 0) & (centers[0] < 0)] = 0
    duration = 1 / max(1 - persistence[-1], 1e-12)
    estimated_move = probabilities[:, -1] * max(centers[-1], 0) * volatility * duration
    round_trip = -2 * np.log1p(-fee_bps / 10000)
    action[(dominant == 2) & (centers[-1] > 0) & (estimated_move > round_trip)] = 1
    return action


def signals(x, volatility, dates, request):
    valid = np.isfinite(x).all(axis=1)
    train = (
        valid
        & (dates > request.train_start.isoformat())
        & (dates <= request.train_end.isoformat())
    )
    test = (dates >= request.test_start.isoformat()) & (
        dates <= request.test_end.isoformat()
    )
    if train.sum() < 100 or test.sum() < 20 or not valid[test].all():
        raise ValueError(
            "Sélectionnez au moins 100 variations d’entraînement après les 30 observations de contexte, et 20 variations de test."
        )
    initial = np.flatnonzero(train)[-LOOKBACK:]
    first, last = np.flatnonzero(test)[[0, -1]]
    probabilities, actions, calibrations = [], [], []
    model = None
    index = np.arange(len(x))
    for start in range(first, last + 1, REFIT):
        stop = min(start + REFIT, last + 1)
        proposed = (
            initial
            if model is None
            else np.flatnonzero(valid & (index < start))[-LOOKBACK:]
        )
        failure = None
        try:
            calibrated = fit_regimes(x[proposed])
            model, mean, scale, converged = calibrated
            used = proposed
        except ValueError as exc:
            if model is None:
                raise
            failure = str(exc)
        # Re-filter the new model's own past. No future state smoothing and no
        # assumption that its raw state 0 means the previous model's state 0.
        context = np.flatnonzero(valid & (index >= used[0]) & (index < stop))
        p = forward_filter(model, (x[context] - mean) / scale)[context >= start]
        centers = model.means_[:, 0] * scale[0] + mean[0]
        order = np.argsort(centers)
        p, centers = p[:, order], centers[order]
        transition = model.transmat_[order][:, order]
        actions.extend(
            targets(
                p,
                centers,
                transition.diagonal(),
                volatility[start:stop],
                request.fee_bps,
            )
        )
        probabilities.extend(p.tolist())
        # These are descriptions of the model's observation, not daily return
        # forecasts. The API distinguishes their dimensionless units.
        calibrations.append(
            {
                "first_signal": str(dates[start]),
                "last_signal": str(dates[stop - 1]),
                "train_start": str(dates[used[0]]),
                "train_end": str(dates[used[-1]]),
                "train_points": len(used),
                "converged": bool(converged),
                "failure": failure,
                "centers": centers.tolist(),
                "transition_matrix": transition.tolist(),
            }
        )
    return np.asarray(probabilities), np.asarray(actions), calibrations, train, test


def simulate(changes, dates, action, probabilities, request):
    fee = request.fee_bps / 10000
    net, held = np.zeros(len(changes)), []
    position, pending, pending_probability = 0, -1, None
    positions, trades = [], []
    for i, change in enumerate(changes):
        held.append(position)
        net[i] = np.expm1(change) if position else 0.0
        target = 0 if i == len(changes) - 1 else pending
        if target >= 0 and target != position:
            net[i] = (1 + net[i]) * (1 - fee) - 1
            position = int(target)
            trades.append(
                {
                    "time": dates[i],
                    "side": "buy" if position else "sell",
                    "probability": pending_probability
                    if i < len(changes) - 1
                    else None,
                    "reason": "regime" if i < len(changes) - 1 else "final_liquidation",
                }
            )
        positions.append(position)
        pending = action[i]
        pending_probability = float(probabilities[i, -1])
    market = np.expm1(changes)
    market[0] = (1 + market[0]) * (1 - fee) - 1
    market[-1] = (1 + market[-1]) * (1 - fee) - 1
    return net, market, trades, positions, float(np.mean(held))


def calculate(asset, rows, request):
    if not 2 <= len(rows) <= 40000:
        raise ValueError("Historique insuffisant ou supérieur à 40 000 observations.")
    values = np.array([r["value"] for r in rows], dtype=float)
    if not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError("Les prix doivent être finis et strictement positifs.")
    changes, x, volatility = observations(values)
    dates = np.array([r["date"] for r in rows[1:]])
    train = (
        np.isfinite(x[:, 0])
        & (dates > request.train_start.isoformat())
        & (dates <= request.train_end.isoformat())
    )
    if train.any() and np.std(changes[train]) < 1e-10:
        raise ValueError("La période d’entraînement est constante.")
    p, action, calibrations, train, test = signals(x, volatility, dates, request)
    test_dates = dates[test].tolist()
    net, market, trades, positions, exposure = simulate(
        changes[test], test_dates, action, p, request
    )
    annual = 365 if asset["category"] == "crypto" else 252
    last = calibrations[-1]
    first_index = int(np.flatnonzero(test)[0])
    equity_dates = [rows[first_index]["date"]] + test_dates
    warnings = [
        "HMM à trois états sur le ratio moyenne/volatilité exponentielles des rendements logarithmiques, span 30. Les états décrivent une tendance relative, pas une promesse de rendement.",
        "Trois initialisations départagées par vraisemblance d’entraînement. Réentraînement toutes les 63 observations sur au plus 1 260 variations passées, sans sélection sur le gain de test ni quota d’ordres.",
        "Filtrage causal. Un régime défavorable dominant avec une tendance négative déclenche une sortie, que les frais ne peuvent pas bloquer. Le régime intermédiaire conserve la position ; une entrée favorable doit couvrir une estimation des frais aller-retour sur la durée moyenne apprise du régime.",
        "Signal en clôture t, exécution à la clôture t+1, premier rendement perçu à t+2. Même taux à l’achat et à la vente, benchmark net de frais. Aucun stop ni limite de drawdown. Liquidités non rémunérées, hors glissement et impôts.",
        "Les états et la matrice affichés décrivent la dernière calibration. Les régimes passés conservent leurs probabilités d’origine. Le chevauchement des observations limite la calibration des probabilités.",
        "Méthode expérimentale : une exposition réduite et des changements de régime ne démontrent pas une surperformance. Les historiques réutilisés ne prouvent pas une absence de surapprentissage.",
    ]
    if any(not c["converged"] for c in calibrations):
        warnings.append(
            "Au moins un ajustement n’a pas atteint le seuil de convergence."
        )
    if any(c["failure"] for c in calibrations):
        warnings.append(
            "Au moins une recalibration a échoué ; le dernier modèle utilisable a été conservé, comme indiqué dans le journal des calibrations."
        )
    return {
        "mode": "backtest",
        "regimes": [
            {"time": d, "state": NAMES[int(np.argmax(q))], "probabilities": q.tolist()}
            for d, q in zip(test_dates, p)
        ],
        "states": [
            {
                "name": name,
                "trend_score": float(center),
                "persistence": last["transition_matrix"][i][i],
            }
            for i, (name, center) in enumerate(zip(NAMES, last["centers"]))
        ],
        "transition_matrix": last["transition_matrix"],
        "calibrations": calibrations,
        "model_selection": {
            "method": "fixed_three_state_normalized_trend",
            "feature_span": SPAN,
            "refit_every": REFIT,
            "lookback": LOOKBACK,
            "selected_states": 3,
        },
        "policy": {
            "review": "daily",
            "signal": "dominant_trend_regime",
            "transaction_target": None,
            "position_stop": None,
        },
        "train_points": int(train.sum()),
        "test_points": int(test.sum()),
        "periods_per_year": annual,
        "warnings": warnings,
        "actual_train": [str(dates[train][0]), str(dates[train][-1])],
        "actual_test": [test_dates[0], test_dates[-1]],
        "equity": [
            {"time": d, "strategy": float(a * 100), "benchmark": float(b * 100)}
            for d, a, b in zip(equity_dates, equity(net), equity(market))
        ],
        "strategy_metrics": metrics(net, market, annual, 0),
        "benchmark_metrics": metrics(market, market, annual, 0),
        "trades": trades,
        "exposure": exposure,
        "positions": [
            {"time": d, "position": int(position)}
            for d, position in zip(test_dates, positions)
        ],
        "parameters": request.model_dump(mode="json"),
    }
