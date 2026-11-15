"""PSP5 research only: predeclared ratio/return compromise; never changes production.

PYTHONPATH=backend:scripts uv run python scripts/study_sp500_ratio_tradeoff.py
"""

import hashlib
import json
import sqlite3
import tempfile
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np
import study_sp500_three_years as regression
from study_sp500_amundi_upside import average

from investor import db
from investor.portfolio.sp500_simulation import (
    Sp500SimulationRequest,
    future_sessions,
    sampled_returns,
    simulate_history,
)

OUT = Path("data/backtests/sp500-ratio-tradeoff.json")
BASE = {**regression.BASE, "warm": True}
SEED_OFFSET = 0
RATIOS = ["sharpe", "sortino", "calmar"]
LOWER = ["volatility", "downside_volatility", "cost_eur"]
PLAN = {
    "change": "New objective: improve current CAGR by >=1pp, mean vol <=115% current and mean loss magnitude <=110% current, both below BH. ALL three mean ratios > BH and > current; >=55% paired wins in each ratio vs BH. No requirement to beat BH return. New volatility-only policies have no trend gate: stay invested in quiet uptrends, reduce exposure progressively when realized risk rises. Distinct from previously rejected multiasset strategy and trend-conditioned PSP5 rules.",
    "selection": "100 five-year paths seeds 20000..20099 for search; choose qualifying highest mean CAGR, or explicitly diagnostic minimum normalized mean ratio edge vs BH if none qualify. Freeze exactly one before independent random draws (same historical model, NOT independent future evidence). Never reselect on holdout.",
    "audit": "300 five-year paths 40000..40299, 100 ten-year paths 50000..50099; same gates on EACH horizon. Bootstrap paired 95% CIs for candidate-current CAGR and candidate-BH ratios. Historical 3/5/10y, quarterly starts 5y, fees doubled and delay2. Report failures; no adoption without user decision.",
    "execution": "10000EUR, PSP5 adjusted EUR history only, next close, whole units, fees0.12%, cash yield0, no leverage or shorts. Volatility estimates prefix only, every5 sessions, 5pp band; regression separate sleeves with own integer orders.",
    "generator_audit": "Unchanged app generator. Compare daily moments, quantiles, 21/63session rolling vol, return and squared-return autocorrelations to actual history on 1000 seeded paths. Audit weekday/252 mismatch and block boundary bias. Model not tuned to help candidates.",
}


def metrics(curve, years, fees=0):
    v = np.asarray(curve)
    if v.ndim == 1:
        v = v[:, None]
    r = v[1:] / v[:-1] - 1
    vol = r.std(axis=0, ddof=1) * np.sqrt(252)
    down = np.sqrt(np.mean(np.minimum(r, 0) ** 2, axis=0) * 252)
    growth = (v[-1] / v[0]) ** (1 / years) - 1
    dd = (v / np.maximum.accumulate(v, axis=0) - 1).min(axis=0)

    def div(a, b):
        return np.divide(a, b, out=np.full_like(vol, np.nan), where=b > 1e-12)

    return dict(
        total_return=v[-1] / v[0] - 1,
        cagr=growth,
        volatility=vol,
        downside_volatility=down,
        max_drawdown=dd,
        sharpe=div(r.mean(axis=0) * 252, vol),
        sortino=div(r.mean(axis=0) * 252, down),
        calmar=div(growth, abs(dd)),
        cost_eur=np.broadcast_to(fees, vol.shape),
    )


def grid():
    cs = []
    for window, target, power, floor in product(
        [21, 63, 126], [0.12, 0.14, 0.16], [1, 2], [0.25, 0.5]
    ):
        cs.append(
            dict(family="risk", window=window, target=target, power=power, floor=floor)
        )
    for floor, share, exit_ in product(
        [0.4, 0.55, 0.7], [0.5, 0.75, 1.0], ["level1.5", "armed_ma50"]
    ):
        cs.append(
            {
                **BASE,
                "family": "regression",
                "floor": floor,
                "slow_share": share,
                "exit": exit_,
            }
        )
    return cs


def risk_weights(p, configs):
    r = np.r_[0, np.diff(p) / p[:-1]][None, :]
    risks = {
        w: np.sqrt(
            np.maximum(average(r * r, w) - average(r, w) ** 2, 0) * 252 * w / (w - 1)
        )[0]
        for w in {c["window"] for c in configs}
    }
    return np.array(
        [
            np.clip(
                (c["target"] / np.maximum(risks[c["window"]], 1e-12)) ** c["power"],
                c["floor"],
                1,
            )
            for c in configs
        ]
    )


