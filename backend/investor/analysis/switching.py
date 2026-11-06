"""Long/cash switching driven only by the HMM, accounting for each trading fee."""

import numpy as np


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


def simulate_switching(
    changes, probabilities, dates, request, advantage, cost, bullish
):
    """Signals at close t execute at close t+1, fees symmetric, no stop."""
    fee = request.fee_bps / 10000
    net = np.zeros(len(changes))
    position, pending, pending_probability = 0, None, None
    trades, positions = [], []
    for i, change in enumerate(changes):
        net[i] = np.expm1(change) if position else 0.0
        target = 0 if i == len(changes) - 1 else pending
        if target is not None and target != position:
            net[i] = (1 + net[i]) * (1 - fee) - 1
            position = target
            trades.append(
                {
                    "time": dates[i],
                    "side": "buy" if target else "sell",
                    "probability": pending_probability
                    if i < len(changes) - 1
                    else None,
                    "reason": "regime" if i < len(changes) - 1 else "final_liquidation",
                }
            )
        positions.append(position)
        value = float(probabilities[i] @ advantage)
        pending = None
        if not position and value > cost:
            pending = 1
        elif position and value < -cost:
            pending = 0
        pending_probability = float(probabilities[i, bullish].sum())
    benchmark = np.expm1(changes)
    benchmark[0] = (1 + benchmark[0]) * (1 - fee) - 1
    benchmark[-1] = (1 + benchmark[-1]) * (1 - fee) - 1
    return net, benchmark, trades, positions
