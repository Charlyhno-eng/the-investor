"""Return-only HMM, selected against a single Gaussian on expanding windows."""

import warnings
from functools import lru_cache

import numpy as np
from hmmlearn.hmm import GaussianHMM
from scipy.special import logsumexp
from threadpoolctl import threadpool_limits

from investor.analysis.model import forward_filter

SEEDS = (17, 41, 83, 127, 191)


def observations(values):
    """One completed log return per observation, without overlapping indicators."""
    changes = np.diff(np.log(np.asarray(values, dtype=float)))
    return changes, changes[:, None]


def _fit(training, count):
    mean = training.mean(axis=0)
    scale = np.maximum(training.std(axis=0), 1e-8)
    x = (training - mean) / scale
    if count == 1:
        model = GaussianHMM(n_components=1, covariance_type="full", init_params="")
        model.startprob_ = np.ones(1)
        model.transmat_ = np.ones((1, 1))
        model.means_ = np.zeros((1, 1))
        model.covars_ = np.ones((1, 1, 1))
        model.n_features = 1
        return model, mean, scale, True
    candidates = []
    for i, seed in enumerate(SEEDS):
        model = GaussianHMM(
            n_components=count,
            covariance_type="full",
            n_iter=500,
            tol=1e-3,
            random_state=seed,
            init_params="" if i < 2 else "mc",
            params="tmc",
            transmat_prior=1.05,
            covars_prior=np.array([[0.01]]),
            covars_weight=3,
            implementation="log",
        )
        model.startprob_ = np.full(count, 1 / count)
        model.transmat_ = np.full((count, count), 0.05 / (count - 1))
        np.fill_diagonal(model.transmat_, 0.95)
        if i < 2:
            model.means_ = (
                np.quantile(x[:, 0], np.linspace(0.2, 0.8, count))[:, None]
                if i == 0
                else np.zeros((count, 1))
            )
            model.covars_ = np.linspace(0.25, 2, count).reshape(count, 1, 1)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                model.fit(x)
            history = list(model.monitor_.history)
            converged = (
                len(history) > 1 and -0.01 <= history[-1] - history[-2] < model.tol
            )
            occupancy = model.predict_proba(x).sum(axis=0)
            score = model.score(x)
            if (
                converged
                and np.isfinite(score)
                and occupancy.min() >= max(10, len(x) * 0.02)
                and np.isfinite(model.covars_).all()
                and model.covars_.min() > 1e-5
                and np.isfinite(model.transmat_).all()
            ):
                candidates.append((score, model))
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            continue
    if not candidates:
        raise ValueError(
            "Aucun ajustement convergé avec des états suffisamment représentés."
        )
    _, model = max(candidates, key=lambda item: item[0])
    return model, mean, scale, True


def predictive_return_scores(model, training, mean, scale, cut):
    """Log density of r[t] using only filtered information through t-1."""
    x = (training - mean) / scale
    filtered = forward_filter(model, x)
    prior = filtered[cut - 1 : -1] @ model.transmat_
    variance = model.covars_[:, 0, 0]
    residual = x[cut:, :1] - model.means_[:, 0]
    density = -0.5 * (np.log(2 * np.pi * variance) + residual**2 / variance)
    with np.errstate(divide="ignore"):
        return logsumexp(np.log(prior) + density, axis=1) - np.log(scale[0])


def predictive_return_score(model, training, mean, scale, cut):
    return float(predictive_return_scores(model, training, mean, scale, cut).mean())


def fit_regimes(training):
    training = np.ascontiguousarray(training, dtype=np.float64)
    if training.ndim != 2 or training.shape[1] != 1 or len(training) < 100:
        raise ValueError(
            "Le modèle exige au moins 100 variations et une seule variable."
        )
    if not np.isfinite(training).all() or training.std() < 1e-10:
        raise ValueError(
            "Les variations d’entraînement doivent être finies et non constantes."
        )
    return _fit_cached(training.shape, training.tobytes())


@lru_cache(maxsize=8)
def _fit_cached(shape, data):
    training = np.frombuffer(data, dtype=np.float64).reshape(shape)
    cuts = [int(len(training) * fraction) for fraction in (0.6, 0.8)]
    scores, blocks = {}, {}
    with threadpool_limits(limits=1):
        for count in (1, 2, 3):
            parts = []
            try:
                for cut, end in zip(cuts, [cuts[1], len(training)]):
                    model, mean, scale, _ = _fit(training[:cut], count)
                    parts.append(
                        predictive_return_scores(
                            model, training[:end], mean, scale, cut
                        )
                    )
            except ValueError:
                continue
            daily = np.concatenate(parts)
            scores[count] = float(daily.mean())
            # Non-overlapping blocks reduce sensitivity to serial dependence.
            blocks[count] = np.array(
                [
                    part.mean()
                    for part in np.array_split(daily, min(10, len(daily) // 5))
                ]
            )
        best = max(scores, key=scores.get)
        # Paired one-standard-error rule: prefer fewer states when validation
        # cannot clearly distinguish them from the highest scoring candidate.
        eligible = []
        for count in sorted(scores):
            difference = blocks[best] - blocks[count]
            error = float(difference.std(ddof=1) / np.sqrt(len(difference)))
            if scores[best] - scores[count] <= error + 1e-12:
                eligible.append(count)
        for count in eligible + [
            k for k in sorted(scores, key=scores.get, reverse=True) if k not in eligible
        ]:
            try:
                fitted = _fit(training, count)
                break
            except ValueError:
                continue
        else:
            raise ValueError("Aucun modèle stable après validation chronologique.")
    return (
        *fitted,
        {
            "method": "expanding_window_predictive_likelihood_one_standard_error",
            "fit_points": cuts[0],
            "validation_points": len(training) - cuts[0],
            "folds": [
                {"fit_points": cut, "validation_points": end - cut}
                for cut, end in zip(cuts, [cuts[1], len(training)])
            ],
            "validation_scores": {str(k): v for k, v in scores.items()},
            "baseline_score": scores[1],
            "selected_states": count,
            "regimes_supported": count > 1,
            "observable_columns": [0],
            "feature_window": 1,
            "seeds": list(SEEDS),
        },
    )
