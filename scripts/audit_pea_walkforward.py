"""Historical forward-only optimizer and attribution of the frozen downside rule."""

import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import audit_pea_phase as phase
import numpy as np
import study_pea_timing as base

from investor.assets.momentum import months_before


def metrics(curve, years):
    return [
        (curve[-1] / curve[0]) ** (1 / years) - 1,
        float((curve / np.maximum.accumulate(curve) - 1).min()),
    ]


def main():
    with (
        tempfile.TemporaryDirectory() as tmp,
        sqlite3.connect(
            f"file:{base.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
        ) as src,
        sqlite3.connect(":memory:") as conn,
    ):
        src.backup(conn)
        ds, p = base.read_data(conn, "yf-psp5.pa")
        lib = base.compile_ledger(tmp)
        rules = [base.PASSIVE, *base.GRID]
        features = base.Features(p)
        lo = int(np.searchsorted(ds, "2021-01-01"))
        out = {}
        for frequency in [3, 12]:
            month = ds.astype("datetime64[M]").astype(int)
            quarter = month // frequency
            anchors = np.r_[
                lo, lo + 1 + np.flatnonzero(quarter[lo + 1 :] != quarter[lo:-1]), len(p)
            ]
            actions = []
            weights = []
            choices = []
            for i, j in zip(anchors[:-1], anchors[1:], strict=True):
                now = date.fromisoformat(ds[i])
                train = months_before(now, 60).isoformat()
                mid = months_before(now, 24).isoformat()
                split = np.searchsorted(ds, mid)
                # No data from the current decision date enters selection.
                a = base.evaluate(lib, ds, p, rules, train, ds[split - 1])
                b = base.evaluate(lib, ds, p, rules, mid, ds[i - 1])
                margin = np.minimum(a[:, :2] - a[:1, :2], b[:, :2] - b[:1, :2])
                ids = np.flatnonzero((margin > 1e-10).all(1))
                selection = int(ids[np.argmax(margin[ids, 0])]) if len(ids) else 0
                c = rules[selection]
                family, w, k, step, floor = c
                sig = (
                    np.arange(i, j, step)
                    if step
                    else np.r_[
                        i, i + 1 + np.flatnonzero(month[i + 1 : j] != month[i : j - 1])
                    ]
                )
                target = np.where(features.mode(family, w, k)[sig], floor, 1)
                actions.extend(sig - lo)
                weights.extend(target)
                choices.append([ds[i], int(len(ids)), c])
            curve, fees, n = phase.ledger(
                p[lo:], np.array(actions), np.array(weights), 10000.0, 0.0012, 1
            )
            yy = (date.fromisoformat(ds[-1]) - date.fromisoformat(ds[lo])).days / 365.25
            out[str(frequency)] = dict(
                choices=choices, metrics=metrics(curve, yy), fees=fees, orders=int(n)
            )
        start = np.searchsorted(ds, "2016-11-19")
        ids = np.arange(start, len(ds), 5)
        mode = features.mode("downside", 21, 0.8)
        curve, _, _ = phase.ledger(
            p[start:], ids - start, 1 - mode[ids], 10000.0, 0.0012, 1
        )
        passive, _, _ = phase.ledger(
            p[start:], np.array([0]), np.array([1.0]), 10000.0, 0.0012, 1
        )
        delta = np.diff(np.log(curve / passive))
        yrs = ds[start + 1 :].astype("datetime64[Y]").astype(str)
        out["logrelative_by_year"] = {
            y: float(delta[yrs == y].sum()) for y in np.unique(yrs)
        }
        out["net_excluding_2020_logrelative"] = float(delta[yrs != "2020"].sum())
        out["benchmark_post2020"] = base.evaluate(
            lib, ds, p, [base.PASSIVE], "2021-01-01"
        )[0, :2].tolist()
        Path("data/backtests/pea-walkforward.json").write_text(
            json.dumps(out, indent=2) + "\n"
        )
        print({k: v["metrics"] for k, v in out.items() if k in ["3", "12"]})


if __name__ == "__main__":
    main()
