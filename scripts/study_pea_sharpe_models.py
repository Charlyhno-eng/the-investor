"""Causal allocation models, research only. Run with PYTHONPATH=backend:scripts."""

import ctypes
import hashlib
import json
import sqlite3
import subprocess
import tempfile
from datetime import date
from functools import cache, cached_property
from itertools import product
from pathlib import Path

import numpy as np
import study_pea_timing as base
from numpy.ctypeslib import ndpointer
from scipy.signal import lfilter

from investor.assets.momentum import months_before
from investor.portfolio.psp5_downside import books
from investor.portfolio.sp500_batch import PreparedBatch
from investor.portfolio.sp500_simulation import Sp500SimulationRequest, prepare_history
from investor.portfolio.validation import ValidationRequest, validation_data

OUT = Path("data/backtests/pea-sharpe-models.json")
FAMILIES = [
    "asymmetric",
    "jumps",
    "state_mean",
    "ridge",
    "serial",
    "expert_mix",
    "tail",
    "consensus",
]
GRID = list(
    product(FAMILIES, [0, 1, 2], [0.08, 0.12, 0.16], [1, 2], [1, 5, 15], [0.05, 0.15])
)
REF = [
    ("passive", 0, 0, 0, 1, -1),
    ("current", 0, 0, 0, 5, -1),
    ("previous", 0, 0, 0, 1, -1),
]
TRAIN_SEED = 94210000
AUDITS = [
    ("5y", 5, 1000, 94212000, 63, False),
    ("10y", 10, 300, 94214000, 63, False),
    ("post2020", 5, 400, 94216000, 63, True),
    ("short_blocks", 5, 300, 94218000, 21, False),
    ("long_blocks", 5, 300, 94220000, 126, False),
]
METRICS = [
    "sharpe",
    "cagr",
    "drawdown",
    "volatility",
    "fees_eur",
    "orders",
    "mean_exposure",
]


def ew(x, span):
    a = 2 / (span + 1)
    return lfilter([a], [1, a - 1], x, zi=[(1 - a) * x[0]])[0]


