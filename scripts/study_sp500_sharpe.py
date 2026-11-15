"""Sharpe-only research, separate from all previous return/drawdown gates.

PYTHONPATH=backend:scripts .venv/bin/python scripts/study_sp500_sharpe.py
"""

import hashlib
import json
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from pathlib import Path

import numpy as np
import study_sp500_deep_search as engine
import study_sp500_online_ensemble as online

OUT = Path("data/backtests/sp500-sharpe.json")
ORIGINAL_WEIGHTS = engine.weights
PLAN = {
    "objective": "User explicitly replaces all return/drawdown objectives with maximization of Sharpe alone. No CAGR floor, DD ceiling, Sortino or Calmar gate. PSP5 EUR/cash, no shorts, leverage or derivatives. Research only, no automatic production replacement.",
    "metric": "Existing application Sharpe: sqrt(252)*mean(simple daily net returns)/sample standard deviation. Risk-free rate0 and cash yield0, not an estimate of historical EUR excess-return Sharpe. Whole shares,10000EUR,fee0.0012 each actual order,next-close execution,independent real-budget sleeves,no terminal liquidation. Constant cash dilution does not mechanically improve ideal frictionless zero-rate Sharpe; undefined zero-variance ratios are not ranked.",
    "preselection": "Explicit reuse of previously inspected training ONLY: all2409 declared configurations in deep-search/deep-continuation/online-ensemble. Retain one highest mean Sharpe per source/family, with100% valid Sharpe paths; ties lower original index. No historical CAGR/DD or previous qualification gates. This is post-hoc reuse, not a new2409-config experiment or untouched economic holdout.",
    "new_grid": "162 volatility/variance-sizing rules: window21/63/126,target8/12/16%annual,floor0/25/50%,power1/2,independent v4 budget0/35/65%. Target exposure clipped(floor,1) of(target/causal-vol)^power. Warmupfixed16%annual,no futurefill,5session decisions,5pp band. Previously rejected risk sizing reconsidered explicitly for different sole Sharpe objective against v5.",
    "selection": "All preselected plus162 new configs on SAME200 five-year draws1710000..1710199. Rank ONLY descending mean Sharpe, all200 must be defined. Stable lowest-index tie. Freeze ONE overall winner before reserved draws, no fallback/reselection. No historical performance filters.",
    "audit": "Frozen winner ONLY on1000five-year draws1720000..1720999 and300ten-year1730000..1730299. Paired2000-resample bootstrap95% interval of Sharpe delta vs v5; report mean,median,wins,ties,losses and valid counts. Evidence of modeled Sharpe improvement requires100% defined pairs and lower CI>0 in BOTH horizons. No other financial metric gate. Also report historical1/3/5/10,24quarterly5y windows,fees doubled and delay2, without reselection or additional acceptance gates.",
    "limits": "All economic history already inspected. Reserved seeds are new draws of same model, not independent future evidence; selection, multiplicity and bootstrap-model bias remain. Cash0/rf0 assumption material for pure Sharpe objective. Do not equate CAGR/volatility with Sharpe. Generator,production,UI and user database unchanged. No global optimum or future superiority claim.",
    "source": "https://www.nber.org/papers/w22208; volatility/variance-sizing inspiration only, bounded unlevered adaptation, not paper replication.",
}


def grid():
    return [
        dict(
            family="sharpe_vol", window=w, target=t, floor=f, power=p, active=a, step=5
        )
        for w, t, f, p, a in product(
            [21, 63, 126], [0.08, 0.12, 0.16], [0, 0.25, 0.5], [1, 2], [0, 0.35, 0.65]
        )
    ]


