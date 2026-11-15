"""Separate historical-Sharpe selection, declared before reading its ranking.

Historical optimization is in-sample; audit never reselects a replacement.
"""

import hashlib
import json
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import study_sp500_sharpe as study

OUT = Path("data/backtests/sp500-sharpe-history.json")
PLAN = {
    "objective": "Sharpe ONLY, no CAGR/DD/Sortino/Calmar filters. Separate branch declared after first synthetic winner frozen and its historical Sharpe seen, BEFORE inspecting historical Sharpe ranking of all old configs or any reserved audit outcomes. Does not rewrite first branch selection.",
    "selection": "Rank all2409 old declared configs plus162vol rules by arithmetic mean of historical Sharpe3/5/10 years through2026-11-13. All three ratios defined required; stable first-index tie. Include exact v5 as incumbent: only a higher score can win. Overlapping/nested windows and extensively seen history: explicitly IN-SAMPLE historical optimization, not validation. Retain one winner, no reselection.",
    "audit": "Frozen historical winner on300five-year1820000..1820299 and100ten-year1830000..1830099, paired2000bootstrap95% Sharpe delta vs v5. Evidence within model requires all pairs defined and positive lower CI on BOTH horizons. Same model as first branch; new seeds not new economic evidence. Historical1/3/5/10,24quarterly5y windows, doublefees/delay2 diagnostics, no extra metric gates.",
    "execution": study.PLAN["metric"],
    "limits": study.PLAN["limits"],
}


def main():
    engine = study.engine
    engine.weights = study.weights
    report = dict(plan=PLAN, adopted=False)

    def save():
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    save()
    cs, scores, provenance = [], [], []
    for name in ["deep-search", "deep-continuation", "online-ensemble"]:
        path = Path(f"data/backtests/sp500-{name}.json")
        source = json.loads(path.read_text())
        h = source["historical_screen"]
        if not cs:
            report["incumbent_score"] = float(
                np.mean([h[str(y)][1]["sharpe"] for y in [3, 5, 10]])
            )
        for i, c in enumerate(source["configs"]):
            values = [h[str(y)][i + 2]["sharpe"] for y in [3, 5, 10]]
            cs.append(c)
            scores.append(float(np.mean(values)) if None not in values else None)
            provenance.append(dict(source=name, index=i))
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
        assert (
            report["snapshot_sha256"]
            == json.loads(Path("data/backtests/sp500-sharpe.json").read_text())[
                "snapshot_sha256"
            ]
        )
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        p = np.array([r[1] for r in rows])
        assert np.array_equal(p, [r[2] for r in rows])
        extra = study.grid()
        h = {
            str(y): engine.evaluate(days, p, extra, [f"{2026 - y}-11-13", days[-1]])
            for y in [3, 5, 10]
        }
        for i, c in enumerate(extra):
            values = [h[str(y)][i + 2]["sharpe"] for y in [3, 5, 10]]
            cs.append(c)
            scores.append(float(np.mean(values)) if None not in values else None)
            provenance.append(dict(source="new_vol_grid", index=i))
        index = max(
            (i for i, score in enumerate(scores) if score is not None),
            key=lambda i: (scores[i], -i),
        )
        report.update(
            configs=cs,
            historical_scores=scores,
            provenance=provenance,
            frozen_index=index,
            frozen_config=cs[index],
        )
        if scores[index] <= report["incumbent_score"]:
            report["frozen_config"] = dict(
                family="regression_joint", passive=0.35, regression=engine.BASE
            )
            report["incumbent_retained"] = True
        frozen = [report["frozen_config"]]
        report["historical"] = {
            str(y): engine.evaluate(days, p, frozen, [f"{2026 - y}-11-13", days[-1]])
            for y in [1, 3, 5, 10]
        }
        if not report.get("incumbent_retained"):
            np.testing.assert_allclose(
                np.mean(
                    [report["historical"][str(y)][2]["sharpe"] for y in [3, 5, 10]]
                ),
                scores[index],
                atol=1e-12,
                rtol=0,
            )
        save()
        print("HISTORICAL FROZEN", index, frozen, scores[index], flush=True)
        report["audit"] = {}
        for years, seed, count in [(5, 1820000, 300), (10, 1830000, 100)]:
            paths = []
            with ProcessPoolExecutor(max_workers=2) as pool:
                for i, row in enumerate(
                    pool.map(
                        study.sampled,
                        ((days, p, frozen, years, seed + i) for i in range(count)),
                    )
                ):
                    paths.append(row)
                    if i == 0:
                        prod = engine.simulate_history(
                            rows, engine.Sp500SimulationRequest(years=years, seed=seed)
                        )["comparison"]["metrics"]
                        for j, key in [(0, "benchmark"), (1, "strategy")]:
                            for k, v in row[j].items():
                                np.testing.assert_allclose(
                                    v, prod[key][k], atol=1e-9, rtol=0
                                )
                    if (i + 1) % 100 == 0:
                        print(
                            "Historical Sharpe audit",
                            years,
                            i + 1,
                            "/",
                            count,
                            flush=True,
                        )
            a = dict(**engine.summary(paths), paths=paths)
            delta = np.array(
                [
                    r[2]["sharpe"] - r[1]["sharpe"]
                    for r in paths
                    if r[1]["sharpe"] is not None and r[2]["sharpe"] is not None
                ]
            )
            ids = np.random.default_rng(seed).integers(
                len(delta), size=(2000, len(delta))
            )
            a["sharpe_delta"] = dict(
                valid_pairs=len(delta),
                mean=float(delta.mean()),
                median=float(np.median(delta)),
                ci95=np.quantile(delta[ids].mean(axis=1), [0.025, 0.975]).tolist(),
                wins=int(np.sum(delta > 1e-12)),
                ties=int(np.sum(abs(delta) <= 1e-12)),
                losses=int(np.sum(delta < -1e-12)),
            )
            a["sharpe_evidence"] = bool(
                len(delta) == count and a["sharpe_delta"]["ci95"][0] > 0
            )
            report["audit"][str(years)] = a
            save()
        report["rolling"] = {
            f"{y}-{m:02}-13": engine.evaluate(
                days, p, frozen, [f"{y}-{m:02}-13", f"{y + 5}-{m:02}-13"]
            )
            for y in range(2016, 2022)
            for m in [2, 5, 8, 11]
            if f"{y + 5}-{m:02}-13" <= days[-1]
        }
        report["stress"] = {
            name: {
                str(y): engine.evaluate(
                    days, p, frozen, [f"{2026 - y}-11-13", days[-1]], **kw
                )
                for y in [3, 5, 10]
            }
            for name, kw in [
                ("double_fees", dict(fee=0.0024)),
                ("delay2", dict(delay=2)),
            ]
        }
        report["modeled_sharpe_evidence"] = all(
            a["sharpe_evidence"] for a in report["audit"].values()
        )
        save()
        print("DONE HISTORICAL", report["modeled_sharpe_evidence"], flush=True)


if __name__ == "__main__":
    main()
