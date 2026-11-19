"""Run from repo root with PYTHONPATH=backend .venv/bin/python scripts/study_spmo_optimizer.py."""

import json
import sqlite3
from pathlib import Path

import numpy as np
import spmo_archived as spmo

from investor.db import DATA_DIR


def main():
    with (
        sqlite3.connect(f"file:{DATA_DIR}/investor.sqlite3?mode=ro", uri=True) as src,
        sqlite3.connect(":memory:") as copy,
    ):
        src.backup(copy)
        days, prices = spmo.history(copy)
    selection = spmo.simulate(days, prices, spmo.RULES, 5, 250, 191101)
    index = spmo.select(selection)
    rules = [spmo.BASE]
    if index is not None and spmo.RULES[index] != spmo.BASE:
        rules.append(spmo.RULES[index])
    report = dict(
        source_end=days[-1],
        rules=rules,
        selection=spmo.summarize(selection),
        audit={},
        historical={},
    )
    for years in (3, 5, 10):
        report["historical"][years] = spmo.historical(
            days, prices, rules, years
        ).tolist()
    for years in (5, 10):
        paths = spmo.simulate(days, prices, rules, years, 1000, 191200 + years)
        stats = spmo.summarize(paths)
        diff = paths[:, :-2] - paths[:, -2:-1]
        samples = np.random.default_rng(1313).integers(1000, size=(2000, 1000))
        report["audit"][years] = dict(
            stats=stats,
            mean_delta_ci95=np.quantile(
                diff[samples].mean(1), [0.025, 0.975], axis=0
            ).tolist(),
        )
        print(years, rules, stats, flush=True)
    candidates = [spmo.BASE, *spmo.ENSEMBLES]
    second = spmo.simulate(days, prices, candidates, 5, 400, 194000)
    # Require a positive lower confidence bound on average drawdown improvement
    # during selection, then maximize mean CAGR among eligible candidates.
    delta = second[:, :-2] - second[:, -2:-1]
    lower = delta.mean(0) - 1.96 * delta.std(0, ddof=1) / np.sqrt(len(second))
    eligible = np.flatnonzero((lower > 0).all(1))
    if len(eligible):
        challenger = candidates[eligible[np.argmax(delta.mean(0)[eligible, 0])]]
        rules = [spmo.BASE, challenger]
        report["second"] = dict(rules=rules, audit={}, historical={})
        for years in (3, 5, 10):
            report["second"]["historical"][years] = spmo.historical(
                days, prices, rules, years
            ).tolist()
        for years in (5, 10):
            paths = spmo.simulate(days, prices, rules, years, 1000, 194100 + years)
            report["second"]["audit"][years] = spmo.summarize(paths)
            print(
                "second",
                years,
                challenger,
                report["second"]["audit"][years],
                flush=True,
            )
    report["second_selection"] = spmo.summarize(second)
    Path("data/backtests/spmo-optimizer.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
