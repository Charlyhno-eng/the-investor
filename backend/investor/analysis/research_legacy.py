"""Archived fitting and Bellman rule for historical research scripts only.

Not imported by the active analysis service. Kept to reproduce old studies.
"""

import warnings
from functools import lru_cache

import numpy as np
from hmmlearn.hmm import GaussianHMM
from threadpoolctl import threadpool_limits

SEEDS = (17, 41, 83)


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


def switching_values(model, log_means, fee_bps):
    """Average-reward Bellman difference for held versus flat portfolios.

    d(s) = clip(r(s) + P d(s), -c, c). Continuation values account for
    learned state persistence rather than a target holding time or trade quota.
    With a next-close execution lag, reward starts two transitions after today's
    filtered observation. No reward is credited on the signal/execution bars.
    """
    cost = -np.log1p(-fee_bps / 10000)
    transition = model.transmat_
    reward = transition @ transition @ log_means
    difference = np.zeros(len(log_means))
    for _ in range(10000):
        updated = np.clip(reward + transition @ difference, -cost, cost)
        if np.max(np.abs(updated - difference)) < 1e-12:
            return reward + transition @ updated, float(cost)
        # Averaging avoids a two-cycle for a periodic transition matrix.
        difference = (difference + updated) / 2
    raise ValueError("La politique de coûts HMM n’a pas convergé.")


def features(values, is_yield):
    """One observable: daily simple return, as in the FrenchQuant example.

    Log returns are returned separately for the close-to-close simulator.
    There is no rolling indicator or warm-up beyond the first price.
    """
    changes = np.diff(values) if is_yield else np.diff(np.log(values))
    observed = changes if is_yield else np.expm1(changes)
    return changes, observed[:, None]


def fit_model(training):
    # Key only the training features: fees, test dates and test observations do
    # not change the trained model. Bytes also invalidate on historical edits.
    training = np.ascontiguousarray(training, dtype=np.float64)
    return _fit_cached(training.shape, training.tobytes())


@lru_cache(maxsize=8)
def _fit_cached(shape, data):
    """Bounded process-local cache; callers must treat fitted models as read-only."""
    training = np.frombuffer(data, dtype=np.float64).reshape(shape)
    mean, scale = training.mean(axis=0), training.std(axis=0)
    scale = np.maximum(scale, 1e-8)
    x = (training - mean) / scale
    candidates = []
    with threadpool_limits(limits=1):
        for seed in (17, 41, 83):
            model = GaussianHMM(
                n_components=2,
                covariance_type="full",
                n_iter=1000,
                tol=1e-2,
                min_covar=1e-3,
                random_state=seed,
                implementation="scaling",
            )
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    model.fit(x)
                score = model.score(x)
            except (ValueError, np.linalg.LinAlgError, FloatingPointError):
                # One degenerate initialization must not discard the others.
                continue
            improvement = (
                model.monitor_.history[-1] - model.monitor_.history[-2]
                if len(model.monitor_.history) > 1
                else float("inf")
            )
            converged = np.isfinite(improvement) and -0.01 <= improvement < model.tol
            if (
                np.isfinite(score)
                and np.isfinite(model.transmat_).all()
                and np.isfinite(model.covars_).all()
            ):
                candidates.append((score, model, converged))
    if not candidates:
        raise ValueError(
            "Ajustement impossible : série trop peu variable pour deux régimes."
        )
    _, model, converged = max(candidates, key=lambda item: item[0])
    return model, mean, scale, converged
