"""Post-selection study of loss clustering, short-term reversal and re-entry timing."""

import json
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np
import study_pea_timing as base
from scipy.ndimage import maximum_filter1d

OUTPUT = Path("data/backtests/pea-reentries.json")
FAMILIES = {
    "loss_recency": ([10, 15, 21, 30, 42], [0.72, 0.76, 0.80, 0.84, 0.88]),
    "loss_persistence": ([15, 21, 30], [0.70, 0.75, 0.80, 0.85]),
    "loss_rebound": ([15, 21, 30], [0.70, 0.75, 0.80, 0.85]),
    "loss_agreement": ([15, 21, 30], [0.70, 0.75, 0.80, 0.85]),
    "dip_hold": ([2, 3, 5], [2, 5, 10]),
    "sell_rally": ([2, 3, 5], [2, 5, 10]),
    "rsi_band": ([2, 5, 10], [0.7, 0.8, 0.9]),
    "turning_trend": ([10, 21, 42], [63, 126, 252]),
}


class Reentry(base.Features):
    def mode(self, name, w, k):
        if name == "passive":
            return super().mode(name, w, k)
        if name.startswith("loss"):
            frac = self.series("down", w) / self.series("rms", w) ** 2
            if name == "loss_recency":
                flag = frac > k
            elif name == "loss_persistence":
                flag = self.roll((frac > k).astype(float), 3) >= 2 / 3
            elif name == "loss_rebound":
                flag = (frac > k) & (self.series("ret", 3) < 0)
            else:
                frac2 = self.series("down", 2 * w) / self.series("rms", 2 * w) ** 2
                flag = (frac > k) & (frac2 > 0.55)
        elif name in ["dip_hold", "sell_rally"]:
            z = self.series("ret", w) / (self.series("rms", 63) * np.sqrt(w))
            event = (z < -1.5) if name == "dip_hold" else (z > 1.5)
            held = (
                maximum_filter1d(
                    event.astype(np.int8),
                    int(k),
                    origin=(int(k) - 1) // 2,
                    mode="nearest",
                )
                > 0
            )
            flag = ~held if name == "dip_hold" else held
        elif name == "rsi_band":
            gain = self.roll(np.maximum(self.r, 0), w)
            strength = gain / np.maximum(self.series("abs", w), 1e-10)
            # Hysteresis: cut after a rally, restore after an oversold signal.
            i = np.arange(len(self.p))
            last_sell = np.maximum.accumulate(np.where(strength > k, i, -1))
            last_buy = np.maximum.accumulate(np.where(strength < 1 - k, i, -1))
            flag = last_sell > last_buy
        elif name == "turning_trend":
            # Reduce risk only if fast and slow trends both point down.
            flag = (self.series("ret", w) < 0) & (self.series("ret", int(k)) < 0)
        return np.ascontiguousarray(flag, dtype=np.int8)


GRID = [
    (f, w, k, step, floor)
    for f, (ws, ks) in FAMILIES.items()
    for w, k, step, floor in product(ws, ks, [1, 3, 5, 10], [0, 0.35, 0.70, 0.90])
]
ORIGINAL = ("loss_recency", 21, 0.8, 5, 0.0)


def run(lib, ds, p, cs, start, end=None, fee=0.0012, delay=1):
    n = len(ds) if end is None else np.searchsorted(ds, end, side="right")
    return base.evaluate(lib, ds, p, cs, start, end, fee, delay, Reentry(p[:n]))


def sample(args):
    lib, ds, p, cs, years, ids = args
    dates = base.future_sessions(date.fromisoformat(ds[-1]), years)
    days = np.r_[ds[-505:], np.array(dates)]
    rets = np.diff(np.log(p))
    rows = []
    for seed in ids:
        new = p[-1] * np.exp(np.cumsum(base.sampled_returns(rets, len(dates), seed)))
        pp = np.r_[p[-505:], new]
        rows.append(run(lib, days, pp, cs, ds[-1]))
    return np.array(rows)


def batch(lib, ds, p, cs, y, seed):
    args = [
        (lib, ds, p, cs, y, ids)
        for ids in np.array_split(np.arange(seed, seed + 1000), 32)
    ]
    with ProcessPoolExecutor(max_workers=4) as pool:
        return np.concatenate(list(pool.map(sample, args)))


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
        s, q = base.read_data(conn, "yf-spy")
        q = q / q[0] * 25
        lib = base.compile_ledger(tmp)
        grid = [base.PASSIVE, *GRID]
        train = np.array(
            [
                run(lib, s, q, grid, "1998-01-02", "2005-12-30"),
                run(lib, s, q, grid, "2006-01-03", "2013-12-31"),
                run(lib, d, p, grid, "2016-01-04", "2020-12-31"),
            ]
        )
        delta = train[:, :, :2] - train[:, :1, :2]

        def rank(j):
            m = delta[:, j, :].min()
            return (
                m > 1e-10,
                delta[:, j, 0].mean() if m > 1e-10 else m,
                delta[:, j, 0].mean(),
                -j,
            )

        ids = [
            max((i for i, c in enumerate(grid) if c[0] == name), key=rank)
            for name in FAMILIES
        ]
        best = max(ids, key=rank)
        cs = [base.PASSIVE, ORIGINAL, *[grid[i] for i in ids]]
        report = dict(
            frozen=cs,
            winner=ids.index(best) + 2,
            grid=grid,
            train_delta=delta.tolist(),
            eligible=int((delta[:, 1:] > 1e-10).all((0, 2)).sum()),
        )
        report["post2020"] = run(lib, d, p, cs, "2021-01-01").tolist()
        report["real"] = {
            str(y): run(lib, d, p, cs, f"{2026 - y}-11-19").tolist()
            for y in [1, 3, 5, 10]
        }
        report["stress"] = run(
            lib, d, p, cs, "2021-01-01", fee=0.0024, delay=2
        ).tolist()
        report["rolling"] = {
            f"{y}-{m:02}-19": run(
                lib, d, p, cs, f"{y}-{m:02}-19", f"{y + 5}-{m:02}-19"
            ).tolist()
            for y in range(2016, 2022)
            for m in [2, 5, 8, 11]
        }
        report["start_offsets"] = {
            str(y): [
                run(
                    lib, d, p, cs, d[np.searchsorted(d, f"{2026 - y}-11-19") + offset]
                ).tolist()
                for offset in range(5)
            ]
            for y in [3, 5, 10]
        }
        print("FROZEN", len(GRID), report["eligible"], cs, report["winner"], flush=True)
        report["audit"] = {}
        for y, seed in [(5, 3910000), (10, 3920000)]:
            report["audit"][str(y)] = base.stats(batch(lib, d, p, cs, y, seed))
            OUTPUT.write_text(json.dumps(report, allow_nan=False) + "\n")
            print("AUDIT", y, flush=True)


if __name__ == "__main__":
    main()
