"""Fit on period 1 only, then use a forward filter, never smoothed test states."""

import warnings
from functools import lru_cache

import numpy as np
from hmmlearn import _hmmc
from hmmlearn.hmm import GaussianHMM
from scipy.special import logsumexp
from threadpoolctl import threadpool_limits


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


def forward_filter(model, observations):
    """p(state_t | x_1..x_t), O(T*K²); likelihoods are vectorized in NumPy."""
    if not len(observations):
        return np.empty((0, model.n_components))
    emissions = model._compute_log_likelihood(observations)
    # The compiled hmmlearn forward kernel returns causal filtered posteriors.
    # predict_proba would instead smooth using future observations. Row scaling
    # cancels in normalization and avoids Gaussian-density underflow.
    likelihoods = np.exp(emissions - emissions.max(axis=1, keepdims=True))
    try:
        _, probabilities, _ = _hmmc.forward_scaling(
            model.startprob_, model.transmat_, likelihoods
        )
        return probabilities
    except ValueError:
        # Extreme observations or unreachable states can underflow even after
        # row scaling. Log space preserves the model's exact zero transitions.
        _, lattice = _hmmc.forward_log(model.startprob_, model.transmat_, emissions)
        return np.exp(lattice - logsumexp(lattice, axis=1, keepdims=True))
