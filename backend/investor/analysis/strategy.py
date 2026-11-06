"""Long/cash strategy, close-to-close with a full observation of execution lag."""

import numpy as np


def simulate(changes, probabilities, dates, favorable, request, periods_per_year):
    cost = (request.fee_bps + request.slippage_bps) / 10000
    cash = (1 + request.risk_free_rate) ** (1 / periods_per_year) - 1
    net = np.zeros(len(changes))
    position, held, streak, candidate, transactions = 0, 0, 0, 0, []
    positions = []
    for i, change in enumerate(changes):
        # Signal from previous close executes at this close, after this bar's P&L.
        net[i] = np.expm1(change) if position else cash
        held += 1
        if i > 0:
            probability = float(probabilities[i - 1, favorable])
            target = (
                int(probability >= request.exit_probability)
                if position
                else int(probability >= request.entry_probability)
            )
            if target != position:
                streak = streak + 1 if candidate == target else 1
                candidate = target
            else:
                streak = 0
            # Always reserve one transaction for final liquidation.
            room = len(transactions) < request.max_trades - (1 if not position else 0)
            if (
                target != position
                and streak >= request.confirmation
                and (not position or held >= request.min_hold)
                and room
                and i < len(changes) - 1
            ):
                net[i] = (1 + net[i]) * (1 - cost) - 1
                position, held, streak = target, 0, 0
                transactions.append(
                    {
                        "time": dates[i],
                        "side": "buy" if target else "sell",
                        "probability": probability,
                    }
                )
        positions.append(position)
    if position:
        net[-1] = (1 + net[-1]) * (1 - cost) - 1
        transactions.append({"time": dates[-1], "side": "sell", "probability": None})
        positions[-1] = 0
    benchmark = np.expm1(changes)
    benchmark[0] = (1 + benchmark[0]) * (1 - cost) - 1
    benchmark[-1] = (1 + benchmark[-1]) * (1 - cost) - 1
    return net, benchmark, transactions, positions
