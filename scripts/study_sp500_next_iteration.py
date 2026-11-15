"""Frozen-protocol exploration of the adopted two-sleeve ESE policy.

Run: PYTHONPATH=backend:scripts uv run python scripts/study_sp500_next_iteration.py
Research only: the user database is opened read-only and backed up privately.
"""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np
import study_sp500_regression as old

from investor import db

OUT = Path("data/backtests/sp500-next-iteration.json")
BASE = dict(
    exit="level",
    recovery="none",
    floor=0.25,
    slow_share=0.75,
    weekly=False,
    scope="slow",
)
PLAN = {
    "baseline": "Adopted slow_defensive_v2, independent75/25 initial budgets, no rebalancing between sleeves.",
    "hypotheses": [
        "Retain overbought trends until a price moving-average break after arming at+1.5sigma",
        "Earlier slow-sleeve recovery when trend and63-session momentum recover",
        "Different defensive floors and initial sleeve split",
        "Fixed Friday defensive calendar instead of simulation-anchored5sessions",
    ],
    "selection": "Choose ONE on2018-09-17..2020-12-31 and2021-01-04..2023-12-29 only. Require CAGR gain>=0.5percentage point on BOTH, no worse absolute DD and volatility<=1.15baseline; Sharpe>=baseline-0.03; rank worst CAGR gain, then Sharpe. Freeze before later/5y/10y/rolling/stress/USD audits. No fallback candidate after failure.",
    "adoption": "On later2024+,5y,10y: gain>=0.3percentage point, DD no worse, volatility<=1.15baseline, Sharpe>=baseline-0.03. At least12/14rolling windows: CAGR>=baseline-0.2point, DD<=baseline+0.5point absolute, vol<=1.15baseline. Fee1% and delay2sessions5/10y retain positive CAGR gain and no worse DD. USD2000-03,2007-09,1993+ DD<=1.05baseline. All gates must pass.",
    "execution": "ESE EUR only;10000EUR, independent integer-share ledgers,0.5% each side, next close, zero-yield cash, no leverage/netting/transfers; decisions from known adjusted prices only.",
    "limits": "All historical data already examined; no untouched or future sample. Selection bias and repeated testing. USD total-return index is a diagnostic, not an ESE/PEA tradeable history.",
}


def grid():
    return [
        dict(exit=e, recovery=r, floor=f, slow_share=w, weekly=c, scope=s)
        for e, r, f, w, c, s in product(
            ["level", "trail_0.5", "trail_1", "trend50", "trend100", "trend200"],
            ["none", "ma100", "ma200", "rebound0"],
            [0.25, 0.35, 0.45],
            [0.5, 0.75, 0.9],
            [False, True],
            ["slow", "both"],
        )
        if e != "level" or s == "slow"
    ]


def prepare(days, prices):
    feat, _ = old.features(days, prices)
    averages = {}
    for span in [50, 100, 200]:
        a = np.full(len(days), np.nan)
        for i in range(span - 1, len(days)):
            a[i] = prices[i - span + 1 : i + 1].mean()
        averages[span] = a
    momentum = np.full(len(days), np.nan)
    momentum[63:] = prices[63:] / prices[:-63] - 1
    return feat, averages, momentum


