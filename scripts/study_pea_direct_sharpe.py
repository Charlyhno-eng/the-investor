"""Fit smooth long-only exposure policies to a transaction-cost-adjusted Sharpe."""

import json
import sqlite3
import subprocess
import tempfile
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np
import study_pea_sharpe_models as core
import study_pea_timing as base
from scipy.optimize import minimize
from scipy.special import expit

from investor.assets.momentum import months_before

OUT = Path("data/backtests/pea-direct-sharpe.json")
SPECS = list(
    product(
        ["linear", "interactions", "stress"], [0.01, 0.05, 0.2], ["pea", "dual", "bag"]
    )
)
EXEC = [(1, 0.05), (5, 0.1), (10, 0.15)]
FOLDS = [("2017-01-01", "2018-12-31"), ("2019-01-01", "2020-12-31")]


def features(p, kind):
    m = core.Models(p)
    z = m.factors
    risk = np.clip(np.log(0.16 / m.risk), -2, 2)
    concentration = m.series("down", 32) / m.series("rms", 32) ** 2
    inputs = [
        z[:, 0] / 2,
        z[:, 1] / 2,
        z[:, 2] / 2,
        z[:, 3],
        z[:, 4],
        risk,
        2 * concentration - 1,
    ]
    if kind == "interactions":
        inputs.extend(
            [z[:, 0] * z[:, 2] / 4, z[:, 0] * risk, z[:, 2] * z[:, 3] / 2, z[:, 4] ** 2]
        )
    elif kind == "stress":
        inputs.extend(
            [
                np.maximum(0, (concentration - 0.7) * 5),
                np.maximum(-z[:, 1], 0),
                np.maximum(z[:, 3], 0) * np.maximum(-z[:, 0], 0),
                np.maximum(-risk, 0),
            ]
        )
    return np.column_stack([np.ones(len(p)), *inputs])


def episode(d, p, kind, a, b):
    lo = d.searchsorted(a)
    hi = d.searchsorted(b, side="right")
    x = features(p[:hi], kind)[lo:hi]
    return x, np.expm1(np.diff(np.log(p[lo:hi])))


def objective(theta, episodes, penalty):
    # Missing exposure pre-entry is zero; a close-t decision fills at t+1.
    value = 0.0
    grad = np.zeros_like(theta)
    for x, r in episodes:
        pos = 0.05 + 0.95 * expit(x @ theta)
        jac = ((pos - 0.05) * (1 - pos) / 0.95)[:, None] * x
        held = np.r_[0, pos[:-2]]
        prev = np.vstack([np.zeros(len(theta)), jac[:-2]])
        change = pos[:-1] - held
        dc = jac[:-1] - prev
        smooth = np.sqrt(change**2 + 1e-8)
        net = held * r - 0.0012 * (smooth - 1e-4)
        dn = prev * r[:, None] - 0.0012 * (change / smooth)[:, None] * dc
        mu = net.mean()
        sd = net.std(ddof=1)
        value += np.sqrt(252) * mu / sd
        grad += np.sqrt(252) * (
            dn.mean(axis=0) / sd - mu * ((net - mu) @ dn) / ((len(net) - 1) * sd**3)
        )
    cost = -value / len(episodes) + penalty * (theta[1:] @ theta[1:])
    derivative = -grad / len(episodes)
    derivative[1:] += 2 * penalty * theta[1:]
    return cost, derivative


def fit(episodes, lam):
    init = np.zeros(episodes[0][0].shape[1])
    init[0] = 1.0
    fit = minimize(
        objective,
        init,
        args=(episodes, lam),
        jac=True,
        method="L-BFGS-B",
        bounds=[(-4, 4)] * len(init),
        options=dict(maxiter=500, ftol=1e-9, maxls=100),
    )
    if not np.isfinite(fit.fun) or not fit.success:
        raise RuntimeError(fit.message)
    return fit.x


def train(d, p, spy, q, end):
    out = {}
    for kind in ["linear", "interactions", "stress"]:
        # Split the two instruments into chronological episodes with equal
        # total weight when pooled (SPY is an explicitly labelled proxy).
        split = "2018-01-01" if end > "2019-01-01" else "2016-01-01"
        pea = [
            episode(d, p, kind, "2015-01-01", str(np.datetime64(split) - 1)),
            episode(d, p, kind, split, end),
        ]
        us = [
            episode(spy, q, kind, "1998-01-01", "2005-12-31"),
            episode(spy, q, kind, "2006-01-01", "2013-12-31"),
        ]
        for lam in (0.01, 0.05, 0.2):
            qp = fit(pea, lam)
            qu = fit(us, lam)
            out[kind, lam, "pea"] = [qp]
            out[kind, lam, "dual"] = [fit(pea + us, lam)]
            out[kind, lam, "bag"] = [qp, qu]
    return out


