"""Compare predeclared slower two-state HMMs on all stocks, without promotion.

Develop 30 candidates on annual 2020-2023, freeze one global candidate, then
report all candidates transparently on UI defaults and 2024-2026. These latter
histories were already examined in previous experiments: not a virgin holdout.
"""

import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

from audit_hmm_stocks import default_request, universe
from investor.analysis.persistent import POLICIES, REPRESENTATIONS, evaluate


def summary(results):
    output = []
    for policy in sorted({r["policy"] for r in results if "policy" in r}):
        group = [r for r in results if r.get("policy") == policy]
        output.append(
            {
                "policy": policy,
                "count": len(group),
                "wins": sum(r["excess_return"] > 1e-10 for r in group),
                "median_excess": median(r["excess_return"] for r in group),
                "median_transactions": median(r["transactions"] for r in group),
            }
        )
    return sorted(
        output,
        key=lambda r: (r["wins"] / r["count"], r["median_excess"]),
        reverse=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/investor.sqlite3"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    catalog = universe(args.database)
    data = {
        "protocol": {
            "states": 2,
            "representations": REPRESENTATIONS,
            "policies": POLICIES,
            "cadences": [1, 21],
            "selection": "global_pre2024_win_fraction_then_median_excess",
            "fee_bps": 50,
            "execution": "signal_close_t_execution_close_t_plus_1",
            "previously_examined_evaluation_history": True,
            "source_sha256": {
                file: hashlib.sha256(Path(file).read_bytes()).hexdigest()
                for file in (
                    "backend/investor/analysis/persistent.py",
                    "backend/investor/analysis/model.py",
                    "backend/investor/analysis/metrics.py",
                    __file__,
                )
            },
        },
        "development": [],
        "evaluation": [],
    }
    if args.output.exists():
        old = json.loads(args.output.read_text())
        if old["protocol"] != data["protocol"]:
            raise ValueError("Existing experiment has different protocol/source hashes")
        data = old

    def save():
        args.output.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")

    for phase in ("development", "evaluation"):
        if phase == "evaluation":
            ranked = summary(data["development"])
            data["development_summary"] = ranked
            # A failed fit or missing stock-period must never improve ranking.
            expected = sum("error" not in r for r in data["development"]) // 32
            eligible = [
                r
                for r in ranked
                if not r["policy"].startswith("control_") and r["count"] == expected
            ]
            if not eligible:
                raise ValueError("No complete development candidate")
            data["selected"] = eligible[0]
            save()
            print("FROZEN", json.dumps(data["selected"]), flush=True)
        for asset, full in catalog:
            years = (
                (2020, 2021, 2022, 2023)
                if phase == "development"
                else (2024, 2025, 2026)
            )
            periods = [
                (
                    f"annual_{y}",
                    max(full[0]["date"], f"{y - 5}-01-01"),
                    f"{y}-01-01",
                    min(full[-1]["date"], f"{y}-12-31"),
                )
                for y in years
            ]
            if phase == "evaluation":
                request = default_request(full)
                periods.insert(
                    0,
                    (
                        "interface_default",
                        request.train_start.isoformat(),
                        request.test_start.isoformat(),
                        request.test_end.isoformat(),
                    ),
                )
            for case, start, cut, end in periods:
                if any(
                    r["asset_id"] == asset["id"] and r["case"] == case
                    for r in data[phase]
                ):
                    continue
                rows = [r for r in full if start <= r["date"] <= end]
                base = {
                    "asset_id": asset["id"],
                    "name": asset["name"],
                    "case": case,
                    "train_start": start,
                    "test_start": cut,
                    "test_end": end,
                    "data_sha256": hashlib.sha256(
                        json.dumps(rows, sort_keys=True).encode()
                    ).hexdigest(),
                }
                try:
                    entries = evaluate(rows, cut)
                    data[phase].extend(dict(**base, **r) for r in entries)
                except (ValueError, ArithmeticError) as exc:
                    data[phase].append(dict(**base, error=str(exc)))
                save()
                print(phase, asset["id"], case, flush=True)
    data["evaluation_summary"] = {
        case: summary([r for r in data["evaluation"] if r["case"] == case])
        for case in ("interface_default", "annual_2024", "annual_2025", "annual_2026")
    }
    save()
    for case, ranked in data["evaluation_summary"].items():
        selected = next(r for r in ranked if r["policy"] == data["selected"]["policy"])
        print(
            case,
            "SELECTED",
            json.dumps(selected),
            "BEST_EXPLORATORY",
            json.dumps(ranked[0]),
            flush=True,
        )


if __name__ == "__main__":
    main()
