"""Monthly SPMO/cash strategies signalled by the EUR PSP5 close."""

from datetime import date
from itertools import product

import numpy as np

from investor.assets.momentum import months_before
from investor.portfolio.sp500_simulation import future_sessions

BASE = (200, 0.75)
RULES = list(product((100, 150, 200, 250), (0.25, 0.5, 0.65, 0.75, 0.85, 0.95)))


ENSEMBLES = [
    (fast, floor, slow)
    for fast, floor, slow in product(
        (50, 100, 150), (0.4, 0.5, 0.6, 0.7, 0.8), (200, 250)
    )
]


def history(conn):
    ids = ("yf-psp5.pa", "yf-spmo", "yf-eurusd=x")
    rows = conn.execute(
        """SELECT a.date, a.asset_id, a.value, p.value FROM observations a
        JOIN price_observations p USING (asset_id, date)
        WHERE a.asset_id IN (?, ?, ?) ORDER BY a.date""",
        ids,
    )
    by_day = {}
    for day, asset, adjusted, close in rows:
        by_day.setdefault(day, {})[asset] = (adjusted, close)
    days = [day for day, values in by_day.items() if len(values) == 3]
    if len(days) < 500 or any(
        (date.fromisoformat(b) - date.fromisoformat(a)).days > 14
        for a, b in zip(days[:-1], days[1:], strict=True)
    ):
        raise ValueError(
            "Historique commun PSP5, SPMO et EUR/USD insuffisant ou discontinu."
        )
    data = np.array([[by_day[d][k] for k in ids] for d in days], dtype=float)
    if not np.isfinite(data).all() or (data <= 0).any():
        raise ValueError("Cours ou taux de change invalide.")
    # Columns: adjusted PSP5, tradable PSP5, adjusted SPMO EUR, tradable SPMO EUR.
    return np.array(days), np.column_stack((data[:, 0], data[:, 1] / data[:, 2, :1]))


def evaluate(prices, start, signals, rules, years, fee=0.0012, delay=1):
    """Mark every common close, even during intervals with no orders."""
    signal = prices[:, 0]
    cumsum = np.r_[0.0, np.cumsum(signal)]
    votes = {}
    targets = []
    for fast, floor, *confirmation in rules:
        windows = (fast, *confirmation)
        for window in windows:
            if window not in votes:
                means = (cumsum[signals + 1] - cumsum[signals + 1 - window]) / window
                votes[window] = signal[signals] > means
        exposure = np.mean([votes[w] for w in windows], axis=0)
        targets.append(floor + (1 - floor) * exposure)
    targets = np.column_stack(targets)
    # SPMO cash distributions inferred from adjusted and split-adjusted close.
    dist = np.r_[
        0.0, np.cumsum(prices[:-1, 3] * prices[1:, 2] / prices[:-1, 2] - prices[1:, 3])
    ]
    end = len(prices)
    nav = np.full((end - start, len(rules)), 10000.0)
    cash = np.full(len(rules), 10000.0)
    units = np.zeros(len(rules))
    last = np.full(len(rules), -1.0)
    previous = start
    orders = signals + delay
    for j, at in enumerate(orders):
        price = prices[at, 3]
        cash += units * (dist[at] - dist[previous])
        target = targets[j]
        wanted = np.floor(target * (cash + units * price) / (price * (1 + fee)))
        trade = np.where(target != last, wanted - units, 0.0)
        cash -= trade * price + abs(trade) * price * fee
        units += trade
        stop = orders[j + 1] if j + 1 < len(orders) else end
        nav[at - start : stop - start] = (
            cash + units * (prices[at:stop, 3] + dist[at:stop] - dist[at])[:, None]
        )
        previous, last = at, target
    # Passive controls buy whole units only once and retain their distributions.
    controls = []
    for adjusted, raw in [(0, 1), (2, 3)]:
        at = start + delay
        qty = np.floor(10000 / (prices[at, raw] * (1 + fee)))
        flows = (
            prices[at:-1, raw] * prices[at + 1 :, adjusted] / prices[at:-1, adjusted]
            - prices[at + 1 :, raw]
        )
        controls.append(
            np.r_[
                np.full(delay, 10000.0),
                10000
                + qty
                * (
                    prices[at:, raw]
                    - prices[at, raw] * (1 + fee)
                    + np.r_[0.0, np.cumsum(flows)]
                ),
            ]
        )
    nav = np.column_stack((nav, *controls))
    return np.column_stack(
        (
            (nav[-1] / 10000) ** (1 / years) - 1,
            (nav / np.maximum.accumulate(nav, axis=0) - 1).min(0),
        )
    )


