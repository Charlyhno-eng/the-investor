"""Cross native regression deviation and native calendar momentum, research only.

PYTHONPATH=backend:scripts uv run python scripts/study_sp500_sigma_momentum.py --workers 4
"""

from datetime import date
from itertools import product
from pathlib import Path

import numpy as np
import study_sp500_drawdown_frontier as engine

from investor.assets.momentum import months_before

OUT = Path("data/backtests/sp500-sigma-momentum.json")
ORIGINAL_TACTICAL = engine.tactical
PLAN = {
    **engine.PLAN,
    "change": "Cross native log-regression residual z (18/60 calendar months) and native momentum6/12/36 months excluding latest calendar month. Four conditional policies, NOT rejected fixed70/30 multiasset ranking. Confirm entries, buy trend pullbacks, defer exits during strong momentum, or continuous interaction. Replacement or independent v4 budget35/65%; tactical remainder. PSP5 momentum benchmark is itself: relative component identically zero, no synthetic USD benchmark.",
    "selection": engine.PLAN["selection"].replace("210000..210149", "1110000..1110149"),
    "audit": engine.PLAN["audit"]
    .replace("220000..220999", "1120000..1120999")
    .replace("230000..230299", "1130000..1130299"),
    "sources": [
        "https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum"
    ],
    "signals": "Native momentum formula score50+50*(.4*tanh(annual_log_return/.3)+.3*tanh(annual_slope/.3))*sqrt(R2)/(1+sigma/.1), relative component0. Exact calendar endpoints/coverage and60-observation minimum; no score when unavailable. Ensemble averages available6/12/36 scores. Regression as app, ddof2, minimum251observations18m/501observations60m. Missing signals use defensive floor. No replay profit; conditional states replayed on same5session grid strictly before start with fresh capital. Daily score, decisions every5 observed sessions, band5pp, next close, independent budgets.",
}


def grid():
    return [
        dict(
            family=family,
            months=months,
            momentum=mom,
            threshold=threshold,
            floor=floor,
            step=5,
            active=active,
        )
        for family, months, mom, threshold, floor, active in product(
            ["confirm", "pullback_momentum", "defer_exit", "interaction"],
            [18, 60],
            ["6", "12", "ensemble"],
            [50, 55],
            [0.25, 0.5],
            [0, 0.35, 0.65],
        )
    ]


def ols(x, y, lo, hi):
    """Vector prefix sums; all windows end at or before their signal close."""
    n = hi - lo

    def sums(a):
        c = np.r_[0.0, np.cumsum(a)]
        return c[hi] - c[lo]

    safe = np.maximum(n, 1)
    sx, sy = sums(x), sums(y)
    xx = sums(x * x) - sx * sx / safe
    yy = np.maximum(sums(y * y) - sy * sy / safe, 0)
    xy = sums(x * y) - sx * sy / safe
    slope = xy / np.maximum(xx, 1e-20)
    sse = np.maximum(yy - slope * xy, 0)
    sigma = np.sqrt(sse / np.maximum(n - 2, 1))
    r2 = np.clip(1 - sse / np.maximum(yy, 1e-20), 0, 1)
    residual = (
        y[np.maximum(hi - 1, 0)]
        - sy / safe
        - slope * (x[np.maximum(hi - 1, 0)] - sx / safe)
    )
    return slope, sigma, r2, residual