def evaluate(lib, d, p, weights, specs, start, end=None, fee=0.0012, delay=1):
    hi = len(d) if end is None else d.searchsorted(end, side="right")
    lo = d.searchsorted(start)
    years = (date.fromisoformat(d[hi - 1]) - date.fromisoformat(d[lo])).days / 365.25
    inputs = {}
    targets = {}
    rows = []
    for spec, step, band in specs:
        if spec not in targets:
            k = spec[0]
            if k not in inputs:
                inputs[k] = features(p[:hi], k)
            targets[spec] = np.mean(
                [0.05 + 0.95 * expit(inputs[k] @ theta) for theta in weights[spec]],
                axis=0,
            )
        row = np.zeros(7)
        core.ledger(lib)(hi, lo, step, delay, band, fee, years, p, targets[spec], row)
        rows.append(row)
    return np.array(rows)


def main():
    report = dict(
        plan="Direct Sharpe fit. Freeze one policy per feature architecture and one overall winner from only two chronological validation folds before 2021. Refit frozen specification through 2020, no future refit or audit reselection.",
        folds=FOLDS,
        history={},
        audit={},
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
        sd, q = base.read_data(conn, "yf-spy")
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
        specs = [(s, step, band) for s in SPECS for step, band in EXEC]
        e = [episode(d, p, "linear", "2015-01-01", "2016-12-31")]
        theta = np.linspace(-0.3, 0.4, e[0][0].shape[1])
        _, g = objective(theta, e, 0.05)
        for i in range(len(theta)):
            bump = np.eye(len(theta))[i] * 1e-6
            np.testing.assert_allclose(
                g[i],
                (
                    objective(theta + bump, e, 0.05)[0]
                    - objective(theta - bump, e, 0.05)[0]
                )
                / 2e-6,
                atol=1e-7,
            )
        val = []
        for a, b in FOLDS:
            weights = train(d, p, sd, q, str(np.datetime64(a) - 1))
            val.append(evaluate(lib, d, p, weights, specs, a, b)[:, 0])
        scores = np.mean(val, axis=0)
        j = int(scores.argmax())
        winners = [
            specs[
                max(
                    (i for i, s in enumerate(specs) if s[0][0] == k),
                    key=lambda i: scores[i],
                )
            ]
            for k in ("linear", "interactions", "stress")
        ]
        best = winners.index(specs[j])
        weights = train(d, p, sd, q, "2020-12-31")
        report.update(
            specs=specs,
            scores=scores.tolist(),
            frozen=winners,
            winner=best,
            coefficients=[[v.tolist() for v in weights[s]] for s, _, _ in winners],
        )
        OUT.write_text(json.dumps(report, allow_nan=False))
        print("Direct frozen", specs[j], flush=True)
        end = date.fromisoformat(d[-1])
        for label, a in [
            (str(y), months_before(end, 12 * y).isoformat()) for y in (1, 3, 5)
        ] + [("2021+", "2021-01-01")]:
            report["history"][label] = evaluate(lib, d, p, weights, winners, a).tolist()
        report["stress"] = {
            str((fee, delay)): evaluate(
                lib, d, p, weights, winners, "2021-01-01", fee=fee, delay=delay
            ).tolist()
            for fee, delay in [(0.0024, 1), (0.0012, 2), (0.0024, 2)]
        }
        report["rolling"] = {
            a: evaluate(
                lib,
                d,
                p,
                weights,
                winners,
                a,
                months_before(date.fromisoformat(a), -36).isoformat(),
            ).tolist()
            for a in [
                f"{y}-{m:02}-01" for y in (2021, 2022, 2023) for m in (1, 4, 7, 10)
            ]
        }
        for label, y, n, seed, recent in [
            ("5y", 5, 1000, 97512000, False),
            ("10y", 10, 300, 97514000, False),
            ("post2020", 5, 300, 97516000, True),
        ]:
            future = base.future_sessions(end, y)
            cal = np.r_[d[-1008:], future]
            hist = p[d.searchsorted("2021-01-01") :] if recent else p
            ret = np.diff(np.log(hist))
            paths = []
            for i in range(n):
                pp = np.r_[
                    p[-1008:],
                    p[-1]
                    * np.exp(
                        np.cumsum(base.sampled_returns(ret, len(future), seed + i))
                    ),
                ]
                refs = core.run(lib, cal, pp, core.REF, d[-1])
                policies = evaluate(lib, cal, pp, weights, winners, d[-1])
                paths.append(np.vstack([refs, policies]))
            rows = np.array(paths)
            audit = core.summary(rows)
            sr = rows[:, :, 0]
            audit["paired"] = {
                c[0]: core.paired(sr[:, 3 + best], sr[:, i])
                for i, c in enumerate(core.REF)
            }
            if not recent:
                v6 = core.v6_paths(d, p, y, n, seed)
                np.testing.assert_allclose(v6[:, 0], sr[:, 0], atol=1e-9)
                audit["v6"] = v6[:, 1].mean()
                audit["paired"]["v6"] = core.paired(sr[:, 3 + best], v6[:, 1])
            report["audit"][label] = audit
            OUT.write_text(json.dumps(report, allow_nan=False))
            print(label, flush=True)


if __name__ == "__main__":
    main()
