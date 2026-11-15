"""Research missed trend entries without changing production or the user database.

Run: PYTHONPATH=backend:scripts uv run python scripts/study_sp500_three_years.py
The plan is persisted before calculation; historical samples are already examined.
"""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np
import study_sp500_next_iteration as previous

from investor import db

OUT = Path("data/backtests/sp500-three-years.json")
BASE = dict(entry="daily_cross", exit="level1.5", cadence="monthly", warm=False)
PLAN = {
    "baseline": "Historical v3 baseline (before explicit v4 adoption), independent 75/25 budgets; slow60m / defensive18m; floor25%.",
    "hypotheses": [
        "Initialize slow state from earlier monthly decisions instead of resetting defensive.",
        "Detect a crossing between monthly decisions rather than on one daily interval only.",
        "Permit a sustained positive trend to enter without requiring a rare crossing.",
        "Avoid selling persistent trends merely because the regression residual is high.",
        "Compare monthly versus fixed Friday slow decisions; defensive unchanged.",
    ],
    "selection": "On 2018-09-17..2020-12-31 and 2021-01-04..2023-12-29 ONLY: CAGR >= baseline-0.2pp, DD absolute <= baseline+0.5pp, volatility <=1.20baseline, Sharpe>=baseline-0.05. Require average CAGR gain >=0.5pp. Rank worst CAGR gain then average gain. Freeze ONE before target/5y/10y audits; no fallback.",
    "adoption": "Target3y CAGR >= same ETF reference-2pp; 5y/10y CAGR>=baseline-0.2pp; all three DD absolute<=baseline+0.5pp, volatility<=1.20baseline, Sharpe>=baseline-0.05. At least12/14 rolling windows pass the same risk and CAGR-retention gates. Repeat target/5y/10y at fee1% and delay2; retain positive target CAGR gain and no worse DD by more than0.5pp. USD crises/long DD<=1.05baseline absolute. ALL required.",
    "execution": "Adjusted prefix-only signals, next raw close, whole shares per sleeve, fee0.5% per side, EUR10000, zero-interest cash, no leverage/transfers/netting. Warm state changes only initial targets, never credits earlier profits. Defensive cadence unchanged, anchored at each evaluation start.",
    "limitations": "Exploratory repeated historical research; target three years explicitly motivated by observed weakness. No unknown future sample. Overlapping rolling windows are not independent. Report all results and failures; no period-dependent rule.",
}


