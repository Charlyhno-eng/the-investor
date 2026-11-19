"""Joint market-state resampling and causal macro allocation on PSP5 only."""

import json
import sqlite3
import subprocess
import tempfile
from datetime import date
from functools import cached_property
from itertools import product
from pathlib import Path

import numpy as np
import study_pea_cross_signals as external
import study_pea_sharpe_models as core
import study_pea_timing as base

from investor.assets.momentum import months_before

OUT = Path("data/backtests/pea-sharpe-macro.json")
FAMILIES = [
    "implied",
    "currency_regime",
    "macro_ridge",
    "risk_premium",
    "cross_consensus",
]
GRID = list(
    product(FAMILIES, [0, 1, 2], [0.08, 0.12, 0.16], [1, 2], [3, 10, 21], [0.05, 0.15])
)


def factors(days, conn):
    raw = external.inputs(conn, days)
    v, v3, spy, fx, long, short, age = raw.T
    f = base.Features(np.exp(spy - spy[0]))
    rv = np.sqrt(252 * f.roll(f.r**2, 21))
    x = np.column_stack(
        [
            (v / v3 - 0.95) * 8,
            np.log(np.maximum(v, 0.1) / 18),
            np.log(np.maximum(v, 0.1) / 100 / np.maximum(rv, 0.04)),
            (fx - f.lag(fx, 21)) * 35,
            (long - short) / 2,
            (long - f.lag(long, 63)) * 2,
        ]
    )
    return np.where(age[:, None] > 10, 0, np.clip(x, -3, 3))


class Macro(core.Models):
    def __init__(self, p, x):
        super().__init__(p)
        self.external = x

    @cached_property
    def factors(self):
        return np.column_stack([super().factors, self.external])

    def signal(self, family, k):
        key = (family, k)
        if key in self.memo:
            return self.memo[key]
        term, vix, premium, fx, slope, shock = self.external.T
        if family == "implied":
            # Premium above realised risk and an inverted term structure receive
            # separate loadings; high implied and falling risk can coexist.
            score = (
                np.exp(
                    np.clip(
                        0.2 * premium - [0.25, 0.5, 0.85][k] * term - 0.25 * vix, -2, 1
                    )
                )
                / self.risk
            )
        elif family == "currency_regime":
            score = (
                np.exp(
                    np.clip(
                        -[0.25, 0.5, 0.75][k] * fx + 0.15 * slope - 0.25 * shock, -2, 1
                    )
                )
                / self.risk
            )
        elif family == "macro_ridge":
            score = self.ridge(k) / self.risk
        elif family == "risk_premium":
            # Learn PSP5's conditional daily premium from previously observed
            # joint volatility, FX and interest-rate environments.
            state = (term > 0).astype(int) + 2 * (fx > 0) + 4 * (premium > 0)
            lag = self.lag(state, 2)
            span = [252, 504, 756][k]
            strength = [30, 75, 150][k]
            mu = np.zeros(len(state))
            for j in range(8):
                match = (lag == j).astype(float)
                estimate = (
                    span * core.ew(self.r * match, span) * 252 + strength * 0.08
                ) / (span * core.ew(match, span) + strength)
                mu[state == j] = estimate[state == j]
            score = np.clip(mu / 0.08, 0.1, 2) / self.risk
        elif family == "cross_consensus":
            score = np.median([self.signal(f, k) for f in FAMILIES[:-1]], axis=0)
        else:
            raise ValueError(family)
        self.memo[key] = score
        return score


def paths(days, p, x, y, n, seed, block=63, recent=False):
    future = base.future_sessions(date.fromisoformat(days[-1]), y)
    calendar = np.r_[days[-1008:], future]
    lo = days.searchsorted("2021-01-01") if recent else 0
    ret = np.diff(np.log(p[lo:]))
    for i in range(n):
        main, noise = np.random.SeedSequence(seed + i).spawn(2)
        rng = np.random.default_rng(main)
        ids = np.empty(len(future), int)
        j = len(ret)
        for t in range(len(ids)):
            if j >= len(ret) or rng.random() < 1 / block:
                j = int(rng.integers(len(ret)))
            ids[t] = j
            j += 1
        inc = ret[ids] + np.random.default_rng(noise).normal(
            0, 0.05 * ret.std(ddof=1), len(ids)
        )
        if i == 0 and block == 63:
            np.testing.assert_array_equal(
                inc, base.sampled_returns(ret, len(ids), seed)
            )
        pp = np.r_[p[-1008:], p[-1] * np.exp(np.cumsum(inc))]
        xx = np.vstack([x[-1008:], x[lo + 1 + ids]])
        yield calendar, pp, xx


def score(lib, d, p, x, rules, a, b=None, fee=0.0012, delay=1):
    hi = len(d) if b is None else d.searchsorted(b, side="right")
    return core.run(lib, d, p, rules, a, b, fee, delay, Macro(p[:hi], x[:hi]))


