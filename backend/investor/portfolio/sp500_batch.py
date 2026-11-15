"""Bounded, column-wise S&P simulations; audited against full validation_data.

Only the batch's paired metrics are retained. Calendars and the historical warm
state are shared; random streams, trading books and fees remain independent.
"""

from bisect import bisect_left
from datetime import date

import numpy as np

from investor.assets.momentum import months_before
from investor.portfolio import etf_switch
from investor.portfolio.reversion import log_regression_scores, regression_z
from investor.portfolio.statistics import curve_metrics
from investor.portfolio.validation_history import maturities

# Bound temporary matrices and the time spent calculating after disconnection.
CHUNK_SIZE = 64


def _rebalance(value, cash, target, fee):
    """The production rebalance bisection, independently for each scalar book."""
    wealth = value + cash
    low, high = np.zeros_like(wealth), wealth.copy()
    for _ in range(60):
        net = (low + high) / 2
        over = net + fee * np.abs(net * target - value) > wealth
        high = np.where(over, net, high)
        low = np.where(over, low, net)
    net = (low + high) / 2
    return net * target, net * (1 - target)


class PreparedBatch:
    def __init__(self, source, request):
        self.source = source
        self.request = request
        self.days = source["days"] + source["synthetic_days"]
        self.dates = [date.fromisoformat(d) for d in self.days]
        self.first = len(source["days"]) - 1
        self.windows = {}
        self.matured = maturities(
            [dict.fromkeys(self.days)],
            self.days,
            months=etf_switch.REGRESSION_MONTHS,
            min_observations=etf_switch.MIN_OBSERVATIONS,
        )[:, 0]
        self.initial_state = etf_switch.initial_slow_state(
            self.dates,
            self.first,
            lambda s: regression_z(
                source["prices"][:, None],
                self.dates,
                s,
                months=etf_switch.SLOW_REGRESSION_MONTHS,
                min_observations=etf_switch.SLOW_MIN_OBSERVATIONS,
            )[0],
        )
        self.events = set()
        quarter = 0
        self.error = None
        while True:
            signal = bisect_left(
                self.dates, months_before(self.dates[self.first], -3 * quarter)
            )
            if signal + 1 >= len(self.days):
                break
            lower_date = months_before(self.dates[signal], etf_switch.REGRESSION_MONTHS)
            lower = bisect_left(self.dates, lower_date)
            if (
                signal - lower < etf_switch.MIN_OBSERVATIONS - 1
                or (self.dates[lower] - lower_date).days > 7
            ):
                self.error = {
                    "status": "insufficient",
                    "message": (
                        f"{etf_switch.REGRESSION_MONTHS} mois et au moins "
                        f"{etf_switch.MIN_OBSERVATIONS - 1} variations communes "
                        f"sont nécessaires au {self.days[signal]}."
                    ),
                }
                break
            self.events.add(signal + 1)
            quarter += 1

        for signal in range(self.first, len(self.days) - 1):
            for sleeve, due in enumerate(self._scheduled(signal)):
                if not due:
                    continue
                months, minimum = (
                    (
                        etf_switch.SLOW_REGRESSION_MONTHS,
                        etf_switch.SLOW_MIN_OBSERVATIONS,
                    )
                    if sleeve == 0
                    else (etf_switch.REGRESSION_MONTHS, etf_switch.MIN_OBSERVATIONS)
                )
                for s in (signal, signal - 1):
                    cutoff = months_before(self.dates[s], months)
                    lower = bisect_left(self.dates, cutoff)
                    if s - lower + 1 < minimum or (self.dates[lower] - cutoff).days > 7:
                        self.windows[sleeve, s] = None
                    else:
                        x = np.array(
                            [
                                (d - self.dates[lower]).days / 365.25
                                for d in self.dates[lower : s + 1]
                            ]
                        )
                        self.windows[sleeve, s] = (lower, x - x.mean())

    def _scheduled(self, signal):
        return (
            self.days[signal][:7] != self.days[signal - 1][:7],
            (signal - self.first) % etf_switch.DECISION_SESSIONS == 0,
        )

    def _scores(self, logs, sleeve, signal):
        window = self.windows[sleeve, signal]
        if window is None:
            return [None] * logs.shape[1]
        lower, centered = window
        y = logs[lower : signal + 1]
        scores = log_regression_scores(y, centered)
        # Column-wise reductions can differ by machine epsilon from a scalar
        # fit. At a decision boundary, use the exact single-path reduction.
        thresholds = (
            (etf_switch.SLOW_ENTRY_Z, etf_switch.SLOW_REENTRY_Z, etf_switch.EXIT_Z)
            if sleeve == 0
            else (etf_switch.ENTRY_Z, etf_switch.EXIT_Z)
        )
        if y.shape[1] > 1:
            for j, score in enumerate(scores):
                if score is not None and any(abs(score - t) < 1e-9 for t in thresholds):
                    scores[j] = log_regression_scores(y[:, j : j + 1], centered)[0]
        return scores

    def simulate(self, seeds):
        # Import here to avoid a cycle with the public streaming entry point.
        from investor.portfolio.sp500_simulation import BATCH_METRICS, sampled_returns

        if self.error:
            return [self.error for _ in seeds]
        source, request = self.source, self.request
        n = len(seeds)
        increments = np.column_stack(
            [
                sampled_returns(source["returns"], len(source["synthetic_days"]), seed)
                for seed in seeds
            ]
        )
        with np.errstate(over="ignore", invalid="ignore"):
            future = source["anchor"] * np.exp(np.cumsum(increments, axis=0))
        prices = np.concatenate(
            (np.broadcast_to(source["prices"][:, None], (self.first + 1, n)), future)
        )
        valid = np.all(np.isfinite(prices) & (prices > 0), axis=0)
        # An invalid column will be reported, never silently omitted. Keep it out
        # of the arithmetic so it cannot contaminate other paths in the group.
        prices[:, ~valid] = source["anchor"]
        logs = np.log(prices)
        fee = request.fee_rate
        scale = request.initial_capital / 100
        values = np.zeros((n, len(etf_switch.SLEEVE_NAMES)))
        cash = np.broadcast_to(
            100 * np.array(etf_switch.INITIAL_SHARES), values.shape
        ).copy()
        state = np.zeros_like(values, dtype=bool)
        state[:, 0] = self.initial_state
        last = np.full_like(values, np.nan)
        strategy_value, strategy_cash = np.zeros(n), np.full(n, 100.0)
        benchmark_value, benchmark_cash = np.zeros(n), np.full(n, 100.0)
        strategy_cost, benchmark_cost, turnover = (np.zeros(n) for _ in range(3))
        entered = np.zeros(n, dtype=bool)
        curves = np.full((len(future) + 1, n, 2), 100.0)
        quarter_base = None
        quarters = []
        for i in range(self.first + 1, len(self.days)):
            growth = prices[i] / prices[i - 1]
            strategy_value *= growth
            benchmark_value *= growth
            values *= growth[:, None]
            if i in self.events:
                before = np.column_stack(
                    (benchmark_value + benchmark_cash, strategy_value + strategy_cash)
                )
                if quarter_base is not None:
                    quarters.append(before / quarter_base - 1)
                quarter_base = before
                if i == self.first + 1:
                    benchmark_value, benchmark_cash = _rebalance(
                        benchmark_value, benchmark_cash, np.ones(n), fee
                    )
                    if request.whole_shares:
                        unit = prices[i] / scale
                        benchmark_value = (
                            np.floor(benchmark_value / unit + 1e-10) * unit
                        )
                        benchmark_cash = 100 - benchmark_value - benchmark_value * fee
                    benchmark_cost = benchmark_value * fee
            signal = i - 1
            scheduled = self._scheduled(signal)
            changed = np.zeros_like(state)
            target = np.where(state, 1.0, etf_switch.DEFENSIVE_WEIGHT)
            if self.matured[signal]:
                for sleeve, due in enumerate(scheduled):
                    if due:
                        scores = self._scores(logs, sleeve, signal)
                        previous = self._scores(logs, sleeve, signal - 1)
                        transition = (
                            etf_switch.slow_target
                            if sleeve == 0
                            else etf_switch.defensive_target
                        )
                        state[:, sleeve] = [
                            transition(score, prior, on)
                            for score, prior, on in zip(
                                scores, previous, state[:, sleeve], strict=True
                            )
                        ]
                    target[:, sleeve] = np.where(
                        state[:, sleeve], 1.0, etf_switch.DEFENSIVE_WEIGHT
                    )
                    if due or np.isnan(last[:, sleeve]).any():
                        changed[:, sleeve] = target[:, sleeve] != last[:, sleeve]
            if changed.any():
                new, _ = _rebalance(values, cash, target, fee)
                if request.whole_shares:
                    unit = prices[i, :, None] / scale
                    new = np.floor(new / unit + 1e-10) * unit
                delta = np.where(changed, new - values, 0.0)
                costs = np.abs(delta) * fee
                remaining = np.maximum(0.0, values + cash - new - costs)
                allocation_capital = strategy_value + strategy_cash
                initial_allocation = ~entered
                # Same sales-before-purchases order as the production ledger.
                order = np.argsort(delta, axis=1, kind="stable")
                for rank in range(len(etf_switch.SLEEVE_NAMES)):
                    rows = np.arange(n)
                    sleeve = order[:, rank]
                    trade = delta[rows, sleeve]
                    cost = costs[rows, sleeve]
                    strategy_value += trade
                    strategy_cash -= trade + cost
                    strategy_cost += cost
                    initial = (np.abs(trade) > 1e-9) & initial_allocation
                    turnover += np.where(
                        initial, 0.0, np.abs(trade) / allocation_capital
                    )
                    entered |= initial
                values = np.where(changed, new, values)
                cash = np.where(changed, remaining, cash)
                last = np.where(changed, target, last)
            curves[i - self.first, :, 0] = benchmark_value + benchmark_cash
            curves[i - self.first, :, 1] = strategy_value + strategy_cash
        elapsed = (self.dates[-1] - self.dates[self.first]).days / 365.25
        quarters = np.array(quarters)
        results = []
        for j in range(n):
            curve = curves[:, j]
            if not valid[j] or not np.all(np.isfinite(curve) & (curve > 0)):
                results.append(
                    {
                        "status": "insufficient",
                        "message": "Les valeurs simulées dépassent les limites du calcul.",
                    }
                )
                continue
            changes = curve[1:] / curve[:-1] - 1
            metrics = {}
            for k, key in enumerate(("benchmark", "strategy")):
                row = curve_metrics(
                    curve[:, k], changes[:, k], changes[:, 0], elapsed, 252
                )
                row.update(
                    cost_eur=float(
                        (benchmark_cost if k == 0 else strategy_cost)[j] * scale
                    ),
                    annual_turnover=float(0 if k == 0 else turnover[j] / elapsed),
                    positive_quarters=int(np.sum(quarters[:, j, k] > 0)),
                    worst_quarter=float(np.min(quarters[:, j, k]))
                    if len(quarters)
                    else None,
                )
                metrics[key] = {name: row[name] for name in BATCH_METRICS}
            results.append({"status": "ready", "comparison": {"metrics": metrics}})
        return results
