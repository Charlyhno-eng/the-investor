"""PSP5 agreement policy endpoints and archived 21-session comparison ledger."""

from bisect import bisect_left
from datetime import date
from math import floor, isfinite

import numpy as np

from investor.assets.momentum import months_before
from investor.db import connect
from investor.portfolio import psp5_agreement
from investor.portfolio.statistics import curve_metrics

FEE = 0.0012
WINDOW = 21


def invested_target(returns):
    return np.square(np.minimum(returns, 0)).sum(axis=-1) <= 0.8 * np.square(
        returns
    ).sum(axis=-1)


def books(prices, start, capital, fee, whole):
    """Return daily net equity for both portfolios, euro costs and turnover."""
    prices = np.asarray(prices, dtype=float)
    future = prices[start:]
    signals = np.arange(start, len(prices) - 1, 5)
    returns = np.diff(np.log(prices))
    windows = np.lib.stride_tricks.sliding_window_view(returns, WINDOW)[
        signals - WINDOW
    ]
    invested = invested_target(windows)
    changed = np.r_[True, invested[1:] != invested[:-1]]
    orders = signals[changed] - start + 1
    targets = invested[changed]
    curves = np.full((len(future), 2), float(capital))
    costs = [0.0, 0.0]
    turnover = [0.0, 0.0]
    for col, (times, states) in enumerate(((np.array([1]), [True]), (orders, targets))):
        cash, units, entered = capital, 0.0, False
        for at, stop, on in zip(times, [*times[1:], len(future)], states, strict=True):
            price = future[at]
            nav = cash + units * price
            target = cash / (price * (1 + fee)) if on else 0.0
            if whole:
                target = floor(target)
            trade = (target - units) * price
            cost = abs(trade) * fee
            cash -= trade + cost
            units = target
            costs[col] += cost
            if entered:
                turnover[col] += abs(trade) / nav
            entered |= trade != 0
            curves[at:stop, col] = cash + units * future[at:stop]
    return curves, costs, turnover


def compare(days, prices, start):
    curves, _, _ = psp5_agreement.books(
        [d.isoformat() for d in days], prices, start, 10000.0, FEE, True
    )
    years = (days[-1] - days[start]).days / 365.25
    gain = (curves[-1] / 10000) ** (1 / years) - 1
    dd = (curves / np.maximum.accumulate(curves, axis=0) - 1).min(0)
    return dict(
        start=days[start],
        cagr=gain[1],
        passive_cagr=gain[0],
        drawdown=dd[1],
        passive_drawdown=dd[0],
    )


class DownsideSimulation:
    def __init__(self, source, request):
        self.source = source
        self.request = request
        self.days = [source["days"][-1], *source["synthetic_days"]]
        start = source["start"]
        self.years = (date.fromisoformat(self.days[-1]) - start).days / 365.25
        self.quarters = [0]
        for q in range(1, request.years * 4 + 1):
            at = bisect_left(self.days, months_before(start, -3 * q).isoformat())
            if at < len(self.days):
                self.quarters.append(at)

    def path(self, seed, equity=False):
        from investor.portfolio.sp500_simulation import sampled_returns

        s = self.source
        r = self.request
        increments = sampled_returns(s["returns"], len(self.days) - 1, seed)
        prices = np.r_[s["prices"], s["anchor"] * np.exp(np.cumsum(increments))]
        if not np.all(np.isfinite(prices) & (prices > 0)):
            return dict(status="insufficient", message="Cours simulés hors limites.")
        curves, costs, turnover = psp5_agreement.books(
            s["days"] + s["synthetic_days"],
            prices,
            len(s["days"]) - 1,
            r.initial_capital,
            r.fee_rate,
            r.whole_shares,
        )
        changes = curves[1:] / curves[:-1] - 1
        q = curves[self.quarters]
        quarters = q[1:] / q[:-1] - 1
        metrics = {}
        for i, key in enumerate(("benchmark", "strategy")):
            row = curve_metrics(
                curves[:, i],
                changes[:, i],
                changes[:, 0],
                self.years,
                252,
                benchmark=i == 0,
            )
            row.update(
                cost_eur=float(costs[i]),
                annual_turnover=float(turnover[i] / self.years),
                worst_quarter=float(quarters[:, i].min()) if len(quarters) else None,
                positive_quarters=int((quarters[:, i] > 0).sum()),
                winning_quarters=int((quarters[:, i] > quarters[:, 0]).sum()),
            )
            metrics[key] = row
        comparison = dict(
            metrics=metrics,
            benchmark_name="PSP5 passif",
            completed_quarters=len(quarters),
        )
        if equity:
            comparison["equity"] = [
                dict(time=d, benchmark=a, strategy=b)
                for d, (a, b) in zip(
                    self.days, curves * 100 / r.initial_capital, strict=True
                )
            ]
        return dict(
            status="ready",
            comparison=comparison,
            simulation=dict(
                seed=seed, source_start=s["days"][0], source_end=self.days[0]
            ),
        )

    def simulate(self, seeds):
        return [self.path(seed) for seed in seeds]


def history():
    with connect() as conn:
        rows = conn.execute(
            "SELECT date,value FROM observations WHERE asset_id='yf-psp5.pa' ORDER BY date"
        ).fetchall()
    days = [date.fromisoformat(row[0]) for row in rows]
    prices = [row[1] for row in rows]
    result = []
    if days and all(isfinite(p) and p > 0 for p in prices):
        periods = [
            (f"{y} an" if y == 1 else f"{y} ans", months_before(days[-1], 12 * y))
            for y in (1, 3, 5, 10)
        ]
        periods.append(("Depuis début 2021", date(2021, 1, 1)))
        for label, first in periods:
            start = bisect_left(days, first)
            if psp5_agreement.WINDOW <= start < len(days) - 1:
                result.append(dict(label=label, **compare(days, prices, start)))
    return dict(end=days[-1] if days else None, rows=result)
