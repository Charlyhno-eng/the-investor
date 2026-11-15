"""Second preregistered campaign: reduce turnover after first holdout ratio failure.

PYTHONPATH=backend:scripts uv run python scripts/study_sp500_ratio_costs.py
Fresh random draws, same PSP5 model; no claim of independent economic evidence.
"""

from itertools import product
from pathlib import Path

import study_sp500_ratio_tradeoff as study

original_grid = study.grid


def grid():
    return [
        {**c, "step": step, "band": band}
        for c, step, band in product(original_grid()[:36], [10, 21], [0.1, 0.2])
    ]


if __name__ == "__main__":
    study.OUT = Path("data/backtests/sp500-ratio-costs.json")
    study.SEED_OFFSET = 50000
    study.PLAN = {
        **study.PLAN,
        "change": "Follow-up after first frozen candidate failed five-year holdout Sharpe/Sortino. Reduce trading costs by decision intervals10/21sessions and10/20pp no-trade bands. 144 volatility-only configurations; same 36 risk policies. No change to generator or production. This is another search, NOT an untouched economic sample.",
        "selection": study.PLAN["selection"].replace("20000..20099", "70000..70099"),
        "audit": study.PLAN["audit"]
        .replace("40000..40299", "90000..90299")
        .replace("50000..50099", "100000..100099"),
        "execution": study.PLAN["execution"].replace(
            "every5 sessions, 5pp band", "every10/21 sessions, 10/20pp band"
        ),
        "requirements": "Unchanged gates: CAGR gain>=1pp current, vol<=1.15current, absoluteDD<=1.10current, vol/DD better than BH; ALL mean ratios higher than current and BH and >=55% wins each vsBH. No promotion following any failed gate.",
    }
    study.grid = grid
    study.main()
