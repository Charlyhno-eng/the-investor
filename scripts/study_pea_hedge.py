"""Distinct PEA share-class rotation study using actual PSP5 and PSPH closes."""

import json
import sqlite3
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, date, datetime
from itertools import product
from pathlib import Path

import numpy as np
import study_pea_timing as base

OUT = Path("data/backtests/pea-hedge.json")
GRID = [
    (f, w, k, step)
    for f, w, k, step in product(
        ["relative_momentum", "fx_reversal", "dual_horizon", "trend_with_cash"],
        [21, 63, 126, 189],
        [0, 0.01, 0.025],
        [5, 0],
    )
]
CONTROLS = [("psp5", 0, 0, 0), ("psph", 0, 0, 0)]


def dataset(conn):
    r = json.loads(Path("data/backtests/pea-inputs/PSPH.PA.json").read_text())["chart"][
        "result"
    ][0]
    assert r["meta"]["symbol"] == "PSPH.PA" and r["meta"]["currency"] == "EUR"
    q = np.array(r["indicators"]["quote"][0]["close"])
    assert np.array_equal(q, r["indicators"]["adjclose"][0]["adjclose"])
    days = np.array(
        [datetime.fromtimestamp(t, UTC).date().isoformat() for t in r["timestamp"]]
    )
    d, p = base.read_data(conn, "yf-psp5.pa")
    dates, i, j = np.intersect1d(d, days, return_indices=True)
    return dates, np.column_stack((p[i], q[j]))


def evaluate(d, p, cs, start, end=None, fee=0.0012, delay=1):
    if end:
        hi = np.searchsorted(d, end, side="right")
        d, p = d[:hi], p[:hi]
    lo = np.searchsorted(d, start)
    years = (date.fromisoformat(d[-1]) - date.fromisoformat(d[lo])).days / 365.25
    f = base.Features(p[:, 1] / p[:, 0])
    equity = base.Features(p[:, 0])
    month = d.astype("datetime64[M]")
    first = np.r_[lo, np.flatnonzero(month[lo + 1 :] != month[lo:-1]) + lo + 1]
    result = []
    for name, w, k, step in cs:
        dates = first if step == 0 else np.arange(lo, len(p), step)
        dates = dates[dates + delay < len(p)]
        ret = f.series("ret", w)[dates] if w else np.zeros(len(dates))
        if name == "relative_momentum":
            asset = ret > k
        elif name == "fx_reversal":
            asset = ret < -k
        elif name == "dual_horizon":
            asset = (ret > k) & (f.series("ret", 10)[dates] > 0)
        elif name == "trend_with_cash":
            asset = ret > k
        else:
            asset = np.full(len(dates), name == "psph")
        asset = asset.astype(int)
        if name == "trend_with_cash":
            asset[
                (equity.series("ret", 126)[dates] < 0)
                & (p[dates, 1] < base.Features(p[:, 1]).series("ma", 126)[dates])
            ] = 2
        change = np.r_[True, asset[1:] != asset[:-1]]
        cash = 10000.0
        prev = 2
        units = 0
        nav = np.full(len(p) - lo, 10000.0)
        times = dates[change] + delay
        for i, at in enumerate(times):
            hold = asset[change][i]
            if prev != 2:
                cash += units * p[at, prev] * (1 - fee)
            if hold != 2:
                units = np.floor(cash / (p[at, hold] * (1 + fee)) + 1e-10)
                cash -= units * p[at, hold] * (1 + fee)
            else:
                units = 0
            stop = times[i + 1] if i + 1 < len(times) else len(p)
            nav[at - lo : stop - lo] = (
                cash if hold == 2 else cash + units * p[at:stop, hold]
            )
            prev = hold
        result.append(
            [
                (nav[-1] / 10000) ** (1 / years) - 1,
                (nav / np.maximum.accumulate(nav) - 1).min(),
            ]
        )
    return np.array(result)


def sample(args):
    d, p, cs, y, seeds = args
    returns = np.diff(np.log(p), axis=0)
    fut = base.future_sessions(date.fromisoformat(d[-1]), y)
    dates = np.r_[d[-252:], np.array(fut)]
    data = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        idx = []
        while len(idx) < len(fut):
            i = rng.integers(len(returns))
            n = min(rng.geometric(1 / 63), len(returns) - i)
            idx.extend(range(i, i + n))
        pp = np.vstack(
            (p[-252:], p[-1] * np.exp(np.cumsum(returns[idx[: len(fut)]], axis=0)))
        )
        data.append(evaluate(dates, pp, cs, d[-1]))
    return np.array(data)


def main():
    with (
        sqlite3.connect(
            f"file:{base.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
        ) as src,
        sqlite3.connect(":memory:") as conn,
    ):
        src.backup(conn)
        d, p = dataset(conn)
    grid = [*CONTROLS, *GRID]
    train = np.array(
        [
            evaluate(d, p, grid, "2019-11-19", "2020-12-31"),
            evaluate(d, p, grid, "2021-01-01", "2021-12-31"),
        ]
    )
    delta = train[:, :, 0:2] - train[:, :1, 0:2]

    def score(i):
        m = delta[:, i].min()
        return (
            m > 1e-10,
            delta[:, i, 0].mean() if m > 1e-10 else m,
            delta[:, i, 0].mean(),
            -i,
        )

    ids = [
        max((i for i, c in enumerate(grid) if c[0] == family), key=score)
        for family in dict.fromkeys(c[0] for c in GRID)
    ]
    cs = [*CONTROLS, *[grid[i] for i in ids]]
    report = dict(
        dates=[d[0], d[-1], len(d)],
        grid=grid,
        training=train.tolist(),
        eligible=int((delta[:, 2:] > 1e-10).all((0, 2)).sum()),
        frozen=cs,
        winner=ids.index(max(ids, key=score)) + 2,
    )
    report["post2021"] = evaluate(d, p, cs, "2022-01-01").tolist()
    report["real"] = {
        str(y): evaluate(d, p, cs, f"{2026 - y}-11-19").tolist() for y in [1, 3, 5]
    }
    report["stress"] = evaluate(d, p, cs, "2022-01-01", fee=0.0024, delay=2).tolist()
    report["audit"] = {}
    for y, seed in [(5, 4210000), (10, 4220000)]:
        args = [
            (d, p, cs, y, ss) for ss in np.array_split(np.arange(seed, seed + 1000), 32)
        ]
        with ProcessPoolExecutor(max_workers=4) as pool:
            paths = np.concatenate(list(pool.map(sample, args)))
        report["audit"][str(y)] = base.stats(paths)
        OUT.write_text(json.dumps(report, allow_nan=False) + "\n")
        print("AUDIT", y, flush=True)


if __name__ == "__main__":
    main()
