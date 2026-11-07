"""Minimal two-state Gaussian HMM experiment: higher-mean state versus other.

One log-return observable, fixed two states, dominant filtered state, long/cash.
No economic threshold, forecast horizon, indicator or model-count selection.
"""

from functools import lru_cache

import numpy as np
from hmmlearn.hmm import GaussianHMM
from threadpoolctl import threadpool_limits

from investor.analysis.metrics import metrics
from investor.analysis.model import forward_filter

SEEDS = (17, 41, 83)
VERSION = "basic-two-state-dominant-filtered-return-v1"


def fit_cached(training):
    """Reuse training fits when only dates of test or trading fees change."""
    return _fit_cached(np.asarray(training, dtype=np.float64).reshape(-1).tobytes())


@lru_cache(maxsize=8)
def _fit_cached(data):
    return fit(np.frombuffer(data, dtype=np.float64))


def fit(training):
    training = np.asarray(training, dtype=float).reshape(-1, 1)
    if len(training) < 100 or not np.isfinite(training).all():
        raise ValueError("At least 100 finite training returns are required")
    mean, scale = float(training.mean()), float(training.std())
    if scale < 1e-10:
        raise ValueError("Training returns must not be constant")
    x = (training - mean) / scale
    candidates = []
    with threadpool_limits(limits=1):
        for seed in SEEDS:
            model = GaussianHMM(
                n_components=2,
                covariance_type="diag",
                n_iter=500,
                tol=1e-3,
                random_state=seed,
            )
            try:
                model.fit(x)
                score = float(model.score(x))
                if np.isfinite(score):
                    candidates.append((score, seed, model))
            except (ValueError, np.linalg.LinAlgError):
                continue
    if not candidates:
        raise ValueError("No finite two-state Gaussian HMM fit")
    _, seed, model = max(candidates, key=lambda item: item[0])
    return model, mean, scale, seed


def simulate(changes, filtered, bullish, fee_bps):
    """filtered[0] precedes the test; close t signal executes at close t+1.

    Each return is earned with the position held before that day's execution.
    Fees change performance only: targets/trades never depend on their value.
    """
    if not 0 <= fee_bps <= 500:
        raise ValueError("Fees must be between 0 and 500 bps")
    if np.asarray(filtered).shape != (len(changes) + 1, 2):
        raise ValueError(
            "Expected one pre-test posterior and two-state test posteriors"
        )
    targets = (np.argmax(filtered[:-1], axis=1) == bullish).astype(int)
    net = np.zeros(len(changes))
    position, trades, positions = 0, [], []
    fee = fee_bps / 10000
    for i, change in enumerate(changes):
        net[i] = np.expm1(change) if position else 0.0
        target = 0 if i == len(changes) - 1 else int(targets[i])
        if target != position:
            net[i] = (1 + net[i]) * (1 - fee) - 1
            trades.append({"index": i, "side": "buy" if target else "sell"})
            position = target
        positions.append(position)
    benchmark = np.expm1(changes)
    benchmark[0] = (1 + benchmark[0]) * (1 - fee) - 1
    benchmark[-1] = (1 + benchmark[-1]) * (1 - fee) - 1
    return net, benchmark, trades, positions


def evaluate(rows, request, fees=(0, 50)):
    prices = np.asarray([r["value"] for r in rows], dtype=float)
    if not np.isfinite(prices).all() or np.any(prices <= 0):
        raise ValueError("Prices must be finite and strictly positive")
    dates = np.array([r["date"] for r in rows[1:]], dtype="U10")
    changes = np.diff(np.log(prices))
    train = (dates > request.train_start.isoformat()) & (
        dates <= request.train_end.isoformat()
    )
    test = (dates >= request.test_start.isoformat()) & (
        dates <= request.test_end.isoformat()
    )
    if train.sum() < 100 or test.sum() < 20:
        raise ValueError("At least 100 training and 20 test returns are required")
    model, mean, scale, seed = fit(changes[train])
    means = model.means_[:, 0] * scale + mean
    bullish = int(np.argmax(means))
    probabilities = forward_filter(model, (changes[:, None] - mean) / scale)
    indices = np.flatnonzero(test)
    if indices[0] == 0:
        raise ValueError("A pre-test posterior is required")
    test_probabilities = probabilities[indices[0] - 1 : indices[-1] + 1]
    result = []
    for fee in fees:
        net, benchmark, trades, positions = simulate(
            changes[test], test_probabilities, bullish, fee
        )
        strategy_metrics = metrics(net, benchmark, 252, 0)
        benchmark_metrics = metrics(benchmark, benchmark, 252, 0)
        result.append(
            {
                "fee_bps": fee,
                "strategy": strategy_metrics,
                "benchmark": benchmark_metrics,
                "excess_return": strategy_metrics["total_return"]
                - benchmark_metrics["total_return"],
                "exposure": float(np.mean(positions)),
                "transactions": len(trades),
                "regime_exits": sum(t["side"] == "sell" for t in trades[:-1]),
                "training_log_means": means.tolist(),
                "bullish_state": bullish,
                "bullish_mean_positive": bool(means[bullish] > 0),
                "transition_matrix": model.transmat_.tolist(),
                "seed": seed,
                "train_points": int(train.sum()),
                "test_points": int(test.sum()),
                "actual_train": [str(dates[train][0]), str(dates[train][-1])],
                "actual_test": [str(dates[test][0]), str(dates[test][-1])],
            }
        )
    return result