class Models(base.Features):
    """All features at t use prices observed through close t only."""

    @cached_property
    def risk(self):
        return np.maximum(
            0.035,
            np.sqrt(
                252
                * (
                    0.5 * ew(self.r**2, 12)
                    + 0.3 * ew(self.r**2, 42)
                    + 0.2 * ew(self.r**2, 126)
                )
            ),
        )

    @cached_property
    def factors(self):
        def z(w):
            return np.clip(
                self.series("ret", w) / (self.risk * np.sqrt(w / 252)), -3, 3
            )

        return np.column_stack(
            [
                z(3),
                z(21),
                z(126),
                np.clip(
                    np.log(self.series("rms", 10) / self.series("rms", 126)), -2, 2
                ),
                2 * self.series("down", 21) / self.series("rms", 21) ** 2 - 1,
            ]
        )

    def ridge(self, k):
        # A decision at u fills at u+1. Its five subsequent returns are
        # fully observable only at u+6. Refit every 21 closes; predict daily.
        x = self.factors
        y = np.zeros(len(x))
        y[:-6] = (self.log[6:] - self.log[1:-5]) * 252 / 5
        forecast = np.full(len(x), 0.08)
        for t in range(126, len(x), 21):
            fit = x[max(0, t - [252, 504, 756][k]) : t - 5]
            response = y[max(0, t - [252, 504, 756][k]) : t - 5]
            n = len(fit)
            beta = np.linalg.solve(
                fit.T @ fit + n * [1, 4, 12][k] * np.eye(x.shape[1]),
                fit.T @ (response - 0.08),
            )
            forecast[t : t + 21] = 0.08 + x[t : t + 21] @ beta
        return np.clip(forecast / 0.08, 0.1, 2)

    def state_mean(self, k):
        # Posterior for a discrete return regime: shrink empirical drift to
        # a fixed premium. Each label is paired with the next executable return.
        x = self.factors
        state = (x[:, 1] > 0).astype(int) + 2 * (x[:, 3] > 0) + 4 * (x[:, 0] < -0.6)
        past = self.lag(state, 2)
        span = [252, 504, 756][k]
        strength = [30, 90, 180][k]
        mu = np.full(len(x), 0.08)
        for j in range(8):
            match = (past == j).astype(float)
            mu_j = (span * ew(match * self.r, span) * 252 + strength * 0.08) / (
                span * ew(match, span) + strength
            )
            mu[state == j] = mu_j[state == j]
        return np.clip(mu / 0.08, 0.1, 2)

    def signal(self, family, k):
        key = (family, k)
        if key in self.memo:
            return self.memo[key]
        risk = self.risk
        r = self.r
        if family == "asymmetric":
            ratio = [1, 2, 4][k]
            # Different persistence of adverse shocks and favourable shocks.
            var = (
                2
                * (
                    ratio * ew(np.minimum(r, 0) ** 2, 12)
                    + ew(np.maximum(r, 0) ** 2, 63)
                )
                / (1 + ratio)
            )
            score = 1 / np.maximum(0.035, np.sqrt(252 * var))
        elif family == "jumps":
            # Bipower variation distinguishes isolated jumps from continuous risk.
            bv = np.pi / 2 * ew(abs(r) * abs(self.lag(r, 1)), 21)
            jump = np.maximum(ew(r * r, 21) - bv, 0)
            score = 1 / np.maximum(0.035, np.sqrt(252 * (bv + [1, 3, 6][k] * jump)))
        elif family == "tail":
            # Expected loss conditional on a breach of a lagged volatility barrier.
            alarm = r < -[0.75, 1.25, 1.75][k] * self.lag(risk, 1) / np.sqrt(252)
            tail = (ew(np.where(alarm, -r, 0), 63) + 0.0005) / (
                ew(alarm.astype(float), 63) + 0.05
            )
            score = 1 / np.maximum(
                0.035, 0.5 * risk + 0.5 * tail * np.sqrt(252) / [1.33, 1.73, 2.16][k]
            )
        elif family == "serial":
            # Autocorrelation determines whether to follow or fade a short move.
            corr = ew(r * self.lag(r, 1), [21, 63, 126][k]) / np.maximum(
                ew(r * r, 63), 1e-8
            )
            score = np.clip(1 + np.tanh(6 * corr) * self.factors[:, 0], 0.1, 1.9) / risk
        elif family == "ridge":
            score = self.ridge(k) / risk
        elif family == "state_mean":
            score = self.state_mean(k) / risk
        elif family == "expert_mix":
            # Advisory experts are assessed on executable lagged net returns.
            legs = np.array(
                [
                    np.ones(len(r)),
                    np.minimum(1, 0.12 / risk),
                    np.clip(0.55 + 0.35 * self.factors[:, 2], 0.1, 1),
                    np.clip(0.7 - 0.3 * self.factors[:, 0], 0.1, 1),
                    np.where(
                        self.series("down", 21) > 0.8 * self.series("rms", 21) ** 2,
                        0.1,
                        1,
                    ),
                ]
            )
            net = np.array(
                [
                    self.lag(w, 2) * np.expm1(r)
                    - 0.0012 * abs(self.lag(w, 1) - self.lag(w, 2))
                    for w in legs
                ]
            )
            span = [63, 126, 252][k]
            sr = np.array(
                [
                    ew(v, span)
                    / np.sqrt(np.maximum(ew(v * v, span), 1e-7))
                    * np.sqrt(252)
                    for v in net
                ]
            )
            alloc = np.exp(np.clip(sr - sr.max(axis=0), -12, 0))
            score = (alloc * legs).sum(axis=0) / alloc.sum(axis=0) / risk
        elif family == "consensus":
            score = np.median(
                [
                    self.signal(name, k)
                    for name in ("asymmetric", "state_mean", "ridge", "serial", "jumps")
                ],
                axis=0,
            )
        else:
            raise ValueError(family)
        self.memo[key] = score
        return score

    def target(self, rule):
        family, k, target, power, _, _ = rule
        if family == "passive":
            return np.ones(len(self.r))
        if family in ("current", "previous"):
            w = 21 if family == "current" else 32
            return (self.series("down", w) <= 0.8 * self.series("rms", w) ** 2).astype(
                float
            )
        return np.clip((target * self.signal(family, k)) ** power, 0.05, 1.0)


@cache
def ledger(lib):
    fn = ctypes.CDLL(lib).allocation
    arr = ndpointer(np.float64, flags="C_CONTIGUOUS")
    fn.argtypes = [ctypes.c_int] * 4 + [ctypes.c_double] * 3 + [arr] * 3
    fn.restype = None
    return fn