def calendar(days, start, delay=1):
    months = days.astype("datetime64[M]")
    signals = np.r_[
        start, np.flatnonzero(months[start + 1 :] != months[start:-1]) + start + 1
    ]
    return signals[signals + delay < len(days)]


def historical(days, prices, rules, years, fee=0.0012, delay=1):
    end = date.fromisoformat(days[-1])
    start = int(np.searchsorted(days, months_before(end, 12 * years).isoformat()))
    if start + 1 < max(
        max(rule[0], rule[2] if len(rule) == 3 else rule[0]) for rule in rules
    ) or start + delay >= len(days):
        raise ValueError("Historique insuffisant pour cet horizon et cette fenêtre.")
    elapsed = (end - date.fromisoformat(days[start])).days / 365.25
    return evaluate(
        prices, start, calendar(days, start, delay), rules, elapsed, fee, delay
    )


def simulate(days, prices, rules, years, count, seed):
    future = future_sessions(date.fromisoformat(days[-1]), years)
    dates = np.r_[days[-250:], np.array(future)]
    signals = calendar(dates, 249)
    ratios = prices[1:] / prices[:-1]
    elapsed = (
        date.fromisoformat(future[-1]) - date.fromisoformat(days[-1])
    ).days / 365.25
    paths = []
    for child in np.random.SeedSequence(seed).spawn(count):
        rng = np.random.default_rng(child)
        # Joint circular blocks preserve cross-asset and FX co-movement.
        idx = []
        while len(idx) < len(future):
            block = rng.geometric(1 / 63)
            idx.extend((rng.integers(len(ratios)) + np.arange(block)) % len(ratios))
        simulated = prices[-1] * np.cumprod(ratios[idx[: len(future)]], axis=0)
        paths.append(
            evaluate(
                np.vstack((prices[-250:], simulated)), 249, signals, rules, elapsed
            )
        )
    return np.array(paths)


def select(paths):
    mean = paths.mean(0)
    delta = mean[:-2] - mean[-2]
    eligible = np.flatnonzero((delta > 0).all(axis=1))
    return int(eligible[np.argmax(delta[eligible, 0])]) if len(eligible) else None


def summarize(paths):
    delta = paths - paths[:, -2:-1]
    return [
        dict(
            cagr=float(m[0]),
            drawdown=float(m[1]),
            joint=int(w),
            return_wins=int(r),
            drawdown_wins=int(d),
        )
        for m, w, (r, d) in zip(
            paths.mean(0), (delta > 0).all(2).sum(0), (delta > 0).sum(0), strict=True
        )
    ]


def comparison(days, prices, years, seed, count):
    candidates = [*RULES, *ENSEMBLES]
    # Validate horizon and signal warmup before starting the simulation lot.
    history_metrics = historical(days, prices, candidates, years)
    train_seed, audit_seed = np.random.SeedSequence(seed).generate_state(2)
    training = simulate(days, prices, candidates, years, 250, int(train_seed))
    chosen = select(training)
    rules = [BASE, (150, 0.7, 200)]
    if chosen is not None and candidates[chosen] not in rules:
        rules.append(candidates[chosen])
    audit = simulate(days, prices, rules, years, count, int(audit_seed))
    metrics = history_metrics[[*(candidates.index(rule) for rule in rules), -2, -1]]
    labels = [rule_label(rule) for rule in rules] + ["PSP5 passif", "SPMO passif"]
    return dict(
        seed=seed,
        count=count,
        end=days[-1],
        selected=rule_label(candidates[chosen]) if chosen is not None else None,
        rows=[
            dict(label=label, history_cagr=h[0], history_drawdown=h[1], **stats)
            for label, h, stats in zip(labels, metrics, summarize(audit), strict=True)
        ],
    )


def rule_label(rule):
    window, floor, *second = rule
    windows = f"{window}/{second[0]}" if second else str(window)
    return f"SPMO · MM {windows} · plancher {floor:.0%}"


def monthly_signal(days, prices):
    month = days[-1][:7]
    at = int(np.searchsorted(days, month))
    if at < BASE[0] - 1:
        raise ValueError("Historique insuffisant pour calculer la moyenne mobile.")
    average = float(prices[at - BASE[0] + 1 : at + 1, 0].mean())
    return dict(
        day=days[at],
        execution=days[at + 1] if at + 1 < len(days) else None,
        target=1.0 if prices[at, 0] > average else BASE[1],
        average=average,
        psp5=float(prices[at, 0]),
    )
