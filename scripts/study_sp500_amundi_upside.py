"""Research only: frozen long-only upside/protection hypotheses on PSP5.

PYTHONPATH=backend:scripts uv run python scripts/study_sp500_amundi_upside.py
No production rules changed; all experiments use a private database snapshot.
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
from investor.portfolio.sp500_simulation import future_sessions, sampled_returns
from investor.portfolio.validation import ValidationRequest, portfolio_validation

OUT = Path("data/backtests/sp500-amundi-upside.json")
PLAN = {
    "instrument": "PSP5.PA only, actual EUR adjusted=raw closes verified; no leverage/shorts",
    "execution": "10000EUR fresh capital, integer units, fee0.0012 per side, signal close then next close, cash0%, initial entry charged, no terminal liquidation",
    "grid": "Trend hysteresis; multi-horizon trend votes; asymmetric crash protection/fast re-entry; trend-conditioned volatility caps; buy pullbacks only within established trends. Different single-index policies from rejected multi-asset momentum/variance strategies.",
    "selection": "2016-11-13..2020-12-31 and 2021-01-04..2023-12-29 only. Require BOTH CAGR>BuyHold, vol<=80% BuyHold, absDD<=80% BuyHold, Sharpe>BuyHold. Rank minimum CAGR advantage then mean. Freeze before 5/10-year results. If none, no successful selection; diagnostic candidate maximizes worst CAGR advantage among rules satisfying risk gates on both, otherwise all rules. Never an adoption fallback.",
    "audit": "Same four requirements on BOTH 5/10 years ending latest local close; on >=75% quarterly-start completed5y windows; fee0.0024 and extra session delay. Synthetic seeds0..999 for5/10years fixed; at least60% return wins,90% vol wins,90% DD wins, and mean CAGR>BH with mean vol/DD <=80%BH. All necessary for a positive research conclusion. No production adoption in this study.",
    "limitations": "Already examined history, overlapping windows, no untouched sample; historical block draws do not establish independent future evidence. Whole shares and tax/liquidity constraints. No guaranteed drawdown cap.",
}


def grid():
    result = []
    for ma, hysteresis, floor, cadence in product(
        [100, 150, 200], [0.01, 0.03], [0, 0.25, 0.5], [1, 5]
    ):
        result.append(
            dict(
                family="trend",
                ma=ma,
                hysteresis=hysteresis,
                floor=floor,
                cadence=cadence,
            )
        )
    for horizons, floor, cadence in product(
        [[50, 100, 200], [100, 150, 200, 250]], [0, 0.25, 0.5], [1, 5]
    ):
        result.append(
            dict(family="votes", horizons=horizons, floor=floor, cadence=cadence)
        )
    for stop, recovery, floor, cadence in product(
        [0.06, 0.10, 0.15], [20, 50, 100], [0, 0.25, 0.5], [1, 5]
    ):
        result.append(
            dict(
                family="crash",
                stop=stop,
                recovery=recovery,
                floor=floor,
                cadence=cadence,
            )
        )
    for target, window, floor, cadence in product(
        [0.10, 0.125, 0.15], [21, 63], [0, 0.25, 0.5], [1, 5]
    ):
        result.append(
            dict(
                family="voltrend",
                target=target,
                window=window,
                floor=floor,
                cadence=cadence,
            )
        )
    for entry, exit_, floor, cadence in product(
        [20, 30], [60, 80], [0, 0.25, 0.5], [1, 5]
    ):
        result.append(
            dict(
                family="pullback", entry=entry, exit=exit_, floor=floor, cadence=cadence
            )
        )
    return result


def average(x, window):
    c = np.cumsum(np.pad(x, ((0, 0), (1, 0))), axis=1)
    out = np.full_like(x, np.nan)
    out[:, window - 1 :] = (c[:, window:] - c[:, :-window]) / window
    return out


def weights(prices, configs):
    """Prefix-only features, prices=(paths,time); logical states replay all history."""
    p = np.atleast_2d(prices)
    ret = np.zeros_like(p)
    ret[:, 1:] = p[:, 1:] / p[:, :-1] - 1
    ma = {w: average(p, w) for w in [20, 50, 100, 150, 200, 250]}
    risk = {
        w: np.sqrt(
            np.maximum(average(ret**2, w) - average(ret, w) ** 2, 0) * 252 * w / (w - 1)
        )
        for w in [21, 63]
    }
    peak = np.maximum.accumulate(p, axis=1)
    # 252-session trailing maximum, never a future/full-sample maximum.
    rolling_peak = np.column_stack(
        [p[:, max(0, i - 251) : i + 1].max(axis=1) for i in range(p.shape[1])]
    )
    assert np.all(rolling_peak <= peak + 1e-8)
    up = average(np.maximum(ret, 0), 5)
    down = average(np.maximum(-ret, 0), 5)
    rsi = 100 * np.divide(
        up, up + down, out=np.full_like(up, 0.5), where=(up + down) > 0
    )
    all_weights = []
    for c in configs:
        family = c["family"]
        state = np.zeros(p.shape[0], dtype=bool)
        w = np.empty_like(p)
        if family == "votes":
            w = np.mean([p > ma[h] for h in c["horizons"]], axis=0)
        elif family == "voltrend":
            trend = (p > ma[200]).astype(float)
            allocation = c["floor"] + (1 - c["floor"]) * trend
            w = allocation * np.minimum(
                1,
                np.divide(
                    c["target"],
                    risk[c["window"]],
                    out=np.ones_like(p),
                    where=risk[c["window"]] > 0,
                ),
            )
        else:
            for i in range(p.shape[1]):
                if family == "trend":
                    ratio = p[:, i] / ma[c["ma"]][:, i]
                    state = np.where(
                        ratio > 1 + c["hysteresis"],
                        True,
                        np.where(ratio < 1 - c["hysteresis"], False, state),
                    )
                elif family == "crash":
                    # Fully invested normally; cut only drawdown AND long-trend failure.
                    danger = (p[:, i] / rolling_peak[:, i] - 1 < -c["stop"]) & (
                        p[:, i] < ma[200][:, i]
                    )
                    recovery = p[:, i] > ma[c["recovery"]][:, i]
                    # Danger takes precedence; no same-day repeated sell/buy.
                    state = np.where(danger, False, np.where(recovery, True, state))
                elif family == "pullback":
                    trend = p[:, i] > ma[200][:, i]
                    state = np.where(
                        ~trend | (rsi[:, i] > c["exit"]),
                        False,
                        np.where(trend & (rsi[:, i] < c["entry"]), True, state),
                    )
                w[:, i] = state
        if family != "voltrend":
            w = c["floor"] + (1 - c["floor"]) * w
        all_weights.append(w)
    return np.asarray(all_weights)


def simulate(days, prices, allocation, configs, period, *, fee=0.0012, delay=1):
    """Vector ledger shared by historical and Monte Carlo; no negative cash."""
    p = np.atleast_2d(prices)
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    # A benchmark row uses identical execution and fee conventions.
    w = np.concatenate([allocation, np.ones((1, *p.shape))])
    cadence = np.array([c["cadence"] for c in configs] + [1])[:, None]
    cash = np.full((len(configs) + 1, len(p)), 10000.0)
    units = np.zeros_like(cash)
    last = np.full_like(cash, np.nan)
    fees = np.zeros_like(cash)
    turnover = np.zeros_like(cash)
    curves = [cash.copy()]
    exposure = np.zeros_like(cash)
    for i in range(lo + 1, hi):
        s = i - delay
        if s >= lo:
            due = (s - lo) % cadence == 0
            known_value = cash + units * p[:, s]
            known_weight = units * p[:, s] / known_value
            # Five-point no-trade band for continuous votes/vol targets.
            target = w[:, :, s]
            discrete = np.array(
                [c["family"] not in ["votes", "voltrend"] for c in configs] + [True]
            )[:, None]
            change = (s == lo) | (
                due
                & np.where(
                    discrete, target != last, np.abs(target - known_weight) >= 0.05
                )
            )
            change[-1] = s == lo
            nav = cash + units * p[:, i]
            old = units * p[:, i]
            buy = target * nav > old
            amount = (
                target
                * (nav + np.where(buy, fee * old, -fee * old))
                / (1 + np.where(buy, fee * target, -fee * target))
            )
            new = np.where(change, np.floor(amount / p[:, i] + 1e-10), units)
            delta = new - units
            cost = np.abs(delta) * p[:, i] * fee
            cash -= delta * p[:, i] + cost
            assert cash.min() > -1e-6
            fees += cost
            if s > lo:
                turnover += np.abs(delta) * p[:, i] / nav
            units = new
            last = np.where(change, target, last)
        nav = cash + units * p[:, i]
        curves.append(nav.copy())
        exposure += units * p[:, i] / nav
    curves = np.asarray(curves)
    r = curves[1:] / curves[:-1] - 1
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    vol = r.std(axis=0, ddof=1) * np.sqrt(252)
    downside = np.sqrt(np.mean(np.minimum(r, 0) ** 2, axis=0) * 252)
    cagr = (curves[-1] / 10000) ** (1 / years) - 1
    dd = (curves / np.maximum.accumulate(curves, axis=0) - 1).min(axis=0)
    m = dict(
        total_return=curves[-1] / 10000 - 1,
        cagr=cagr,
        volatility=vol,
        max_drawdown=dd,
        downside_volatility=downside,
        sharpe=np.divide(
            r.mean(axis=0) * 252, vol, out=np.zeros_like(vol), where=vol > 1e-12
        ),
        sortino=np.divide(
            r.mean(axis=0) * 252,
            downside,
            out=np.zeros_like(vol),
            where=downside > 1e-12,
        ),
        calmar=np.divide(cagr, abs(dd), out=np.zeros_like(vol), where=abs(dd) > 1e-12),
        cost_eur=fees,
        final_value=curves[-1],
        annual_turnover=turnover / years,
        market_exposure=exposure / len(r),
    )
    return [
        {k: np.asarray(v[j]).tolist() for k, v in m.items()}
        for j in range(len(configs) + 1)
    ]


def scalar(result):
    return [{k: v[0] for k, v in row.items()} for row in result]


def gate(m, b):
    return bool(
        m["cagr"] > b["cagr"]
        and m["volatility"] <= 0.8 * b["volatility"]
        and abs(m["max_drawdown"]) <= 0.8 * abs(b["max_drawdown"])
        and m["sharpe"] > b["sharpe"]
    )


def main():
    configs = grid()
    report = dict(plan=PLAN, configs=configs, adopted=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    def save():
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    save()  # Persist entire search and gates BEFORE reading results.
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "investor.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        report["snapshot_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with sqlite3.connect(path) as c:
            rows = c.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        prices = np.array([r[1] for r in rows])
        raw = np.array([r[2] for r in rows])
        assert np.array_equal(prices, raw), (
            "Split/distribution handling needs explicit support"
        )
        report["source"] = dict(start=days[0], end=days[-1], count=len(days))
        w = weights(prices, configs)
        # Causality audit: truncating future prices leaves ALL past allocations unchanged.
        cut = len(days) - 300
        np.testing.assert_allclose(weights(prices[:cut], configs), w[:, :, :cut])
        report["causality_prefix_check"] = True
        periods = dict(
            train=["2016-11-13", "2020-12-31"], validation=["2021-01-04", "2023-12-29"]
        )
        early = {
            k: scalar(simulate(days, prices, w, configs, p)) for k, p in periods.items()
        }
        qualified = [
            j
            for j in range(len(configs))
            if all(gate(ms[j], ms[-1]) for ms in early.values())
        ]
        risk = [
            j
            for j in range(len(configs))
            if all(
                ms[j]["volatility"] <= 0.8 * ms[-1]["volatility"]
                and abs(ms[j]["max_drawdown"]) <= 0.8 * abs(ms[-1]["max_drawdown"])
                for ms in early.values()
            )
        ]

        def rank(j):
            return min(ms[j]["cagr"] - ms[-1]["cagr"] for ms in early.values())

        diagnostic = max(risk or list(range(len(configs))), key=rank)
        selected = max(qualified, key=rank) if qualified else None
        fixed = [
            configs.index(
                dict(family="trend", ma=200, hysteresis=0.01, floor=0, cadence=5)
            ),
            configs.index(
                dict(family="crash", stop=0.10, recovery=50, floor=0, cadence=1)
            ),
            configs.index(
                dict(family="voltrend", target=0.125, window=63, floor=0.25, cadence=5)
            ),
        ]
        audits = list(dict.fromkeys([diagnostic, *fixed]))
        report.update(
            early=early,
            qualified=qualified,
            selected=selected,
            diagnostic=diagnostic,
            audited=audits,
        )
        save()
        print(
            "Frozen selection:",
            len(configs),
            "rules",
            len(qualified),
            "qualified; diagnostic",
            diagnostic,
            configs[diagnostic],
            flush=True,
        )
        periods.update(
            five_years=["2021-11-13", days[-1]], ten_years=["2016-11-13", days[-1]]
        )
        historical = {
            k: scalar(simulate(days, prices, w, configs, p)) for k, p in periods.items()
        }
        report.update(
            periods=periods,
            historical=historical,
            recent_pass=[
                j
                for j in range(len(configs))
                if all(
                    gate(historical[k][j], historical[k][-1])
                    for k in ["five_years", "ten_years"]
                )
            ],
        )
        # Exact current production benchmark, on the private snapshot, same costs/dates.
        original = db.DATA_DIR
        db.DATA_DIR = Path(folder)
        try:
            report["production"] = {}
            for name in ["five_years", "ten_years"]:
                r = portfolio_validation(
                    ValidationRequest(
                        asset_ids=["yf-psp5.pa"],
                        mode="etf_switch",
                        years=5 if name == "five_years" else 10,
                        whole_shares=True,
                        start_date=date.fromisoformat(periods[name][0]),
                        end_date=date.fromisoformat(days[-1]),
                    )
                )
                assert r["status"] == "ready", r
                report["production"][name] = dict(
                    start=r["start"], end=r["end"], metrics=r["metrics"]
                )
                for metric in [
                    "cagr",
                    "volatility",
                    "max_drawdown",
                    "sharpe",
                    "cost_eur",
                    "total_return",
                ]:
                    assert (
                        abs(
                            historical[name][-1][metric]
                            - r["metrics"]["benchmark"][metric]
                        )
                        < 1e-9
                    ), (
                        name,
                        metric,
                        historical[name][-1][metric],
                        r["metrics"]["benchmark"][metric],
                    )
        finally:
            db.DATA_DIR = original
        report["benchmark_production_match"] = True
        report["rolling"] = {}
        for year in range(2016, 2022):
            for month in [2, 5, 8, 11]:
                p = [f"{year}-{month:02}-13", f"{year + 5}-{month:02}-13"]
                if p[1] <= days[-1]:
                    report["rolling"][p[0]] = scalar(
                        simulate(
                            days, prices, w[audits], [configs[j] for j in audits], p
                        )
                    )
        report["stress"] = {}
        for label, kw in [
            ("double_fee", dict(fee=0.0024)),
            ("extra_delay", dict(delay=2)),
        ]:
            report["stress"][label] = {
                k: scalar(
                    simulate(
                        days,
                        prices,
                        w[audits],
                        [configs[j] for j in audits],
                        periods[k],
                        **kw,
                    )
                )
                for k in ["five_years", "ten_years"]
            }
        save()
        print(
            "Historical/rolling/stress complete; recent pass",
            report["recent_pass"],
            flush=True,
        )
        report["synthetic"] = {}
        # Sequential seed prefixes identical to the app; no favorable-seed selection.
        for years in [5, 10]:
            future = future_sessions(date.fromisoformat(days[-1]), years)
            synthetic = np.array(
                [
                    prices[-1]
                    * np.exp(
                        np.cumsum(
                            sampled_returns(np.diff(np.log(prices)), len(future), seed)
                        )
                    )
                    for seed in range(1000)
                ]
            )
            all_days = days + future
            # Process fixed-size chunks to bound memory while vectorizing paths.
            chunks = []
            for lo in range(0, 1000, 50):
                p = np.concatenate(
                    [np.tile(prices, (50, 1)), synthetic[lo : lo + 50]], axis=1
                )
                cs = [configs[j] for j in audits]
                ww = weights(p, cs)
                chunks.append(simulate(all_days, p, ww, cs, [days[-1], future[-1]]))
            merged = [
                {
                    k: np.concatenate([np.array(chunk[j][k]) for chunk in chunks])
                    for k in chunks[0][j]
                }
                for j in range(len(audits) + 1)
            ]
            b = merged[-1]
            summary = []
            for m in merged[:-1]:
                summary.append(
                    {
                        k: dict(
                            mean=float(v.mean()),
                            benchmark_mean=float(b[k].mean()),
                            wins=int(np.sum(v < b[k] - 1e-10))
                            if k
                            in [
                                "volatility",
                                "downside_volatility",
                                "cost_eur",
                                "annual_turnover",
                            ]
                            else int(np.sum(v > b[k] + 1e-10)),
                            ties=int(
                                np.sum(np.isclose(v, b[k], atol=1e-10, rtol=1e-9))
                            ),
                        )
                        for k, v in m.items()
                    }
                )
            report["synthetic"][str(years)] = dict(
                count=1000, seeds=[0, 999], audited=audits, summary=summary
            )
            save()
            print("Synthetic", years, "years complete", flush=True)
    print("Report:", OUT, flush=True)


if __name__ == "__main__":
    main()
