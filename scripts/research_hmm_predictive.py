"""Predeclared predictive HMM experiment, developed on 2020-2023 only.

States describe causal trend/volatility; their *future* return is estimated from
completed training outcomes, with an embargo equal to the forecast horizon.
This is a new experiment, never automatically promoted to production.
"""

import argparse
import hashlib
import json
import warnings
from pathlib import Path

import numpy as np
from audit_hmm_stocks import universe
from hmmlearn.hmm import GaussianHMM
from investor.analysis.metrics import metrics
from investor.analysis.model import forward_filter
from research_hmm_stock_policies import simulate_actions
from threadpoolctl import threadpool_limits

CONFIGURATIONS = [
    (window, horizon, charge)
    for window in (21, 63)
    for horizon in (21, 63)
    for charge in (0, 1)
]


def features(prices, window):
    r = np.diff(np.log(prices))
    x = np.full((len(r), 3), np.nan)
    for i in range(max(window, 21) - 1, len(r)):
        vol = max(r[i - 20 : i + 1].std(), 1e-8)
        x[i] = [
            r[i - window + 1 : i + 1].sum() / (vol * np.sqrt(window)),
            r[i - 4 : i + 1].sum() / (vol * np.sqrt(5)),
            np.log(vol),
        ]
    return r, x


def fit(x):
    mean = x.mean(axis=0)
    scale = np.maximum(x.std(axis=0), 1e-8)
    normalized = (x - mean) / scale
    candidates = []
    with threadpool_limits(limits=1):
        for seed in (17, 41, 83):
            model = GaussianHMM(
                n_components=3,
                covariance_type="full",
                n_iter=300,
                tol=0.01,
                random_state=seed,
                init_params="mc",
                params="tmc",
                transmat_prior=1.05,
                covars_prior=0.01 * np.eye(3),
                covars_weight=5,
            )
            model.startprob_ = np.ones(3) / 3
            model.transmat_ = np.full((3, 3), 0.01)
            np.fill_diagonal(model.transmat_, 0.98)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    model.fit(normalized)
                score = model.score(normalized)
                occupancy = model.predict_proba(normalized).sum(axis=0)
                if np.isfinite(score) and occupancy.min() >= 20:
                    candidates.append((score, model))
            except (ValueError, np.linalg.LinAlgError):
                continue
    if not candidates:
        raise ValueError("No non-degenerate HMM")
    return max(candidates, key=lambda pair: pair[0])[1], mean, scale


def rewards(r, p, training_end, horizon):
    # State at i predicts r[i+2]..r[i+horizon+1]. Every target must be fully
    # realized before the training boundary, so no validation label is used.
    indices = np.arange(training_end - horizon - 1)
    cumulative = np.r_[0.0, r.cumsum()]
    target = cumulative[indices + horizon + 2] - cumulative[indices + 2]
    weights = p[indices]
    # Ridge to a common intercept shrinks rare states toward the global drift.
    center = target.mean()
    gram = weights.T @ weights
    return np.linalg.solve(gram + 20 * np.eye(3), weights.T @ target + 20 * center)


def evaluate(rows, cut, window, horizons=(21, 63)):
    dates = np.array([row["date"] for row in rows[1:]], dtype="U10")
    r, x = features(np.array([row["value"] for row in rows]), window)
    valid = np.isfinite(x).all(axis=1)
    x = x[valid]
    r = r[valid]
    dates = dates[valid]
    train = dates < cut
    test = ~train
    end = int(train.sum())
    if end < 252 or test.sum() < 100:
        return []
    model, mean, scale = fit(x[train])
    p = forward_filter(model, (x - mean) / scale)
    output = []
    for horizon in horizons:
        state_returns = rewards(r, p, end, horizon)
        forecast = p @ state_returns
        for charge in (0, 1):
            threshold = charge * (-2 * np.log(0.995))
            actions = np.full(int(test.sum()), -1, dtype=int)
            for i in range(0, len(actions) - 1, 5):
                value = forecast[end + i - 1]
                if value > threshold:
                    actions[i] = 1
                elif value < -threshold:
                    actions[i] = 0
            net, bm, trades, exposure = simulate_actions(r[test], actions)
            strategy = metrics(net, bm, 252, 0)
            benchmark = metrics(bm, bm, 252, 0)
            output.append(
                {
                    "policy": f"predictive_w{window}_h{horizon}_cost{charge}",
                    "excess_return": strategy["total_return"]
                    - benchmark["total_return"],
                    "strategy": strategy,
                    "benchmark": benchmark,
                    "exposure": exposure,
                    "transactions": trades,
                    "state_forecasts": state_returns.tolist(),
                }
            )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/investor.sqlite3"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = []
    if args.output.exists():
        output = json.loads(args.output.read_text())["results"]
    for asset, full in universe(args.database):
        for year in (2020, 2021, 2022, 2023):
            rows = [
                r
                for r in full
                if f"{year - 5}-01-01" <= r["date"] < f"{year + 1}-01-01"
            ]
            for window in (21, 63):
                existing = [
                    entry
                    for entry in output
                    if entry.get("asset_id") == asset["id"]
                    and entry.get("year") == year
                    and entry.get("policy", "").startswith(f"predictive_w{window}_")
                ]
                if len(existing) == 4:
                    continue
                try:
                    entries = evaluate(rows, f"{year}-01-01", window)
                    output.extend(
                        dict(
                            asset_id=asset["id"],
                            year=year,
                            data_sha256=hashlib.sha256(
                                json.dumps(rows, sort_keys=True).encode()
                            ).hexdigest(),
                            **entry,
                        )
                        for entry in entries
                    )
                except ValueError as exc:
                    output.append(
                        {
                            "asset_id": asset["id"],
                            "year": year,
                            "window": window,
                            "error": str(exc),
                        }
                    )
                args.output.write_text(
                    json.dumps(
                        {
                            "protocol": "predictive_hmm_development_pre_2024_only",
                            "configurations": CONFIGURATIONS,
                            "results": output,
                        },
                        indent=2,
                        allow_nan=False,
                    )
                    + "\n"
                )
            print(asset["id"], year, flush=True)
    from statistics import median

    for policy in sorted({r["policy"] for r in output if "policy" in r}):
        g = [r for r in output if r.get("policy") == policy]
        print(
            json.dumps(
                {
                    "policy": policy,
                    "count": len(g),
                    "wins": sum(r["excess_return"] > 1e-10 for r in g),
                    "median_excess": median(r["excess_return"] for r in g),
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
