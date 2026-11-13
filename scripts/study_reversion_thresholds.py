"""Chronological, finite search of regression-deviation strategies on frozen data.

PYTHONPATH=backend uv run python scripts/study_reversion_thresholds.py
The shortlist and winner use calibration/validation only, never the final test.
"""

import argparse
import hashlib
import json
import sqlite3
import tempfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from audit_validation import UNIVERSES, summarize

from investor import db
from investor.portfolio.validation import ValidationRequest, portfolio_validation


@dataclass(frozen=True)
class Candidate:
    name: str
    entry: float
    exit: float
    mode: str = "threshold"
    funding: float = 0

    def parameters(self):
        return {
            "reversion_entry_z": self.entry,
            "reversion_exit_z": self.exit,
            "reversion_exit_mode": self.mode,
            "reversion_funding_min_z": self.funding,
            "reversion_trailing_gap": 0.5,
        }


def candidates():
    symmetric = [
        Candidate(f"symmetric_{z:g}", z, z)
        for z in (0.8, 1, 1.2, 1.4, 1.6, 1.8, 2, 2.2)
    ]
    asymmetric = [
        Candidate(f"asymmetric_{e:g}_{x:g}", e, x)
        for e in (1.2, 1.6, 2)
        for x in (0, 0.7, 1.4, 2.1)
    ]
    trailing = [
        Candidate(f"trailing_{z:g}", z, z, "trailing_z")
        for z in (1.2, 1.4, 1.6, 1.8, 2)
    ]
    funding = [Candidate(f"funding_0.5_{z:g}", z, z, funding=0.5) for z in (1.4, 1.6)]
    return symmetric + asymmetric + trailing + funding


def ranked(results, baseline):
    reference = results[baseline]["metrics"]["strategy"]
    eligible = [
        name
        for name, r in results.items()
        if r["transactions"] >= 8
        and r["metrics"]["strategy"]["cagr"] >= reference["cagr"] - 1e-12
        and r["metrics"]["strategy"]["max_drawdown"] >= reference["max_drawdown"] - 0.05
    ]
    return sorted(
        eligible,
        key=lambda name: (
            results[name]["metrics"]["strategy"]["calmar"] or -1e9,
            results[name]["metrics"]["strategy"]["cagr"],
            name,
        ),
        reverse=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/backtests/reversion-threshold-study.json"),
    )
    parser.add_argument(
        "--snapshot", type=Path, help="Optional existing SQLite archive"
    )
    args = parser.parse_args()
    grid = candidates()
    by_name = {c.name: c for c in grid}
    baseline = "symmetric_1.4"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source = args.snapshot or db.DATA_DIR / "investor.sqlite3"
    with tempfile.TemporaryDirectory(prefix="investor-thresholds-") as temporary:
        frozen = Path(temporary) / "investor.sqlite3"
        with (
            sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True) as src,
            sqlite3.connect(frozen) as dst,
        ):
            src.backup(dst)
        digest = hashlib.sha256(frozen.read_bytes()).hexdigest()
        # Pin every run to the same prices. Any refresh jobs stay in this copy.
        db.DATA_DIR = Path(temporary)
        result = {
            "created": date.today().isoformat(),
            "snapshot_sha256": digest,
            "universe": UNIVERSES["journal_14"],
            "grid": [asdict(c) for c in grid],
            "selection_rule": "Calmar, CAGR >= baseline, drawdown no more than 5 pp worse, >=8 operations",
            "calibration": {},
            "validation": {},
            "test": {},
            "full_five_years": {},
            "robustness": {},
        }

        def checkpoint():
            args.output.write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n"
            )

        def run(candidate, start, end, ids=None, fee=0.005):
            request = ValidationRequest(
                asset_ids=ids or UNIVERSES["journal_14"],
                mode="mean_reversion",
                years=10,
                initial_capital=10000,
                fee_rate=fee,
                whole_shares=True,
                start_date=start,
                end_date=end,
                **candidate.parameters(),
            )
            measured = portfolio_validation(request)
            if measured["status"] != "ready":
                raise RuntimeError(f"{candidate.name}: {measured}")
            summary = summarize(measured)
            m = summary["metrics"]["strategy"]
            print(
                f"{start}..{end} {candidate.name}: net={m['total_return']:.2%} DD={m['max_drawdown']:.2%} costs={m['cost_eur']:.2f}",
                flush=True,
            )
            return summary

        # Stage boundaries and all 27 trials are fixed before any results exist.
        for c in grid:
            result["calibration"][c.name] = run(c, "2016-11-14", "2021-11-12")
            checkpoint()
        shortlist = list(
            dict.fromkeys([baseline, *ranked(result["calibration"], baseline)[:5]])
        )
        result["shortlist"] = shortlist
        for name in shortlist:
            result["validation"][name] = run(by_name[name], "2021-11-15", "2024-11-14")
            checkpoint()
        validation_rank = ranked(result["validation"], baseline)
        winner = validation_rank[0] if validation_rank else baseline
        result["selected_before_final_test"] = winner
        checkpoint()
        for name in dict.fromkeys([baseline, winner]):
            result["test"][name] = run(by_name[name], "2024-11-15", "2026-11-13")
            checkpoint()
        # Descriptive five-year table, computed only AFTER freezing the winner.
        for c in [
            c for c in grid if c.name.startswith("symmetric_") or c.name == winner
        ]:
            result["full_five_years"][c.name] = run(c, "2021-11-15", "2026-11-13")
            checkpoint()
        for universe in ("actions_11", "crypto_4"):
            for name in dict.fromkeys([baseline, winner]):
                result["robustness"][f"{universe}:{name}"] = run(
                    by_name[name], "2021-11-15", "2026-11-13", ids=UNIVERSES[universe]
                )
                checkpoint()
        for name in dict.fromkeys([baseline, winner]):
            result["robustness"][f"fee_1pct:{name}"] = run(
                by_name[name], "2021-11-15", "2026-11-13", fee=0.01
            )
            checkpoint()
        print(f"Frozen selection: {winner}. Report: {args.output}", flush=True)


if __name__ == "__main__":
    main()