def run(lib, days, p, rules, start, end=None, fee=0.0012, delay=1, model=None):
    hi = len(days) if end is None else days.searchsorted(end, side="right")
    lo = int(days.searchsorted(start))
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    m = Models(p[:hi]) if model is None else model
    assert len(m.p) == hi
    out = np.zeros((len(rules), 7))
    targets = {}
    for j, c in enumerate(rules):
        if c[:4] not in targets:
            targets[c[:4]] = m.target(c)
        ledger(lib)(hi, lo, c[4], delay, c[5], fee, years, m.p, targets[c[:4]], out[j])
    if not np.isfinite(out).all():
        raise ArithmeticError("undefined metric")
    return out


def draws(lib, days, p, rules, y, count, seed, block=63, recent=False):
    future = base.future_sessions(date.fromisoformat(days[-1]), y)
    warm = 1008
    calendar = np.r_[days[-warm:], np.array(future)]
    history = p[days.searchsorted("2021-01-01") :] if recent else p
    ret = np.diff(np.log(history))
    rows = []
    for i in range(count):
        if block == 63:
            inc = base.sampled_returns(ret, len(future), seed + i)
        else:
            rng = np.random.default_rng(seed + i)
            chunks = []
            left = len(future)
            while left:
                j = rng.integers(len(ret))
                n = min(left, rng.geometric(1 / block), len(ret) - j)
                chunks.append(ret[j : j + n])
                left -= n
            inc = np.concatenate(chunks) + rng.normal(
                0, 0.05 * ret.std(ddof=1), len(future)
            )
        pp = np.r_[p[-warm:], p[-1] * np.exp(np.cumsum(inc))]
        rows.append(run(lib, calendar, pp, rules, days[-1]))
    return np.array(rows)


def regression_history(days, p, start, end):
    hist = dict(zip(days.tolist(), p.tolist(), strict=True))
    asset = dict(id="yf-psp5.pa", name="PSP5", category="etf", frequency="daily")
    result = validation_data(
        [asset],
        [hist],
        hist,
        ValidationRequest(
            mode="etf_switch",
            asset_ids=[asset["id"]],
            whole_shares=True,
            start_date=start,
            end_date=end,
        ),
        execution_histories=[hist, hist],
        benchmark_asset=asset,
    )
    assert result["start"] == days[days.searchsorted(start)]
    return result["metrics"]["strategy"]["sharpe"]


def v6_paths(days, p, y, count, seed):
    source = prepare_history(list(zip(days.tolist(), p, p, strict=True)), y)
    engine = PreparedBatch(source, Sp500SimulationRequest(years=y, whole_shares=True))
    return np.array(
        [
            [r["comparison"]["metrics"][s]["sharpe"] for s in ("benchmark", "strategy")]
            for offset in range(0, count, 64)
            for r in engine.simulate(
                range(seed + offset, seed + min(count, offset + 64))
            )
        ]
    )


def save(report):
    OUT.write_text(json.dumps(report, allow_nan=False))


def summary(rows):
    return dict(
        mean=rows.mean(axis=0).tolist(),
        median_sharpe=np.median(rows[:, :, 0], axis=0).tolist(),
    )


def paired(a, b):
    d = a - b
    half = 1.96 * d.std(ddof=1) / np.sqrt(len(d))
    return dict(
        delta=float(d.mean()),
        ci=[d.mean() - half, d.mean() + half],
        wins=int((d > 1e-10).sum()),
        ties=int((abs(d) <= 1e-10).sum()),
    )


