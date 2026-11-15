"""Additional diagnostics of the frozen warm-state candidate; no reselection.

Run: PYTHONPATH=backend:scripts uv run python scripts/audit_sp500_three_years.py
Monthly starts test sensitivity beyond the November-only rolling windows.
"""

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import study_sp500_three_years as study

from investor import db

OUT = Path("data/backtests/sp500-three-years-audit.json")


def main():
    frozen = json.loads(study.OUT.read_text())
    candidate = frozen["selected"]
    if candidate != {**study.BASE, "warm": True}:
        raise ValueError("Audit is restricted to the previously frozen warm-state rule")
    report = dict(
        candidate=candidate,
        plan="Additional diagnostic after initial gates failed: all completed monthly starts on ESE from2016, horizons3/5y, unchanged end-boundary month/day. Compare cold/warm CAGR, DD, volatility, Sharpe. Report ALL windows and worst regressions, no reselection or relaxed adoption. Also evaluate1y and continuous10y curve's last3y; these are different investment experiments. No automatic adoption.",
        initial_adoption_passed=frozen["adopt"],
        monthly={},
    )
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as source,
            sqlite3.connect(path) as dest,
        ):
            source.backup(dest)
        fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
        if fingerprint != frozen["snapshot_sha256"]:
            raise ValueError("Research snapshot has changed")
        report["snapshot_sha256"] = fingerprint
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-ese.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        adjusted, raw = np.array([[r[1], r[2]] for r in rows]).T
        features = study.previous.prepare(days, adjusted)
        pair = [study.BASE, candidate]
        for span in [3, 5]:
            for year in range(2016, 2027 - span):
                for month in range(1, 13):
                    period = [f"{year}-{month:02d}-13", f"{year + span}-{month:02d}-13"]
                    if period[1] > days[-1]:
                        continue
                    name = f"{span}y_{year}_{month:02d}"
                    report["monthly"][name] = study.simulate(
                        days, raw, adjusted, features, pair, period
                    )["metrics"]
                print("Monthly starts", span, year, "complete", flush=True)
        windows = list(report["monthly"].items())
        report["summary"] = dict(
            count=len(windows),
            gain=sum(ms[1]["cagr"] > ms[0]["cagr"] + 1e-10 for _, ms in windows),
            unchanged=sum(
                abs(ms[1]["cagr"] - ms[0]["cagr"]) <= 1e-10 for _, ms in windows
            ),
            loss=sum(ms[1]["cagr"] < ms[0]["cagr"] - 1e-10 for _, ms in windows),
            risk_gate_pass=sum(study.gate(ms[1], ms[0]) for _, ms in windows),
            worst_cagr_window=min(
                windows, key=lambda w: w[1][1]["cagr"] - w[1][0]["cagr"]
            )[0],
            worst_dd_window=max(
                windows,
                key=lambda w: (
                    abs(w[1][1]["max_drawdown"]) - abs(w[1][0]["max_drawdown"])
                ),
            )[0],
            worse_dd_count=sum(
                abs(ms[1]["max_drawdown"]) > abs(ms[0]["max_drawdown"]) + 0.005
                for _, ms in windows
            ),
        )
        report["one_year"] = study.simulate(
            days, raw, adjusted, features, pair, ["2025-11-13", days[-1]]
        )["metrics"]
        continuous = study.simulate(
            days,
            raw,
            adjusted,
            features,
            [study.BASE],
            frozen["periods"]["ten_years"],
            keep_curve=True,
        )
        start = int(np.searchsorted(days, frozen["periods"]["ten_years"][0]))
        three = int(np.searchsorted(days, frozen["periods"]["three_years"][0]))
        nav = np.array(continuous["curve"])[three - start :, 0]
        changes = nav[1:] / nav[:-1] - 1
        report["continuous_ten_year_last_three"] = dict(
            total_return=float(nav[-1] / nav[0] - 1),
            volatility=float(changes.std(ddof=1) * np.sqrt(252)),
            max_drawdown=float((nav / np.maximum.accumulate(nav) - 1).min()),
            first_value=float(nav[0]),
            final_value=float(nav[-1]),
        )
        report["adopt"] = False
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(json.dumps(report["summary"], indent=2), flush=True)
        print("one year", report["one_year"], flush=True)


if __name__ == "__main__":
    main()
