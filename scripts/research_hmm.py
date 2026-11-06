"""Predeclared validation then frozen asset/time audit. All results stay local."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from statistics import median

from investor.analysis.schemas import AnalysisRequest
from investor.analysis.service import calculate
from investor.analysis.strategy import POLICIES, describe_policy

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "scripts/hmm_research_plan.json"
OUTPUT = ROOT / "data/backtests/hmm-risk"


def kernel_hash():
    digest = hashlib.sha256()
    for name in ("model.py", "strategy.py"):
        content = (ROOT / "backend/investor/analysis" / name).read_text()
        # Default changes to the validation winner; every policy is explicit here.
        content = "\n".join(
            line
            for line in content.splitlines()
            if not line.startswith("DEFAULT_POLICY_NAME =")
        )
        digest.update(content.encode())
    return digest.hexdigest()


def summarize(rows):
    if not rows:
        return {"cases": 0}
    return {
        "cases": len(rows),
        "median_return": median(r["strategy"]["total_return"] for r in rows),
        "median_sharpe": median(r["strategy"]["sharpe"] or 0 for r in rows),
        "median_drawdown": median(r["strategy"]["maximum_drawdown"] for r in rows),
        "median_orders": median(r["orders"] for r in rows),
        "profitable": sum(r["strategy"]["total_return"] > 0 for r in rows),
        "beats_market": sum(
            r["strategy"]["total_return"] > r["benchmark"]["total_return"] for r in rows
        ),
        "drawdown_exceeds_10pct": sum(
            r["strategy"]["maximum_drawdown"] > 0.1 + 1e-12 for r in rows
        ),
        "stopped": sum(bool(r["risk_control"]["events"]) for r in rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("validation", "audit"))
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text())
    plan_hash = hashlib.sha256(PLAN.read_bytes()).hexdigest()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    selection_path = OUTPUT / "selection.json"
    if args.phase == "validation":
        names, assets = list(plan["policies"]), plan["development_assets"]
        period = plan["validation"]
    else:
        selection = json.loads(selection_path.read_text())
        if (
            selection["kernel_hash"] != kernel_hash()
            or selection["plan_hash"] != plan_hash
        ):
            raise SystemExit(
                "Model/policies/plan changed after validation; audit refused."
            )
        names = list(
            dict.fromkeys(
                [
                    selection["selected"],
                    "daily_original",
                    "daily_guard",
                    "weekly_trend_control",
                ]
            )
        )
        assets, period = plan["audit_assets"], plan["audit"]
    for name in names:
        expected = dict(plan["policies"][name])
        expected.setdefault("ignore_hmm", False)
        assert describe_policy(POLICIES[name]) == expected
    rows, skipped = [], []
    with sqlite3.connect(
        f"file:{ROOT / 'data/investor.sqlite3'}?mode=ro", uri=True
    ) as db:
        db.row_factory = sqlite3.Row
        for aid in assets:
            asset = db.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone()
            history = [
                dict(r)
                for r in db.execute(
                    "SELECT date,value FROM observations WHERE asset_id=? AND date>=? AND date<=? ORDER BY date",
                    (aid, period["train_start"], period["test_end"]),
                )
            ]
            if (
                asset is None
                or sum(r["date"] <= period["train_end"] for r in history) < 101
            ):
                skipped.append(aid)
                continue
            fingerprint = hashlib.sha256(
                json.dumps(history, sort_keys=True).encode()
            ).hexdigest()
            for name in names:
                for fee in plan["fees_bps"]:
                    request = AnalysisRequest(**period, fee_bps=fee)
                    result = calculate(
                        dict(asset), history, request, policy=POLICIES[name]
                    )
                    rows.append(
                        {
                            "asset": aid,
                            "policy": name,
                            "fee_bps": fee,
                            "data_sha256": fingerprint,
                            "train": result["actual_train"],
                            "test": result["actual_test"],
                            "strategy": result["strategy_metrics"],
                            "benchmark": result["benchmark_metrics"],
                            "orders": len(result["trades"]),
                            "exposure": result["exposure"],
                            "risk_control": result["risk_control"],
                            "trades": result["trades"],
                            "equity": result["equity"],
                        }
                    )
    summaries = {
        f"{name}/{fee}": summarize(
            [r for r in rows if r["policy"] == name and r["fee_bps"] == fee]
        )
        for name in names
        for fee in plan["fees_bps"]
    }
    artifact = {
        "phase": args.phase,
        "kernel_hash": kernel_hash(),
        "plan_hash": plan_hash,
        "summaries": summaries,
        "skipped": skipped,
        "results": rows,
    }
    path = OUTPUT / f"{args.phase}.json"
    if path.exists():
        raise SystemExit(f"Refusing to overwrite audit trail: {path}")
    path.write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n")
    if args.phase == "validation":
        chosen = max(
            plan["eligible"], key=lambda name: summaries[f"{name}/10"]["median_sharpe"]
        )
        selection_path.write_text(
            json.dumps(
                {
                    "selected": chosen,
                    "plan_hash": plan_hash,
                    "kernel_hash": kernel_hash(),
                    "selection_criterion": plan["selection"],
                },
                indent=2,
            )
            + "\n"
        )
        print("FROZEN SELECTION:", chosen)
    for name, summary in summaries.items():
        print(name, json.dumps(summary))
    print(path, "skipped:", skipped)


if __name__ == "__main__":
    main()