def main():
    report = dict(
        metrics=METRICS,
        rules=GRID,
        plan="One decision before audits: highest equally weighted mean Sharpe across pre-2021 PSP5 simulated paths, three real PSP5 training periods and four pre-2014 SPY proxy periods. Freeze one representative per family for diagnostics. Compare the overall winner with passive, 21/5, 32/1 and production v6. No audit reselection.",
        audits={},
        history={},
    )
    with (
        sqlite3.connect(
            f"file:{base.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
        ) as src,
        sqlite3.connect(":memory:") as copy,
        tempfile.TemporaryDirectory() as tmp,
    ):
        src.backup(copy)
        days, p = base.read_data(copy, "yf-psp5.pa")
        spy, q = base.read_data(copy, "yf-spy")
        lib = str(Path(tmp) / "allocation.so")
        subprocess.run(
            [
                "cc",
                "-O3",
                "-shared",
                "-fPIC",
                str(Path(__file__).with_name("pea_sharpe_allocation.c")),
                "-lm",
                "-o",
                lib,
            ],
            check=True,
        )
        report["source"] = [
            str(days[0]),
            str(days[-1]),
            len(days),
            hashlib.sha256(p.tobytes()).hexdigest(),
        ]
        # Guard against future-dependent feature construction.
        full = Models(p)
        for cut in (502, 1111):
            prefix = Models(p[:cut])
            for family, k in product(FAMILIES, range(3)):
                np.testing.assert_allclose(
                    full.signal(family, k)[:cut], prefix.signal(family, k), atol=1e-10
                )
        psp_periods = [
            ("2015-01-01", "2016-12-31"),
            ("2017-01-01", "2018-12-31"),
            ("2019-01-01", "2020-12-31"),
        ]
        spy_periods = [
            ("1998-01-01", "2001-12-31"),
            ("2002-01-01", "2005-12-31"),
            ("2006-01-01", "2009-12-31"),
            ("2010-01-01", "2013-12-31"),
        ]
        # Scale SPY to a comparable unit price, fixed from its first observation.
        q = q / q[0] * 25
        h = np.array([run(lib, days, p, GRID, a, b)[:, 0] for a, b in psp_periods])
        proxy = np.array([run(lib, spy, q, GRID, a, b)[:, 0] for a, b in spy_periods])
        cutoff = days.searchsorted("2021-01-01")
        s = draws(lib, days[:cutoff], p[:cutoff], GRID, 5, 160, TRAIN_SEED)[
            :, :, 0
        ].mean(axis=0)
        score = (s + h.mean(axis=0) + proxy.mean(axis=0)) / 3
        best = int(np.argmax(score))
        ids = [
            max((i for i, c in enumerate(GRID) if c[0] == f), key=lambda i: score[i])
            for f in FAMILIES
        ]
        frozen = REF + [GRID[i] for i in ids]
        win = frozen.index(GRID[best])
        report.update(
            frozen=frozen,
            winner=win,
            training=dict(
                psp=h.tolist(),
                spy=proxy.tolist(),
                simulation=s.tolist(),
                score=score.tolist(),
            ),
        )
        save(report)
        print("Frozen", GRID[best], flush=True)
        end = date.fromisoformat(days[-1])
        periods = [
            (str(y), months_before(end, 12 * y).isoformat(), days[-1])
            for y in [1, 3, 5, 10]
        ] + [("2021+", "2021-01-01", days[-1])]
        for label, a, b in periods:
            rows = run(lib, days, p, frozen, a, b)
            curves, _, _ = books(p, days.searchsorted(a), 10000, 0.0012, True)
            changes = curves[1:] / curves[:-1] - 1
            np.testing.assert_allclose(
                rows[:2, 0],
                np.sqrt(252) * changes.mean(axis=0) / changes.std(axis=0, ddof=1),
                atol=1e-10,
            )
            report["history"][label] = dict(
                rows=rows.tolist(), v6=regression_history(days, p, a, b)
            )
        report["stress"] = {
            str((fee, delay)): run(
                lib, days, p, frozen, "2021-01-01", fee=fee, delay=delay
            ).tolist()
            for fee, delay in [(0.0024, 1), (0.0012, 2), (0.0024, 2)]
        }
        starts = [f"{y}-{m:02}-01" for y in range(2021, 2024) for m in (1, 4, 7, 10)]
        report["rolling"] = {
            a: run(
                lib,
                days,
                p,
                frozen,
                a,
                months_before(date.fromisoformat(a), -36).isoformat(),
            ).tolist()
            for a in starts
        }
        save(report)
        for name, y, count, seed, block, recent in AUDITS:
            rows = draws(lib, days, p, frozen, y, count, seed, block, recent)
            audit = summary(rows)
            sr = rows[:, :, 0]
            audit["paired"] = {
                c[0]: paired(sr[:, win], sr[:, j]) for j, c in enumerate(REF)
            }
            if name in ("5y", "10y"):
                v6 = v6_paths(days, p, y, count, seed)
                np.testing.assert_allclose(v6[:, 0], sr[:, 0], atol=1e-9)
                audit["v6"] = v6[:, 1].mean()
                audit["paired"]["v6"] = paired(sr[:, win], v6[:, 1])
            report["audits"][name] = audit
            save(report)
            print(name, count, audit["paired"], flush=True)


if __name__ == "__main__":
    main()
