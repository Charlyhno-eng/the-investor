"""Economic acceptance gate; model convergence never implies trading acceptance."""

import math
from collections import Counter


def majority_acceptance(results, expected_assets):
    """Require net total-return superiority on strictly more than half the catalog.

    Errors, missing assets and duplicates fail coverage. Ties do not count as
    wins. The reported excess is recomputed from net strategy/benchmark results.
    """
    expected = set(expected_assets)
    counts = Counter(row.get("asset_id") for row in results)
    missing = sorted(expected - counts.keys())
    unexpected = sorted(str(asset) for asset in counts.keys() - expected)
    duplicates = sorted(str(asset) for asset, count in counts.items() if count != 1)
    errors, excesses = [], []
    for row in results:
        asset = row.get("asset_id")
        if asset not in expected or counts[asset] != 1:
            continue
        try:
            if row.get("error"):
                raise ValueError(row["error"])
            strategy = float(row["strategy"]["total_return"])
            benchmark = float(row["benchmark"]["total_return"])
            if not math.isfinite(strategy) or not math.isfinite(benchmark):
                raise ValueError("Non-finite net return")
            excesses.append(strategy - benchmark)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append({"asset_id": asset, "error": str(exc)})
    wins = sum(excess > 1e-10 for excess in excesses)
    losses = sum(excess < -1e-10 for excess in excesses)
    required = len(expected) // 2 + 1
    complete = bool(expected) and not (missing or unexpected or duplicates or errors)
    return {
        "criterion": "strict_majority_net_total_return_above_buy_and_hold",
        "universe_count": len(expected),
        "evaluated_count": len(excesses),
        "required_wins": required,
        "wins": wins,
        "losses": losses,
        "ties": len(excesses) - wins - losses,
        "win_rate": wins / len(expected) if expected else 0.0,
        "missing_assets": missing,
        "unexpected_assets": unexpected,
        "duplicate_assets": duplicates,
        "errors": errors,
        "passed": complete and wins >= required,
    }
