"""Second, separately frozen study: the classic low-volatility HMM risk filter.

This is a different hypothesis from directional forecasting. The current
EWM study is preserved, including its negative results. No test-return grid.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from backtest_hmm_literature import aggregate, diagnostics, digest
from backtest_regimes import windows
from hmm_regime_candidates import execute
from investor.analysis.model import forward_filter
from investor.analysis.regimes import _fit
from investor.analysis.schemas import AnalysisRequest
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/backtests/hmm-volatility"
STUDY = ROOT / "data/backtests/hmm-literature"
POLICIES = ("volatility_frozen", "volatility_rolling")


def risk_signals(changes, dates, request, rolling):
    x = changes[:, None]
    train = (dates > request.train_start.isoformat()) & (
        dates <= request.train_end.isoformat()
    )
    test = (dates >= request.test_start.isoformat()) & (
        dates <= request.test_end.isoformat()
    )
    initial = np.flatnonzero(train)[-1260:]
    first, last = np.flatnonzero(test)[[0, -1]]
    value, probability, calibrations = [], [], []
    model = None
    for start in range(first, last + 1, 63 if rolling else last - first + 1):
        stop = min(start + 63, last + 1) if rolling else last + 1
        indices = initial if model is None else np.arange(max(0, start - 1260), start)
        failure = None
        try:
            with threadpool_limits(limits=1):
                calibrated = _fit(x[indices], 2)
            model, mean, scale, converged = calibrated
            used = indices
        except ValueError as exc:
            if model is None:
                raise
            failure = str(exc)
        probabilities = forward_filter(model, (x[used[0] : stop] - mean) / scale)[
            start - used[0] :
        ]
        calm = int(np.argmin(model.covars_[:, 0, 0]))
        # Two states, MAP decoding: p(calm)>p(stress), with no tuned threshold.
        p = probabilities[:, calm]
        value.extend((p - 0.5).tolist())
        probability.extend(p.tolist())
        calibrations.append(
            {
                "first_signal": str(dates[start]),
                "calibration_start": str(dates[used[0]]),
                "calibration_end": str(dates[used[-1]]),
                "fit_points": len(used),
                "converged": bool(converged),
                "failure": failure,
                "calm_state": calm,
                "drift": (model.means_[:, 0] * scale[0] + mean[0]).tolist(),
                "volatility": (np.sqrt(model.covars_[:, 0, 0]) * scale[0]).tolist(),
                "transition_matrix": model.transmat_.tolist(),
            }
        )
    return np.array(value), np.array(probability), calibrations


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "plan.json").exists():
        raise SystemExit("Refusing to overwrite a frozen study")
    first_results = json.loads((STUDY / "results.json").read_text())["results"]
    baseline = {
        (r["asset"], r["case"], r["fee_multiple"]): r
        for r in first_results
        if r["policy"] == "current_hmm"
    }
    assets = json.loads((STUDY / "data.json").read_text())
    sources = [
        "scripts/backtest_hmm_volatility.py",
        "scripts/backtest_hmm_literature.py",
        "scripts/hmm_regime_candidates.py",
        "scripts/backtest_regimes.py",
        "backend/investor/analysis/model.py",
        "backend/investor/analysis/regimes.py",
        "backend/investor/analysis/metrics.py",
    ]
    plan = {
        "rules_fixed_before_run": True,
        "policies": list(POLICIES),
        "method": "GaussianHMM 2 states, log daily returns, train-only scaling, three initializations by training likelihood; invest iff causal current p(lowest variance)>0.5; no stop/leverage/indicators",
        "recalibration": "frozen or every 63 observations, trailing up to 1260 observations, strictly before signal bar; failed refresh carries last model and is recorded",
        "fees_and_execution": "same as EWM study, both requested defaults and twice defaults; fees charged at every execution, without fee-tuning the posterior threshold",
        "gate": json.loads((STUDY / "plan.json").read_text())["gate"],
        "limitations": "Additional exploratory hypotheses specified after seeing EWM study, NOT independent confirmation. Same reused data; no choice by test returns.",
        "prior_study_sha256": hashlib.sha256(
            (STUDY / "results.json").read_bytes()
        ).hexdigest(),
        "data_sha256": digest(assets),
        "sources": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources
        },
    }
    (OUT / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    results = []
    for asset, rows in assets:
        for case, data, period in windows(rows):
            if (asset["id"], case, 1) not in baseline:
                continue
            changes = np.diff(np.log([r["value"] for r in data]))
            dates = np.array([r["date"] for r in data[1:]])
            for policy in POLICIES:
                request = AnalysisRequest(
                    **baseline[(asset["id"], case, 1)]["parameters"]
                )
                test = (dates >= request.test_start.isoformat()) & (
                    dates <= request.test_end.isoformat()
                )
                try:
                    values, probability, audit = risk_signals(
                        changes, dates, request, policy.endswith("rolling")
                    )
                    for multiple in (1, 2):
                        old = baseline[(asset["id"], case, multiple)]
                        request = AnalysisRequest(**old["parameters"])
                        net, market, trades, held = execute(
                            changes[test],
                            dates[test],
                            values,
                            0.0,
                            probability,
                            request.fee_bps,
                        )
                        d = diagnostics(
                            net,
                            market,
                            held,
                            values,
                            changes[test],
                            365 if asset["category"] == "crypto" else 252,
                        )
                        np.testing.assert_allclose(
                            d["benchmark_metrics"]["total_return"],
                            old["benchmark_metrics"]["total_return"],
                            atol=1e-12,
                        )
                        results.append(
                            {
                                **{
                                    k: old[k]
                                    for k in (
                                        "asset",
                                        "name",
                                        "category",
                                        "case",
                                        "fee_multiple",
                                        "fee_bps",
                                        "parameters",
                                        "data_sha256",
                                        "test_points",
                                    )
                                },
                                "policy": policy,
                                **d,
                                "trades": trades,
                                "held": held.tolist(),
                                "signal": values.tolist(),
                                "calibrations": audit,
                            }
                        )
                except ValueError as exc:
                    for multiple in (1, 2):
                        old = baseline[(asset["id"], case, multiple)]
                        results.append(
                            {
                                "asset": asset["id"],
                                "case": case,
                                "policy": policy,
                                "fee_multiple": multiple,
                                "error": str(exc),
                            }
                        )
            print(asset["id"], case, "completed", flush=True)
            (OUT / "progress.json").write_text(json.dumps(results, allow_nan=False))
    summary = []
    for policy in POLICIES:
        renamed = [
            dict(r, policy="current_hmm") for r in results if r["policy"] == policy
        ]
        summary.extend(dict(r, policy=policy) for r in aggregate(renamed))
    (OUT / "results.json").write_text(
        json.dumps({"plan": plan, "results": results}, allow_nan=False)
    )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    print(
        "Completed",
        len(results),
        "cases;",
        sum("error" in r for r in results),
        "errors",
    )


if __name__ == "__main__":
    main()
