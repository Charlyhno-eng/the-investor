"""Broad S&P risk-policy study. Proxy-only selection, ESE verification, no DB writes."""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np

from investor import db

OUT = Path("data/backtests/sp500-adaptive-risk.json")
PLAN = {
    "selection": "Select on USD total-return index 1993-2002 and 2003-2012 only. ESE EUR 2016-2026 is verification, never used to reselect. All dates already historically examined; no truly unseen sample.",
    "objective": "Drawdown first. On proxy train AND validation require abs drawdown <=75% benchmark, volatility <=85%, CAGR >=80% positive benchmark CAGR, Sharpe >=benchmark. Rank qualified by worst of train/validation score (drawdown reduction + volatility reduction + capped return retention); if none qualify diagnostic fallback only.",
    "adoption": "Selected policy must on BOTH ESE five and ten years have CAGR >=14%, abs drawdown <=80% benchmark, volatility <=90%, Sharpe >=benchmark+0.1. At least75% of yearly-start rolling 3/5-year cases must have drawdown <=80% and volatility <=90% benchmark, retain >=80% CAGR when benchmark positive. Double-fee and extra-delay five/ten-year tests must also satisfy same risk/return gates. No retuning or replacing candidate after ESE outcomes.",
    "mechanics": "ESE only/cash, no short or leverage. 10000 EUR, integer ESE, 0.5% each side. Decisions every5/21 sessions, execute one session later. Weight bands5/15 percentage points skip small trades. Cash earns0. Proxy USD uses fractional index units; not an ETF or currency substitute.",
    "families": "Single/ensemble price trends; multi-horizon momentum breadth; asymmetric breakouts; trend hysteresis; drawdown-budget exposure; volatility and downside-volatility caps; combinations with defensive floors.",
    "difference_from_rejected": "Single-index policies, multi-horizon signals and cost bands differ from rejected multi-asset capped momentum/variance allocations; new predeclared drawdown and cross-period criteria, not identical reinstatement.",
    "limitations": "No PEA tax or live liquidity model. Index before ETF listing is a diagnostic proxy. 14% is a user historical target, not a promise. No claim of testing every mathematically possible policy.",
}


def grid():
    cores = (
        [("ma", n) for n in [100, 150, 200, 250]]
        + [("ensemble_ma", n) for n in [0, 1]]
        + [("ensemble_mom", n) for n in [0, 1]]
        + [("breakout", n) for n in [126, 252]]
        + [("hysteresis", n) for n in [0.01, 0.03]]
        + [("drawdown", n) for n in [0.10, 0.15, 0.20]]
        + [("volatility", 63), ("downside", 63)]
    )
    return [
        dict(family=f, param=p, cadence=c, band=b, floor=q, vol_target=v)
        for (f, p), c, b, q, v in product(
            cores, [5, 21], [0.05, 0.15], [0, 0.25, 0.5], [None, 0.1, 0.15]
        )
        if not (f in ["volatility", "downside"] and v is None)
    ]


