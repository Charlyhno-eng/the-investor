"""PEA external information study, only PSP5 is tradable.

Cboe daily close CSV files in data/backtests/pea-inputs/{VIX,VIX3M}.csv from
https://cdn.cboe.com/api/global/us_indices/daily_prices/{VIX,VIX3M}_History.csv.
"""

import csv
import hashlib
import json
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime
from itertools import product
from pathlib import Path

import numpy as np
import study_pea_timing as base

FAMILIES = {
    "term_structure": ([1, 3, 5], [1.0, 1.05, 1.1, 1.2]),
    "panic_reentry": ([3, 5, 10], [1.0, 1.05, 1.1]),
    "variance_premium": ([10, 21, 42], [0.7, 0.9, 1.0, 1.1]),
    "panic_fade": ([1, 5, 21], [18, 22, 28]),
    "fx_stress": ([5, 21, 63], [0.01, 0.025, 0.05]),
    "rates": ([10, 21, 63], [0, 0.25, 0.5]),
    "macro_trend": ([50, 100, 200], [-0.5, 0, 0.5]),
    "macro_votes": ([10, 21, 63], [2, 3]),
}
GRID = [
    (family, w, k, step, floor)
    for family, (ws, ks) in FAMILIES.items()
    for w, k, step, floor in product(ws, ks, [1, 5, 0], [0, 0.5, 0.85])
]
OUT = Path("data/backtests/pea-cross-signals.json")
FOLDER = Path("data/backtests/pea-inputs")


def cboe(name):
    with (FOLDER / f"{name}.csv").open() as f:
        rows = sorted(
            (
                datetime.strptime(r["DATE"], "%m/%d/%Y").date().isoformat(),
                float(r["CLOSE"]),
            )
            for r in csv.DictReader(f)
        )
    return np.array([r[0] for r in rows]), np.array([r[1] for r in rows])


def known(days, src, lag=0):
    d, v = src
    # Most recent foreign close strictly before the French session.
    ids = np.searchsorted(d, days, side="left") - 1
    if (ids < 0).any():
        raise ValueError("Missing source history")
    if lag:
        ids = ids[np.maximum(np.arange(len(days)) - lag, 0)]
    age = (days.astype("datetime64[D]") - d[ids].astype("datetime64[D]")).astype(int)
    return v[ids], age


def inputs(conn, days):
    names = [
        "yf-spy",
        "yf-jpyusd=x",
        "yf-chfusd=x",
        "yf-audusd=x",
        "yf-cadusd=x",
        "DGS10",
        "DGS3MO",
    ]
    sources = [cboe("VIX"), cboe("VIX3M"), *[base.read_data(conn, k) for k in names]]
    series = []
    ages = []
    for i, source in enumerate(sources):
        values, age = known(days, source, lag=int(i >= 7))
        series.append(values)
        ages.append(age)
    # Prices of funding/safe currencies vs cyclical currencies in common USD.
    fx = (
        np.log(series[3]) + np.log(series[4]) - np.log(series[5]) - np.log(series[6])
    ) / 2
    return np.column_stack(
        [
            series[0],
            series[1],
            np.log(series[2]),
            fx,
            series[7],
            series[8],
            np.max(ages, axis=0),
        ]
    )


class External(base.Features):
    def __init__(self, p, external):
        super().__init__(p)
        self.vix, self.vix3m, self.spy, self.fx, self.long, self.short, self.age = (
            external.T
        )
        self.term = self.vix / self.vix3m

    def mode(self, family, w, k):
        if family == "passive":
            return super().mode(family, w, k)
        if family == "term_structure":
            flag = self.roll(self.term, w) > k
        elif family == "panic_reentry":
            flag = (self.term > k) & (self.vix >= self.lag(self.vix, w))
        elif family == "variance_premium":
            key = ("usd_rv", w)
            if key not in self.memo:
                self.memo[key] = (
                    np.sqrt(
                        self.roll(np.diff(self.spy, prepend=self.spy[0]) ** 2, w) * 252
                    )
                    * 100
                )
            flag = self.vix < k * self.memo[key]
        elif family == "panic_fade":
            flag = (
                (self.vix > k)
                & (self.vix > self.lag(self.vix, w))
                & (self.p < self.series("ma", 21))
            )
        elif family == "fx_stress":
            flag = self.fx - self.lag(self.fx, w) > k
        elif family == "rates":
            flag = (self.long - self.short < 0.5) & (
                self.long - self.lag(self.long, w) > k
            )
        elif family == "macro_trend":
            flag = (self.long - self.short < k) & (self.p < self.series("ma", w))
        elif family == "macro_votes":
            votes = (
                (self.term > 1).astype(int)
                + (self.fx - self.lag(self.fx, w) > 0.015)
                + (self.long < self.short)
                + (self.p < self.series("ma", 100))
            )
            flag = votes >= k
        else:
            raise ValueError(family)
        # Revert to benchmark exposure if an external source is excessively old.
        return np.ascontiguousarray(flag & (self.age <= 14), dtype=np.int8)