def simulate(
    days,
    raw,
    adjusted,
    features,
    configs,
    period,
    *,
    fee=0.005,
    delay=1,
    whole=True,
    keep_curve=False,
):
    """Two self-financing sleeve books per candidate; prefix-only decisions."""
    feat, averages, momentum = features
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    n = len(configs)
    shares = np.array([c["slow_share"] for c in configs])
    cash = 10000 * np.column_stack([shares, 1 - shares])
    units = np.zeros((n, 2))
    state = np.zeros((n, 2), dtype=bool)
    armed = np.zeros((n, 2), dtype=bool)
    peak_z = np.full((n, 2), -np.inf)
    last = np.full((n, 2), np.nan)
    floors = np.array([c["floor"] for c in configs])[:, None]
    exit_modes = np.array([c["exit"] for c in configs])
    recoveries = np.array([c["recovery"] for c in configs])
    scopes = np.array([c["scope"] for c in configs])
    weekly = np.array([c["weekly"] for c in configs])
    recovery_z = np.array(
        [
            0.0
            if c["recovery"] == "rebound0"
            else float(c["recovery"].split("_", 1)[1])
            if c["recovery"].startswith("rebound_")
            else np.nan
            for c in configs
        ]
    )
    navs, fees = [np.full(n, 10000.0)], np.zeros(n)
    for i in range(lo + 1, hi):
        s = i - delay
        if s >= lo:
            scores = np.array([feat[60][0][s], feat[18][0][s]])
            prev = np.array([feat[60][0][max(0, s - 1)], feat[18][0][max(0, s - 1)]])
            month = s > 0 and days[s][:7] != days[s - 1][:7]
            scheduled = np.column_stack(
                [
                    np.full(n, month),
                    np.where(
                        weekly,
                        date.fromisoformat(days[s]).weekday() == 4,
                        (s - lo) % 5 == 0,
                    ),
                ]
            ) & np.isfinite(scores)
            # State changes use prior state, so exit and entry cannot coincide.
            entry = np.column_stack(
                [
                    np.full(n, scores[0] < -2),
                    np.full(n, prev[1] < -0.5 and scores[1] >= -0.5),
                ]
            )
            for span in [100, 200]:
                recovery = (
                    (recoveries == f"ma{span}")
                    & (adjusted[s] > averages[span][s])
                    & (momentum[s] > 0)
                    & (scores[0] < 0.5)
                )
                entry[:, 0] |= recovery
            entry[:, 0] |= (
                np.isfinite(recovery_z)
                & (prev[0] < recovery_z)
                & (scores[0] >= recovery_z)
            )
            peak_z = np.where(state & scheduled, np.maximum(peak_z, scores), peak_z)
            armed |= state & scheduled & (scores > 1.5)
            sell = np.broadcast_to(scores > 1.5, (n, 2)).copy()
            for j in range(2):
                affected = np.full(n, j == 0) | (scopes == "both")
                for mode, distance in [("trail_0.5", 0.5), ("trail_1", 1.0)]:
                    mask = affected & (exit_modes == mode)
                    sell[mask, j] = armed[mask, j] & (
                        peak_z[mask, j] - scores[j] >= distance
                    )
                for span in [50, 100, 200]:
                    mask = affected & (exit_modes == f"trend{span}")
                    sell[mask, j] = armed[mask, j] & (adjusted[s] < averages[span][s])
            enter = ~state & scheduled & entry
            leave = state & scheduled & sell
            state = (state & ~leave) | enter
            armed = np.where(enter | leave, False, armed)
            peak_z = np.where(enter, scores, np.where(leave, -np.inf, peak_z))
            target = np.where(state, 1.0, floors)
            changed = target != last
            value = cash + units * raw[i]
            old_value = units * raw[i]
            buying = target * value > old_value
            amount = (
                target
                * (value + np.where(buying, fee * old_value, -fee * old_value))
                / (1 + np.where(buying, fee * target, -fee * target))
            )
            new_units = amount / raw[i]
            if whole:
                new_units = np.floor(new_units + 1e-10)
            new_units = np.where(changed, new_units, units)
            delta = new_units - units
            cost = np.abs(delta) * raw[i] * fee
            cash -= delta * raw[i] + cost
            if np.any(cash < -1e-6):
                raise AssertionError("Borrowing")
            fees += cost.sum(axis=1)
            units = new_units
            last = target
        navs.append((cash + units * raw[i]).sum(axis=1))
    navs = np.array(navs)
    changes = navs[1:] / navs[:-1] - 1
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    vol = changes.std(axis=0, ddof=1) * np.sqrt(252)
    sharp = np.divide(
        changes.mean(axis=0) * 252, vol, out=np.zeros(n), where=vol > 1e-12
    )
    dd = (navs / np.maximum.accumulate(navs, axis=0) - 1).min(axis=0)
    metrics = [
        dict(
            cagr=float((navs[-1, j] / 10000) ** (1 / years) - 1),
            volatility=float(vol[j]),
            sharpe=float(sharp[j]),
            max_drawdown=float(dd[j]),
            fees=float(fees[j]),
            final_value=float(navs[-1, j]),
        )
        for j in range(n)
    ]
    return dict(metrics=metrics, curve=navs.tolist() if keep_curve else None)


