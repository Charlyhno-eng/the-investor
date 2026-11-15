"""Compare fixed experimental variants on a copied database, never tune parameters."""

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


def main():
    output = Path("data/backtests/allocation-improvements.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "protocol": "Tolerance 0.03; OAS covariance; residual half-life <=63 and shift <=1. Separate variants, no tuning. Retrospective periods, not unseen validation.",
        "results": {},
    }
    with tempfile.TemporaryDirectory() as directory:
        frozen = Path(directory) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as source,
            sqlite3.connect(frozen) as destination,
        ):
            source.backup(destination)
        report["snapshot_sha256"] = hashlib.sha256(frozen.read_bytes()).hexdigest()
        original = db.DATA_DIR
        db.DATA_DIR = Path(directory)
        try:
            for universe in ("journal_14", "actions_11", "crypto_4"):
                for period, (start, end) in PERIODS.items():
                    for mode in (
                        "volatility",
                        "correlation",
                        "risk_parity",
                        "mean_reversion",
                    ):
                        base = ValidationRequest(
                            asset_ids=UNIVERSES[universe],
                            mode=mode,
                            whole_shares=True,
                            start_date=date.fromisoformat(start),
                            end_date=date.fromisoformat(end),
                            reversion_entry_z=2,
                            reversion_exit_z=2,
                            reversion_exit_mode="trailing_z",
                            reversion_trailing_gap=1,
                            reversion_funding_min_z=0.3,
                        )
                        inputs = load_inputs(base)
                        variants = {"control": {}}
                        if mode == "mean_reversion":
                            variants["quality"] = {"reversion_quality_filter": True}
                        else:
                            variants["tolerance"] = {"rebalance_tolerance": 0.03}
                        if mode == "volatility":
                            variants["oas"] = {"regularize_covariance": True}
                        for name, changes in variants.items():
                            request = base.model_copy(update=changes)
                            result = validation_data(**inputs, request=request)
                            key = f"{universe}:{period}:{mode}:{name}"
                            report["results"][key] = {
                                k: result[k]
                                for k in (
                                    "status",
                                    "metrics",
                                    "parameters",
                                    "message",
                                    "transactions",
                                )
                                if k in result
                            }
                            print(key, result["status"], flush=True)
                            output.write_text(json.dumps(report, indent=2) + "\n")
        finally:
            db.DATA_DIR = original


if __name__ == "__main__":
    main()
