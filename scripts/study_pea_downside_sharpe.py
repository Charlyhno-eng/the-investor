"""Maximise mean net Sharpe, with chronological data separation."""

import json
import sqlite3
import tempfile
from datetime import date
from itertools import product

import numpy as np
import study_pea_downside_refinements as prior
import study_pea_timing as base

from investor.assets.momentum import months_before
from investor.portfolio.psp5_downside import books

SEEDS = (81302000, 81303000, 81305000)


def scenarios(lib, days, prices, rules, years, count, seed):
    sessions = base.future_sessions(date.fromisoformat(days[-1]), years)
    dates = np.r_[days[-505:], np.array(sessions)]
    returns = np.diff(np.log(prices))
    for i in range(count):
        increments = base.sampled_returns(returns, len(sessions), seed + i)
        path = np.r_[prices[-505:], prices[-1] * np.exp(np.cumsum(increments))]
        yield prior.evaluate(lib, dates, path, rules, days[-1], include_sharpe=True)


def main():
    rules = list(
        dict.fromkeys(
            [
                *prior.RULES,
                *prior.GRID,
                *base.GRID,
                *product(
                    ["downside"],
                    [10, 15, 21, 32, 42, 63],
                    [0.55, 0.65, 0.75, 0.8, 0.85, 0.9],
                    [1, 3, 5, 8, 15],
                    [0.0, 0.15, 0.35, 0.65],
                ),
            ]
        )
    )
    with (
        sqlite3.connect(
            f"file:{base.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
        ) as src,
        sqlite3.connect(":memory:") as conn,
        tempfile.TemporaryDirectory() as tmp,
    ):
        src.backup(conn)
        days, prices = base.read_data(conn, "yf-psp5.pa")
        cutoff = days.searchsorted("2021-01-01")
        lib = base.compile_ledger(tmp)
        sims = np.array(
            [
                row[:, -1]
                for row in scenarios(
                    lib, days[:cutoff], prices[:cutoff], rules, 5, 120, SEEDS[0]
                )
            ]
        )
        real = np.array(
            [
                prior.evaluate(lib, days, prices, rules, a, b, include_sharpe=True)[
                    :, -1
                ]
                for a, b in prior.TRAIN
            ]
        )
        scores = [sims.mean(axis=0), real.mean(axis=0)]
        selected = [int(np.nanargmax(s)) for s in scores]
        frozen = prior.RULES + [rules[i] for i in selected]
        report = dict(
            rules=frozen,
            selection_winners=[
                float(s[i]) for s, i in zip(scores, selected, strict=True)
            ],
            grid=rules,
            seeds=SEEDS,
            history={},
            reserved={},
            scores=[[float(x) if np.isfinite(x) else None for x in s] for s in scores],
        )
        end = date.fromisoformat(days[-1])
        for label, start, fee, delay in [
            (str(y), months_before(end, y * 12).isoformat(), 0.0012, 1)
            for y in (1, 3, 5, 10)
        ] + [("2021+", "2021-01-01", 0.0012, 1), ("stress", "2021-01-01", 0.0024, 2)]:
            row = prior.evaluate(
                lib,
                days,
                prices,
                frozen,
                start,
                fee=fee,
                delay=delay,
                include_sharpe=True,
            )
            report["history"][label] = row.tolist()
            if delay == 1:
                curves, _, _ = books(prices, days.searchsorted(start), 10000, fee, True)
                changes = curves[1:] / curves[:-1] - 1
                np.testing.assert_allclose(
                    row[:2, -1],
                    changes.mean(axis=0) / changes.std(axis=0, ddof=1) * np.sqrt(252),
                    atol=1e-10,
                )
        for years, count, seed in [(5, 1000, SEEDS[1]), (10, 300, SEEDS[2])]:
            paths = np.array(
                list(scenarios(lib, days, prices, frozen, years, count, seed))
            )
            sh = paths[:, :, -1]
            delta = sh - sh[:, 1:2]
            report["reserved"][years] = dict(
                mean=paths.mean(axis=0).tolist(),
                wins=(delta > 1e-10).sum(axis=0).tolist(),
                ties=(abs(delta) <= 1e-10).sum(axis=0).tolist(),
                se=(delta.std(axis=0, ddof=1) / np.sqrt(count)).tolist(),
            )
        output = base.OUTPUT.with_name("pea-downside-sharpe.json")
        output.write_text(json.dumps(report, allow_nan=False))
        print(frozen, len(rules), report["selection_winners"])
        for name, rows in report["history"].items():
            print(name, np.round(np.array(rows)[:, -1], 4))
        for name, res in report["reserved"].items():
            print(name, np.round(res["mean"], 4), res["wins"], res["se"])


if __name__ == "__main__":
    main()
