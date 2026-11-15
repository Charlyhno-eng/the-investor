"""Three predeclared candidates, isolated engine copies; no production mutations."""

import hashlib
import inspect
import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
from audit_validation import UNIVERSES
from study_quantitative_strategies import PERIODS, load_inputs

from investor import db
from investor.portfolio import reversion, validation

PROTOCOL = {
    "tolerance": "3 percentage-point weight/cash bands, volatility and correlation separately",
    "group_cap": "Mean reversion: 40% NAV maximum per correlated group for new orders; exits unchanged",
    "group_allocation": "Quarterly: equal budget per correlated group, equal weights within each group",
    "groups": "Connected components of positive correlation >=0.70 on trailing 252 returns; no future data; undefined pairs unlinked",
    "retention": "Every universe/window/fee: CAGR loss <=0.005, Sharpe loss <=0.03, drawdown deterioration <=0.01. Tolerance additionally reduces summed fees and turnover. Other candidates: mean Sharpe gain >=0.05 and mean absolute drawdown reduction >=10%. No retuning.",
    "limitations": "Retrospective selected universes; overlapping windows; no prospective proof. Grouping is correlation-based, not current sector metadata.",
}


def groups(returns):
    n = returns.shape[1]
    parent = list(range(n))

    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i

    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.atleast_2d(np.corrcoef(returns, rowvar=False))
    for i in range(n):
        for j in range(i):
            if corr[i, j] >= 0.70:
                parent[root(i)] = root(j)
    return np.array([root(i) for i in range(n)])


def grouped_weights(returns, *args, **kwargs):
    labels = groups(returns[-252:])
    return np.array([1 / len(set(labels)) / np.sum(labels == g) for g in labels])


def capped_orders(values, cash, z, fee, *, group_labels, **kwargs):
    # Clone the existing order planner: reject infeasible group budgets before
    # donor sales, preserving its fees, minimums, whole shares and single donor.
    scope = dict(vars(reversion))
    scope["group_labels"] = group_labels
    source = inspect.getsource(reversion.reversion_orders).replace(
        "return target, required, deficit <= max(1e-12, np.spacing(pool) * 8)",
        "return target, required, deficit <= max(1e-12, np.spacing(pool) * 8) and all(float(target[group_labels == g].sum()) <= 0.40 * capital + 1e-10 for g in set(group_labels[candidates]))",
    )
    exec(source, scope)
    return scope["reversion_orders"](values, cash, z, fee, **kwargs)


def engine(candidate):
    scope = dict(vars(validation))
    source = inspect.getsource(validation.validation_data)
    if candidate == "group_allocation":
        scope["optimize_weights"] = grouped_weights
    if candidate == "group_cap":
        scope.update(capped_orders=capped_orders, groups=groups)
        source = source.replace(
            "values, remaining_cash = reversion_orders(",
            "values, remaining_cash = capped_orders(",
        )
        source = source.replace(
            "entry_z=request.reversion_entry_z,",
            "group_labels=groups((signal_prices[max(0, i-253)+1:i] / signal_prices[max(0, i-253):i-1] - 1)),\n                entry_z=request.reversion_entry_z,",
        )
    exec(source, scope)
    return scope["validation_data"]


def main():
    output = Path("data/backtests/three-optimizations.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {"protocol": PROTOCOL, "results": {}}
    output.write_text(json.dumps(report, indent=2))
    with tempfile.TemporaryDirectory() as folder:
        frozen = Path(folder) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(frozen) as dst,
        ):
            src.backup(dst)
        report["snapshot_sha256"] = hashlib.sha256(frozen.read_bytes()).hexdigest()
        original = db.DATA_DIR
        db.DATA_DIR = Path(folder)
        try:
            for universe in ("journal_14", "actions_11", "crypto_4"):
                for period, (start, end) in PERIODS.items():
                    for fee in (0.005, 0.01):
                        for mode in ("volatility", "correlation", "mean_reversion"):
                            request = validation.ValidationRequest(
                                asset_ids=UNIVERSES[universe],
                                mode=mode,
                                whole_shares=True,
                                fee_rate=fee,
                                start_date=date.fromisoformat(start),
                                end_date=date.fromisoformat(end),
                                reversion_entry_z=2,
                                reversion_exit_z=2,
                                reversion_exit_mode="trailing_z",
                                reversion_trailing_gap=1,
                                reversion_funding_min_z=0.3,
                            )
                            inputs = load_inputs(request)
                            candidates = (
                                ["control", "group_cap"]
                                if mode == "mean_reversion"
                                else ["control", "tolerance"]
                                + (["group_allocation"] if mode == "volatility" else [])
                            )
                            key = f"{universe}:{period}:{fee}:{mode}"
                            report["results"][key] = {}
                            for candidate in candidates:
                                req = (
                                    request.model_copy(
                                        update={"rebalance_tolerance": 0.03}
                                    )
                                    if candidate == "tolerance"
                                    else request
                                )
                                result = engine(candidate)(**inputs, request=req)
                                if result["status"] != "ready":
                                    raise RuntimeError(result)
                                report["results"][key][candidate] = result["metrics"][
                                    "strategy"
                                ]
                            output.write_text(json.dumps(report, indent=2))
                            print(key, flush=True)
        finally:
            db.DATA_DIR = original
    decisions = {}
    for candidate, mode in (
        ("tolerance", "volatility"),
        ("tolerance", "correlation"),
        ("group_cap", "mean_reversion"),
        ("group_allocation", "volatility"),
    ):
        pairs = [
            (key, case["control"], case[candidate])
            for key, case in report["results"].items()
            if key.endswith(":" + mode) and candidate in case
        ]
        failures = [
            key
            for key, a, b in pairs
            if b["cagr"] < a["cagr"] - 0.005
            or b["sharpe"] < a["sharpe"] - 0.03
            or b["max_drawdown"] < a["max_drawdown"] - 0.01
        ]
        fees = sum(b["cost_eur"] - a["cost_eur"] for _, a, b in pairs)
        turnover = sum(b["annual_turnover"] - a["annual_turnover"] for _, a, b in pairs)
        sharpe = float(np.mean([b["sharpe"] - a["sharpe"] for _, a, b in pairs]))
        dd = float(
            np.mean(
                [
                    1 - abs(b["max_drawdown"]) / max(abs(a["max_drawdown"]), 1e-10)
                    for _, a, b in pairs
                ]
            )
        )
        decisions[candidate + ":" + mode] = dict(
            retain=not failures
            and (
                fees < 0 and turnover < 0
                if candidate == "tolerance"
                else sharpe >= 0.05 and dd >= 0.10
            ),
            failures=failures,
            fee_delta=fees,
            turnover_delta=turnover,
            mean_sharpe_gain=sharpe,
            mean_drawdown_reduction=dd,
        )
    report["decisions"] = decisions
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(decisions, indent=2), flush=True)


if __name__ == "__main__":
    main()
