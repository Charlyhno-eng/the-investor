"""Explicit post-selection audit of small gains; never overrides strict studies."""

import hashlib
import json
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import study_sp500_deep_search as engine

OUT = Path("data/backtests/sp500-modest-edge.json")
INDICES = [1056, 1322, 1316, 1250]
PLAN = {
    "status": "Post-hoc question declared after training/historical results of the first study, before inspecting any reserved results. Not a success of its original protocol. Four candidates with positive training CAGR, DDloss increase<=0.5pp and historical3/5/10 CAGR within0.25pp/DD within1pp; all four retained, no winner reselection.",
    "criteria": "Separate modest objective: BOTH reserved horizons mean CAGR>v5, bootstrap95 lower paired CAGR>0, mean DDloss increase<=0.5pp and bootstrap95 upper mean DDloss increase<=0.5pp, loss95 increase<=1pp. Historical3/5/10 CAGR>=v5, DDloss increase<=0.5pp; at least18/24windows CAGR>=v5-0.5pp/DDloss increase<=1pp/vol<=1.15v5. Double fees and delay2 retain historical criteria. ALL needed, no automatic adoption.",
    "selection": "Reuse the first study selection seeds1310000..1310199, no new selection. Indices1056/1322/1316/1250 frozen before new audit seeds.",
    "audit": "1000five-year seeds1620000..1620999;300ten-year1630000..1630299. Same PSP5 generator, fees, whole shares and v5 control. Bootstrap2000paired resamples; no multiplicity correction and no new economic observations.",
}


def history_ok(h, j):
    return all(
        h[str(y)][j]["cagr"] >= h[str(y)][1]["cagr"] - 1e-12
        and h[str(y)][j]["max_drawdown"] >= h[str(y)][1]["max_drawdown"] - 0.005
        for y in [3, 5, 10]
    )


def main():
    source = json.loads(Path("data/backtests/sp500-deep-search.json").read_text())
    cs = [source["configs"][i] for i in INDICES]
    report = dict(plan=PLAN, configs=cs, source_indices=INDICES, adopted=False)

    def save():
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    save()
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
        assert report["snapshot_sha256"] == source["snapshot_sha256"]
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        p = np.array([r[1] for r in rows])
        assert np.array_equal(p, [r[2] for r in rows])
        report["source"] = source["source"]
        training = [
            [row[0], row[1], *[row[i + 2] for i in INDICES]]
            for row in source["training"]["paths"]
        ]
        report["training"] = engine.summary(training)
        report["historical"] = {
            str(y): engine.evaluate(days, p, cs, [f"{2026 - y}-11-13", days[-1]])
            for y in [1, 3, 5, 10]
        }
        report["audit"] = {}
        save()
        for years, seed, count in [(5, 1620000, 1000), (10, 1630000, 300)]:
            paths = []
            with ProcessPoolExecutor(max_workers=2) as pool:
                for i, result in enumerate(
                    pool.map(
                        engine.sampled,
                        ((days, p, cs, years, seed + i) for i in range(count)),
                    )
                ):
                    paths.append(result)
                    if i == 0:
                        prod = engine.simulate_history(
                            rows, engine.Sp500SimulationRequest(years=years, seed=seed)
                        )["comparison"]["metrics"]
                        for j, key in [(0, "benchmark"), (1, "strategy")]:
                            for k, v in result[j].items():
                                np.testing.assert_allclose(
                                    v, prod[key][k], rtol=0, atol=1e-9
                                )
                    if (i + 1) % 100 == 0:
                        print("modest", years, i + 1, "/", count, flush=True)
            a = dict(**engine.summary(paths), paths=paths)
            ids = np.random.default_rng(seed).integers(count, size=(2000, count))
            a["paired_ci95"] = {
                k: np.quantile(
                    (
                        np.array([[m[k] for m in row] for row in paths])
                        - np.array([row[1][k] for row in paths])[:, None]
                    )[ids].mean(axis=1),
                    [0.025, 0.975],
                    axis=0,
                ).T.tolist()
                for k in ["cagr", "max_drawdown"]
            }
            a["passed"] = [
                a["means"][j]["cagr"] > a["means"][1]["cagr"]
                and a["paired_ci95"]["cagr"][j][0] > 0
                and a["means"][j]["max_drawdown"]
                >= a["means"][1]["max_drawdown"] - 0.005
                and a["paired_ci95"]["max_drawdown"][j][0] >= -0.005
                and a["loss95"][j] <= a["loss95"][1] + 0.01
                for j in range(2, 6)
            ]
            report["audit"][str(years)] = a
            save()
        report["rolling"] = {
            f"{y}-{m:02}-13": engine.evaluate(
                days, p, cs, [f"{y}-{m:02}-13", f"{y + 5}-{m:02}-13"]
            )
            for y in range(2016, 2022)
            for m in [2, 5, 8, 11]
            if f"{y + 5}-{m:02}-13" <= days[-1]
        }
        report["rolling_pass"] = [
            sum(
                row[j]["cagr"] >= row[1]["cagr"] - 0.005
                and row[j]["max_drawdown"] >= row[1]["max_drawdown"] - 0.01
                and row[j]["volatility"] <= 1.15 * row[1]["volatility"]
                for row in report["rolling"].values()
            )
            for j in range(2, 6)
        ]
        report["stress"] = {
            name: {
                str(y): engine.evaluate(
                    days, p, cs, [f"{2026 - y}-11-13", days[-1]], **kw
                )
                for y in [3, 5, 10]
            }
            for name, kw in [
                ("double_fees", dict(fee=0.0024)),
                ("delay2", dict(delay=2)),
            ]
        }
        report["modest_all_pass"] = [
            all(a["passed"][j - 2] for a in report["audit"].values())
            and history_ok(report["historical"], j)
            and report["rolling_pass"][j - 2] >= 18
            and all(history_ok(h, j) for h in report["stress"].values())
            for j in range(2, 6)
        ]
        save()
        print("DONE", OUT, report["modest_all_pass"], flush=True)


if __name__ == "__main__":
    main()
