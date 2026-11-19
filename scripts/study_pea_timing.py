"""PEA timing research. PYTHONPATH=backend .venv/bin/python scripts/study_pea_timing.py"""

import ctypes
import hashlib
import json
import sqlite3
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from functools import cache
from itertools import product
from pathlib import Path

import numpy as np
from numpy.ctypeslib import ndpointer
from scipy.ndimage import maximum_filter1d, minimum_filter1d

from investor.db import DATA_DIR
from investor.portfolio.sp500_simulation import future_sessions, sampled_returns

OUTPUT = Path("data/backtests/pea-timing.json")
PASSIVE = ("passive", 0, 0, 1, 1.0)
FAMILIES = {
    "trend": ([50, 100, 150, 200, 250], [0, 0.02]),
    "momentum": ([63, 126, 189, 252], [0, 21]),
    "reversal": ([2, 3, 5, 10], [0.5, 1, 1.5]),
    "buy_dip": ([3, 5, 10], [63, 126, 200]),
    "stretch": ([5, 10, 21], [1, 1.5, 2]),
    "variance": ([10, 21, 42], [1.2, 1.5, 2]),
    "channel": ([21, 63, 126], [0.2, 0.35, 0.5]),
    "efficiency": ([21, 63, 126], [0.1, 0.2, 0.3]),
    "downside": ([10, 21, 63], [0.6, 0.7, 0.8]),
    "shock_recovery": ([10, 21, 42], [1.5, 2, 2.5]),
    "conditional": ([63, 126, 252], [2, 5, 10]),
}
GRID = [
    (family, w, threshold, step, floor)
    for family, (windows, levels) in FAMILIES.items()
    for w, threshold, step, floor in product(
        windows, levels, [1, 5, 0], [0, 0.5, 0.8, 0.95]
    )
]
KEYS = ["cagr", "drawdown", "volatility", "fees", "orders", "exposure"]


class Features:
    def __init__(self, p):
        self.p = p
        self.log = np.log(p)
        self.r = np.diff(self.log, prepend=self.log[0])
        self.memo = {}

    def roll(self, values, w):
        prefix = np.r_[0.0, np.cumsum(values)]
        idx = np.arange(1, len(prefix))
        start = np.maximum(idx - w, 0)
        return (prefix[idx] - prefix[start]) / (idx - start)

    def lag(self, x, w):
        return x[np.maximum(np.arange(len(x)) - w, 0)]

    def series(self, name, w):
        key = name, w
        if key not in self.memo:
            if name == "ret":
                values = self.log - self.lag(self.log, w)
            elif name == "ma":
                values = self.roll(self.p, w)
            elif name == "rms":
                values = np.sqrt(np.maximum(self.roll(self.r**2, w), 1e-12))
            elif name == "down":
                values = self.roll(np.minimum(self.r, 0) ** 2, w)
            elif name == "abs":
                values = self.roll(abs(self.r), w)
            elif name == "peak":
                values = maximum_filter1d(
                    self.p, w, origin=(w - 1) // 2, mode="nearest"
                )
            elif name == "low":
                values = minimum_filter1d(
                    self.p, w, origin=(w - 1) // 2, mode="nearest"
                )
            else:
                raise ValueError(name)
            self.memo[key] = values
        return self.memo[key]

    def mode(self, family, w, k):
        s = self.series
        if family == "passive":
            return np.zeros(len(self.p), dtype=np.int8)
        if family == "trend":
            flag = self.p < s("ma", w) * (1 - k)
        elif family == "momentum":
            flag = self.lag(self.log, int(k)) < self.lag(self.log, w)
        elif family == "reversal":
            flag = s("ret", w) > k * s("rms", 63) * np.sqrt(w)
        elif family == "buy_dip":
            flag = (self.p < s("ma", int(k))) & (
                s("ret", w) > -s("rms", 63) * np.sqrt(w)
            )
        elif family == "stretch":
            flag = (self.log - np.log(s("ma", w))) > k * s("rms", 63) * np.sqrt(w / 3)
        elif family == "variance":
            flag = s("rms", w) > k * s("rms", 126)
        elif family == "channel":
            flag = self.p < s("low", w) + k * (s("peak", w) - s("low", w))
        elif family == "efficiency":
            flag = s("ret", w) < -k * w * s("abs", w)
        elif family == "downside":
            flag = s("down", w) > k * s("rms", w) ** 2
        elif family == "shock_recovery":
            flag = (s("ret", w) < -k * s("rms", 126) * np.sqrt(w)) & (
                self.p < s("ma", 5)
            )
        elif family == "conditional":
            # Two states. At t a historical feature at t-2 can be paired with
            # the return ending at t, after one close for execution.
            state = (s("ret", int(k)) < 0).astype(float)
            known = self.lag(state, 2)
            prior = 0.08 / 252
            count = self.roll(known, w) * w
            total = self.roll(known * self.r, w) * w
            estimate = np.where(
                state > 0,
                (total + 20 * prior) / (count + 20),
                (self.roll(self.r, w) * w - total + 20 * prior) / (w - count + 20),
            )
            flag = estimate < 0
        else:
            raise ValueError(family)
        return np.ascontiguousarray(flag, dtype=np.int8)


