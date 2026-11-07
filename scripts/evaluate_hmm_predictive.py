"""Evaluate a frozen development-selected candidate on every catalog stock.

Selection uses 2020-2023 only. All default periods and annual 2024-2026 periods
are reported, including errors/exclusions. No outcome can change the candidate.
"""

import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

from audit_hmm_stocks import default_request, universe
from research_hmm_predictive import evaluate


def select_candidate(development_files):
    summary = []
    for file in development_files:
        data = json.loads(file.read_text())
        entries = data["results"]
        if any(r["year"] >= 2024 for r in entries):
            raise ValueError("Candidate selection cannot include post-2023 results")
        for policy in sorted({r["policy"] for r in entries if "policy" in r}):
            group = [r for r in entries if r.get("policy") == policy]
            summary.append(
                {
                    "policy": policy,
                    "count": len(group),
                    "wins": sum(r["excess_return"] > 1e-10 for r in group),
                    "median_excess": median(r["excess_return"] for r in group),
                }
            )
    selected = max(summary, key=lambda r: (r["wins"] / r["count"], r["median_excess"]))
    return selected, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/investor.sqlite3"))
    parser.add_argument("--policy-development", type=Path, required=True)
    parser.add_argument("--predictive-development", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    selected, summary = select_candidate(
        [args.policy_development, args.predictive_development]
    )
    # The selection is frozen before loading any final evaluation price series.
    args.output.write_text(
        json.dumps(
            {"selected": selected, "development": summary, "results": []}, indent=2
        )
        + "\n"
    )
    name = selected["policy"]
    if not name.startswith("predictive_"):
        raise ValueError(f"Winner requires the return-policy evaluator: {name}")
    _, window, horizon, charge = name.split("_")
    window = int(window[1:])
    horizon = int(horizon[1:])
    charge = int(charge[4:])
    output = []
    for asset, full in universe(args.database):
        request = default_request(full)
        periods = [
            (
                "interface_default",
                request.train_start.isoformat(),
                request.test_start.isoformat(),
                request.test_end.isoformat(),
            )
        ]
        periods.extend(
            (
                f"annual_{year}",
                f"{year - 5}-01-01",
                f"{year}-01-01",
                min(f"{year}-12-31", full[-1]["date"]),
            )
            for year in (2024, 2025, 2026)
        )
        for case, start, cut, end in periods:
            rows = [r for r in full if start <= r["date"] <= end]
            entry = {
                "asset_id": asset["id"],
                "name": asset["name"],
                "case": case,
                "train_start": start,
                "test_start": cut,
                "test_end": end,
                "fee_bps": 50,
                "data_sha256": hashlib.sha256(
                    json.dumps(rows, sort_keys=True).encode()
                ).hexdigest(),
            }
            try:
                results = evaluate(rows, cut, window, horizons=(horizon,))
                matching = [r for r in results if r["policy"] == name]
                if len(matching) != 1:
                    raise ValueError("Insufficient history for the predeclared period")
                entry.update(matching[0])
            except (ValueError, ArithmeticError) as exc:
                entry["error"] = str(exc)
            output.append(entry)
            print(
                json.dumps(
                    {
                        k: entry.get(k)
                        for k in (
                            "asset_id",
                            "case",
                            "excess_return",
                            "transactions",
                            "error",
                        )
                    }
                ),
                flush=True,
            )
            args.output.write_text(
                json.dumps(
                    {"selected": selected, "development": summary, "results": output},
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            )


if __name__ == "__main__":
    main()