def weights(p, cs, days=None):
    result = np.empty((len(cs), len(p)))
    risk = None
    for family in {c["family"] for c in cs}:
        ids = [i for i, c in enumerate(cs) if c["family"] == family]
        subset = [cs[i] for i in ids]
        if family == "sharpe_vol":
            if risk is None:
                risk = engine.common.features(p)[0]
            for i in ids:
                c = cs[i]
                vol = np.nan_to_num(risk[c["window"]], nan=0.16)
                result[i] = np.clip(
                    (c["target"] / np.maximum(vol, 1e-8)) ** c["power"],
                    c["floor"],
                    1,
                )
        elif family == "online_ensemble":
            result[ids] = online.weights(p, subset, days=days)
        else:
            result[ids] = ORIGINAL_WEIGHTS(p, subset, days=days)
    return result


def winner(s):
    valid = [
        j
        for j in range(2, len(s["means"]))
        if s["valid_counts"][j]["sharpe"] == s["count"]
    ]
    if not valid:
        raise ValueError("No candidate has all Sharpe ratios defined")
    return max(valid, key=lambda j: (s["means"][j]["sharpe"], -j)) - 2


def preselection():
    configs, provenance, fingerprints = [], [], {}
    for name in ["deep-search", "deep-continuation", "online-ensemble"]:
        path = Path(f"data/backtests/sp500-{name}.json")
        raw = path.read_bytes()
        source = json.loads(raw)
        fingerprints[name] = hashlib.sha256(raw).hexdigest()
        grouped = {}
        for i, c in enumerate(source["configs"]):
            s = source["training"]
            if s["valid_counts"][i + 2]["sharpe"] != s["count"]:
                continue
            score = s["means"][i + 2]["sharpe"]
            family = c["family"]
            if family not in grouped or score > grouped[family][0]:
                grouped[family] = score, i
        for family, (score, i) in sorted(grouped.items()):
            configs.append(source["configs"][i])
            provenance.append(
                dict(source=name, family=family, index=i, reused_training_sharpe=score)
            )
    return configs, provenance, fingerprints


def sampled(args):
    engine.weights = weights
    return engine.sampled(args)


def main():
    engine.weights = weights
    selected, provenance, fingerprints = preselection()
    cs = selected + grid()
    report = dict(
        plan=PLAN,
        configs=cs,
        provenance=provenance,
        source_report_sha256=fingerprints,
        adopted=False,
    )

    def save():
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    save()  # Declare complete protocol and grid BEFORE new experiment results.
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
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        p = np.array([r[1] for r in rows])
        assert np.array_equal(p, [r[2] for r in rows])
        report["source"] = dict(first=days[0], last=days[-1], count=len(days))

        def batch(configs, years, seed, count):
            paths = []
            with ProcessPoolExecutor(max_workers=2) as pool:
                for i, row in enumerate(
                    pool.map(
                        sampled,
                        ((days, p, configs, years, seed + i) for i in range(count)),
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
                        print("Sharpe", years, i + 1, "/", count, flush=True)
            return dict(**engine.summary(paths), paths=paths)

        report["selection"] = batch(cs, 5, 1710000, 200)
        index = winner(report["selection"])
        report["frozen_index"] = index
        report["frozen_config"] = cs[index]
        save()  # Freeze before accessing any reserved draw.
        frozen = [cs[index]]
        report["audit"] = {}
        for years, seed, count in [(5, 1720000, 1000), (10, 1730000, 300)]:
            a = batch(frozen, years, seed, count)
            pairs = np.array(
                [
                    [r[1]["sharpe"], r[2]["sharpe"]]
                    for r in a["paths"]
                    if r[1]["sharpe"] is not None and r[2]["sharpe"] is not None
                ]
            )
            delta = pairs[:, 1] - pairs[:, 0]
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
        report["historical"] = {
            str(y): engine.evaluate(days, p, frozen, [f"{2026 - y}-11-13", days[-1]])
            for y in [1, 3, 5, 10]
        }
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
        print(
            "DONE",
            report["frozen_config"],
            report["modeled_sharpe_evidence"],
            flush=True,
        )


if __name__ == "__main__":
    main()
