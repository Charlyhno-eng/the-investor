"""Model-driven positions, cost bands and an independently resting position stop."""

import numpy as np

STOP = 0.10


def model_signals(model, probabilities, state_means, fee_bps, annualization):
    """Forecast next return and amortize round-trip costs over learned state duration.

    No transaction target, calendar restriction or threshold search. The HMM is
    fit on training data only; filtering probabilities are causal.
    """
    predicted = probabilities @ model.transmat_
    forecast = predicted @ state_means
    duration = np.minimum(
        1 / np.maximum(1 - np.diag(model.transmat_), 1e-8), annualization
    )
    horizon = predicted @ duration
    cost = fee_bps / 10000
    band = np.expm1(-2 * np.log1p(-cost) / horizon)
    return forecast, band


def simulate_reentry(
    changes,
    probabilities,
    dates,
    favorable,
    request,
    forecast,
    band,
    *,
    bars=None,
    risk_events=None,
):
    events = risk_events if risk_events is not None else []
    cost = request.fee_bps / 10000
    net = np.zeros(len(changes))
    capital, position_peak = 1.0, None
    position, pending = 0, None
    pending_probability = None
    transactions, positions = [], []
    waiting, last_stop = False, -1
    for i, change in enumerate(changes):
        previous_capital = capital
        growth = float(np.exp(change)) if position else 1.0
        stopped = False
        if position:
            # This stop is set before this bar. Today's high cannot retroactively
            # raise it before today's low: only past closing peaks are used.
            fill_ratio = (1 - STOP) * position_peak / (capital * (1 - cost))
            bar = bars[i] if bars is not None else None
            source, gap, fill = "close_only", False, None
            if bar is not None:
                opening, low = bar["open_ratio"], bar["low_ratio"]
                source = "daily_ohlc"
                if opening <= fill_ratio:
                    fill, gap = opening, opening < fill_ratio - 1e-12
                elif low <= fill_ratio:
                    fill = fill_ratio
            elif growth <= fill_ratio:
                fill = growth  # Observed close, never invent an intraday fill.
            if fill is not None:
                growth = fill * (1 - cost)
                position, pending, stopped = 0, None, True
                waiting, last_stop = True, i
                events.append(
                    {
                        "triggered_at": dates[i],
                        "executed_at": dates[i],
                        "drawdown_at_trigger": float(
                            1 - capital * growth / position_peak
                        ),
                        "already_in_cash": False,
                        "source": source,
                        "gap": bool(gap),
                        "reentered_at": None,
                    }
                )
                transactions.append(
                    {
                        "time": dates[i],
                        "side": "sell",
                        "probability": None,
                        "reason": "position_stop",
                        "execution": source,
                    }
                )
        target = 0 if i == len(changes) - 1 else pending
        if not stopped and target is not None and target != position:
            growth *= 1 - cost
            if target:
                position_peak = previous_capital  # Include entry fee in the 10% budget.
                if waiting:
                    events[-1]["reentered_at"] = dates[i]
                    waiting = False
            position = target
            transactions.append(
                {
                    "time": dates[i],
                    "side": "buy" if target else "sell",
                    "probability": pending_probability
                    if i < len(changes) - 1
                    else None,
                    "reason": "signal" if i < len(changes) - 1 else "final_liquidation",
                    "execution": "close",
                }
            )
        net[i] = growth - 1
        capital *= growth
        if position:
            position_peak = max(position_peak, capital)
        positions.append(position)
        pending, pending_probability = None, None
        if not stopped:
            if position:
                if forecast[i] < -band[i]:
                    pending = 0
            elif forecast[i] > band[i]:
                fresh_rise = (
                    i > last_stop
                    and change > 0
                    and (i == 0 or forecast[i] >= forecast[i - 1])
                )
                if not waiting or fresh_rise:
                    pending = 1
            if pending is not None:
                pending_probability = float(probabilities[i, favorable])
    benchmark = np.expm1(changes)
    benchmark[0] = (1 + benchmark[0]) * (1 - cost) - 1
    benchmark[-1] = (1 + benchmark[-1]) * (1 - cost) - 1
    return net, benchmark, transactions, positions
