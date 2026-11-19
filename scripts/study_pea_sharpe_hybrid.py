"""Paired audit of combinations with the previously frozen five-expert policy."""

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
import study_pea_sharpe_models as core
import study_pea_timing as base
import study_sp500_online_ensemble as online

from investor.assets.momentum import months_before

OUT = Path("data/backtests/pea-sharpe-hybrid.json")
ARCHIVE = dict(
    family="online_ensemble",
    window=252,
    eta=2,
    aversion=3,
    dd_penalty=0,
    floor=0.1,
    active=0,
    step=5,
)
FAMS = ["average", "agreement", "veto", "adaptive"]
GRID = list(product(FAMS, [0.25, 0.5, 0.75], [21, 32], [1, 5, 10], [0.05, 0.15]))
REF = [*core.REF, ("archive", 1.0, 0, 5, 0.05)]
METRICS = core.METRICS


@cache
def calendar(days):
    dates = [date.fromisoformat(s) for s in days]
    x = np.array([(d - dates[0]).days / 365.25 for d in dates])
    lower = []
    for w in (60, 18):
        cutoff = np.array([months_before(d, w).isoformat() for d in dates])
        lower.append((np.asarray(days).searchsorted(cutoff), cutoff >= days[0]))
    return x, lower


def window_sum(v, lo):
    prefix = np.r_[0.0, v.cumsum()]
    return prefix[1:] - prefix[lo]


def scores(days, p):
    x, windows = calendar(tuple(days))
    y = np.log(p / p[0])
    result = []
    for lo, valid in windows:
        n = np.arange(1, len(p) + 1) - lo
        sx = window_sum(x, lo)
        sy = window_sum(y, lo)
        vx = window_sum(x * x, lo) - sx * sx / n
        xy = window_sum(x * y, lo) - sx * sy / n
        slope = xy / np.maximum(vx, 1e-14)
        ss = window_sum(y * y, lo) - sy * sy / n - slope * xy
        sd = np.sqrt(np.maximum(0, ss) / np.maximum(1, n - 2))
        z = (y - sy / n - slope * (x - sx / n)) / np.maximum(sd, 1e-14)
        result.append(np.where(valid & (n >= 41) & (sd > 1e-10), z, np.nan))
    return result


def evaluate(lib, days, p, rules, start, end=None, fee=0.0012, delay=1, verify=False):
    hi = len(days) if end is None else days.searchsorted(end, side="right")
    days = days[:hi]
    p = p[:hi]
    start_i = days.searchsorted(start)
    elapsed = (
        date.fromisoformat(days[-1]) - date.fromisoformat(days[start_i])
    ).days / 365.25
    model = core.Models(p)
    archived = online.weights(
        p, [ARCHIVE], days=days, regression_scores=scores(days, p)
    )[0]
    if verify:
        np.testing.assert_allclose(
            archived, online.weights(p, [ARCHIVE], days=days)[0], atol=1e-10
        )
    targets = {}
    result = []
    for c in rules:
        family = c[0]
        if family in ("passive", "current", "previous"):
            t = model.target(c)
            step, band = c[-2:]
        else:
            _, a, w, step, band = c
            key = family, a, w
            if key not in targets:
                if family == "archive":
                    t = archived
                else:
                    binary = (
                        model.series("down", w) <= 0.8 * model.series("rms", w) ** 2
                    ).astype(float)
                    if family == "average":
                        t = a * archived + (1 - a) * binary
                    elif family == "agreement":
                        t = (a * archived + (1 - a) * binary) * (
                            0.5 + 0.5 * np.minimum(archived, binary)
                        )
                    elif family == "veto":
                        t = archived * (a + (1 - a) * binary)
                    elif family == "adaptive":

                        def sr(target):
                            net = model.lag(target, 2) * np.expm1(
                                model.r
                            ) - 0.0012 * abs(
                                model.lag(target, 1) - model.lag(target, 2)
                            )
                            return (
                                core.ew(net, 126)
                                / np.sqrt(np.maximum(core.ew(net**2, 126), 1e-8))
                                * np.sqrt(252)
                            )

                        weight = 1 / (
                            1
                            + np.exp(
                                -np.clip(
                                    np.log(a / (1 - a)) + sr(archived) - sr(binary),
                                    -20,
                                    20,
                                )
                            )
                        )
                        t = weight * archived + (1 - weight) * binary
                targets[key] = t
            t = targets[key]
        row = np.zeros(7)
        core.ledger(lib)(hi, start_i, step, delay, band, fee, elapsed, p, t, row)
        result.append(row)
    rows = np.array(result)
    assert np.isfinite(rows).all()
    return rows


