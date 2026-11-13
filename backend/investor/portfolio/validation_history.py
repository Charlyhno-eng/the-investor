"""Past-only alignment of staggered listings on the benchmark calendar."""

from bisect import bisect_left, bisect_right
from datetime import date

import numpy as np

from investor.assets.momentum import months_before


def align(history, days):
    """Carry known quotes for valuation; never fill before the first quote."""
    quotes = sorted(history)
    values = np.full(len(days), np.nan)
    for i, day in enumerate(days):
        k = bisect_right(quotes, day) - 1
        if k >= 0:
            values[i] = history[quotes[k]]
    return values


def _mature(quotes, day):
    if not quotes:
        return False
    lower = months_before(date.fromisoformat(day), 36).isoformat()
    left, right = bisect_left(quotes, lower), bisect_right(quotes, day)
    return (
        right - left >= 501
        and quotes[0] <= lower
        and (date.fromisoformat(quotes[left]) - date.fromisoformat(lower)).days <= 7
    )


def maturities(histories, days):
    """Precompute eligibility with sorted histories, avoiding repeated full scans."""
    return np.column_stack(
        [
            [_mature(quotes, day) for day in days]
            for quotes in (sorted(h) for h in histories)
        ]
    )


def history_notices(assets, histories, request, start):
    notices = []
    for asset, history in zip(assets, histories, strict=True):
        name = asset["name"]
        if not history:
            reason = (
                "sa part reste en liquidités"
                if request.mode == "mean_reversion"
                and asset.get("category", "stock") not in ("stock", "crypto")
                else "aucune transaction sur cet actif"
            )
            notices.append(f"{name} : aucun cours exploitable ; {reason}.")
            continue
        if request.mode == "mean_reversion" and asset.get("category", "stock") not in (
            "stock",
            "crypto",
        ):
            notices.append(
                f"{name} : retour à la moyenne non appliqué ; achat puis quantité conservée dès sa disponibilité."
            )
        if min(history) > start:
            notices.append(
                f"{name} : premières cotations le {min(history)}, aucune position avant cette date."
            )
    return notices