def gate(m, b, gain=0.005):
    return bool(
        m["cagr"] >= b["cagr"] + gain
        and abs(m["max_drawdown"]) <= abs(b["max_drawdown"]) + 1e-12
        and m["volatility"] <= 1.15 * b["volatility"]
        and m["sharpe"] >= b["sharpe"] - 0.03
    )


def main():
    configs = grid()
    report = dict(plan=PLAN, configs=configs, candidate_count=len(configs))
    OUT.parent.mkdir(parents=True, exist_ok=True)
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
        report["snapshot_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-ese.pa' ORDER BY o.date"
            ).fetchall()
            proxy = conn.execute(
                "SELECT date,value FROM reference_observations WHERE symbol='^SP500TR' ORDER BY date"
            ).fetchall()
        days = [r[0] for r in rows]
        adjusted, raw = np.array([[r[1], r[2]] for r in rows]).T
        features = prepare(days, adjusted)
        # Assert the NEW research engine reproduces all15 archived production baselines.
        archived = json.loads(
            Path(
                "data/backtests/sp500-compromise-production-verification.json"
            ).read_text()
        )
        report["matches_old_snapshot"] = (
            report["snapshot_sha256"] == archived["snapshot_sha256"]
        )
        # The application now runs v3. Keep this study's v2 comparison fixed
        # against its archived production output rather than the changing engine.
        for name, result in archived["results"].items():
            period = [result["start"], result["end"]]
            m = simulate(days, raw, adjusted, features, [BASE], period)["metrics"][0]
            for key in ["cagr", "volatility", "sharpe", "max_drawdown"]:
                if abs(m[key] - result["metrics"]["strategy"][key]) > 1e-9:
                    raise AssertionError((name, key, "historical v2 baseline changed"))
            if abs(m["fees"] - result["metrics"]["strategy"]["cost_eur"]) > 1e-6:
                raise AssertionError((name, "historical v2 fees changed"))
        report["baseline_matches_15_production_cases"] = True
        periods = {
            "train": ["2018-09-17", "2020-12-31"],
            "validation": ["2021-01-04", "2023-12-29"],
            "later": ["2024-01-02", days[-1]],
            "five_years": ["2021-11-13", days[-1]],
            "ten_years": ["2016-11-13", days[-1]],
        }
        results = {}
        for name in ["train", "validation"]:
            result = simulate(
                days, raw, adjusted, features, [BASE] + configs, periods[name]
            )["metrics"]
            results[name] = dict(baseline=result[0], candidates=result[1:])
        qualified = [
            i
            for i in range(len(configs))
            if all(
                gate(results[k]["candidates"][i], results[k]["baseline"])
                for k in ["train", "validation"]
            )
        ]
        selected = (
            max(
                qualified,
                key=lambda i: (
                    min(
                        results[k]["candidates"][i]["cagr"]
                        - results[k]["baseline"]["cagr"]
                        for k in ["train", "validation"]
                    ),
                    min(
                        results[k]["candidates"][i]["sharpe"]
                        for k in ["train", "validation"]
                    ),
                ),
            )
            if qualified
            else None
        )
        report.update(
            results=results,
            qualified_count=len(qualified),
            selected_index=selected,
            selected=configs[selected] if selected is not None else None,
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            "Selection frozen:",
            len(configs),
            "candidates;",
            len(qualified),
            "qualified;",
            report["selected"],
            flush=True,
        )
        # All candidates below are descriptive only; no re-selection from later outcomes.
        for name in ["later", "five_years", "ten_years"]:
            result = simulate(
                days, raw, adjusted, features, [BASE] + configs, periods[name]
            )["metrics"]
            results[name] = dict(baseline=result[0], candidates=result[1:])
        descriptive = [
            i
            for i in range(len(configs))
            if all(
                gate(results[k]["candidates"][i], results[k]["baseline"], 0.003)
                for k in ["five_years", "ten_years"]
            )
        ]
        report["descriptive_5_10_pass_count"] = len(descriptive)
        audit_index = (
            selected
            if selected is not None
            else (descriptive[0] if len(descriptive) == 1 else None)
        )
        report["audit_index"] = audit_index
        report["audit_reason"] = (
            "Selected candidate"
            if selected is not None
            else "ADDITIONAL POST-HOC diagnostic of the sole5/10 qualifying candidate; not selected by the initial protocol, no silent fallback or automatic adoption."
        )
        report["adopt"] = False
        if audit_index is not None:
            pair = [BASE, configs[audit_index]]

            def run(period, **kw):
                b, m = simulate(days, raw, adjusted, features, pair, period, **kw)[
                    "metrics"
                ]
                return dict(baseline=b, candidate=m)

            report["rolling"] = {
                f"{span}y_{year}": run([f"{year}-11-13", f"{year + span}-11-13"])
                for span in [3, 5]
                for year in range(2016, 2027 - span)
            }
            report["rolling_pass"] = sum(
                m["candidate"]["cagr"] >= m["baseline"]["cagr"] - 0.002
                and abs(m["candidate"]["max_drawdown"])
                <= abs(m["baseline"]["max_drawdown"]) + 0.005
                and m["candidate"]["volatility"] <= 1.15 * m["baseline"]["volatility"]
                for m in report["rolling"].values()
            )
            report["stress"] = {
                name: {k: run(periods[k], **kw) for k in ["five_years", "ten_years"]}
                for name, kw in [("fee1pct", {"fee": 0.01}), ("delay2", {"delay": 2})]
            }
            p_days = [r[0] for r in proxy]
            p_raw = np.array([r[1] for r in proxy])
            p_f = prepare(p_days, p_raw)
            report["usd_proxy"] = {
                k: dict(
                    zip(
                        ["baseline", "candidate"],
                        simulate(p_days, p_raw, p_raw, p_f, pair, period, whole=False)[
                            "metrics"
                        ],
                        strict=True,
                    )
                )
                for k, period in [
                    ("dotcom", ["2000-01-03", "2003-12-31"]),
                    ("crisis", ["2007-01-03", "2009-12-31"]),
                    ("long", ["1993-01-04", p_days[-1]]),
                ]
            }
            report["adopt"] = bool(
                selected is not None
                and all(
                    gate(
                        results[k]["candidates"][selected],
                        results[k]["baseline"],
                        0.003,
                    )
                    for k in ["later", "five_years", "ten_years"]
                )
                and report["rolling_pass"] >= 12
                and all(
                    gate(v["candidate"], v["baseline"], 0)
                    for rows in report["stress"].values()
                    for v in rows.values()
                )
                and all(
                    abs(v["candidate"]["max_drawdown"])
                    <= 1.05 * abs(v["baseline"]["max_drawdown"])
                    for v in report["usd_proxy"].values()
                )
            )
        report["sensitivity_plan"] = (
            "ADDITIONAL exploratory diagnostic, defined after792-grid result: same incumbent plus monthly slow recovery crossing at-0.5/-0.25/0/+0.25/+0.5sigma. All other parameters unchanged. Examine all5 periods and14rolling windows. No reselection and no automatic adoption from these already examined data."
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        thresholds = [-0.5, -0.25, 0.0, 0.25, 0.5]
        sensitivity = [{**BASE, "recovery": f"rebound_{level}"} for level in thresholds]
        report["sensitivity"] = dict(thresholds=thresholds, periods={}, rolling={})
        for name, period in periods.items():
            report["sensitivity"]["periods"][name] = simulate(
                days, raw, adjusted, features, [BASE] + sensitivity, period
            )["metrics"]
        for span in [3, 5]:
            for year in range(2016, 2027 - span):
                name = f"{span}y_{year}"
                report["sensitivity"]["rolling"][name] = simulate(
                    days,
                    raw,
                    adjusted,
                    features,
                    [BASE] + sensitivity,
                    [f"{year}-11-13", f"{year + span}-11-13"],
                )["metrics"]
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            "Completed",
            OUT,
            "adopt=",
            report["adopt"],
            "descriptive5/10passes=",
            report["descriptive_5_10_pass_count"],
            flush=True,
        )
        if audit_index is not None:
            print(
                json.dumps(
                    {
                        k: dict(
                            baseline=results[k]["baseline"],
                            candidate=results[k]["candidates"][audit_index],
                        )
                        for k in periods
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    main()
