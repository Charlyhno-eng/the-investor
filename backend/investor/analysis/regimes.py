"""Directional HMM with causal context and model selection inside training only."""

import warnings
from functools import lru_cache

import numpy as np
from hmmlearn.hmm import GaussianHMM
from scipy.special import logsumexp
from threadpoolctl import threadpool_limits

from investor.analysis.model import forward_filter

WINDOW = 20
SEEDS = (17, 41, 83)


def observations(values):
    """Log return, trailing mean and log volatility over 20 completed returns.

    Rolling context is an emission of the HMM, never a separate trading rule.
    The first 19 rows are unavailable; they must not be padded with future data.
    """
    changes = np.diff(np.log(values))
    x = np.full((len(changes), 3), np.nan)
    if len(changes) >= WINDOW:
        windows = np.lib.stride_tricks.sliding_window_view(changes, WINDOW)
        x[WINDOW - 1 :] = np.column_stack(
            (
                changes[WINDOW - 1 :],
                windows.mean(axis=1),
                np.log(np.maximum(windows.std(axis=1), 1e-8)),
            )
        )
    return changes, x


def _fit(training, count):
    mean, scale = training.mean(axis=0), np.maximum(training.std(axis=0), 1e-8)
    x = (training - mean) / scale
    candidates = []
    for seed in SEEDS:
        model = GaussianHMM(
            n_components=count,
            covariance_type="full",
            n_iter=1000,
            tol=1e-2,
            min_covar=1e-3,
            random_state=seed,
            covars_prior=0.01 * np.eye(x.shape[1]),
            covars_weight=x.shape[1] + 2,
            implementation="scaling",
        )
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                model.fit(x)
            score = model.score(x)
            occupancy = model.predict_proba(x).sum(axis=0)
            if not np.isfinite(score) or occupancy.min() < max(5, len(x) * 0.01):
                continue
            improvement = (
                model.monitor_.history[-1] - model.monitor_.history[-2]
                if len(model.monitor_.history) > 1
                else float("inf")
            )
            converged = np.isfinite(improvement) and -0.01 <= improvement < model.tol
            candidates.append((score, model, converged))
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            continue
    if not candidates:
        raise ValueError(
            "Ajustement HMM instable : historique insuffisamment variable."
        )
    _, model, converged = max(candidates, key=lambda item: item[0])
    return model, mean, scale, converged


def fit_regimes(training):
    training = np.ascontiguousarray(training, dtype=np.float64)
    return _fit_cached(training.shape, training.tobytes())


def predictive_return_score(model, training, mean, scale, cut):
    """Score the same next-return target for all observation dimensions.

    Joint likelihoods of one versus three observables cannot be compared.
    Context is retained only when it helps forecast the held-out daily return.
    """
    x = (training - mean) / scale
    p = forward_filter(model, x)
    prior = p[cut - 1 : -1] @ model.transmat_
    variance = model.covars_[:, 0, 0]
    residual = x[cut:, :1] - model.means_[:, 0]
    density = -0.5 * (np.log(2 * np.pi * variance) + residual**2 / variance)
    with np.errstate(divide="ignore"):
        score = logsumexp(np.log(prior) + density, axis=1) - np.log(scale[0])
    return float(score.mean())


@lru_cache(maxsize=8)
def _fit_cached(shape, data):
    training = np.frombuffer(data, dtype=np.float64).reshape(shape)
    cut = int(len(training) * 0.8)
    scores, candidates = {}, {}
    with threadpool_limits(limits=1):
        for columns in ((0,), (0, 1, 2)):
            for count in (2, 3):
                key = (columns, count)
                observed = training[:, columns]
                try:
                    model, mean, scale, _ = _fit(observed[:cut], count)
                    score = predictive_return_score(model, observed, mean, scale, cut)
                    if np.isfinite(score):
                        scores[key] = score
                except ValueError:
                    continue
        for columns, count in sorted(scores, key=scores.get, reverse=True):
            try:
                candidates[(columns, count)] = _fit(training[:, columns], count)
                break
            except ValueError:
                continue
    if not candidates:
        raise ValueError("Aucun HMM stable après validation chronologique interne.")
    columns, count = next(iter(candidates))
    return (
        *candidates[(columns, count)],
        {
            "method": "chronological_predictive_return_likelihood",
            "fit_points": cut,
            "validation_points": len(training) - cut,
            "validation_scores": {
                f"{'returns' if len(c) == 1 else 'context'}_{k}": score
                for (c, k), score in scores.items()
            },
            "selected_states": count,
            "observable_columns": list(columns),
            "feature_window": WINDOW,
        },
    )