def signals(days, p):
    dates = [date.fromisoformat(d) for d in days]
    ordinal = np.array([d.toordinal() for d in dates])
    x = (ordinal - ordinal[0]) / 365.25
    y = np.log(p / p[0])
    scores, zs = {}, {}
    for months in [6, 12, 36]:
        start = np.array([months_before(d, months).toordinal() for d in dates])
        end = np.array([months_before(d, 1).toordinal() for d in dates])
        lo, hi = (
            np.searchsorted(ordinal, start),
            np.searchsorted(ordinal, end, side="right"),
        )
        hi_safe = np.maximum(hi - 1, 0)
        slope, sigma, r2, _ = ols(x, y, lo, hi)
        duration = x[hi_safe] - x[lo]
        annual = (y[hi_safe] - y[lo]) / np.maximum(duration, 1e-10)
        gaps = np.r_[0, np.diff(ordinal) > 14].cumsum()
        valid = (
            (hi - lo >= 60)
            & (ordinal[lo] - start <= 7)
            & (end - ordinal[hi_safe] <= 7)
            & (gaps[hi_safe] == gaps[lo])
            & (duration > 0)
        )
        strength = 0.4 * np.tanh(annual / 0.3) + 0.3 * np.tanh(slope / 0.3)
        scores[str(months)] = np.where(
            valid, 50 + 50 * strength * np.sqrt(r2) / (1 + sigma / 0.1), np.nan
        )
    matrix = np.array(list(scores.values()))
    count = np.isfinite(matrix).sum(axis=0)
    scores["ensemble"] = np.divide(
        np.nansum(matrix, axis=0), count, out=np.full(len(p), np.nan), where=count > 0
    )
    for months, minimum in [(18, 251), (60, 501)]:
        start = np.array([months_before(d, months).toordinal() for d in dates])
        lo = np.searchsorted(ordinal, start)
        hi = np.arange(1, len(p) + 1)
        _, sigma, _, residual = ols(x, y, lo, hi)
        valid = (start >= ordinal[0]) & (hi - lo >= minimum) & (sigma > 1e-10)
        zs[months] = np.where(valid, residual / np.maximum(sigma, 1e-10), np.nan)
    return zs, scores


def weights(days, p, cs, period):
    zs, scores = signals(days, p)
    lo = int(np.searchsorted(days, period[0]))
    result = np.empty((len(cs), len(p)))
    # Exogenous conditional state: replay same anchored five-session grid before
    # start; no synthetic past positions, profits or transaction fees.
    for j, c in enumerate(cs):
        z, m = zs[c["months"]], scores[c["momentum"]]
        floor, threshold = c["floor"], c["threshold"]
        valid = np.isfinite(z) & np.isfinite(m)
        if c["family"] == "interaction":
            trend = np.clip(0.5 + (m - threshold) / 15, 0, 1)
            cheap = np.clip(0.5 - z / 4, 0, 1)
            exposure = floor + (1 - floor) * np.clip(
                0.7 * trend + 0.3 * cheap + 0.4 * trend * cheap, 0, 1
            )
            result[j] = np.where(valid, exposure, floor)
            continue
        prior_z = np.r_[np.nan, z[:-1]]
        cross = (prior_z <= 0) & (z > 0)
        if c["family"] == "confirm":
            enter = (m > threshold) & ((z < -1) | cross | ((z > 0) & (z < 1.5)))
            exit_ = (m < threshold - 5) | (z > 2)
        elif c["family"] == "pullback_momentum":
            enter = (m > threshold) & (z < 0.5)
            exit_ = (m < threshold - 5) | ((z > 1.5) & (m < threshold + 5))
        elif c["family"] == "defer_exit":
            enter = (z < -2) | ((m > threshold) & (z > 0))
            exit_ = ((z > 1.5) & (m < threshold)) | ((m < threshold - 8) & (z < -0.5))
        else:
            raise ValueError(c["family"])
        state = False
        for i in range(len(p)):
            if (i - lo) % c["step"] == 0:
                if not valid[i]:
                    state = False
                elif state:
                    state = not exit_[i]
                else:
                    state = bool(enter[i])
            result[j, i] = 1.0 if state else floor
    return result


def tactical(days, p, cs, period, fee=0.0012, delay=1):
    return ORIGINAL_TACTICAL(
        days, p, cs, period, fee, delay, target_weights=weights(days, p, cs, period)
    )


def configure():
    engine.OUT, engine.PLAN, engine.grid, engine.tactical = OUT, PLAN, grid, tactical


if __name__ == "__main__":
    configure()
    engine.main(seed_offset=900000, **engine.arguments())