def main():
    first = json.loads(core.OUT.read_text())
    price_rule = tuple(first["frozen"][first["winner"]])
    report = dict(
        plan="Rank macro grid on equally weighted mean real PSP5 2015-2020 and 160 training paths from that history. Freeze highest Sharpe and one per family. Also freeze a 50/50 mix of the two winners' target weights, 5-session decisions and 10pp band. No audit reselection.",
        grid=GRID,
        history={},
        audit={},
        metrics=core.METRICS,
    )
    with (
        sqlite3.connect(
            f"file:{base.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
        ) as src,
        sqlite3.connect(":memory:") as conn,
        tempfile.TemporaryDirectory() as tmp,
    ):
        src.backup(conn)
        d, p = base.read_data(conn, "yf-psp5.pa")
        x = factors(d, conn)
        for cut in (530, 1133):
            np.testing.assert_allclose(x[:cut], factors(d[:cut], conn))
            for f, k in product(FAMILIES, range(3)):
                np.testing.assert_allclose(
                    Macro(p[:cut], x[:cut]).signal(f, k),
                    Macro(p, x).signal(f, k)[:cut],
                    atol=1e-10,
                )
        lib = str(Path(tmp) / "model.so")
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
        dates = [
            ("2015-01-01", "2016-12-31"),
            ("2017-01-01", "2018-12-31"),
            ("2019-01-01", "2020-12-31"),
        ]
        h = np.mean([score(lib, d, p, x, GRID, a, b)[:, 0] for a, b in dates], axis=0)
        cut = d.searchsorted("2021-01-01")
        sim = np.mean(
            [
                score(lib, cal, pp, xx, GRID, d[cut - 1])[:, 0]
                for cal, pp, xx in paths(d[:cut], p[:cut], x[:cut], 5, 160, 95310000)
            ],
            axis=0,
        )
        ranks = (h + sim) / 2
        best = int(ranks.argmax())
        representatives = [
            GRID[
                max(
                    (j for j, c in enumerate(GRID) if c[0] == f), key=lambda j: ranks[j]
                )
            ]
            for f in FAMILIES
        ]
        macro_rule = GRID[best]
        frozen = [*core.REF, price_rule, *representatives, ("mix", 0, 0, 0, 5, 0.1)]
        win = frozen.index(macro_rule)
        report.update(
            frozen=frozen,
            winner=win,
            training_real=h.tolist(),
            training_sim=sim.tolist(),
        )
        OUT.write_text(json.dumps(report, allow_nan=False))
        print("Macro frozen", macro_rule, flush=True)

        class Joint(Macro):
            def target(self, c):
                if c == price_rule or c[0] == "mix":
                    value = core.Models(self.p).target(price_rule)
                    return (
                        value
                        if c == price_rule
                        else 0.5 * (value + super().target(macro_rule))
                    )
                return super().target(c)

        def evaluate(cal, pp, xx, a, b=None, fee=0.0012, delay=1):
            hi = len(cal) if b is None else cal.searchsorted(b, side="right")
            return core.run(
                lib, cal, pp, frozen, a, b, fee, delay, Joint(pp[:hi], xx[:hi])
            )

        end = date.fromisoformat(d[-1])
        for y in (1, 3, 5, 10):
            report["history"][y] = evaluate(
                d, p, x, months_before(end, 12 * y).isoformat()
            ).tolist()
        report["history"]["2021+"] = evaluate(d, p, x, "2021-01-01").tolist()
        report["stress"] = {
            str((fee, delay)): evaluate(
                d, p, x, "2021-01-01", fee=fee, delay=delay
            ).tolist()
            for fee, delay in [(0.0024, 1), (0.0012, 2), (0.0024, 2)]
        }
        report["rolling"] = {
            a: evaluate(
                d, p, x, a, months_before(date.fromisoformat(a), -36).isoformat()
            ).tolist()
            for a in first["rolling"]
        }
        for label, y, n, seed, block, recent in core.AUDITS:
            rows = np.array(
                [
                    evaluate(cal, pp, xx, d[-1])
                    for cal, pp, xx in paths(d, p, x, y, n, seed, block, recent)
                ]
            )
            audit = core.summary(rows)
            sr = rows[:, :, 0]
            refs = {frozen[j][0]: sr[:, j] for j in range(4)}
            if label in ("5y", "10y"):
                v6 = core.v6_paths(d, p, y, n, seed)
                np.testing.assert_allclose(v6[:, 0], sr[:, 0], atol=1e-9)
                refs["v6"] = v6[:, 1]
                audit["v6"] = v6[:, 1].mean()
            audit["paired"] = {
                frozen[j][0]: {
                    name: core.paired(sr[:, j], v) for name, v in refs.items()
                }
                for j in (win, len(frozen) - 1)
            }
            report["audit"][label] = audit
            OUT.write_text(json.dumps(report, allow_nan=False))
            print(label, flush=True)


if __name__ == "__main__":
    main()
