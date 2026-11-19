"""Compare seven downside signals against the adopted PSP5 strategy."""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from itertools import product

import numpy as np
import study_pea_timing as base
from scipy.signal import lfilter

from investor.assets.momentum import months_before
from investor.portfolio.psp5_downside import books

FAMILIES = [
    "capped",
    "absolute",
    "exponential",
    "two_day",
    "breadth",
    "vol_alert",
    "trend_alert",
]
RULES = [base.PASSIVE, ("downside", 21, 0.8, 5, 0.0)]
GRID = list(
    product(FAMILIES, [15, 21, 32], [0.7, 0.75, 0.8, 0.85], [3, 5, 8], [0.0, 0.35])
)
TRAIN = [
    ("2015-01-01", "2016-12-31"),
    ("2017-01-01", "2018-12-31"),
    ("2019-01-01", "2020-12-31"),
]
SEED = 381905100


class Features(base.Features):
    def mode(self, family, w, k):
        if family not in FAMILIES:
            return super().mode(family, w, k)
        r = self.r
        if family == "two_day":
            r = self.series("ret", 2)
        elif family == "capped":
            cap = 2 * self.lag(self.series("rms", 63), 1)
            r = np.clip(r, -cap, cap)
        magnitude = abs(r) if family == "absolute" else r**2
        negative = np.where(r < 0, magnitude, 0.0)
        if family == "exponential":
            alpha = 2 / (w + 1)
            smooth = lambda x: lfilter([alpha], [1, alpha - 1], x)  # noqa: E731
            flag = smooth(negative) > k * smooth(magnitude)
        else:
            flag = self.roll(negative, w) > k * self.roll(magnitude, w)
        if family == "breadth":
            flag &= self.roll((r < 0).astype(float), w) > 0.5
        elif family == "vol_alert":
            flag |= (self.series("rms", 10) > 1.6 * self.series("rms", 126)) & (
                self.series("ret", 21) < 0
            )
        elif family == "trend_alert":
            flag |= (self.p < self.series("ma", 150)) & (self.series("ret", 42) < 0)
        return np.ascontiguousarray(flag, dtype=np.int8)


def evaluate(lib, days, prices, rules, start, end=None, **kwargs):
    hi = len(days) if end is None else days.searchsorted(end, side="right")
    return base.evaluate(
        lib, days, prices, rules, start, end, features=Features(prices[:hi]), **kwargs
    )


def main():
    with (
        sqlite3.connect(
            f"file:{base.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
        ) as src,
        sqlite3.connect(":memory:") as copy,
        tempfile.TemporaryDirectory() as tmp,
    ):
        src.backup(copy)
        days, prices = base.read_data(copy, "yf-psp5.pa")
        lib = base.compile_ledger(tmp)
        rules = RULES + GRID
        train = np.array([evaluate(lib, days, prices, rules, a, b) for a, b in TRAIN])
        gains = (train[:, :, :3] - train[:, 1:2, :3]) * [1, 1, -1]
        # Reward gains on all three metrics and penalise the weakest training period.
        score = gains.mean(axis=0).min(axis=1) + gains.mean(axis=2).min(axis=0)
        winners = [
            max((j for j, c in enumerate(rules) if c[0] == f), key=lambda j: score[j])
            for f in FAMILIES
        ]
        frozen = RULES + [rules[j] for j in winners]
        report = dict(
            rules=frozen,
            metrics=base.KEYS,
            selection=TRAIN,
            grid=len(GRID),
            seed=SEED,
            history_sha256=hashlib.sha256(
                days.tobytes() + prices.tobytes()
            ).hexdigest(),
            train=train.tolist(),
            history={},
            simulated={},
        )
        end = date.fromisoformat(days[-1])
        for label, start in [
            (str(y), months_before(end, 12 * y).isoformat()) for y in (1, 3, 5, 10)
        ] + [("2021+", "2021-01-01")]:
            rows = evaluate(lib, days, prices, frozen, start)
            report["history"][label] = rows.tolist()
            lo = days.searchsorted(start)
            curves, _, _ = books(prices, lo, 10000, 0.0012, True)
            annual = (end - date.fromisoformat(days[lo])).days / 365.25
            np.testing.assert_allclose(
                rows[:2, :3],
                np.stack(
                    [
                        (curves[-1] / 10000) ** (1 / annual) - 1,
                        (curves / np.maximum.accumulate(curves, axis=0) - 1).min(
                            axis=0
                        ),
                        np.std(curves[1:] / curves[:-1] - 1, axis=0, ddof=1)
                        * np.sqrt(252),
                    ],
                    axis=1,
                ),
                atol=1e-10,
            )
        start = days.searchsorted("2021-01-01")
        report["phase"] = [
            evaluate(lib, days, prices, frozen, days[start + i]).tolist()
            for i in range(8)
        ]
        report["stress"] = evaluate(
            lib, days, prices, frozen, days[start], fee=0.0024, delay=2
        ).tolist()
        inc = np.diff(np.log(prices))
        for years, count, seed in [(5, 1000, SEED), (10, 300, SEED + 2000)]:
            future = base.future_sessions(end, years)
            dates = np.r_[days[-505:], np.array(future)]
            sims = []
            for i in range(count):
                path = np.r_[
                    prices[-505:],
                    prices[-1]
                    * np.exp(
                        np.cumsum(base.sampled_returns(inc, len(future), seed + i))
                    ),
                ]
                sims.append(evaluate(lib, dates, path, frozen, days[-1]))
            sims = np.array(sims)
            summary = dict(
                mean=sims.mean(axis=0).tolist(),
                deep_dd=np.quantile(sims[:, :, 1], 0.05, axis=0).tolist(),
            )
            for j, ref in enumerate(["passive", "active"]):
                delta = (sims[:, :, :3] - sims[:, j : j + 1, :3]) * [1, 1, -1]
                summary[ref] = dict(
                    joint=((delta[:, :, :2] > 1e-10).all(axis=2)).sum(axis=0).tolist(),
                    triple=((delta > 1e-10).all(axis=2)).sum(axis=0).tolist(),
                    wins=(delta > 1e-10).sum(axis=0).tolist(),
                    paired_se=(delta.std(axis=0, ddof=1) / np.sqrt(count)).tolist(),
                )
            report["simulated"][years] = summary
        output = base.OUTPUT.with_name("pea-downside-refinements.json")
        output.write_text(json.dumps(report, allow_nan=False))
        print(output)


if __name__ == "__main__":
    main()
