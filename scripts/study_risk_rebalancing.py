"""Predeclared risk-parity policy comparison on an isolated SQLite snapshot."""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

from audit_validation import UNIVERSES
from study_quantitative_strategies import PERIODS, load_inputs

from investor import db
from investor.portfolio.validation import ValidationRequest, validation_data

CRITERION = (
    "Every universe/window/fee: CAGR loss <=0.005, Sharpe loss <=0.03, "
    "absolute drawdown deterioration <=0.01; total fees and turnover "
    "strictly lower across cases. No tuning; overlapping retrospective samples, "
    "sum of costs is descriptive only. Retain every passing candidate; "
    "prefer combined, then risk, then weight if several pass."
)
VARIANTS = {
    "control": {},
    "weight": {"rebalance_tolerance": 0.03},
    "risk": {"risk_rebalance_tolerance": 0.03},
    "combined": {"rebalance_tolerance": 0.03, "risk_rebalance_tolerance": 0.03},
}


def main():
    output = Path("data/backtests/risk-rebalancing.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {"criterion": CRITERION, "variants": VARIANTS, "results": {}}
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
        output.write_text(json.dumps(report, indent=2))
        original = db.DATA_DIR
        db.DATA_DIR = Path(folder)
        try:
            for universe in ("journal_14", "actions_11", "crypto_4"):
                for period, (start, end) in PERIODS.items():
                    for fee in (0.005, 0.01):
                        base = ValidationRequest(
                            asset_ids=UNIVERSES[universe],
                            mode="risk_parity",
                            whole_shares=True,
                            fee_rate=fee,
                            start_date=date.fromisoformat(start),
                            end_date=date.fromisoformat(end),
                        )
                        inputs = load_inputs(base)
                        key = f"{universe}:{period}:{fee}"
                        report["results"][key] = {}
                        for name, options in VARIANTS.items():
                            result = validation_data(
                                **inputs, request=base.model_copy(update=options)
                            )
                            if result["status"] != "ready":
                                raise RuntimeError(result)
                            report["results"][key][name] = {
                                "metrics": result["metrics"]["strategy"],
                                "folds": result["folds"],
                                "parameters": result["parameters"],
                            }
                        print(key, flush=True)
                        output.write_text(json.dumps(report, indent=2))
        finally:
            db.DATA_DIR = original
    decisions = {}
    for name in ("weight", "risk", "combined"):
        failures = []
        fee_delta = turnover_delta = 0
        for key, case in report["results"].items():
            a, b = case["control"]["metrics"], case[name]["metrics"]
            if (
                b["cagr"] < a["cagr"] - 0.005
                or b["sharpe"] < a["sharpe"] - 0.03
                or b["max_drawdown"] < a["max_drawdown"] - 0.01
            ):
                failures.append(key)
            fee_delta += b["cost_eur"] - a["cost_eur"]
            turnover_delta += b["annual_turnover"] - a["annual_turnover"]
        decisions[name] = {
            "retain": not failures and fee_delta < 0 and turnover_delta < 0,
            "failures": failures,
            "fee_delta": fee_delta,
            "turnover_delta": turnover_delta,
        }
    report["decisions"] = decisions
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(decisions, indent=2), flush=True)


if __name__ == "__main__":
    main()
