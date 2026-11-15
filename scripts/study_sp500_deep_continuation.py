"""Separate declared branch: trend continuation budgets versus adopted v5.

PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_deep_continuation.py
"""

import argparse
from itertools import product
from pathlib import Path

import study_sp500_deep_search as engine

OUT = Path("data/backtests/sp500-deep-continuation.json")
PLAN = {
    **engine.PLAN,
    "novelty": "Second branch, declared after first1356 historical screen failed (first200-market selection still running). Prior continuation research failed to beat BH under stricter different objectives; now compare JOINT active/passive budgets against v5, not assume prior failure vs BH answers this question. Slow sustained-trend entry and armed exit may capture trends lost to level exits. No past diagnostic adopted.729full-budget joint configurations; new control and reserved seeds. No automatic adoption.",
    "selection": engine.PLAN["selection"].replace(
        "1310000..1310199", "1410000..1410199"
    ),
    "audit": engine.PLAN["audit"]
    .replace("1320000..1320999", "1420000..1420999")
    .replace("1330000..1330299", "1430000..1430299"),
}


def grid():
    result = []
    for entry, exit_, floor, share, defensive_exit, passive in product(
        ["daily_cross", "ma100", "ma200"],
        ["level1.5", "armed_ma50", "armed_ma100"],
        [0.1, 0.25, 0.4],
        [0.5, 0.75, 0.9],
        [1.5, 1.75, 2],
        [0, 0.2, 0.35],
    ):
        reg = {
            **engine.BASE,
            "entry": entry,
            "exit": exit_,
            "floor": floor,
            "slow_share": share,
            "defensive_exit": defensive_exit,
        }
        result.append(dict(family="regression_joint", regression=reg, passive=passive))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4)
    engine.OUT, engine.PLAN, engine.grid = OUT, PLAN, grid
    engine.main(seed_offset=100000, **vars(parser.parse_args()))