def grid():
    return [BASE] + [
        dict(entry=e, exit=x, cadence=c, warm=w)
        for e, x, c, w in product(
            ["daily_cross", "monthly_cross", "positive_band", "ma100", "ma200"],
            ["level1.5", "level2", "level2.5", "armed_ma50", "armed_ma100"],
            ["monthly", "friday"],
            [False, True],
        )
        if dict(entry=e, exit=x, cadence=c, warm=w) != BASE
    ]


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
    keep_trace=True,
    initial_capital=10000.0,
    exposure_caps=None,
):
    """Two independent sleeve accounts; optional pre-start replay has no capital."""
    feat, averages, momentum = features
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    n = len(configs)
    shares = np.array([c.get("slow_share", 0.75) for c in configs])
    capital = np.broadcast_to(np.asarray(initial_capital, dtype=float), (n,))
    cash = capital[:, None] * np.column_stack([shares, 1 - shares])
    units = np.zeros((n, 2))
    state = np.zeros((n, 2), dtype=bool)
    armed = np.zeros(n, dtype=bool)
    prior_decision = np.full(n, np.nan)
    last = np.full((n, 2), np.nan)
    entries = np.array([c["entry"] for c in configs])
    exits = np.array([c["exit"] for c in configs])
    warm = np.array([c["warm"] for c in configs])
    friday = np.array([c["cadence"] == "friday" for c in configs])
    floors = np.array([c.get("floor", 0.25) for c in configs])[:, None]
    defensive_entry = np.array([c.get("defensive_entry", -0.5) for c in configs])
    defensive_exit = np.array([c.get("defensive_exit", 1.5) for c in configs])
    defensive_step = np.array([c.get("defensive_step", 5) for c in configs])
    guard_ma = np.array([c.get("guard_ma", 0) for c in configs])
    guard_momentum = np.array([c.get("guard_momentum", 0) for c in configs])
    guard_cap = np.array([c.get("guard_cap", 0.25) for c in configs])[:, None]
    guard_scope = np.column_stack(
        [np.ones(n, dtype=bool), [c.get("guard_both", True) for c in configs]]
    )
    navs, fees, exposures = [capital.copy()], np.zeros(n), []
    trades = np.zeros(n, dtype=int)
    trace = []

    def decision(s, replay=False):
        nonlocal state, armed, prior_decision
        z = feat[60][0][s]
        prev = feat[60][0][s - 1] if s else np.nan
        month = s > 0 and days[s][:7] != days[s - 1][:7]
        scheduled = np.where(friday, date.fromisoformat(days[s]).weekday() == 4, month)
        scheduled &= np.isfinite(z)
        if replay:
            scheduled &= warm
        enter = np.full(n, z < -2)
        enter |= (entries == "daily_cross") & (prev < 0) & (z >= 0)
        enter |= (entries == "monthly_cross") & (prior_decision < 0) & (z >= 0)
        trend = (adjusted[s] > averages[200][s]) & (momentum[s] > 0)
        enter |= (entries == "positive_band") & trend & (z >= 0) & (z <= 1)
        for span in [100, 200]:
            enter |= (
                (entries == f"ma{span}")
                & (adjusted[s] > averages[span][s])
                & (momentum[s] > 0)
            )
        armed |= state[:, 0] & scheduled & (z > 1.5)
        sell = np.zeros(n, dtype=bool)
        for level in [1.5, 2, 2.5]:
            sell |= (exits == f"level{level}") & (z > level)
        for span in [50, 100]:
            sell |= (
                (exits == f"armed_ma{span}") & armed & (adjusted[s] < averages[span][s])
            )
        entering = ~state[:, 0] & scheduled & enter
        leaving = state[:, 0] & scheduled & sell
        state[:, 0] = (state[:, 0] & ~leaving) | entering
        armed &= ~(entering | leaving)
        prior_decision = np.where(scheduled, z, prior_decision)
        if not replay:
            z, prev = feat[18][0][s], feat[18][0][s - 1] if s else np.nan
            due = (s - lo) % defensive_step == 0
            if np.isfinite(z):
                proposed = np.where(
                    state[:, 1],
                    z <= defensive_exit,
                    (prev < defensive_entry) & (z >= defensive_entry),
                )
                state[:, 1] = np.where(due, proposed, state[:, 1])

    # State only, no pre-start positions, profits, transaction fees or curve points.
    if warm.any():
        has_friday = bool(friday.any())
        for s in range(lo):
            # Every state assignment is gated by the decision calendar. Skip
            # closes where neither calendar can change any warm state.
            monthly = s > 0 and days[s][:7] != days[s - 1][:7]
            if monthly or (has_friday and date.fromisoformat(days[s]).weekday() == 4):
                decision(s, replay=True)
    # Cold monthly crossing uses last scheduled score, without inheriting its state.
    for j, config in enumerate(configs):
        if not config["warm"]:
            prior_decision[j] = np.nan
    for i in range(lo + 1, hi):
        s = i - delay
        if s >= lo:
            decision(s)
            target = np.where(state, 1.0, floors)
            if exposure_caps is not None:
                target = np.minimum(target, exposure_caps[:, s, None])
            for span in [100, 200]:
                if np.any(guard_ma == span):
                    guarded = (
                        (guard_ma == span)
                        & (adjusted[s] < averages[span][s])
                        & (momentum[s] < guard_momentum)
                    )
                    target = np.where(
                        guarded[:, None] & guard_scope,
                        np.minimum(target, guard_cap),
                        target,
                    )
            changed = target != last
            value = cash + units * raw[i]
            old = units * raw[i]
            buying = target * value > old
            amount = (
                target
                * (value + np.where(buying, fee * old, -fee * old))
                / (1 + np.where(buying, fee * target, -fee * target))
            )
            new = amount / raw[i]
            if whole:
                new = np.floor(new + 1e-10)
            new = np.where(changed, new, units)
            delta = new - units
            cost = np.abs(delta) * raw[i] * fee
            cash -= delta * raw[i] + cost
            if np.any(cash < -1e-6):
                raise AssertionError("Borrowing")
            fees += cost.sum(axis=1)
            trades += (np.abs(delta) > 1e-8).sum(axis=1)
            units, last = new, target
            if keep_curve and keep_trace:
                trace.append(
                    dict(
                        signal=days[s],
                        execution=days[i],
                        state=state.tolist(),
                        units=units.tolist(),
                        cash=cash.tolist(),
                    )
                )
        nav = (cash + units * raw[i]).sum(axis=1)
        navs.append(nav)
        exposures.append((units * raw[i]).sum(axis=1) / nav)
    navs = np.array(navs)
    changes = navs[1:] / navs[:-1] - 1
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    vol = changes.std(axis=0, ddof=1) * np.sqrt(252)
    sharpe = np.divide(
        changes.mean(axis=0) * 252, vol, out=np.zeros(n), where=vol > 1e-12
    )
    dd = (navs / np.maximum.accumulate(navs, axis=0) - 1).min(axis=0)
    metrics = [
        dict(
            cagr=float((navs[-1, j] / capital[j]) ** (1 / years) - 1),
            volatility=float(vol[j]),
            sharpe=float(sharpe[j]),
            max_drawdown=float(dd[j]),
            fees=float(fees[j]),
            final_value=float(navs[-1, j]),
            exposure=float(np.mean(exposures, axis=0)[j]),
            trades=int(trades[j]),
        )
        for j in range(n)
    ]
    return dict(
        metrics=metrics,
        curve=navs.tolist() if keep_curve else None,
        trace=trace if keep_curve and keep_trace else None,
    )


