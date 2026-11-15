"""Dense monthly PSP5 windows for the fixed small-gain candidate, after its audit."""

import hashlib
import json
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import study_sp500_deep_search as engine

OUT = Path("data/backtests/sp500-modest-edge-monthly.json")
PLAN = "Exploratory follow-up declared AFTER secondary success1250, before dense-window outcomes. Fixed candidate, no reselection or automatic adoption. Because the same exit had historical ESE/v4 counterexamples, inspect ALL eligible monthly3/5y starts on PSP5. New windows are overlapping, already observed history, not independent validation. Preserve the secondary24window procedure and its result, do not rewrite its rules. Exact same fees, integer budgets, next close. Full-series causal features computed once and reused only for identical data."


def one(args):
    days, p, cs, years, start, end = args
    return dict(
        years=years,
        start=start,
        end=end,
        metrics=engine.evaluate(days, p, cs, [start, end]),
    )


def main():
    parent = json.loads(Path("data/backtests/sp500-modest-edge.json").read_text())
    assert parent["modest_all_pass"] == [False, False, False, True]
    cs = [parent["configs"][3]]
    report = dict(plan=PLAN, config=cs[0], source_index=1250, adopted=False)
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    # Private backup of the read-only source; all observed prices are unchanged.
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "snapshot.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(engine.db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro",
                uri=True,
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        report["snapshot_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        assert report["snapshot_sha256"] == parent["snapshot_sha256"]
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT date,value FROM observations WHERE asset_id='yf-psp5.pa' ORDER BY date"
            ).fetchall()
        days = [r[0] for r in rows]
        p = np.array([r[1] for r in rows])
        prepare = engine.common.common.regression.previous.prepare
        features = prepare(days, p)

        def cached(d, q):
            assert d == days and np.array_equal(q, p)
            return features

        engine.common.common.regression.previous.prepare = cached
        jobs = []
        for years in [3, 5]:
            for y in range(2015, 2024):
                for m in range(1, 13):
                    start = f"{y}-{m:02}-13"
                    end = f"{y + years}-{m:02}-13"
                    if start >= "2015-12-13" and end <= days[-1]:
                        jobs.append((days, p, cs, years, start, end))
        with ProcessPoolExecutor(max_workers=2) as pool:
            report["windows"] = list(pool.map(one, jobs))
        report["counts"] = {}
        for years in [3, 5]:
            windows = [r for r in report["windows"] if r["years"] == years]
            dd = [
                r["metrics"][2]["max_drawdown"] - r["metrics"][1]["max_drawdown"]
                for r in windows
            ]
            gains = [r["metrics"][2]["cagr"] - r["metrics"][1]["cagr"] for r in windows]
            report["counts"][str(years)] = {
                "total": len(windows),
                "cagr_better": sum(d > 1e-12 for d in gains),
                "cagr_equal": sum(abs(d) <= 1e-12 for d in gains),
                "cagr_worse": sum(d < -1e-12 for d in gains),
                "dd_worse": sum(d < -1e-12 for d in dd),
                "dd_worst": windows[int(np.argmin(dd))],
                "cagr_worst": windows[int(np.argmin(gains))],
                "max_dd_aggravation": max(0, -min(dd)),
            }
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print("DONE", OUT, report["counts"], flush=True)


if __name__ == "__main__":
    main()
