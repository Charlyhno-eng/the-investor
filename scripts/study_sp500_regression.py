"""Large, chronology-safe ESE search. Research only; never changes application rules.

Run: PYTHONPATH=backend uv run python scripts/study_sp500_regression.py
"""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np

from investor import db
from investor.assets.momentum import months_before

OUT = Path("data/backtests/sp500-regression-study.json")
PROTOCOL = {
    "asset": "yf-ese.pa",
    "capital": 10000,
    "fees_per_side": 0.005,
    "whole_shares": True,
    "cash_return": 0,
    "leverage": False,
    "windows_months": [3, 6, 12, 18, 24, 36, 60],
    "entry_z": [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5],
    "exit_z": [0.5, 1, 1.5, 2, 2.5, 3],
    "exit_rules": ["level", "trail_0.5", "trail_1"],
    "filters": ["none", "ma200", "positive_slope"],
    "decision_every_sessions": [1, 5, 21],
    "defensive_weight": [0, 0.25],
    "entry_rules": ["below", "rebound"],
    "train": ["2018-09-17", "2020-12-31"],
    "validation": ["2021-01-04", "2023-12-29"],
    "reserved_test": ["2024-01-02", "2026-11-13"],
    "selection": "Rank all on train; shortlist 20. Select on validation only, prioritizing candidates passing BOTH train and validation gates. Freeze before reserved test. Never select on final test. All periods restart with 10000 and cash.",
    "gate": "Versus same ETF buy-and-hold with identical first execution, integer shares and fees: CAGR >= reference +0.005, Sharpe >= reference +0.10, volatility <=0.90 reference, absolute max drawdown <=0.90 reference; >=3 buys on train. Adoption requires gates on train, validation, reserved test and stressed reserved tests.",
    "rank": "excess CAGR /0.02 + Sharpe gain /0.2 + volatility reduction ratio /0.1 + drawdown reduction ratio /0.2; rank passing candidates first; deterministic original grid order breaks ties.",
    "stress": [
        "fees 1%",
        "extra session delay",
        "20bp additional one-way execution cost",
        "fractional shares",
    ],
    "limitations": "Historical dates already available and previously explored; reserved within this experiment, not a truly unseen future. Multiple testing and survivorship. No guarantee all testable rules are covered. Sharpe reference rate zero. No liquidity yield or tax model. Fixed 5/21-session schedule anchored at each evaluation start.",
    "method_source": "https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf",
}


def grid():
    return [
        dict(
            months=m,
            entry=a,
            exit=b,
            rule=r,
            filter=f,
            cadence=c,
            floor=q,
            entry_rule=e,
        )
        for m, a, b, r, f, c, q, e in product(
            PROTOCOL["windows_months"],
            PROTOCOL["entry_z"],
            PROTOCOL["exit_z"],
            PROTOCOL["exit_rules"],
            PROTOCOL["filters"],
            PROTOCOL["decision_every_sessions"],
            PROTOCOL["defensive_weight"],
            PROTOCOL["entry_rules"],
        )
        if a < b
    ]


def features(days, prices):
    """Each value uses a prefix ending at that close, calendar OLS, residual ddof=2."""
    dates = [date.fromisoformat(d) for d in days]
    ordinal = np.array([d.toordinal() for d in dates])
    y = np.log(prices)
    result = {}
    for months in PROTOCOL["windows_months"]:
        z, slopes = np.full(len(days), np.nan), np.full(len(days), np.nan)
        for i, d in enumerate(dates):
            start = months_before(d, months)
            lo = np.searchsorted(ordinal, start.toordinal())
            if dates[0] > start or i - lo < 40:
                continue
            x = (ordinal[lo : i + 1] - ordinal[lo]) / 365.25
            x -= x.mean()
            v = y[lo : i + 1]
            centered = v - v.mean()
            slope = x @ centered / (x @ x)
            residual = centered - slope * x
            sd = np.sqrt(residual @ residual / (len(v) - 2))
            if sd > 1e-10:
                z[i] = residual[-1] / sd
                slopes[i] = slope
        result[months] = (z, slopes)
    ma = np.full(len(days), np.nan)
    for i in range(199, len(days)):
        ma[i] = prices[i - 199 : i + 1].mean()
    return result, ma


