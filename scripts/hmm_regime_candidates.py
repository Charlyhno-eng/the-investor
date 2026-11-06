"""Research candidates; deliberately not connected to the application API.

Inspired by Werge (2021), arXiv:2107.05535, sections 4–5, and causal rolling
re-estimation in mehmetoaltekin/hmm-regime-detection. This is an adaptation,
not a reproduction of either author's reported investment performance.
"""

from functools import lru_cache

import numpy as np
from investor.analysis.model import forward_filter
from investor.analysis.regimes import _fit
from investor.analysis.switching import switching_values
from threadpoolctl import threadpool_limits

SPAN = 30
REFIT = 63
LOOKBACK = 1260
CANDIDATES = ("ewm_frozen_pesr", "ewm_rolling_pesr", "ewm_rolling_cost")


def ewm_observations(values):
    """Past-only exponentially weighted mean and central standard deviation.

    The variance recursion avoids subtracting two nearly equal raw moments.
    The first SPAN-1 features are unavailable, without backfilling.
    """
    changes = np.diff(np.log(values))
    x = np.full((len(changes), 2), np.nan)
    if not len(changes):
        return changes, x
    alpha = 2 / (SPAN + 1)
    mean, variance = changes[0], 0.0
    for i, change in enumerate(changes):
        delta = change - mean
        mean += alpha * delta
        variance = (1 - alpha) * (variance + alpha * delta**2)
        if i >= SPAN - 1:
            x[i] = mean, np.sqrt(max(variance, 1e-16))
    return changes, x


@lru_cache(maxsize=128)
def _calibration(shape, data):
    training = np.frombuffer(data, dtype=np.float64).reshape(shape)
    with threadpool_limits(limits=1):
        return _fit(training, 3)


def fit(training):
    training = np.ascontiguousarray(training, dtype=np.float64)
    return _calibration(training.shape, training.tobytes())


def candidate_signals(x, dates, request):
    """Immutable signals for each date; refits never rewrite earlier beliefs.

    Initial parameters use only the requested training interval. Subsequent
    refits use completed observations strictly before their first signal bar,
    at a fixed 63-observation cadence, trailing at most 1260 observations.
    A new model re-filters its own calibration history to initialize its belief;
    raw state indices are never carried between different fitted models.
    """
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
        raise ValueError("Not enough causal EWM training/test observations")
    indices = np.flatnonzero(test)
    first, end = indices[0], indices[-1] + 1
    initial = np.flatnonzero(train)[-LOOKBACK:]
    model, mean, scale, converged = fit(x[initial])
    frozen = (model, mean, scale, converged)
    output = {}
    for rolling in (False, True):
        model, mean, scale, converged = frozen
        last_fit_indices = initial
        series = {k: np.zeros(len(indices)) for k in ("pesr", "advantage", "bull")}
        audit = []
        for start in range(first, end, REFIT if rolling else end - first):
            stop = min(start + REFIT, end) if rolling else end
            fit_indices = initial
            failure = None
            if rolling and start > first:
                proposed = np.flatnonzero(valid & (np.arange(len(x)) < start))[
                    -LOOKBACK:
                ]
                try:
                    calibrated = fit(x[proposed])
                    model, mean, scale, converged = calibrated
                    fit_indices = proposed
                except ValueError as exc:
                    # A failed refresh preserves the last usable model. The
                    # failure is recorded, never silently dropped from results.
                    failure = str(exc)
                    fit_indices = last_fit_indices
            last_fit_indices = fit_indices
            context = np.flatnonzero(
                valid
                & (np.arange(len(x)) >= fit_indices[0])
                & (np.arange(len(x)) < stop)
            )
            p = forward_filter(model, (x[context] - mean) / scale)
            p = p[context >= start]
            moments = model.means_ * scale + mean
            drift, vol = moments[:, 0], np.maximum(moments[:, 1], 1e-8)
            advantage, _ = switching_values(model, drift, request.fee_bps)
            dst = slice(start - first, stop - first)
            series["pesr"][dst] = p @ model.transmat_ @ model.transmat_ @ (drift / vol)
            series["advantage"][dst] = p @ advantage
            series["bull"][dst] = p[:, drift > 0].sum(axis=1)
            audit.append(
                {
                    "first_signal": str(dates[start]),
                    "calibration_end": str(dates[fit_indices[-1]]),
                    "calibration_start": str(dates[fit_indices[0]]),
                    "fit_points": len(fit_indices),
                    "converged": bool(converged),
                    "failure": failure,
                    "drift": drift.tolist(),
                    "volatility": vol.tolist(),
                    "transition_matrix": model.transmat_.tolist(),
                }
            )
        prefix = "ewm_rolling" if rolling else "ewm_frozen"
        output[prefix + "_pesr"] = {
            "value": series["pesr"],
            "cost": 0.0,
            "probability": series["bull"],
            "calibrations": audit,
        }
        if rolling:
            output["ewm_rolling_cost"] = {
                "value": series["advantage"],
                "cost": float(-np.log1p(-request.fee_bps / 10000)),
                "probability": series["bull"],
                "calibrations": audit,
            }
    return output


def execute(changes, dates, value, cost, probability, fee_bps):
    """Same execution clock as production; also record exposure per return bar."""
    fee = fee_bps / 10000
    net, held = np.zeros(len(changes)), np.zeros(len(changes), dtype=int)
    position, pending, pending_probability = 0, None, None
    trades = []
    for i, change in enumerate(changes):
        held[i] = position
        net[i] = np.expm1(change) if position else 0.0
        target = 0 if i == len(changes) - 1 else pending
        if target is not None and target != position:
            net[i] = (1 + net[i]) * (1 - fee) - 1
            position = target
            trades.append(
                {
                    "time": str(dates[i]),
                    "side": "buy" if target else "sell",
                    "probability": pending_probability
                    if i < len(changes) - 1
                    else None,
                    "reason": "regime" if i < len(changes) - 1 else "final_liquidation",
                }
            )
        pending = None
        if not position and value[i] > cost:
            pending = 1
        elif position and value[i] < -cost:
            pending = 0
        pending_probability = float(probability[i])
    market = np.expm1(changes)
    market[0] = (1 + market[0]) * (1 - fee) - 1
    market[-1] = (1 + market[-1]) * (1 - fee) - 1
    return net, market, trades, held