def chunk(args):
    lib, days, p, rules, y, seeds, recent = args
    future = base.future_sessions(date.fromisoformat(days[-1]), y)
    cal = np.r_[days, future]
    history = p[days.searchsorted("2021-01-01") :] if recent else p
    ret = np.diff(np.log(history))
    result = []
    for seed in seeds:
        inc = base.sampled_returns(ret, len(future), seed)
        pp = np.r_[p, p[-1] * np.exp(np.cumsum(inc))]
        result.append(evaluate(lib, cal, pp, rules, days[-1]))
    return result


def batch(pool, lib, d, p, rules, y, n, seed, recent=False):
    return np.concatenate(
        list(
            pool.map(
                chunk,
                [
                    (lib, d, p, rules, y, ids, recent)
                    for ids in np.array_split(np.arange(seed, seed + n), min(32, n))
                ],
            )
        )
    )


def main():
    report = dict(
        plan="Additional branch after the price-only screening. 144 family configurations, frozen archive and three controls. Select maximum of equally weighted pre-2021 PSP5 historical and simulated mean Sharpe. Audit winner once using separate seed ranges, report all controls; no switching winners.",
        grid=GRID,
        history={},
        audit={},
    )
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
        rules = REF + GRID
        periods = [
            ("2015-01-01", "2016-12-31"),
            ("2017-01-01", "2018-12-31"),
            ("2019-01-01", "2020-12-31"),
        ]
        h = np.mean(
            [evaluate(lib, d, p, rules, a, b, verify=True)[:, 0] for a, b in periods],
            axis=0,
        )
        cut = d.searchsorted("2021-01-01")
        s = batch(pool, lib, d[:cut], p[:cut], rules, 5, 160, 96410000)[:, :, 0].mean(
            axis=0
        )
        ranks = (h + s) / 2
        win = int(ranks.argmax())
        reps = [
            rules[
                max(
                    (i for i, c in enumerate(rules) if c[0] == f),
                    key=lambda i: ranks[i],
                )
            ]
            for f in FAMS
        ]
        frozen = REF + reps
        j = frozen.index(rules[win])
        report.update(frozen=frozen, winner=j, scores=ranks.tolist(), rules=rules)
        OUT.write_text(json.dumps(report, allow_nan=False))
        print("Hybrid frozen", frozen[j], flush=True)
        end = date.fromisoformat(d[-1])
        for label, a in [
            (str(y), months_before(end, 12 * y).isoformat()) for y in (1, 3, 5, 10)
        ] + [("2021+", "2021-01-01")]:
            report["history"][label] = evaluate(
                lib, d, p, frozen, a, verify=True
            ).tolist()
        report["stress"] = {
            str((fee, delay)): evaluate(
                lib, d, p, frozen, "2021-01-01", fee=fee, delay=delay
            ).tolist()
            for fee, delay in [(0.0024, 1), (0.0012, 2), (0.0024, 2)]
        }
        report["rolling"] = {
            a: evaluate(
                lib,
                d,
                p,
                frozen,
                a,
                months_before(date.fromisoformat(a), -36).isoformat(),
            ).tolist()
            for a in [
                f"{y}-{m:02}-01" for y in (2021, 2022, 2023) for m in (1, 4, 7, 10)
            ]
        }
        for label, y, n, seed, recent in [
            ("5y", 5, 1000, 96412000, False),
            ("10y", 10, 300, 96414000, False),
            ("post2020", 5, 300, 96416000, True),
        ]:
            rows = batch(pool, lib, d, p, frozen, y, n, seed, recent)
            audit = core.summary(rows)
            sr = rows[:, :, 0]
            audit["paired"] = {
                c[0]: core.paired(sr[:, j], sr[:, i]) for i, c in enumerate(REF)
            }
            if not recent:
                v6 = core.v6_paths(d, p, y, n, seed)
                np.testing.assert_allclose(sr[:, 0], v6[:, 0], atol=1e-9)
                audit["v6"] = v6[:, 1].mean()
                audit["paired"]["v6"] = core.paired(sr[:, j], v6[:, 1])
            report["audit"][label] = audit
            OUT.write_text(json.dumps(report, allow_nan=False))
            print(label, n, flush=True)


if __name__ == "__main__":
    main()
