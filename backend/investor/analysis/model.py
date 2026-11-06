"""Fit on period 1 only, then use a forward filter, never smoothed test states."""

import warnings

import numpy as np
from hmmlearn.hmm import GaussianHMM
from threadpoolctl import threadpool_limits


def features(values, is_yield, window):
    changes = np.diff(values) if is_yield else np.diff(np.log(values))
    # Trailing volatility includes only information observed at that close.
    sums = np.concatenate(([0.0], np.cumsum(changes)))
    squares = np.concatenate(([0.0], np.cumsum(changes**2)))
    ends = np.arange(1, len(changes) + 1)
    starts = np.maximum(0, ends - window)
    count = ends - starts
    rolling = np.sqrt(
        np.maximum(
            0,
            (squares[ends] - squares[starts]) / count
            - ((sums[ends] - sums[starts]) / count) ** 2,
        )
    )
    return changes, np.column_stack((changes, rolling))


def fit_model(training):
    mean, scale = training.mean(axis=0), training.std(axis=0)
    scale = np.maximum(scale, 1e-8)
    x = (training - mean) / scale
    candidates = []
    with threadpool_limits(limits=1):
        for seed in (17, 41, 83):
            model = GaussianHMM(
                n_components=3,
                covariance_type="diag",
                n_iter=150,
                tol=1e-4,
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
            "Ajustement impossible : série trop peu variable pour trois régimes."
        )
    _, model, converged = max(candidates, key=lambda item: item[0])
    return model, mean, scale, converged


def forward_filter(model, observations):
    """p(state_t | x_1..x_t), O(T*K²); likelihoods are vectorized in NumPy."""
    variance = np.maximum(model._covars_, 1e-10)
    emissions = -0.5 * (
        np.log(2 * np.pi * variance).sum(axis=1)[None, :]
        + ((observations[:, None, :] - model.means_[None, :, :]) ** 2 / variance).sum(
            axis=2
        )
    )
    # Row scaling preserves each posterior while avoiding costly logsumexp at
    # every step. Emission evaluation remains vectorized across the full series.
    likelihoods = np.exp(emissions - emissions.max(axis=1, keepdims=True))
    transition = np.maximum(model.transmat_, 1e-300)
    previous = np.maximum(model.startprob_, 1e-300)
    probabilities = np.empty((len(observations), 3))
    for i, likelihood in enumerate(likelihoods):
        prior = previous if i == 0 else previous @ transition
        posterior = prior * likelihood
        previous = posterior / posterior.sum()
        probabilities[i] = previous
    return probabilities