def features(prices, configs):
    n = len(prices)
    r = np.r_[0, prices[1:] / prices[:-1] - 1]
    means = {}
    moms = {}
    for w in [50, 63, 100, 126, 150, 200, 250, 252, 504]:
        avg = np.full(n, np.nan)
        avg[w - 1 :] = np.convolve(prices, np.ones(w) / w, "valid")
        means[w] = avg
        mom = np.full(n, np.nan)
        mom[w:] = prices[w:] / prices[:-w] - 1
        moms[w] = mom
    vol = np.full(n, np.nan)
    down = np.full(n, np.nan)
    for i in range(63, n):
        x = r[i - 62 : i + 1]
        vol[i] = x.std(ddof=1) * np.sqrt(252)
        down[i] = np.sqrt(np.mean(np.minimum(x, 0) ** 2)) * np.sqrt(252)
    cache = {}
    for c in configs:
        k = (c["family"], c["param"])
        if k in cache:
            continue
        f, p = k
        if f == "ma":
            signal = (prices > means[p]).astype(float)
        elif f == "ensemble_ma":
            ws = [50, 100, 200] if p == 0 else [100, 150, 200, 250]
            signal = np.mean([prices > means[w] for w in ws], axis=0)
        elif f == "ensemble_mom":
            ws = [63, 126, 252] if p == 0 else [126, 252, 504]
            signal = np.mean([moms[w] > 0 for w in ws], axis=0)
        elif f == "drawdown":
            peak = np.array([prices[max(0, i - 251) : i + 1].max() for i in range(n)])
            signal = np.clip(1 + (prices / peak - 1) / p, 0, 1)
        elif f in ["breakout", "hysteresis"]:
            signal = np.zeros(n)
            held = False
            for i in range(1, n):
                if f == "breakout" and i >= p:
                    if prices[i] >= prices[i - p : i].max():
                        held = True
                    elif prices[i] < prices[i - p // 2 : i].min():
                        held = False
                if f == "hysteresis" and i >= 199:
                    ratio = prices[i] / means[200][i]
                    if ratio > 1 + p:
                        held = True
                    elif ratio < 1 - p:
                        held = False
                signal[i] = held
        else:
            signal = np.ones(n)
        cache[k] = signal
    weights = []
    for c in configs:
        w = c["floor"] + (1 - c["floor"]) * cache[c["family"], c["param"]]
        if c["vol_target"] is not None:
            risk = down if c["family"] == "downside" else vol
            w = w * np.minimum(
                1, np.divide(c["vol_target"], risk, out=np.ones(n), where=risk > 1e-10)
            )
        weights.append(np.clip(w, 0, 1))
    return np.array(weights)


def simulate(
    days,
    prices,
    weights,
    configs,
    period,
    *,
    fee=0.005,
    delay=1,
    whole=True,
    curve=False,
    calendar=False,
):
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    n = len(configs)
    cadence = np.array([c["cadence"] for c in configs])
    band = np.array([c["band"] for c in configs])
    cash = np.full(n + 1, 10000.0)
    units = np.zeros(n + 1)
    prev = cash.copy()
    peak = prev.copy()
    dd = np.zeros(n + 1)
    sr = np.zeros(n + 1)
    sr2 = sr.copy()
    fees = sr.copy()
    exposure = sr.copy()
    trades = np.zeros(n + 1, dtype=int)
    points = [prev.tolist()] if curve else None
    orders = [] if curve else None
    for i in range(lo + 1, hi):
        s = i - delay
        v = cash + units * prices[i]
        if s >= lo:
            known = units[:-1] * prices[s] / (cash[:-1] + units[:-1] * prices[s])
            if calendar:
                day = date.fromisoformat(days[s])
                first_month = s > 0 and days[s][:7] != days[s - 1][:7]
                scheduled = ((cadence == 5) & (day.weekday() == 4)) | (
                    (cadence == 21) & first_month
                )
            else:
                scheduled = (s - lo) % cadence == 0
            change = (s == lo) | (scheduled & (np.abs(weights[:, s] - known) >= band))
            change = np.r_[change, s == lo]
            target = np.r_[weights[:, s], 1.0]
            old = units * prices[i]
            buying = target * v > old
            amount = (
                target
                * (v + np.where(buying, fee * old, -fee * old))
                / (1 + np.where(buying, fee * target, -fee * target))
            )
            new = amount / prices[i]
            if whole:
                new = np.floor(new + 1e-10)
            new = np.where(change, new, units)
            delta = new - units
            cost = np.abs(delta) * prices[i] * fee
            cash -= delta * prices[i] + cost
            if cash.min() < -1e-6:
                raise ValueError("Unintended borrowing")
            if curve:
                for j in np.flatnonzero(np.abs(delta) > 1e-10):
                    orders.append(
                        dict(
                            instrument=int(j),
                            signal=days[s],
                            execution=days[i],
                            quantity=float(delta[j]),
                            fee=float(cost[j]),
                        )
                    )
            fees += cost
            trades += np.abs(delta) > 1e-10
            units = new
        v = cash + units * prices[i]
        change = v / prev - 1
        sr += change
        sr2 += change**2
        peak = np.maximum(peak, v)
        dd = np.minimum(dd, v / peak - 1)
        exposure += units * prices[i] / v
        prev = v
        if curve:
            points.append(v.tolist())
    count = hi - lo - 1
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    vol = np.sqrt(np.maximum(0, (sr2 - sr**2 / count) / (count - 1)) * 252)
    sharpe = np.divide(sr / count * 252, vol, out=np.zeros(n + 1), where=vol > 1e-12)
    metrics = [
        dict(
            cagr=float((v / 10000) ** (1 / years) - 1),
            volatility=float(vo),
            sharpe=float(sh),
            max_drawdown=float(d),
            fees=float(f),
            trades=int(t),
            exposure=float(e / count),
            final_value=float(v),
        )
        for v, vo, sh, d, f, t, e in zip(
            prev, vol, sharpe, dd, fees, trades, exposure, strict=True
        )
    ]
    return dict(
        dates=[days[lo], days[hi - 1]],
        candidates=metrics[:-1],
        benchmark=metrics[-1],
        curve=points,
        orders=orders,
    )


def gate(m, b, adopt=False):
    return bool(
        abs(m["max_drawdown"]) <= (0.8 if adopt else 0.75) * abs(b["max_drawdown"])
        and m["volatility"] <= (0.9 if adopt else 0.85) * b["volatility"]
        and m["sharpe"] >= b["sharpe"] + (0.1 if adopt else 0)
        and m["cagr"] >= (0.14 if adopt else 0.8 * max(b["cagr"], 0))
    )


def score(m, b):
    return (
        1
        - abs(m["max_drawdown"] / b["max_drawdown"])
        + 1
        - m["volatility"] / b["volatility"]
        + min(m["cagr"] / max(b["cagr"], 0.01), 1.2) / 2
    )


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"protocol": PLAN}, indent=2) + "\n")
    configs = grid()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "copy.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        with sqlite3.connect(path) as conn:
            proxy = conn.execute(
                "SELECT date,value FROM reference_observations WHERE symbol='^SP500TR' ORDER BY date"
            ).fetchall()
            etf = conn.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-ese.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in proxy]
        prices = np.array([r[1] for r in proxy])
        w = features(prices, configs)
        tr = simulate(
            days, prices, w, configs, ["1993-01-04", "2002-12-31"], whole=False
        )
        va = simulate(
            days, prices, w, configs, ["2003-01-02", "2012-12-31"], whole=False
        )
        qualified = [
            i
            for i in range(len(configs))
            if gate(tr["candidates"][i], tr["benchmark"])
            and gate(va["candidates"][i], va["benchmark"])
        ]
        ranking = sorted(
            qualified or range(len(configs)),
            key=lambda i: (
                -min(
                    score(tr["candidates"][i], tr["benchmark"]),
                    score(va["candidates"][i], va["benchmark"]),
                )
            ),
        )
        selected = ranking[0]
        report = dict(
            protocol=PLAN,
            snapshot_sha256=sha,
            candidate_count=len(configs),
            proxy_qualified=len(qualified),
            selected=configs[selected],
            selected_index=selected,
            proxy_train=tr,
            proxy_validation=va,
            configs=configs,
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            "Proxy selection frozen:",
            len(configs),
            "candidates;",
            len(qualified),
            "qualified;",
            configs[selected],
            flush=True,
        )
        report["proxy_later"] = simulate(
            days,
            prices,
            w[[selected]],
            [configs[selected]],
            ["2013-01-02", days[-1]],
            whole=False,
        )
        days = [r[0] for r in etf]
        raw = np.array([r[2] for r in etf])
        adjusted = np.array([r[1] for r in etf])
        if np.max(abs(raw / adjusted - 1)) > 1e-8:
            raise ValueError("Accumulating ESE adjustment assumption invalid")
        w = features(adjusted, configs)
        periods = {
            "five_years": ["2021-11-13", days[-1]],
            "ten_years": ["2016-11-13", days[-1]],
        }
        periods.update(
            {
                f"rolling_{span}y_{year}": [f"{year}-11-13", f"{year + span}-11-13"]
                for span in [3, 5]
                for year in range(2016, 2027 - span)
            }
        )
        report["ese"] = {}
        for name, period in periods.items():
            report["ese"][name] = simulate(days, raw, w, configs, period)
        report["stresses"] = {}
        for name, kwargs in [
            ("double_fees", {"fee": 0.01}),
            ("extra_delay", {"delay": 2}),
        ]:
            report["stresses"][name] = {
                k: simulate(days, raw, w[[selected]], [configs[selected]], p, **kwargs)
                for k, p in list(periods.items())[:2]
            }
        rolling = [r for k, r in report["ese"].items() if k.startswith("rolling")]

        def stable(i):
            return float(
                np.mean(
                    [
                        abs(r["candidates"][i]["max_drawdown"])
                        <= 0.8 * abs(r["benchmark"]["max_drawdown"])
                        and r["candidates"][i]["volatility"]
                        <= 0.9 * r["benchmark"]["volatility"]
                        and r["candidates"][i]["cagr"]
                        >= 0.8 * max(r["benchmark"]["cagr"], 0)
                        for r in rolling
                    ]
                )
            )

        report["selected_rolling_pass_fraction"] = stable(selected)
        report["adopt"] = bool(
            qualified
            and stable(selected) >= 0.75
            and all(
                gate(
                    report["ese"][k]["candidates"][selected],
                    report["ese"][k]["benchmark"],
                    True,
                )
                for k in ["five_years", "ten_years"]
            )
            and all(
                gate(r["candidates"][0], r["benchmark"], True)
                for cases in report["stresses"].values()
                for r in cases.values()
            )
        )
        # Descriptive only: count full-grid successes without selecting on ESE.
        report["ese_both_horizons_14pct_count"] = sum(
            all(
                gate(
                    report["ese"][k]["candidates"][i],
                    report["ese"][k]["benchmark"],
                    True,
                )
                for k in ["five_years", "ten_years"]
            )
            for i in range(len(configs))
        )
        report["selected_ese"] = {
            k: dict(metrics=r["candidates"][selected], benchmark=r["benchmark"])
            for k, r in report["ese"].items()
        }
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            json.dumps(
                {
                    k: report[k]
                    for k in [
                        "selected",
                        "selected_rolling_pass_fraction",
                        "adopt",
                        "ese_both_horizons_14pct_count",
                        "selected_ese",
                    ]
                },
                indent=2,
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
