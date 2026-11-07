"""Causal log-space filtering for Gaussian hidden Markov models."""

import numpy as np
from scipy.special import logsumexp
from scipy.stats import multivariate_normal


def forward_filter(model, observations):
    """Causal normalized forward recursion, independent of hmmlearn internals."""
    if not len(observations):
        return np.empty((0, model.n_components))
    # Public covariance expansion needs this metadata on manually built models.
    if not hasattr(model, "n_features"):
        model.n_features = model.means_.shape[1]
    emissions = np.column_stack(
        [
            multivariate_normal.logpdf(observations, mean=mean, cov=covariance)
            for mean, covariance in zip(model.means_, model.covars_)
        ]
    )
    if not np.isfinite(emissions).all():
        raise ValueError("Densités non finies pendant le filtrage du modèle.")
    probabilities = np.empty_like(emissions)
    with np.errstate(divide="ignore"):
        log_transition = np.log(model.transmat_)
        log_previous = np.log(model.startprob_)
    for i, emission in enumerate(emissions):
        log_prior = (
            log_previous
            if i == 0
            else np.logaddexp.reduce(log_previous[:, None] + log_transition, axis=0)
        )
        posterior = log_prior + emission
        log_previous = posterior - logsumexp(posterior)
        probabilities[i] = np.exp(log_previous)
    return probabilities
