"""Causal long/cash policies with daily, latched equity drawdown protection."""

from dataclasses import asdict, dataclass
from datetime import date

import numpy as np


@dataclass(frozen=True)
class Policy:
    review: str = "weekly"
    entry: float = 0.8
    exit: float = 0.2
    drawdown_stop: float | None = 0.1
    trend_window: int | None = None
    ignore_hmm: bool = False


POLICIES = {
    "daily_original": Policy("daily", 0.5, 0.5, None),
    "daily_guard": Policy("daily", 0.5, 0.5, 0.1),
    "weekly_hmm": Policy(),
    "weekly_trend_hmm": Policy(trend_window=200),
    "weekly_trend_control": Policy(trend_window=200, ignore_hmm=True),
}
DEFAULT_POLICY_NAME = "weekly_hmm"


def trend_filter(values, window):
    """Trailing price/SMA condition; no centered windows or test normalization."""
    allowed = np.zeros(len(values), dtype=bool)
    if len(values) >= window:
        sums = np.r_[0.0, np.cumsum(values)]
        averages = (sums[window:] - sums[:-window]) / window
        allowed[window - 1 :] = values[window - 1 :] > averages
    return allowed


def simulate(
    changes,
    probabilities,
    dates,
    favorable,
    request,
    periods_per_year,
    *,
    policy=None,
    trend=None,
    risk_events=None,
):
    policy = policy or POLICIES[DEFAULT_POLICY_NAME]
    if policy.trend_window and trend is None:
        raise ValueError("La politique de tendance exige son historique causal.")
    events = risk_events if risk_events is not None else []
    cost = request.fee_bps / 10000
    net = np.zeros(len(changes))
    position, transactions, positions = 0, [], []
    capital, peak, latched = 1.0, 1.0, False
    pending, pending_probability = None, None
    previous_week = None
    for i, change in enumerate(changes):
        # Earn this bar with yesterday's executed position, never today's signal.
        net[i] = np.expm1(change) if position else 0
        target = pending
        reason = "drawdown_stop" if latched else "signal"
        if i == len(changes) - 1:
            target = 0  # Liquidate, never open a new position on the final close.
            if not latched:
                reason = "final_liquidation"
        if target is not None and target != position:
            net[i] = (1 + net[i]) * (1 - cost) - 1
            position = target
            transactions.append(
                {
                    "time": dates[i],
                    "side": "buy" if target else "sell",
                    "probability": pending_probability if reason == "signal" else None,
                    "reason": reason,
                }
            )
            if reason == "drawdown_stop":
                events[-1]["executed_at"] = dates[i]
        positions.append(position)
        capital *= 1 + net[i]
        peak = max(peak, capital)
        drawdown = 1 - capital / peak
        if (
            not latched
            and policy.drawdown_stop is not None
            and drawdown >= policy.drawdown_stop - 1e-12
        ):
            latched = True
            events.append(
                {
                    "triggered_at": dates[i],
                    "executed_at": None,
                    "drawdown_at_trigger": float(drawdown),
                    "already_in_cash": not bool(position),
                }
            )
        pending, pending_probability = None, None
        if latched:
            pending = 0  # Daily override, no weekly wait and no automatic rearm.
        else:
            if policy.review == "weekly":
                week = date.fromisoformat(dates[i]).isocalendar()[:2]
                review = week != previous_week
                previous_week = week
            else:
                review = True
            if review:
                probability = float(probabilities[i, favorable])
                target = int(probability > (policy.exit if position else policy.entry))
                if policy.ignore_hmm:
                    target = 1
                if trend is not None and not trend[i]:
                    target = 0
                pending, pending_probability = target, probability
    benchmark = np.expm1(changes)
    benchmark[0] = (1 + benchmark[0]) * (1 - cost) - 1
    benchmark[-1] = (1 + benchmark[-1]) * (1 - cost) - 1
    return net, benchmark, transactions, positions


def describe_policy(policy):
    return asdict(policy)
