"""Train-only per-stock validation of the persistent HMM candidate family.

Exploratory extension: earlier evaluation histories have already been examined.
Choose on the last 252 training observations, never on the current test window.
If validation does not exceed passive holding by 2 points net, remain passive.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from audit_hmm_stocks import universe
from investor.analysis.persistent import evaluate, simulate


def choose(validation, first_return, minimum_advantage=0.02):
    """Compare with identical first-close entry; ties default to passive."""
    ranked = []
    for result in validation:
        if result["policy"].startswith("control_"):
            continue
        matched = (1 + result["benchmark"]["total_return"]) / np.exp(first_return) - 1
        ranked.append((result["strategy"]["total_return"] - matched, result["policy"]))
    if not ranked:
        raise ValueError("No validation candidates")
    advantage, policy = max(ranked)
    return (policy if advantage > minimum_advantage else "passive"), advantage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=Path("data/investor.sqlite3"))
    args = parser.parse_args()
    source = json.loads(args.source.read_text())
    catalog = {a["id"]: rows for a, rows in universe(args.database)}
    protocol = {
        "validation_returns": 252,
        "minimum_validation_advantage": 0.02,
        "fee_bps": 50,
        "fallback": "passive_first_close_entry",
        "previously_examined_evaluation_history": True,
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    output = {"protocol": protocol, "results": []}
    if args.output.exists():
        output = json.loads(args.output.read_text())
        if output["protocol"] != protocol:
            raise ValueError("Incompatible existing adaptive experiment")
    periods = {(r["asset_id"], r["case"]): r for r in source["evaluation"]}
    for (asset_id, case), reference in periods.items():
        if any(
            r["asset_id"] == asset_id and r["case"] == case for r in output["results"]
        ):
            continue
        base = {
            k: reference[k]
            for k in (
                "asset_id",
                "name",
                "case",
                "train_start",
                "test_start",
                "test_end",
                "data_sha256",
            )
        }
        try:
            rows = [
                r
                for r in catalog[asset_id]
                if reference["train_start"] <= r["date"] <= reference["test_end"]
            ]
            test_index = next(
                i for i, r in enumerate(rows) if r["date"] >= reference["test_start"]
            )
            validation_index = test_index - 252
            validation_rows = rows[:test_index]
            validation = evaluate(validation_rows, rows[validation_index]["date"])
            first_return = np.log(
                rows[validation_index]["value"] / rows[validation_index - 1]["value"]
            )
            selected, advantage = choose(validation, first_return)
            if selected == "passive":
                changes = np.diff(np.log([r["value"] for r in rows]))[test_index - 1 :]
                result = simulate(changes, np.ones(len(changes), dtype=int), 50)
            else:
                result = next(
                    r
                    for r in source["evaluation"]
                    if r["asset_id"] == asset_id
                    and r["case"] == case
                    and r.get("policy") == selected
                )
            test_first_return = np.log(
                rows[test_index]["value"] / rows[test_index - 1]["value"]
            )
            matched = (1 + result["benchmark"]["total_return"]) / np.exp(
                test_first_return
            ) - 1
            base.update(
                selected=selected,
                validation_advantage=advantage,
                validation_start=rows[validation_index]["date"],
                validation_end=rows[test_index - 1]["date"],
                strategy=result["strategy"],
                benchmark=result["benchmark"],
                excess_return=result["excess_return"],
                matched_benchmark_return=matched,
                matched_excess_return=result["strategy"]["total_return"] - matched,
                transactions=result["transactions"],
                exposure=result["exposure"],
            )
        except (ValueError, ArithmeticError) as exc:
            base["error"] = str(exc)
        output["results"].append(base)
        args.output.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
        print(
            asset_id,
            case,
            base.get("selected"),
            base.get("matched_excess_return"),
            base.get("error"),
            flush=True,
        )


if __name__ == "__main__":
    main()