def gate(m, b):
    return bool(
        m["cagr"] >= b["cagr"] - 0.002
        and abs(m["max_drawdown"]) <= abs(b["max_drawdown"]) + 0.005
        and m["volatility"] <= 1.20 * b["volatility"]
        and m["sharpe"] >= b["sharpe"] - 0.05
    )


def main():
    configs = grid()
    report = dict(plan=PLAN, configs=configs, count=len(configs), adopt=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    def save():
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    save()
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
        features = previous.prepare(days, adjusted)
        frozen = json.loads(
            Path(
                "data/backtests/sp500-reentry-production-verification.json"
            ).read_text()
        )
        if report["snapshot_sha256"] != frozen["snapshot_sha256"]:
            raise ValueError(
                "Snapshot differs from the archived production verification"
            )
        for name, archived in frozen["results"].items():
            m = simulate(
                days,
                raw,
                adjusted,
                features,
                [BASE],
                [archived["start"], archived["end"]],
            )["metrics"][0]
            for key in ["cagr", "volatility", "sharpe", "max_drawdown"]:
                if abs(m[key] - archived["metrics"]["strategy"][key]) > 1e-9:
                    raise AssertionError((name, key, "Production mismatch"))
            if abs(m["fees"] - archived["metrics"]["strategy"]["cost_eur"]) > 1e-6:
                raise AssertionError((name, "Fees mismatch"))
        report["baseline_matches_production_cases"] = len(frozen["results"])
        periods = dict(
            train=["2018-09-17", "2020-12-31"],
            validation=["2021-01-04", "2023-12-29"],
            three_years=["2023-11-13", days[-1]],
            five_years=["2021-11-13", days[-1]],
            ten_years=["2016-11-13", days[-1]],
        )
        results = {}
        for name in ["train", "validation"]:
            results[name] = simulate(
                days, raw, adjusted, features, configs, periods[name]
            )["metrics"]
        qualified = [
            j
            for j in range(1, len(configs))
            if all(gate(results[k][j], results[k][0]) for k in ["train", "validation"])
            and np.mean(
                [
                    results[k][j]["cagr"] - results[k][0]["cagr"]
                    for k in ["train", "validation"]
                ]
            )
            >= 0.005
        ]
        selected = (
            max(
                qualified,
                key=lambda j: (
                    min(
                        results[k][j]["cagr"] - results[k][0]["cagr"]
                        for k in ["train", "validation"]
                    ),
                    np.mean(
                        [
                            results[k][j]["cagr"] - results[k][0]["cagr"]
                            for k in ["train", "validation"]
                        ]
                    ),
                ),
            )
            if qualified
            else None
        )
        report.update(
            periods=periods,
            results=results,
            qualified=qualified,
            selected_index=selected,
            selected=configs[selected] if selected is not None else None,
        )
        save()
        print(
            "Selection frozen",
            len(configs),
            "configurations",
            len(qualified),
            "qualified",
            report["selected"],
            flush=True,
        )
        for name in ["three_years", "five_years", "ten_years"]:
            results[name] = simulate(
                days, raw, adjusted, features, configs, periods[name]
            )["metrics"]
        reference = {}
        for name, p in periods.items():
            lo = int(np.searchsorted(days, p[0]))
            hi = int(np.searchsorted(days, p[1], side="right"))
            units = np.floor(10000 / (raw[lo + 1] * 1.005))
            cash = 10000 - units * raw[lo + 1] * 1.005
            nav = np.r_[10000, cash + units * raw[lo + 1 : hi]]
            changes = nav[1:] / nav[:-1] - 1
            years = (
                date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
            ).days / 365.25
            vol = changes.std(ddof=1) * np.sqrt(252)
            reference[name] = dict(
                cagr=float((nav[-1] / 10000) ** (1 / years) - 1),
                volatility=float(vol),
                max_drawdown=float((nav / np.maximum.accumulate(nav) - 1).min()),
                sharpe=float(changes.mean() * 252 / vol),
                final_value=float(nav[-1]),
            )
        report["reference"] = reference
        report["rolling"] = {
            f"{span}y_{year}": simulate(
                days,
                raw,
                adjusted,
                features,
                configs,
                [f"{year}-11-13", f"{year + span}-11-13"],
            )["metrics"]
            for span in [3, 5]
            for year in range(2016, 2027 - span)
        }
        report["rolling_pass"] = [
            sum(gate(ms[j], ms[0]) for ms in report["rolling"].values())
            for j in range(len(configs))
        ]
        # All candidates shown for transparency, never reselect from target outcomes.
        report["target_gates_pass"] = [
            j
            for j in range(1, len(configs))
            if all(
                gate(results[k][j], results[k][0])
                for k in ["three_years", "five_years", "ten_years"]
            )
            and results["three_years"][j]["cagr"]
            >= reference["three_years"]["cagr"] - 0.02
        ]
        if selected is not None:
            pair = [BASE, configs[selected]]
            report["stress"] = {
                name: {
                    k: simulate(days, raw, adjusted, features, pair, periods[k], **kw)[
                        "metrics"
                    ]
                    for k in ["three_years", "five_years", "ten_years"]
                }
                for name, kw in [("fee1pct", dict(fee=0.01)), ("delay2", dict(delay=2))]
            }
            pdays = [r[0] for r in proxy]
            prices = np.array([r[1] for r in proxy])
            pf = previous.prepare(pdays, prices)
            report["usd_proxy"] = {
                k: simulate(pdays, prices, prices, pf, pair, p, whole=False)["metrics"]
                for k, p in [
                    ("dotcom", ["2000-01-03", "2003-12-31"]),
                    ("crisis", ["2007-01-03", "2009-12-31"]),
                    ("long", ["1993-01-04", pdays[-1]]),
                ]
            }
            report["adopt"] = bool(
                selected in report["target_gates_pass"]
                and report["rolling_pass"][selected] >= 12
                and all(
                    ms[1]["cagr"] >= ms[0]["cagr"]
                    and abs(ms[1]["max_drawdown"]) <= abs(ms[0]["max_drawdown"]) + 0.005
                    for cases in report["stress"].values()
                    for ms in cases.values()
                )
                and all(
                    abs(ms[1]["max_drawdown"]) <= 1.05 * abs(ms[0]["max_drawdown"])
                    for ms in report["usd_proxy"].values()
                )
            )
        save()
        print(
            "Completed",
            OUT,
            "adopt",
            report["adopt"],
            "target passes",
            len(report["target_gates_pass"]),
            flush=True,
        )
        for k in ["three_years", "five_years", "ten_years"]:
            print(
                k,
                "baseline",
                results[k][0],
                "reference",
                reference[k],
                "selected",
                results[k][selected] if selected is not None else None,
                flush=True,
            )


if __name__ == "__main__":
    main()
