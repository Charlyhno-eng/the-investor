"""Describe ineffective regime switching without manufacturing extra trades."""

import numpy as np


def switching_diagnostics(
    probabilities, drift, advantage, cost, positions, net_return, benchmark_return
):
    """The finite-horizon forecast is linear in belief: its extrema are at pure states.

    If every state's forecast is >= -cost, no posterior can trigger an exit.
    Negative emission means describe fitted states, not next-return forecasts.
    Thresholds for exposure are reporting flags only and never affect orders.
    """
    held = np.r_[0, np.asarray(positions[:-1], dtype=int)]
    adverse = drift[np.argmax(probabilities, axis=1)] < 0
    exit_signals = probabilities @ advantage < -cost
    values = probabilities @ advantage
    return {
        "entry_reachable": bool(np.any(advantage > cost)),
        "entry_signal_observations": int((values > cost).sum()),
        "minimum_state_forecast": float(np.min(advantage)),
        "maximum_state_forecast": float(np.max(advantage)),
        "round_trip_threshold": float(cost),
        "exit_reachable": bool(np.any(advantage < -cost)),
        "negative_states": int(np.sum(drift < 0)),
        "negative_dominant_observations": int(adverse.sum()),
        "negative_dominant_while_held": int((adverse & (held == 1)).sum()),
        "negative_dominant_without_exit_while_held": int(
            (adverse & ~exit_signals & (held == 1)).sum()
        ),
        "exit_signal_observations": int(exit_signals.sum()),
        "net_excess_return": float(net_return - benchmark_return),
        "nearly_always_invested": bool(held.mean() >= 0.95),
        "nearly_always_cash": bool(held.mean() <= 0.05),
    }
