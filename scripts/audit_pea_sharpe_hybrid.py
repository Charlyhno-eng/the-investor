"""Independent post-selection audit of one declared agreement rule."""

import json
import sqlite3
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import study_pea_sharpe_hybrid as hybrid
import study_pea_sharpe_models as core
import study_pea_timing as base
from scipy.optimize import minimize
from scipy.signal import lfilter
from scipy.special import gammaln

OUT = Path("data/backtests/pea-sharpe-agreement-audit.json")
RULES = [*hybrid.REF, ("agreement", 0.25, 32, 1, 0.05)]
PLAN = "Exploratory continuation after the 144-way screening. Freeze just the agreement representative. Require paired Sharpe gains vs 32/1 with lower 95% Monte Carlo bound above zero on both new standard horizons for a claim of modeled superiority over 32/1. No change of candidate after audit. Also measure vs current, archive and v6; additional iid and GJR Student-t generator stresses, not forecasts."
LOTS = [
    ("blocks5", 5, 1500, 98610000),
    ("blocks10", 10, 500, 98613000),
    ("iid", 5, 400, 98615000),
    ("gjr", 5, 400, 98616000),
]


def calibrate(ret):
    mu = ret.mean()
    r = ret - mu
    var = r.var(ddof=1)

    def parameters(v):
        persistence, shock, asym, df = v
        beta = persistence * (1 - shock)
        alpha = persistence * shock * (1 - asym)
        gamma = 2 * persistence * shock * asym
        return var * (1 - persistence), alpha, gamma, beta, df

    def loss(v):
        omega, a, g, b, df = parameters(v)
        sigma = lfilter(
            [1],
            [1, -b],
            np.r_[var, omega + a * r[:-1] ** 2 + g * np.minimum(r[:-1], 0) ** 2],
        )
        nll = (
            0.5 * np.log(sigma * (df - 2) * np.pi)
            + gammaln(df / 2)
            - gammaln((df + 1) / 2)
            + 0.5 * (df + 1) * np.log1p(r**2 / (sigma * (df - 2)))
        )
        return nll.mean()

    fit = minimize(
        loss,
        [0.97, 0.12, 0.5, 8],
        bounds=[(0.7, 0.999), (0.005, 0.6), (0, 1), (3, 40)],
        method="L-BFGS-B",
    )
    if not fit.success:
        raise RuntimeError(fit.message)
    omega, a, g, b, df = parameters(fit.x)
    last = lfilter(
        [1], [1, -b], np.r_[var, omega + a * r**2 + g * np.minimum(r, 0) ** 2]
    )[-1]
    return mu, omega, a, g, b, df, last


def alternative(args):
    lib, d, p, label, seeds, params = args
    sessions = base.future_sessions(date.fromisoformat(d[-1]), 5)
    days = np.r_[d, sessions]
    ret = np.diff(np.log(p))
    result = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        if label == "iid":
            inc = rng.choice(ret, len(sessions))
        else:
            mu, omega, a, g, b, df, var = params
            z = rng.standard_t(df, len(sessions)) * np.sqrt((df - 2) / df)
            inc = np.empty(len(sessions))
            for i, v in enumerate(z):
                eps = np.sqrt(var) * v
                inc[i] = mu + eps
                var = omega + a * eps**2 + g * min(eps, 0) ** 2 + b * var
        pp = np.r_[p, p[-1] * np.exp(np.cumsum(inc))]
        result.append(hybrid.evaluate(lib, days, pp, RULES, d[-1]))
    return result


def verify_ledger(lib, days, prices):
    from study_sp500_drawdown_frontier import tactical
    from study_sp500_online_ensemble import weights

    archived = weights(prices, [hybrid.ARCHIVE], days=days)[0]
    model = core.Models(prices)
    binary = model.target(core.REF[2])
    target = (0.25 * archived + 0.75 * binary) * (
        0.5 + 0.5 * np.minimum(archived, binary)
    )
    for start, fee, delay in [("2016-11-19", 0.0012, 1), ("2021-01-01", 0.0024, 2)]:
        curve, costs = tactical(
            days,
            prices,
            [dict(family="agreement", active=0, step=1, floor=0)],
            [start, days[-1]],
            fee,
            delay,
            target[None, :],
        )
        returns = np.diff(curve[:, 0]) / curve[:-1, 0]
        calculated = hybrid.evaluate(
            lib, days, prices, RULES, start, fee=fee, delay=delay
        )[-1]
        np.testing.assert_allclose(
            [calculated[0], calculated[2], calculated[4]],
            [
                np.sqrt(252) * returns.mean() / returns.std(ddof=1),
                (curve[:, 0] / np.maximum.accumulate(curve[:, 0]) - 1).min(),
                costs[0],
            ],
            atol=1e-9,
            rtol=0,
        )


def main():
    report = dict(plan=PLAN, rules=RULES, lots=LOTS, audit={}, periods={})
    OUT.write_text(json.dumps(report))
    with (
        sqlite3.connect(
            f"file:{base.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
        ) as src,
        sqlite3.connect(":memory:") as conn,
        tempfile.TemporaryDirectory() as tmp,
        ProcessPoolExecutor(max_workers=4) as pool,
    ):
        src.backup(conn)
        d, p = base.read_data(conn, "yf-psp5.pa")
        lib = str(Path(tmp) / "ledger.so")
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
        verify_ledger(lib, d, p)
        params = calibrate(np.diff(np.log(p)))
        report["gjr_parameters"] = params
        for a, b in [
            ("2020-01-02", "2020-12-31"),
            ("2022-01-03", "2022-12-30"),
            ("2023-01-02", "2024-12-31"),
        ]:
            report["periods"][a] = hybrid.evaluate(lib, d, p, RULES, a, b).tolist()
        for name, y, n, seed in LOTS:
            if name.startswith("blocks"):
                rows = hybrid.batch(pool, lib, d, p, RULES, y, n, seed)
            else:
                rows = np.concatenate(
                    list(
                        pool.map(
                            alternative,
                            [
                                (lib, d, p, name, ids, params)
                                for ids in np.array_split(np.arange(seed, seed + n), 32)
                            ],
                        )
                    )
                )
            audit = core.summary(rows)
            sr = rows[:, :, 0]
            audit["paired"] = {
                c[0]: core.paired(sr[:, -1], sr[:, i]) for i, c in enumerate(RULES[:-1])
            }
            if name.startswith("blocks"):
                v6 = core.v6_paths(d, p, y, n, seed)
                np.testing.assert_allclose(v6[:, 0], sr[:, 0], atol=1e-9)
                audit["v6"] = v6[:, 1].mean()
                audit["paired"]["v6"] = core.paired(sr[:, -1], v6[:, 1])
            report["audit"][name] = audit
            OUT.write_text(json.dumps(report, allow_nan=False))
            print(name, flush=True)


if __name__ == "__main__":
    main()
