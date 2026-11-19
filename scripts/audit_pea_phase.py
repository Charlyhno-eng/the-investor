"""Independent float-weight event book, fixed post-selection phase and core controls."""

import json
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import study_pea_timing as base

OUT = Path("data/backtests/pea-phase-audit.json")
NAMES = [
    "passive",
    "original",
    "original_with_15pct_core",
    "five_independent_sleeves",
    "five_votes_one_book",
    "five_votes_with_15pct_core",
]


def ledger(prices, signals, weights, capital, fee, delay):
    changed = np.r_[True, np.diff(weights) != 0]
    times = signals[changed] + delay
    weights = weights[changed]
    valid = times < len(prices)
    times, weights = times[valid], weights[valid]
    unit_changes = np.zeros(len(prices))
    cash_changes = np.zeros(len(prices))
    costs = 0.0
    orders = 0
    cash = capital
    units = 0
    for i, t in zip(times, weights, strict=True):
        p = prices[i]
        value = cash + units * p
        # Solve target after transaction costs on purchases and sales separately.
        if t * value >= units * p:
            target_units = np.floor(
                t * (value + fee * units * p) / (p * (1 + fee * t)) + 1e-10
            )
        else:
            target_units = np.floor(
                t * (value - fee * units * p) / (p * (1 - fee * t)) + 1e-10
            )
        trade = target_units - units
        cost = abs(trade) * p * fee
        delta_cash = -trade * p - cost
        unit_changes[i] = trade
        cash_changes[i] = delta_cash
        units = target_units
        cash += delta_cash
        costs += cost
        orders += trade != 0
        if cash < -0.00001:
            raise ValueError("Negative cash")
    return (
        capital + cash_changes.cumsum() + prices * unit_changes.cumsum(),
        costs,
        orders,
    )


def books(p, lo, years, fee=0.0012, delay=1):
    features = base.Features(p)
    # Daily indicator and all prior states are known at the signal close.
    day = (features.series("down", 21) <= 0.8 * features.series("rms", 21) ** 2).astype(
        float
    )
    idx = np.arange(lo, len(p))
    p = p[lo:]

    def book(i, t, c):
        return ledger(p, i, t, c, fee, delay)

    def combined(*parts):
        return (
            np.sum([r[0] for r in parts], axis=0),
            sum(r[1] for r in parts),
            sum(r[2] for r in parts),
        )

    passive = book(np.array([0]), np.array([1.0]), 10000.0)
    original = book(idx[::5] - lo, day[idx[::5]], 10000.0)
    core = book(np.array([0]), np.array([1.0]), 1500.0)
    core_original = combined(core, book(idx[::5] - lo, day[idx[::5]], 8500.0))
    # Global phases are equivalent under permutation when each book starts
    # with the same budget. Each inherits its most recently observed signal.
    tranches = []
    for k in range(5):
        signal = idx[(idx - lo) % 5 == k]
        if k:
            prior = lo + k - 5
            signal = np.r_[lo, signal]
            weights = np.r_[day[prior], day[signal[1:]]]
        else:
            weights = day[signal]
        tranches.append(book(signal - lo, weights, 2000.0))
    weights = np.convolve(day, np.ones(5) / 5, "valid")[idx - 4]
    daily = book(idx - lo, weights, 10000.0)
    core_daily = combined(core, book(idx - lo, weights, 8500.0))
    books = [passive, original, core_original, combined(*tranches), daily, core_daily]
    rows = []
    for curve, cost, n in books:
        rows.append(
            [
                (curve[-1] / 10000) ** (1 / years) - 1,
                (curve / np.maximum.accumulate(curve) - 1).min(),
                np.std(np.diff(curve) / curve[:-1], ddof=1) * np.sqrt(252),
                cost,
                n,
            ]
        )
    return np.array(rows)


def historical(d, p, start, end=None, fee=0.0012, delay=1):
    hi = len(p) if end is None else np.searchsorted(d, end, side="right")
    lo = np.searchsorted(d, start)
    y = (date.fromisoformat(d[hi - 1]) - date.fromisoformat(d[lo])).days / 365.25
    return books(p[:hi], lo, y, fee, delay)


def sampled(args):
    d, p, y, seeds = args
    fut = base.future_sessions(date.fromisoformat(d[-1]), y)
    years = (date.fromisoformat(fut[-1]) - date.fromisoformat(d[-1])).days / 365.25
    r = np.diff(np.log(p))
    a = []
    for seed in seeds:
        future = p[-1] * np.exp(np.cumsum(base.sampled_returns(r, len(fut), seed)))
        a.append(books(np.r_[p[-505:], future], 504, years))
    return np.array(a)


def main():
    with (
        tempfile.TemporaryDirectory() as tmp,
        sqlite3.connect(
            f"file:{base.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
        ) as src,
        sqlite3.connect(":memory:") as conn,
    ):
        src.backup(conn)
        d, p = base.read_data(conn, "yf-psp5.pa")
        report = dict(rules=NAMES, real={}, audit={})
        for y in [1, 3, 5, 10]:
            start = f"{2026 - y}-11-19"
            r = historical(d, p, start)
            check = base.evaluate(
                base.compile_ledger(tmp),
                d,
                p,
                [base.PASSIVE, ("downside", 21, 0.8, 5, 0.0)],
                start,
            )
            np.testing.assert_allclose(r[:2], check[:, :5], atol=1e-8, rtol=0)
            report["real"][str(y)] = r.tolist()
        report["post2020"] = historical(d, p, "2021-01-01").tolist()
        report["stress"] = historical(d, p, "2021-01-01", fee=0.0024, delay=2).tolist()
        report["rolling"] = {
            f"{y}-{m:02}-19": historical(
                d, p, f"{y}-{m:02}-19", f"{y + 5}-{m:02}-19"
            ).tolist()
            for y in range(2016, 2022)
            for m in range(1, 13)
            if f"{y + 5}-{m:02}-19" <= d[-1]
        }
        report["start_offsets"] = {
            str(y): [
                historical(
                    d, p, d[np.searchsorted(d, f"{2026 - y}-11-19") + i]
                ).tolist()
                for i in range(5)
            ]
            for y in [3, 5, 10]
        }
        for y, seed in [(5, 4110000), (10, 4120000)]:
            args = [
                (d, p, y, ids)
                for ids in np.array_split(np.arange(seed, seed + 1000), 30)
            ]
            with ProcessPoolExecutor(max_workers=4) as pool:
                paths = np.concatenate(list(pool.map(sampled, args)))
            report["audit"][str(y)] = base.stats(paths)
            OUT.write_text(json.dumps(report, allow_nan=False) + "\n")
            print("AUDIT", y, flush=True)


if __name__ == "__main__":
    main()
