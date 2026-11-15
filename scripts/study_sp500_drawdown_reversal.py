"""Independent, predeclared second drawdown campaign: guarded mean reversion.

PYTHONPATH=backend:scripts uv run python scripts/study_sp500_drawdown_reversal.py
Separate seeds/report, identical execution and adoption gates to first campaign.
"""

from itertools import product
from pathlib import Path

import study_sp500_drawdown_frontier as engine


def grid():
    rules = []
    for window, base, amplitude, floor, guard in product(
        [10, 21, 63], [0.65, 0.85], [0.3, 0.6], [0.2, 0.5], ["none", "trend", "shock"]
    ):
        rules.append(
            dict(
                family="pullback",
                window=window,
                base=base,
                amplitude=amplitude,
                floor=floor,
                guard=guard,
                step=5,
            )
        )
    for window, amplitude, floor, guard in product(
        [3, 10, 21], [0.3, 0.6], [0.2, 0.5], ["none", "trend", "shock"]
    ):
        rules.append(
            dict(
                family="rsi_reversal",
                window=window,
                amplitude=amplitude,
                floor=floor,
                guard=guard,
                step=1,
            )
        )
    for window, amplitude, floor, guard in product(
        [10, 21, 63], [0.3, 0.6], [0.2, 0.5], ["none", "trend", "shock"]
    ):
        rules.append(
            dict(
                family="trend_pullback",
                window=window,
                amplitude=amplitude,
                floor=floor,
                guard=guard,
                step=5,
            )
        )
    return [dict(**r, active=active) for r in rules for active in [0, 0.35, 0.65]]


if __name__ == "__main__":
    engine.OUT = Path("data/backtests/sp500-drawdown-reversal.json")
    engine.PLAN = {
        **engine.PLAN,
        "change": "Second campaign declared after first selection failed, BEFORE examining any reserved audit result. Continuous guarded mean reversion: volatility-normalized short-term pullbacks, RSI imbalance, trend-conditioned pullbacks. Single PSP5 ETF long/cash, not reinstatement of rejected multiasset strategies or current native multiasset reversion. Daily/weekly, true budgets and fees. Separate selection, no selection across reserved audits.",
        "selection": engine.PLAN["selection"].replace(
            "210000..210149", "510000..510149"
        ),
        "audit": engine.PLAN["audit"]
        .replace("220000..220999", "520000..520999")
        .replace("230000..230299", "530000..530299"),
    }
    engine.grid = grid
    engine.main(seed_offset=300000, **engine.arguments())
