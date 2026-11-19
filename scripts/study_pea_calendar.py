"""Declared PEA month-end hypotheses; paired complete-month and neutral bootstraps."""

import json
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from itertools import product
from pathlib import Path

import numpy as np
import study_pea_timing as base

OUTPUT = Path("data/backtests/pea-month-end.json")
FAMILIES = ["turn_of_month", "pre_end_exit", "conditional_pre_end"]
GRID = [
    (family, a, b, 1, floor)
    for family in FAMILIES
    for a, b, floor in (
        product([2, 4, 6], [1, 3, 5], [0, 0.5, 0.85])
        if family == "turn_of_month"
        else product([6, 8, 10], [2, 3, 4], [0, 0.5, 0.85])
    )
]


def positions(days):
    dates = days.astype("datetime64[D]")
    month = dates.astype("datetime64[M]")
    # Weekday approximation known in advance, independent of future missing rows.
    return np.busday_count(month.astype("datetime64[D]"), dates), np.busday_count(
        dates, (month + 1).astype("datetime64[D]")
    )


class Calendar(base.Features):
    def __init__(self, p, slots):
        super().__init__(p)
        self.front, self.back = slots

    def mode(self, family, a, b):
        if family == "passive":
            return super().mode(family, a, b)
        if family == "turn_of_month":
            flag = (self.front >= b) & (self.back > a)
        else:
            flag = (self.back <= a) & (self.back >= b)
            if family == "conditional_pre_end":
                flag &= self.p < self.series("ma", 63)
        return np.ascontiguousarray(flag, dtype=np.int8)


def real(lib, days, p, cs, start, end=None, fee=0.0012, delay=1):
    hi = len(days) if end is None else np.searchsorted(days, end, side="right")
    return base.evaluate(
        lib, days, p, cs, start, end, fee, delay, Calendar(p[:hi], positions(days[:hi]))
    )


def sample(args, lib, d, p, cs, groups, years):
    months = d.astype("datetime64[M]")
    boundaries = np.r_[0, np.flatnonzero(months[1:] != months[:-1]) + 1, len(d)]
    # Exclude first and last months as potentially incomplete.
    groups_by_month = [
        np.arange(i, j) for i, j in zip(boundaries[1:-2], boundaries[2:-1], strict=True)
    ]
    logret = np.diff(np.log(p), prepend=np.log(p[0]))
    slots = positions(d)
    nmonths = 12 * years
    output = []
    for seed in args:
        rng = np.random.default_rng(seed)
        choices = []
        while len(choices) < nmonths:
            j = rng.integers(len(groups_by_month))
            length = min(
                rng.geometric(1 / 3), len(groups_by_month) - j, nmonths - len(choices)
            )
            choices.extend(range(j, j + length))
        ids = np.concatenate([groups_by_month[j] for j in choices])
        terminal = boundaries[-2] - 1
        warm = np.arange(terminal - 249, terminal + 1)
        pp = np.r_[p[warm], p[terminal] * np.exp(np.cumsum(logret[ids]))]
        labels = [np.r_[v[warm], v[ids]] for v in slots]
        if groups == "neutral":
            # Rotate the future calendar labels without changing synthetic prices.
            shift = rng.integers(1, len(ids))
            labels = [np.r_[v[:250], np.roll(v[250:], shift)] for v in labels]
        features = Calendar(pp, labels)
        monthly = np.zeros(len(pp), dtype=np.int32)
        metrics = np.zeros((len(cs), 6))
        for i, (f, a, b, step, floor) in enumerate(cs):
            base.load(lib)(
                len(pp),
                249,
                1,
                0.0012,
                float(years),
                pp,
                features.mode(f, a, b),
                monthly,
                step,
                floor,
                metrics[i],
            )
        output.append(metrics)
    return np.array(output)


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
        ds, ps = base.read_data(conn, "yf-spy")
        lib = base.compile_ledger(tmp)
        rules = [base.PASSIVE, *GRID]
        train = np.array(
            [
                real(lib, ds, ps / ps[0] * 25, rules, "1995-01-01", "2013-12-31"),
                real(lib, d, p, rules, "2016-01-01", "2020-12-31"),
            ]
        )
        delta = train[:, 1:, :2] - train[:, :1, :2]

        def score(i):
            m = delta[:, i].min()
            return (
                m > 1e-10,
                delta[:, i, 0].mean() if m > 1e-10 else m,
                delta[:, i, 0].mean(),
                -i,
            )

        ids = [
            max((i for i, c in enumerate(GRID) if c[0] == f), key=score)
            for f in FAMILIES
        ]
        cs = [base.PASSIVE, *[GRID[i] for i in ids]]
        report = dict(
            grid=rules,
            training=train.tolist(),
            frozen=cs,
            winner=ids.index(max(ids, key=score)) + 1,
            eligible=int((delta > 1e-10).all((0, 2)).sum()),
        )
        report["post2020"] = real(lib, d, p, cs, "2021-01-01").tolist()
        report["real"] = {
            str(y): real(lib, d, p, cs, f"{2026 - y}-11-19").tolist()
            for y in [1, 3, 5, 10]
        }
        report["stress"] = real(
            lib, d, p, cs, "2021-01-01", fee=0.0024, delay=2
        ).tolist()
        report["audit"] = {}
        for y in [5, 10]:
            seeds = np.array_split(
                np.arange(4010000 + y * 1000, 4011000 + y * 1000), 24
            )
            for mode in ["aligned", "neutral"]:
                with ProcessPoolExecutor(max_workers=4) as pool:
                    paths = np.concatenate(
                        list(
                            pool.map(
                                partial(
                                    sample,
                                    lib=lib,
                                    d=d,
                                    p=p,
                                    cs=cs,
                                    groups=mode,
                                    years=y,
                                ),
                                seeds,
                            )
                        )
                    )
                report["audit"][f"{y}-{mode}"] = base.stats(paths)
                OUTPUT.write_text(json.dumps(report, allow_nan=False) + "\n")
                print(y, mode, flush=True)


if __name__ == "__main__":
    main()
