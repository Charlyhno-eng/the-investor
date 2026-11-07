"""Research-only two-state HMMs at slower time scales, with hysteresis.

All features, normalization, state labels and decisions are causal. No model is
promoted by this module; the experiment runner selects on pre-2024 data only.
"""

import numpy as np
from hmmlearn.hmm import GaussianHMM
from threadpoolctl import threadpool_limits

from investor.analysis.metrics import metrics
from investor.analysis.model import forward_filter

REPRESENTATIONS = ("return1", "return5", "return21", "trend21", "trend63")
POLICIES = {
    "dominant": (0.5, 0.5, False),
    "hysteresis": (0.7, 0.3, False),
    "defensive": (0.5, 0.2, True),
}
SEEDS = (17, 41, 83)


def observations(changes, representation):
    """Return completed-window features and their indices in daily returns."""
    trend = representation.startswith("trend")
    window = int(representation[5:] if trend else representation[6:])
    indices = np.arange(window - 1, len(changes), 1 if trend else window)
    values = []
    for i in indices:
        segment = changes[i - window + 1 : i + 1]
        if trend:
            vol = max(segment.std(), 1e-8)
            values.append([segment.sum() / (vol * np.sqrt(window)), np.log(vol)])
        else:
            values.append([segment.sum()])
    return np.asarray(values), indices


def probabilities(changes, train_end, representation):
    x, indices = observations(changes, representation)
    training = x[indices < train_end]
    if len(training) < 30:
        raise ValueError("At least 30 completed training observations required")
    center, scale = training.mean(axis=0), np.maximum(training.std(axis=0), 1e-8)
    normalized = (training - center) / scale
    candidates = []
    with threadpool_limits(limits=1):
        for seed in SEEDS:
            model = GaussianHMM(
                n_components=2,
                covariance_type="diag",
                n_iter=300,
                tol=0.01,
                random_state=seed,
            )
            try:
                model.fit(normalized)
                score = float(model.score(normalized))
                if np.isfinite(score):
                    candidates.append((score, seed, model))
            except (ValueError, np.linalg.LinAlgError):
                continue
    if not candidates:
        raise ValueError("No finite HMM")
    _, seed, model = max(candidates, key=lambda item: item[0])
    means = model.means_[:, 0] * scale[0] + center[0]
    bullish = int(np.argmax(means))
    filtered = forward_filter(model, (x - center) / scale)[:, bullish]
    # A completed weekly/monthly observation remains the latest available signal
    # until the next block is complete. No interpolation from future posteriors.
    latest = np.searchsorted(indices, np.arange(len(changes)), side="right") - 1
    p = np.full(len(changes), np.nan)
    available = latest >= 0
    p[available] = filtered[latest[available]]
    return (
        p,
        bool(means[1 - bullish] < 0),
        {
            "state_feature_means": means.tolist(),
            "seed": seed,
            "training_observations": len(training),
        },
    )


def targets(p, policy, cadence, negative_other):
    """Decide after each observed close; unknown regimes initially mean cash."""
    enter, exit_, defensive = POLICIES[policy]
    position = 0
    output = np.zeros(len(p), dtype=int)
    for i, probability in enumerate(p):
        if i % cadence == 0 and np.isfinite(probability):
            if defensive and not negative_other:
                position = 1
            elif position and probability < exit_:
                position = 0
            elif not position and probability >= enter:
                position = 1
        output[i] = position
    return output


def simulate(changes, decisions, fee_bps):
    """decisions[i] uses observations up to the close BEFORE test day i.

    Execute at test close i, earn subsequent returns, and liquidate at last close.
    """
    if len(changes) != len(decisions) or not 0 <= fee_bps <= 500:
        raise ValueError("Invalid decisions or fees")
    fee = fee_bps / 10000
    net, positions = np.zeros(len(changes)), np.zeros(len(changes), dtype=int)
    position, trades = 0, 0
    for i, change in enumerate(changes):
        net[i] = np.expm1(change) if position else 0.0
        target = int(decisions[i]) if i < len(changes) - 1 else 0
        if target != position:
            net[i] = (1 + net[i]) * (1 - fee) - 1
            trades += 1
            position = target
        positions[i] = position
    bm = np.expm1(changes)
    bm[0] = (1 + bm[0]) * (1 - fee) - 1
    bm[-1] = (1 + bm[-1]) * (1 - fee) - 1
    strategy, benchmark = metrics(net, bm, 252, 0), metrics(bm, bm, 252, 0)
    return {
        "strategy": strategy,
        "benchmark": benchmark,
        "excess_return": strategy["total_return"] - benchmark["total_return"],
        "transactions": trades,
        "exposure": float(positions.mean()),
    }


def evaluate(rows, cut, representations=REPRESENTATIONS, fees=(50,)):
    dates = np.asarray([row["date"] for row in rows[1:]], dtype="U10")
    prices = np.asarray([row["value"] for row in rows], dtype=float)
    if not np.isfinite(prices).all() or np.any(prices <= 0):
        raise ValueError("Prices must be finite and positive")
    r = np.diff(np.log(prices))
    end = int(np.sum(dates < cut))
    if end < 630 or len(r) - end < 20:
        raise ValueError("At least 630 training and 20 test returns required")
    results = []
    for representation in representations:
        p, negative, details = probabilities(r, end, representation)
        for policy in POLICIES:
            for cadence in (1, 21):
                decisions = targets(p, policy, cadence, negative)[end - 1 : -1]
                for fee in fees:
                    results.append(
                        dict(
                            policy=f"{representation}_{policy}_c{cadence}",
                            fee_bps=fee,
                            **details,
                            **simulate(r[end:], decisions, fee),
                        )
                    )
    # A plain trend rule is a control: does the HMM add value over its inputs?
    for window in (21, 63):
        sums = np.r_[0.0, r.cumsum()]
        signal = np.zeros(len(r), dtype=int)
        signal[window - 1 :] = (sums[window:] - sums[:-window] > 0).astype(int)
        for fee in fees:
            results.append(
                dict(
                    policy=f"control_momentum{window}",
                    fee_bps=fee,
                    **simulate(r[end:], signal[end - 1 : -1], fee),
                )
            )
    return results