def risk_run(days, p, cs, period, fee=0.0012, delay=1):
    lo = int(np.searchsorted(days, period[0]))
    hi = int(np.searchsorted(days, period[1], side="right"))
    w = risk_weights(p, cs) if cs else np.empty((0, len(p)))
    w = np.r_[w, np.ones((1, len(p)))]
    n = len(w)
    cadences = np.array([c.get("step", 5) for c in cs] + [1])
    bands = np.array([c.get("band", 0.05) for c in cs] + [0])
    cash, units = np.full(n, 10000.0), np.zeros(n)
    fees = np.zeros(n)
    curve = [cash.copy()]
    for i in range(lo + 1, hi):
        s = i - delay
        if s >= lo:
            target = w[:, s]
            nav = cash + units * p[i]
            due = ((s - lo) % cadences == 0) & (
                abs(target - units * p[s] / (cash + units * p[s])) >= bands
            )
            due[-1] = False
            due |= s == lo
            old = units * p[i]
            buy = target * nav > old
            amount = (
                target
                * (nav + np.where(buy, fee * old, -fee * old))
                / (1 + np.where(buy, fee * target, -fee * target))
            )
            new = np.where(due, np.floor(amount / p[i] + 1e-10), units)
            delta = new - units
            cost = abs(delta) * p[i] * fee
            cash -= delta * p[i] + cost
            assert cash.min() > -1e-6
            fees += cost
            units = new
        curve.append(cash + units * p[i])
    years = (
        date.fromisoformat(days[hi - 1]) - date.fromisoformat(days[lo])
    ).days / 365.25
    return metrics(curve, years, fees)


def evaluate(days, p, cs, period, fee=0.0012, delay=1):
    rc = [c for c in cs if c["family"] == "risk"]
    gc = [c for c in cs if c["family"] == "regression"]
    a = risk_run(days, p, rc, period, fee, delay)
    f = regression.previous.prepare(days, p)
    b = regression.simulate(
        days, p, p, f, [BASE, *gc], period, fee=fee, delay=delay, keep_curve=True
    )
    years = (
        date.fromisoformat(
            days[int(np.searchsorted(days, period[1], side="right")) - 1]
        )
        - date.fromisoformat(days[int(np.searchsorted(days, period[0]))])
    ).days / 365.25
    # Derive symmetric ratios from identical daily curves, not ratios of averages.
    bmetrics = metrics(b["curve"], years, np.array([m["fees"] for m in b["metrics"]]))
    rows = []
    for j in range(len(cs) + 2):
        if j == 0:
            source, index = a, -1  # Buy & Hold
        elif j == 1:
            source, index = bmetrics, 0  # current v4
        elif cs[j - 2]["family"] == "risk":
            source, index = a, sum(c["family"] == "risk" for c in cs[: j - 2])
        else:
            source, index = (
                bmetrics,
                1 + sum(c["family"] == "regression" for c in cs[: j - 2]),
            )
        rows.append({k: float(v[index]) for k, v in source.items()})
    return rows


def summarize(paths):
    return [
        {k: float(np.mean([p[j][k] for p in paths])) for k in paths[0][j]}
        for j in range(len(paths[0]))
    ]


def passes(paths, j):
    b, o, c = (summarize(paths)[k] for k in [0, 1, j])
    return bool(
        c["cagr"] >= o["cagr"] + 0.01
        and c["volatility"] <= 1.15 * o["volatility"]
        and abs(c["max_drawdown"]) <= 1.10 * abs(o["max_drawdown"])
        and c["volatility"] < b["volatility"]
        and c["max_drawdown"] > b["max_drawdown"]
        and all(
            c[k] > max(b[k], o[k])
            and np.mean([p[j][k] > p[0][k] for p in paths]) >= 0.55
            for k in RATIOS
        )
    )


def paired(paths):
    means = summarize(paths)
    rng = np.random.default_rng(20261114)
    ci = {}
    for key, ref in [("cagr", 1), *[(k, 0) for k in RATIOS]]:
        d = np.array([p[2][key] - p[ref][key] for p in paths])
        samples = d[rng.integers(len(d), size=(5000, len(d)))].mean(axis=1)
        ci[key] = np.quantile(samples, [0.025, 0.975]).tolist()
    rates = {
        k: dict(
            candidate_beats_bh=float(
                np.mean(
                    [
                        p[2][k] < p[0][k] if k in LOWER else p[2][k] > p[0][k]
                        for p in paths
                    ]
                )
            ),
            candidate_beats_current=float(
                np.mean(
                    [
                        p[2][k] < p[1][k] if k in LOWER else p[2][k] > p[1][k]
                        for p in paths
                    ]
                )
            ),
        )
        for k in means[0]
    }
    return dict(
        means=means, wins=rates, paired_ci95=ci, passes=passes(paths, 2), paths=paths
    )