def simulate(
    days,
    raw,
    feat,
    ma,
    candidates,
    period,
    *,
    fee=0.005,
    delay=1,
    whole=True,
    keep_curve=False,
    initial=None,
    calendar=False,
    initial_capital=10000,
):
    """Vectorized independent self-financing ledgers; known close -> later close.

    ESE is accumulating; integer books use unadjusted closes, matching production.
    Orders only on state changes, hence no hidden daily weight rebalancing.
    """
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    if initial is not None:
        lo -= 1
        if initial["last_index"] != lo:
            raise ValueError("Non-contiguous continuation")
    anchor = lo if initial is None else initial["anchor"]
    n = len(candidates)
    months = np.array([c["months"] for c in candidates])
    z = np.array([feat[m][0] for m in PROTOCOL["windows_months"]])
    sl = np.array([feat[m][1] for m in PROTOCOL["windows_months"]])
    idx = np.searchsorted(PROTOCOL["windows_months"], months)
    entry = np.array([c["entry"] for c in candidates])
    exit_z = np.array([c["exit"] for c in candidates])
    trailing = np.array(
        [0 if c["rule"] == "level" else float(c["rule"][6:]) for c in candidates]
    )
    filters = np.array([c["filter"] for c in candidates])
    rebound = np.array([c["entry_rule"] == "rebound" for c in candidates])
    cadence = np.array([c["cadence"] for c in candidates])
    floor = np.array([c["floor"] for c in candidates])
    # Add an independent, identical execution-date buy-and-hold ledger.
    cash, units = np.full(n + 1, float(initial_capital)), np.zeros(n + 1)
    state = np.zeros(n, dtype=bool)
    armed = np.zeros(n, dtype=bool)
    peak_z = np.full(n, -np.inf)
    last_target = np.zeros(n)
    if initial is not None:
        cash = np.array(initial["cash"])
        units = np.array(initial["units"])
        state = np.array(initial["state"], dtype=bool)
        armed = np.array(initial["armed"], dtype=bool)
        peak_z = np.array(initial["peak_z"], dtype=float)
        peak_z = np.where(np.isnan(peak_z), -np.inf, peak_z)
        last_target = np.array(initial["last_target"])
    initial_nav = cash + units * raw[lo]
    total_fee, trades, buys = (
        np.zeros(n + 1),
        np.zeros(n + 1, dtype=int),
        np.zeros(n + 1, dtype=int),
    )
    peak, maxdd = initial_nav.copy(), np.zeros(n + 1)
    total_r, total_r2, exposure = np.zeros(n + 1), np.zeros(n + 1), np.zeros(n + 1)
    previous = initial_nav.copy()
    curve = [previous.tolist()] if keep_curve else None
    for i in range(lo + 1, hi):
        s = i - delay
        target = last_target.copy()
        if s >= anchor:
            score = z[idx, s]
            permitted = (
                (filters == "none")
                | ((filters == "ma200") & (raw[s] > ma[s]))
                | ((filters == "positive_slope") & (sl[idx, s] > 0))
            )
            if calendar:
                d = date.fromisoformat(days[s])
                month_start = s > 0 and days[s][:7] != days[s - 1][:7]
                scheduled = (
                    (cadence == 1)
                    | ((cadence == 5) & (d.weekday() == 4))
                    | ((cadence == 21) & month_start)
                )
            else:
                scheduled = (s - anchor) % cadence == 0
            valid = np.isfinite(score) & scheduled
            peak_z = np.where(state & valid, np.maximum(peak_z, score), peak_z)
            armed |= state & valid & (score >= exit_z)
            sell = (
                state
                & valid
                & (
                    ((trailing == 0) & (score > exit_z))
                    | ((trailing > 0) & armed & (peak_z - score >= trailing))
                    | ~permitted
                )
            )
            enter = (
                (~state)
                & valid
                & permitted
                & np.where(
                    rebound,
                    (z[idx, max(0, s - 1)] < entry) & (score >= entry),
                    score < entry,
                )
            )
            state = (state & ~sell) | enter
            armed = np.where(sell | enter, False, armed)
            peak_z = np.where(enter, score, np.where(sell, -np.inf, peak_z))
            target = np.where(state, 1.0, floor)
        changed = np.r_[target != last_target, s == anchor]
        if s < anchor:
            changed[:] = False
        desired = np.r_[target, 1.0]
        value = cash + units * raw[i]
        # Exact fee-aware amount for target risky share after transaction fees.
        old = units * raw[i]
        buying = desired * value > old
        amount = (
            desired
            * (value + np.where(buying, fee * old, -fee * old))
            / (1 + np.where(buying, fee * desired, -fee * desired))
        )
        new_units = amount / raw[i]
        if whole:
            new_units = np.floor(new_units + 1e-10)
        new_units = np.where(changed, new_units, units)
        delta = new_units - units
        cost = np.abs(delta) * raw[i] * fee
        cash -= delta * raw[i] + cost
        if np.any(cash < -1e-6):
            raise AssertionError("Borrowing in unlevered ledger")
        total_fee += cost
        trades += np.abs(delta) > 1e-10
        buys += delta > 1e-10
        units = new_units
        value = cash + units * raw[i]
        change = value / previous - 1
        total_r += change
        total_r2 += change**2
        peak = np.maximum(peak, value)
        maxdd = np.minimum(maxdd, value / peak - 1)
        exposure += units * raw[i] / value
        previous = value
        last_target = target
        if keep_curve:
            curve.append(value.tolist())
    count = hi - lo - 1
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    var = np.maximum(0, (total_r2 - total_r**2 / count) / (count - 1))
    vol = np.sqrt(var * 252)
    sharpe = np.divide(
        total_r / count * 252, vol, out=np.zeros(n + 1), where=vol > 1e-12
    )
    metrics = [
        dict(
            cagr=float((v / start) ** (1 / years) - 1),
            total_return=float(v / start - 1),
            volatility=float(vo),
            sharpe=float(sh),
            max_drawdown=float(dd),
            final_value=float(v),
            fees=float(f),
            trades=int(t),
            buys=int(b),
            exposure=float(e / count),
        )
        for v, start, vo, sh, dd, f, t, b, e in zip(
            previous,
            initial_nav,
            vol,
            sharpe,
            maxdd,
            total_fee,
            trades,
            buys,
            exposure,
            strict=True,
        )
    ]
    return dict(
        dates=[days[lo], days[hi - 1]],
        candidates=metrics[:-1],
        benchmark=metrics[-1],
        curve=curve,
        terminal_state=dict(
            cash=cash.tolist(),
            units=units.tolist(),
            state=state.tolist(),
            armed=armed.tolist(),
            peak_z=[float(v) if np.isfinite(v) else None for v in peak_z],
            last_target=last_target.tolist(),
            anchor=anchor,
            last_index=hi - 1,
        ),
    )


