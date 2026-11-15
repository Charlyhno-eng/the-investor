"""PSP5: independent 75/25 slow/defensive budgets, 10% defensive exposure."""

import math

REGRESSION_MONTHS = 18
MIN_OBSERVATIONS = 251
ENTRY_Z = -0.5
EXIT_Z = 1.5
DECISION_SESSIONS = 5
DEFENSIVE_WEIGHT = 0.10
SLOW_REGRESSION_MONTHS = 60
SLOW_MIN_OBSERVATIONS = 501
SLOW_ENTRY_Z = -2.0
ACTIVE_SHARE = 1.0
PASSIVE_SHARE = 0.0
SLEEVE_NAMES = ("slow", "defensive")
INITIAL_SHARES = (0.75, 0.25)
SLOW_REENTRY_Z = 0.0
VERSION = "slow_defensive_sharpe_v6"


def defensive_target(score, previous_score, risk_on):
    """Enter on a daily upward crossing; retain the state between scheduled checks."""
    if score is None or not math.isfinite(score):
        return bool(risk_on)
    if risk_on:
        return score <= EXIT_Z
    return (
        previous_score is not None
        and math.isfinite(previous_score)
        and previous_score < ENTRY_Z
        and score >= ENTRY_Z
    )


def slow_target(score, previous_score, risk_on):
    """Monthly decision: deep discount or daily upward recovery crossing."""
    if score is None or not math.isfinite(score):
        return bool(risk_on)
    if risk_on:
        return score <= EXIT_Z
    return score < SLOW_ENTRY_Z or (
        previous_score is not None
        and math.isfinite(previous_score)
        and previous_score < SLOW_REENTRY_Z
        and score >= SLOW_REENTRY_Z
    )


def initial_slow_state(dates, first, score_at):
    """Replay monthly signals strictly before the test, without a trading book."""
    risk_on = False
    for signal in range(1, first):
        if dates[signal].month != dates[signal - 1].month:
            risk_on = slow_target(score_at(signal), score_at(signal - 1), risk_on)
    return risk_on


def protocol():
    return {
        "signal_asset_id": "yf-psp5.pa",
        "version": VERSION,
        "active_initial_share": ACTIVE_SHARE,
        "passive_initial_share": PASSIVE_SHARE,
        "active_rule": VERSION,
        "defensive_weight": DEFENSIVE_WEIGHT,
        "risk_on_weight": 1.0,
        "rebalance_on_state_change_only": True,
        "transfers_between_sleeves": False,
        "net_opposing_trades": False,
        "sleeves": [
            {
                "id": "slow",
                "initial_share": INITIAL_SHARES[0],
                "regression_months": SLOW_REGRESSION_MONTHS,
                "min_observations": SLOW_MIN_OBSERVATIONS,
                "entry_rule": "strictly_below_or_upward_crossing",
                "entry_z": SLOW_ENTRY_Z,
                "reentry_z": SLOW_REENTRY_Z,
                "reentry_comparison": "previous_session",
                "exit_above_z": EXIT_Z,
                "decision_frequency": "first_session_of_month",
                "initial_state": "historical_monthly_signals",
                "initial_state_history": "strictly_before_simulation_start",
            },
            {
                "id": "defensive",
                "initial_share": INITIAL_SHARES[1],
                "regression_months": REGRESSION_MONTHS,
                "min_observations": MIN_OBSERVATIONS,
                "entry_rule": "upward_crossing",
                "entry_z": ENTRY_Z,
                "exit_above_z": EXIT_Z,
                "decision_every_sessions": DECISION_SESSIONS,
                "decision_anchor": "simulation_first_signal",
                "initial_state": "defensive",
            },
        ],
    }