def compile_ledger(directory):
    library = Path(directory) / "ledger.so"
    subprocess.run(
        [
            "cc",
            "-O3",
            "-shared",
            "-fPIC",
            str(Path(__file__).with_name("pea_timing_ledger.c")),
            "-lm",
            "-o",
            str(library),
        ],
        check=True,
    )
    return str(library)


@cache
def load(lib):
    fn = ctypes.CDLL(lib).pea_book
    fn.restype = ctypes.c_double
    f64 = ndpointer(np.float64, flags="C_CONTIGUOUS")
    fn.argtypes = (
        [ctypes.c_int] * 3
        + [ctypes.c_double] * 2
        + [
            f64,
            ndpointer(np.int8, flags="C_CONTIGUOUS"),
            ndpointer(np.int32, flags="C_CONTIGUOUS"),
            ctypes.c_int,
            ctypes.c_double,
            f64,
        ]
    )
    return fn


def evaluate(
    lib,
    days,
    p,
    rules,
    start,
    end=None,
    fee=0.0012,
    delay=1,
    features=None,
    include_sharpe=False,
):
    end = end or days[-1]
    hi = np.searchsorted(days, end, side="right")
    p = np.ascontiguousarray(p[:hi], dtype=float)
    days = days[:hi]
    lo = int(np.searchsorted(days, start))
    elapsed = (
        date.fromisoformat(days[-1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    month = days.astype("datetime64[M]")
    monthly = np.ascontiguousarray(np.r_[True, month[1:] != month[:-1]], dtype=np.int32)
    if features is None:
        features = Features(p)
    modes = {}
    out = np.zeros((len(rules), 7 if include_sharpe else 6))
    for j, (family, w, k, step, floor) in enumerate(rules):
        key = family, w, k
        if key not in modes:
            modes[key] = features.mode(*key)
        sharpe = load(lib)(
            hi, lo, delay, fee, elapsed, p, modes[key], monthly, step, floor, out[j]
        )
        if include_sharpe:
            out[j, 6] = sharpe
    if not np.isfinite(out[:, :6]).all():
        raise ArithmeticError("Invalid book")
    return out


def read_data(conn, asset):
    rows = conn.execute(
        "SELECT date,value FROM observations WHERE asset_id=? ORDER BY date", (asset,)
    ).fetchall()
    return np.array([d for d, p in rows]), np.array([p for d, p in rows])


def sample_batch(args):
    lib, days, p, rules, years, seeds, blocks = args
    future = future_sessions(date.fromisoformat(days[-1]), years)
    dates = np.r_[days[-505:], np.array(future)]
    returns = np.diff(np.log(p))
    output = []
    for seed in seeds:
        if blocks == 63:
            increments = sampled_returns(returns, len(future), seed)
        else:
            rng = np.random.default_rng(seed)
            idx = []
            while len(idx) < len(future):
                i = rng.integers(len(returns))
                n = min(rng.geometric(1 / blocks), len(returns) - i)
                idx.extend(range(i, i + n))
            increments = returns[idx[: len(future)]] + rng.normal(
                0, 0.05 * returns.std(ddof=1), len(future)
            )
        prices = np.r_[p[-505:], p[-1] * np.exp(np.cumsum(increments))]
        output.append(evaluate(lib, dates, prices, rules, days[-1]))
    return np.array(output)


def batch(lib, days, p, rules, y, start, count, blocks=63):
    subsets = np.array_split(np.arange(start, start + count), min(30, count))
    args = [(lib, days, p, rules, y, ids, blocks) for ids in subsets]
    with ProcessPoolExecutor(max_workers=4) as pool:
        return np.concatenate(list(pool.map(sample_batch, args)))


def stats(paths):
    diff = paths[:, :, :2] - paths[:, :1, :2]
    draws = np.random.default_rng(1971).integers(len(paths), size=(1000, len(paths)))
    return {
        "mean": paths.mean(0).tolist(),
        "joint": (diff > 1e-10).all(2).sum(0).tolist(),
        "return_wins": (diff[:, :, 0] > 1e-10).sum(0).tolist(),
        "dd_wins": (diff[:, :, 1] > 1e-10).sum(0).tolist(),
        "ci95": np.quantile(diff[draws].mean(1), [0.025, 0.975], axis=0).tolist(),
        "delta_q05": np.quantile(diff, 0.05, axis=0).tolist(),
    }


def main():
    with (
        tempfile.TemporaryDirectory() as temp,
        sqlite3.connect(f"file:{DATA_DIR}/investor.sqlite3?mode=ro", uri=True) as src,
        sqlite3.connect(":memory:") as conn,
    ):
        src.backup(conn)
        days, p = read_data(conn, "yf-psp5.pa")
        raw = conn.execute(
            "select date,value from price_observations where asset_id='yf-psp5.pa' order by date"
        ).fetchall()
        assert np.array_equal(days, [r[0] for r in raw]) and np.array_equal(
            p, [r[1] for r in raw]
        )
        spy_d, spy_p = read_data(conn, "yf-spy")
        lib = compile_ledger(temp)
        cut = np.searchsorted(days, "2021-01-01")
        rules = [PASSIVE, *GRID]
        real = evaluate(lib, days[:cut], p[:cut], rules, "2016-01-01")
        training = batch(lib, days[:cut], p[:cut], rules, 5, 3700000, 160).mean(0)
        deltas = np.concatenate(
            [real[:, 0:2] - real[0, 0:2], training[:, 0:2] - training[0, 0:2]], axis=1
        )

        def score(i):
            worst = deltas[i].min()
            return (worst > 0, deltas[i, 2] if worst > 0 else worst, deltas[i, 0], -i)

        ids = [
            max((i for i, c in enumerate(rules) if c[0] == family), key=score)
            for family in FAMILIES
        ]
        best = max(ids, key=score)
        frozen = [PASSIVE, *[rules[i] for i in ids]]
        report = dict(
            source=[days[0], days[-1], len(p)],
            sha256=hashlib.sha256(p.tobytes()).hexdigest(),
            metrics=KEYS,
            grid=rules,
            train_history=real.tolist(),
            train_synthetic=training.tolist(),
            eligible=int((deltas[1:] > 0).all(1).sum()),
            frozen=frozen,
            winner=ids.index(best) + 1,
        )

        def save():
            OUTPUT.write_text(json.dumps(report, allow_nan=False) + "\n")

        save()
        print(
            "FROZEN",
            len(GRID),
            report["eligible"],
            frozen,
            report["winner"],
            flush=True,
        )
        report["real"] = {
            str(y): evaluate(lib, days, p, frozen, f"{2026 - y}-11-19").tolist()
            for y in [1, 3, 5, 10]
        }
        report["post2020"] = evaluate(lib, days, p, frozen, "2021-01-01").tolist()
        report["stress"] = {
            str((fee, delay)): evaluate(
                lib, days, p, frozen, "2021-01-01", fee=fee, delay=delay
            ).tolist()
            for fee, delay in [(0.0024, 1), (0.0012, 2), (0.0024, 2)]
        }
        report["rolling"] = {
            f"{y}-{m:02}-19": evaluate(
                lib, days, p, frozen, f"{y}-{m:02}-19", f"{y + 5}-{m:02}-19"
            ).tolist()
            for y in range(2016, 2022)
            for m in [2, 5, 8, 11]
        }
        report["spy_usd_diagnostic"] = {
            a: evaluate(lib, spy_d, spy_p / spy_p[0] * 25, frozen, a, b).tolist()
            for a, b in [
                ("2000-01-03", "2003-01-03"),
                ("2007-10-01", "2009-03-09"),
                ("1995-01-03", "2013-12-31"),
            ]
        }
        report["audit"] = {}
        for y, seed in [(5, 3710000), (10, 3720000)]:
            r = batch(lib, days, p, frozen, y, seed, 1000)
            report["audit"][str(y)] = stats(r)
            save()
            print("AUDIT", y, flush=True)
        report["blocks"] = {
            str(b): stats(
                batch(
                    lib, days, p, [PASSIVE, rules[best]], 5, 3730000 + b * 1000, 500, b
                )
            )
            for b in [21, 126]
        }
        save()


if __name__ == "__main__":
    main()