def evaluate(lib, days, p, x, rules, start, end=None, fee=0.0012, delay=1):
    hi = len(days) if end is None else np.searchsorted(days, end, side="right")
    return base.evaluate(
        lib, days, p, rules, start, end, fee, delay, features=External(p[:hi], x[:hi])
    )


def sample(args):
    lib, days, p, x, rules, years, seeds, block = args
    fut = base.future_sessions(date.fromisoformat(days[-1]), years)
    dates = np.r_[days[-505:], np.array(fut)]
    returns = np.diff(np.log(p))
    noise = 0.05 * returns.std(ddof=1)
    # Synchronous rows: ETF return, available option/yield levels, changes in
    # the last known US total return and FX basket. Simulate levels for the latter.
    dx = np.diff(x[:, 2:4], axis=0)
    results = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        idx = []
        while len(idx) < len(fut):
            i = rng.integers(len(returns))
            n = min(rng.geometric(1 / block), len(returns) - i)
            idx.extend(range(i, i + n))
        idx = np.array(idx[: len(fut)])
        pp = np.r_[
            p[-505:],
            p[-1] * np.exp(np.cumsum(returns[idx] + rng.normal(0, noise, len(idx)))),
        ]
        ex = x[idx + 1].copy()
        ex[:, 2:4] = x[-1, 2:4] + np.cumsum(dx[idx], axis=0)
        xx = np.vstack([x[-505:], ex])
        results.append(evaluate(lib, dates, pp, xx, rules, days[-1]))
    return np.array(results)


def batch(lib, days, p, x, rules, y, seed, n, block=63):
    groups = np.array_split(np.arange(seed, seed + n), 24)
    with ProcessPoolExecutor(max_workers=4) as pool:
        return np.concatenate(
            list(
                pool.map(
                    sample, [(lib, days, p, x, rules, y, ids, block) for ids in groups]
                )
            )
        )


def main():
    with (
        tempfile.TemporaryDirectory() as tmp,
        sqlite3.connect(
            f"file:{base.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
        ) as src,
        sqlite3.connect(":memory:") as conn,
    ):
        src.backup(conn)
        days, p = base.read_data(conn, "yf-psp5.pa")
        x = inputs(conn, days)
        lib = base.compile_ledger(tmp)
        rules = [base.PASSIVE, *GRID]
        cut = np.searchsorted(days, "2021-01-01")
        hist = [
            evaluate(lib, days, p, x, rules, a, b)
            for a, b in [("2016-01-01", "2018-12-31"), ("2019-01-01", "2020-12-31")]
        ]
        training = batch(
            lib, days[:cut], p[:cut], x[:cut], rules, 5, 3810000, 200
        ).mean(0)
        margins = np.concatenate(
            [a[:, :2] - a[:1, :2] for a in [*hist, training]], axis=1
        )

        def score(j):
            m = margins[j].min()
            return (m > 1e-10, margins[j, -2] if m > 1e-10 else m, margins[j, -2], -j)

        ids = [
            max((i for i, r in enumerate(rules) if r[0] == family), key=score)
            for family in FAMILIES
        ]
        frozen = [base.PASSIVE, *[rules[j] for j in ids]]
        win = ids.index(max(ids, key=score)) + 1
        report = dict(
            frozen=frozen,
            winner=win,
            eligible=int((margins[1:] > 1e-10).all(1).sum()),
            grid=rules,
            selection_margins=margins.tolist(),
            input_sha256=hashlib.sha256(np.column_stack((p, x)).tobytes()).hexdigest(),
            external_sha256={
                n: hashlib.sha256((FOLDER / f"{n}.csv").read_bytes()).hexdigest()
                for n in ["VIX", "VIX3M"]
            },
        )
        print("FROZEN", len(GRID), report["eligible"], frozen, win, flush=True)
        report["post2020"] = evaluate(lib, days, p, x, frozen, "2021-01-01").tolist()
        report["real"] = {
            str(y): evaluate(lib, days, p, x, frozen, f"{2026 - y}-11-19").tolist()
            for y in [1, 3, 5, 10]
        }
        report["stress"] = evaluate(
            lib, days, p, x, frozen, "2021-01-01", fee=0.0024, delay=2
        ).tolist()
        report["rolling"] = {
            f"{y}-{m:02}-19": evaluate(
                lib, days, p, x, frozen, f"{y}-{m:02}-19", f"{y + 5}-{m:02}-19"
            ).tolist()
            for y in range(2016, 2022)
            for m in [2, 5, 8, 11]
        }
        report["audit"] = {}
        for y, seed in [(5, 3820000), (10, 3830000)]:
            report["audit"][str(y)] = base.stats(
                batch(lib, days, p, x, frozen, y, seed, 1000)
            )
            OUT.write_text(json.dumps(report, allow_nan=False) + "\n")
            print("AUDIT", y, flush=True)


if __name__ == "__main__":
    main()
