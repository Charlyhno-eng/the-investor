"""Historical weekly policies retained only for explicit research comparisons."""

import numpy as np

from investor.analysis.metrics import equity, metrics
from investor.analysis.model import forward_filter
from investor.analysis.research_legacy import features, fit_model
from investor.analysis.strategy import (
    DEFAULT_POLICY_NAME,
    POLICIES,
    describe_policy,
    simulate,
    trend_filter,
)


def calculate(asset, rows, request, *, policy=None):
    policy = policy or POLICIES[DEFAULT_POLICY_NAME]
    if len(rows) > 40000:
        raise ValueError("Maximum 40 000 observations par analyse.")
    if len(rows) < 2:
        raise ValueError("Historique insuffisant.")
    dates = np.array([r["date"] for r in rows])
    values = np.array([r["value"] for r in rows], dtype=float)
    is_yield = asset["metric"] == "yield"
    if not np.isfinite(values).all():
        raise ValueError("Les observations doivent être finies.")
    if not is_yield and np.any(values <= 0):
        raise ValueError(
            "Les rendements logarithmiques exigent des prix strictement positifs. Réduisez la période."
        )
    changes, x = features(values, is_yield)
    dates = dates[1:]
    train = (dates > request.train_start.isoformat()) & (
        dates <= request.train_end.isoformat()
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
    model, mean, scale, converged = fit_model(x[train])
    probabilities = forward_filter(model, (x - mean) / scale)
    state_means = model.means_[:, 0] * scale[0] + mean[0]
    state_volatility = np.sqrt(model.covars_[:, 0, 0]) * scale[0]
    order = np.argsort(state_volatility)
    labels = ["Taux calmes", "Taux volatils"] if is_yield else ["Calme", "Extrême"]
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
        "Deux régimes gaussiens estimés sur les rendements journaliers : calme et extrême. Le HMM filtre le risque ; les décisions de position sont hebdomadaires avec hystérésis.",
        "États filtrés avec les observations passées uniquement. Paramètres figés après la période 1.",
        "Les régimes sont classés par volatilité sur l’entraînement. Un régime calme peut aussi subir des pertes ; ce modèle est un filtre de risque.",
    ]
    if not converged:
        notes.append(
            "Le meilleur ajustement n’a pas atteint le seuil de convergence : interpréter les régimes avec prudence."
        )
    if asset["frequency"] == "monthly":
        notes.append(
            "Observations mensuelles : le régime est mis à jour une fois par mois."
        )
    output = {
        "mode": "regimes" if is_yield else "backtest",
        "regimes": regimes,
        "states": [
            {
                "name": label_for[int(s)],
                "mean_change": float(state_means[s]),
                "persistence": float(model.transmat_[s, s]),
                "volatility": float(state_volatility[s]),
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
        "positions": [],
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
    risk_events = []
    trend = (
        trend_filter(values, policy.trend_window)[1:][test]
        if policy.trend_window
        else None
    )
    net, benchmark, trades, positions = simulate(
        test_changes,
        test_prob,
        test_dates,
        int(order[0]),
        request,
        annualization,
        policy=policy,
        trend=trend,
        risk_events=risk_events,
    )
    output["policy"] = describe_policy(policy)
    output["risk_control"] = {
        "threshold": policy.drawdown_stop,
        "latched": bool(risk_events),
        "events": risk_events,
    }
    notes.append(
        "Protection : seuil de drawdown net de 10 % depuis le sommet du capital, "
        "détecté à la clôture et exécuté à la clôture suivante. Le seuil peut être dépassé. "
        "Après déclenchement, les achats restent bloqués jusqu’à la fin du test."
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
            "strategy_metrics": metrics(net, benchmark, annualization, 0),
            "benchmark_metrics": metrics(benchmark, benchmark, annualization, 0),
            "positions": [
                {"time": d, "position": int(p)} for d, p in zip(test_dates, positions)
            ],
            "trades": trades,
            "exposure": float(np.mean(positions)),
        }
    )
    if not trades:
        notes.append(
            "Aucune transaction avec ces paramètres ; les ratios à dénominateur nul sont affichés comme indisponibles."
        )
    return output
