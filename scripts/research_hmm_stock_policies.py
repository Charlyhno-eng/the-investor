"""Predeclared policy comparison using only pre-2024 stock observations.

No final/default test observations participate in policy selection. The candidates
share the production return-density HMM; only their execution rules differ.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from audit_hmm_stocks import universe
from investor.analysis.metrics import metrics
from investor.analysis.model import forward_filter
from investor.analysis.regimes import fit_regimes, observations
from investor.analysis.schemas import AnalysisRequest
from investor.analysis.switching import simulate_switching

POLICIES = (
    ("forecast_21", "forecast", 21, 1.0, 1.0),
    ("forecast_63", "forecast", 63, 1.0, 1.0),
    ("forecast_126", "forecast", 126, 1.0, 1.0),
    ("regime_daily_80", "regime", 1, 0.2, 0.8),
    ("regime_weekly_80", "regime", 5, 0.2, 0.8),
    ("regime_weekly_95", "regime", 5, 0.1, 0.95),
    ("regime_monthly_80", "regime", 21, 0.2, 0.8),
    ("regime_monthly_95", "regime", 21, 0.1, 0.95),
)


def simulate_actions(changes, actions, fee=0.005):
    held = 0
    returns = np.zeros(len(changes))
    positions = []
    count = 0
    for i, change in enumerate(changes):
        returns[i] = np.expm1(change) if held else 0
        target = 0 if i == len(changes) - 1 else actions[i]
        if target >= 0 and target != held:
            returns[i] = (1 + returns[i]) * (1 - fee) - 1
            held = int(target)
            count += 1
        positions.append(held)
    benchmark = np.expm1(changes)
    benchmark[0] = (1 + benchmark[0]) * (1 - fee) - 1
    benchmark[-1] = (1 + benchmark[-1]) * (1 - fee) - 1
    return returns, benchmark, count, float(np.mean(positions))


def evaluate_policy(policy, model, mean, scale, p, changes, dates, fee_bps=50):
    name, kind, horizon, entry, exit = policy
    log_means = model.means_[:, 0] * scale[0] + mean[0]
    if kind == "forecast":
        future = model.transmat_ @ log_means
        advantage = np.zeros(len(log_means))
        for _ in range(horizon):
            future = model.transmat_ @ future
            advantage += future
        request = AnalysisRequest(
            train_start="2000-01-01",
            train_end="2001-01-01",
            test_start="2002-01-01",
            test_end="2003-01-01",
            fee_bps=fee_bps,
        )
        net, bm, trades, positions = simulate_switching(
            changes,
            p[1:],
            dates,
            request,
            advantage,
            -2 * np.log1p(-fee_bps / 10000),
            log_means > 0,
            initial_probability=p[0],
        )
        count = len(trades)
        exposure = float(np.mean(positions))
    else:
        adverse = p[:, log_means < 0].sum(axis=1)
        actions = np.full(len(changes), -1, dtype=int)
        for i in range(0, len(changes) - 1, horizon):
            if adverse[i] < entry:
                actions[i] = 1
            elif adverse[i] > exit:
                actions[i] = 0
        net, bm, count, exposure = simulate_actions(changes, actions, fee_bps / 10000)
    strategy = metrics(net, bm, 252, 0)
    benchmark = metrics(bm, bm, 252, 0)
    return {
        "policy": name,
        "strategy": strategy,
        "benchmark": benchmark,
        "excess_return": strategy["total_return"] - benchmark["total_return"],
        "exposure": exposure,
        "transactions": count,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/investor.sqlite3"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = []
    for asset, full in universe(args.database):
        for year in (2020, 2021, 2022, 2023):
            rows = [
                r
                for r in full
                if f"{year - 5}-01-01" <= r["date"] < f"{year + 1}-01-01"
            ]
            if len(rows) < 400:
                continue
            dates = np.array([r["date"] for r in rows[1:]])
            train = dates < f"{year}-01-01"
            test = ~train
            if train.sum() < 252 or test.sum() < 100:
                continue
            changes, x = observations(np.array([r["value"] for r in rows]))
            model, mean, scale, _, _selection = fit_regimes(x[train])
            probabilities = forward_filter(model, (x - mean) / scale)
            first = int(np.flatnonzero(test)[0])
            for policy in POLICIES:
                result = evaluate_policy(
                    policy,
                    model,
                    mean,
                    scale,
                    probabilities[first - 1 :],
                    changes[test],
                    dates[test].tolist(),
                )
                output.append(
                    dict(
                        asset_id=asset["id"],
                        year=year,
                        parameters={
                            "train_start": rows[0]["date"],
                            "train_end": dates[train][-1],
                            "test_start": dates[test][0],
                            "test_end": dates[test][-1],
                        },
                        data_sha256=hashlib.sha256(
                            json.dumps(rows, sort_keys=True).encode()
                        ).hexdigest(),
                        **result,
                    )
                )
            print(asset["id"], year, flush=True)
            args.output.write_text(
                json.dumps(
                    {
                        "protocol": "development_pre_2024_only",
                        "policies": POLICIES,
                        "results": output,
                    },
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            )
    summary = []
    for name, *_ in POLICIES:
        group = [r for r in output if r["policy"] == name]
        row = {
            "policy": name,
            "count": len(group),
            "wins": sum(r["excess_return"] > 1e-10 for r in group),
            "median_excess": float(np.median([r["excess_return"] for r in group])),
            "median_trades": float(np.median([r["transactions"] for r in group])),
        }
        summary.append(row)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