def diagnostics(r):
    def ac(x, lag):
        return float(np.corrcoef(x[:-lag], x[lag:])[0, 1])

    result = dict(
        mean=float(r.mean()),
        volatility=float(r.std(ddof=1) * np.sqrt(252)),
        quantiles=np.quantile(r, [0.01, 0.05, 0.5, 0.95, 0.99]).tolist(),
        skew=float(np.mean(((r - r.mean()) / r.std()) ** 3)),
        excess_kurtosis=float(np.mean(((r - r.mean()) / r.std()) ** 4) - 3),
        autocorrelation=[ac(r, lag) for lag in [1, 5, 21]],
        squared_autocorrelation=[ac(r * r, lag) for lag in [1, 5, 21]],
    )
    for w in [21, 63]:
        v = np.sqrt(
            np.maximum(average((r * r)[None, :], w) - average(r[None, :], w) ** 2, 0)
            * 252
            * w
            / (w - 1)
        )[0, w - 1 :]
        result[f"rolling_vol_{w}"] = np.quantile(v, [0.05, 0.5, 0.95]).tolist()
    return result


def main():
    cs = grid()
    report = dict(plan=PLAN, configs=cs, adopted=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    def save():
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    save()
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
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        p = np.array([r[1] for r in rows])
        assert np.array_equal(p, np.array([r[2] for r in rows]))
        report["source"] = dict(start=days[0], end=days[-1], observations=len(days))
        logret = np.diff(np.log(p))
        actual = np.expm1(logret)
        gen = [
            diagnostics(np.expm1(sampled_returns(logret, 1260, 60000 + i)))
            for i in range(1000)
        ]
        report["generator"] = dict(
            actual=diagnostics(actual),
            draws=1000,
            seeds=[60000, 60999],
            mean_block_sessions=63,
            noise_volatility_ratio=0.05,
            simulated={
                k: np.quantile(
                    np.array([v[k] for v in gen]), [0.05, 0.5, 0.95], axis=0
                ).tolist()
                for k in gen[0]
            },
            weekday_sessions_5y=len(future_sessions(date.fromisoformat(days[-1]), 5)),
        )
        prefix = risk_weights(p[:-200], cs[:36])
        np.testing.assert_allclose(
            prefix, risk_weights(p, cs[:36])[:, :-200], equal_nan=True
        )
        report["prefix_check"] = True
        save()

        def batch(configs, years, seed, count):
            future = future_sessions(date.fromisoformat(days[-1]), years)
            all_days = days + future
            paths = []
            for i in range(count):
                values = p[-1] * np.exp(
                    np.cumsum(sampled_returns(logret, len(future), seed + i))
                )
                pp = np.r_[p, values]
                paths.append(evaluate(all_days, pp, configs, [days[-1], future[-1]]))
                if i == 0:
                    prod = simulate_history(
                        rows, Sp500SimulationRequest(years=years, seed=seed)
                    )["comparison"]["metrics"]
                    for j, key in [(0, "benchmark"), (1, "strategy")]:
                        for k in [
                            "cagr",
                            "total_return",
                            "volatility",
                            "max_drawdown",
                            *RATIOS,
                            "cost_eur",
                        ]:
                            np.testing.assert_allclose(
                                paths[-1][j][k], prod[key][k], atol=1e-9
                            )
                if (i + 1) % 25 == 0:
                    print("batch", years, seed, i + 1, "/", count, flush=True)
            return paths

        train = batch(cs, 5, 20000 + SEED_OFFSET, 100)
        means = summarize(train)
        qualified = [j for j in range(2, len(means)) if passes(train, j)]
        diagnostic = max(
            range(2, len(means)),
            key=lambda j: min(means[j][k] / means[0][k] - 1 for k in RATIOS),
        )
        chosen = (
            max(qualified, key=lambda j: means[j]["cagr"]) if qualified else diagnostic
        )
        report.update(
            training=dict(paths=train, means=means, qualified=qualified),
            chosen_index=chosen - 2,
            chosen=cs[chosen - 2],
            diagnostic_only=not bool(qualified),
        )
        save()
        print("FROZEN", report["chosen"], "qualified", len(qualified), flush=True)
        report["audit"] = {}
        for years, seed, count in [
            (5, 40000 + SEED_OFFSET, 300),
            (10, 50000 + SEED_OFFSET, 100),
        ]:
            report["audit"][str(years)] = paired(
                batch([cs[chosen - 2]], years, seed, count)
            )
            save()
        selected = [cs[chosen - 2]]
        report["historical"] = {
            str(y): evaluate(days, p, selected, [f"{2026 - y}-11-13", days[-1]])
            for y in [3, 5, 10]
        }
        report["stress"] = {
            name: {
                str(y): evaluate(
                    days, p, selected, [f"{2026 - y}-11-13", days[-1]], **kw
                )
                for y in [3, 5, 10]
            }
            for name, kw in [
                ("double_fees", dict(fee=0.0024)),
                ("delay2", dict(delay=2)),
            ]
        }
        report["rolling"] = {
            f"{y}-{m:02}-13": evaluate(
                days, p, selected, [f"{y}-{m:02}-13", f"{y + 5}-{m:02}-13"]
            )
            for y in range(2016, 2022)
            for m in [2, 5, 8, 11]
            if f"{y + 5}-{m:02}-13" <= days[-1]
        }
        save()
        print("DONE", OUT, flush=True)


if __name__ == "__main__":
    main()