def score(m, ref):
    return (
        (m["cagr"] - ref["cagr"]) / 0.02
        + (m["sharpe"] - ref["sharpe"]) / 0.2
        + (1 - m["volatility"] / ref["volatility"]) / 0.1
        + (1 - abs(m["max_drawdown"] / ref["max_drawdown"])) / 0.2
    )


def passes(m, ref, train=False):
    return bool(
        m["cagr"] >= ref["cagr"] + 0.005
        and m["sharpe"] >= ref["sharpe"] + 0.1
        and m["volatility"] <= 0.9 * ref["volatility"]
        and abs(m["max_drawdown"]) <= 0.9 * abs(ref["max_drawdown"])
        and (not train or m["buys"] >= 3)
    )


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    configs = grid()
    report = dict(protocol=PROTOCOL, candidate_count=len(configs))
    # Persist the plan BEFORE accessing outcome data.
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "snapshot.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        report["snapshot_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-ese.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        adjusted, raw = np.array([[r[1], r[2]] for r in rows]).T
        if not np.all(np.isfinite(raw)) or np.any(raw <= 0):
            raise ValueError("Invalid ESE closes")
        report["data"] = dict(
            first=days[0],
            last=days[-1],
            count=len(days),
            max_adjustment_gap=float(np.max(np.abs(adjusted / raw - 1))),
        )
        feat, ma = features(days, adjusted)
        train = simulate(days, raw, feat, ma, configs, PROTOCOL["train"])
        ranked = sorted(
            range(len(configs)),
            key=lambda k: (
                -passes(train["candidates"][k], train["benchmark"], True),
                -score(train["candidates"][k], train["benchmark"]),
                k,
            ),
        )
        shortlist = ranked[:20]
        val = simulate(
            days, raw, feat, ma, [configs[k] for k in shortlist], PROTOCOL["validation"]
        )
        chosen = min(
            range(len(shortlist)),
            key=lambda j: (
                -(
                    passes(train["candidates"][shortlist[j]], train["benchmark"], True)
                    and passes(val["candidates"][j], val["benchmark"])
                ),
                -score(val["candidates"][j], val["benchmark"]),
                j,
            ),
        )
        k = shortlist[chosen]
        selected = configs[k]
        report["train_benchmark"] = train["benchmark"]
        report["train_gate_count"] = sum(
            passes(m, train["benchmark"], True) for m in train["candidates"]
        )
        report["train_results"] = [
            dict(config=c, metrics=m)
            for c, m in zip(configs, train["candidates"], strict=True)
        ]
        report["shortlist"] = [
            dict(
                config=configs[v],
                train=train["candidates"][v],
                validation=val["candidates"][j],
                train_pass=passes(train["candidates"][v], train["benchmark"], True),
                validation_pass=passes(val["candidates"][j], val["benchmark"]),
            )
            for j, v in enumerate(shortlist)
        ]
        report["validation_benchmark"] = val["benchmark"]
        report["selected"] = dict(
            config=selected,
            train=train["candidates"][k],
            validation=val["candidates"][chosen],
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print("Selection frozen:", selected, flush=True)
        baseline = dict(
            months=36,
            entry=1,
            exit=2,
            rule="level",
            filter="none",
            cadence=1,
            floor=0,
            entry_rule="below",
        )
        report["evaluations"] = {}
        for name, period in [
            ("train", PROTOCOL["train"]),
            ("validation", PROTOCOL["validation"]),
            ("reserved_test", PROTOCOL["reserved_test"]),
            ("full", ["2018-09-17", days[-1]]),
            ("last_five_years", ["2021-11-15", days[-1]]),
        ]:
            result = simulate(
                days, raw, feat, ma, [selected, baseline], period, keep_curve=True
            )
            report["evaluations"][name] = result
        report["stresses"] = {}
        for name, kwargs in [
            ("double_fees", {"fee": 0.01}),
            ("extra_delay", {"delay": 2}),
            ("extra_cost_20bp", {"fee": 0.007}),
            ("fractional", {"whole": False}),
        ]:
            report["stresses"][name] = simulate(
                days,
                raw,
                feat,
                ma,
                [selected, baseline],
                PROTOCOL["reserved_test"],
                **kwargs,
            )
        # Annual expanding-window re-selection: each calendar year's choice uses
        # only prior dates; this is a separate algorithm, never chosen from final-test results.
        report["walk_forward"] = []
        for year in range(2021, 2027):
            fit = simulate(
                days, raw, feat, ma, configs, ["2018-09-17", f"{year - 1}-12-31"]
            )
            winner = min(
                range(len(configs)),
                key=lambda j: (
                    -passes(fit["candidates"][j], fit["benchmark"], True),
                    -score(fit["candidates"][j], fit["benchmark"]),
                    j,
                ),
            )
            test = simulate(
                days,
                raw,
                feat,
                ma,
                [configs[winner], baseline],
                [f"{year}-01-01", min(f"{year}-12-31", days[-1])],
            )
            report["walk_forward"].append(
                dict(year=year, config=configs[winner], **test)
            )
            print("Walk forward", year, flush=True)
        # Neighborhood is declared before data: same rule/filter/cadence/floor,
        # entry and exit moved by one grid step. Report all, never reselect.
        neighbors = [
            c
            for c in configs
            if all(
                c[key] == selected[key]
                for key in [
                    "months",
                    "rule",
                    "filter",
                    "cadence",
                    "floor",
                    "entry_rule",
                ]
            )
            and abs(c["entry"] - selected["entry"]) <= 0.5
            and abs(c["exit"] - selected["exit"]) <= 0.5
        ]
        result = simulate(days, raw, feat, ma, neighbors, PROTOCOL["reserved_test"])
        report["neighbors"] = [
            dict(config=c, metrics=m, pass_gate=passes(m, result["benchmark"]))
            for c, m in zip(neighbors, result["candidates"], strict=True)
        ]
        report["adopt"] = bool(
            report["shortlist"][chosen]["train_pass"]
            and report["shortlist"][chosen]["validation_pass"]
            and passes(
                report["evaluations"]["reserved_test"]["candidates"][0],
                report["evaluations"]["reserved_test"]["benchmark"],
            )
            and all(
                passes(s["candidates"][0], s["benchmark"])
                for s in report["stresses"].values()
            )
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print("Done", len(configs), "candidates; adopt:", report["adopt"], flush=True)


if __name__ == "__main__":
    main()
