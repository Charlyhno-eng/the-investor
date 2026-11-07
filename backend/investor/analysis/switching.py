"""Long/cash switching driven only by the HMM, accounting for each trading fee."""

import numpy as np

HORIZON = 5


def switching_values(model, log_means, fee_bps):
    """Five-return forecast after next-close execution, versus round-trip fees.

    At close t the first return earned after execution at close t+1 is r[t+2].
    This fixed horizon is a forecast convention, never a forced holding period.
    There is no infinite-horizon continuation value that can lock a position.
    """
    if not 0 <= fee_bps <= 500:
        raise ValueError(
            "Les frais doivent être compris entre 0 et 500 points de base."
        )
    transition = model.transmat_
    forecast = transition @ log_means
    advantage = np.zeros(len(log_means))
    for _ in range(HORIZON):
        forecast = transition @ forecast
        advantage += forecast
    return advantage, float(-2 * np.log1p(-fee_bps / 10000))


def simulate_switching(
    changes,
    probabilities,
    dates,
    request,
    advantage,
    cost,
    bullish,
    *,
    initial_probability=None,
):
    """Signals at close t execute at close t+1, fees symmetric, no stop."""
    fee = request.fee_bps / 10000
    net = np.zeros(len(changes))
    position, pending, pending_probability = 0, None, None
    trades, positions = [], []
    if (
        initial_probability is not None
        and float(initial_probability @ advantage) > cost
    ):
        pending = 1
        pending_probability = float(initial_probability[bullish].sum())
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
