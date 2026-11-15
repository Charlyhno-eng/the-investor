"""Fixed academic-inspired policies, isolated from the application and frozen data.

PYTHONPATH=backend uv run python scripts/study_quantitative_strategies.py
No parameter search; monthly decisions, next common close, no leverage or shorts.
"""

import argparse
import hashlib
import json
import sqlite3
import tempfile
from bisect import bisect_left
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
from audit_validation import UNIVERSES

from investor import db
from investor.assets.momentum import months_before
from investor.portfolio import validation
from investor.portfolio.statistics import curve_metrics
from investor.portfolio.validation_history import align, maturities

POLICIES = ("equal_monthly", "variance_managed", "time_series_momentum")
PERIODS = {
    "early": ("2016-11-14", "2021-11-12"),
    "middle": ("2021-11-15", "2024-11-14"),
    "recent": ("2024-11-15", "2026-11-13"),
    "five_years": ("2021-11-15", "2026-11-13"),
}
CRITERION = (
    "On BOTH middle and recent journal_14 windows: Sharpe >= equal_monthly + 0.10, "
    "abs(max drawdown) <= 0.80 * equal_monthly, CAGR >= 0.80 * equal_monthly. "
    "Then require positive CAGR and no worse drawdown than equal_monthly in early "
    "and five_years, and the same three initial criteria on recent with 1% fees. "
    "No retuning if a policy fails. This is retrospective, not a new unseen sample."
)


def capped_weights(raw, cap=0.25):
    """Water-fill positive scores; leave cash if fewer than four eligible assets."""
    weights = np.zeros(len(raw))
    remaining = raw > 0
    budget = min(1.0, cap * int(remaining.sum()))
    while remaining.any() and budget > 1e-12:
        indices = np.flatnonzero(remaining)
        proposed = budget * raw[indices] / raw[indices].sum()
        limited = proposed >= cap
        if not limited.any():
            weights[indices] = proposed
            break
        fixed = indices[limited]
        weights[fixed] = cap
        remaining[fixed] = False
        budget -= cap * len(fixed)
    return weights


def policy_weights(policy, prices, dates, signal, eligible):
    """Only the prefix ending at the known signal close reaches this function."""
    count = prices.shape[1]
    if not eligible.any():
        return np.zeros(count)
    lower = bisect_left(dates, months_before(dates[signal], 12))
    changes = prices[lower + 1 : signal + 1] / prices[lower:signal] - 1
    if policy == "time_series_momentum":
        vol = np.std(changes[:, eligible], axis=0, ddof=1) * np.sqrt(252)
        score = np.zeros(count)
        positive = prices[signal, eligible] > prices[lower, eligible]
        score[eligible] = np.where(positive, 1 / np.maximum(vol, 1e-8), 0)
        weights = capped_weights(score)
        covariance = np.cov(changes[:, eligible], rowvar=False, ddof=1)
        w = weights[eligible]
        portfolio_vol = np.sqrt(float(w @ np.atleast_2d(covariance) @ w) * 252)
        return weights * min(1.0, 0.15 / max(portfolio_vol, 1e-8))
    weights = capped_weights(eligible.astype(float))
    if policy == "variance_managed":
        # Realized variance of the fixed underlying basket over the last calendar month.
        lower = bisect_left(dates, months_before(dates[signal], 1))
        returns = prices[lower + 1 : signal + 1] / prices[lower:signal] - 1
        annual_variance = float(np.var(returns @ weights, ddof=1)) * 252
        weights *= min(1.0, 0.15**2 / max(annual_variance, 1e-12))
    return weights


def load_inputs(request):
    captured = {}

    def capture(assets, histories, benchmark, request, **kwargs):
        captured.update(
            assets=[dict(a) for a in assets],
            histories=histories,
            benchmark=benchmark,
            **kwargs,
        )
        return {"status": "captured"}

    with patch.object(validation, "validation_data", capture):
        status = validation.portfolio_validation(request)
    if status["status"] != "captured":
        raise RuntimeError(status)
    return captured


def simulate(inputs, request, policy):
    assets, histories, benchmark = (
        inputs["assets"],
        inputs["histories"],
        inputs["benchmark"],
    )
    end = min(request.end_date.isoformat(), max(benchmark))
    daily = [(min(h), h) for h in histories if h]
    days = sorted(
        d
        for d in benchmark
        if d <= end and all(d < start or d in h for start, h in daily)
    )
    dates = [date.fromisoformat(d) for d in days]
    first = bisect_left(dates, max(request.start_date, months_before(dates[0], -36)))
    if first + 2 >= len(days):
        raise ValueError("Insufficient test history")
    adjusted = np.column_stack([align(h, days) for h in histories])
    matured = maturities(histories, days)
    # A pre-listing placeholder is never eligible or held.
    prices = np.where(np.isfinite(adjusted), adjusted, 1.0)
    whole = np.array(
        [request.whole_shares and a["category"] in ("stock", "etf") for a in assets]
    )
    execution = prices.copy()
    payouts = np.zeros_like(prices)
    for j in np.flatnonzero(whole):
        raw = inputs["execution_histories"][j]
        required = [d for d in histories[j] if days[first] <= d <= days[-1]]
        if any(d not in raw for d in required):
            raise ValueError(f"Missing raw close for {assets[j]['id']}")
        aligned = align(raw, days)
        execution[:, j] = np.where(np.isfinite(aligned), aligned, 1.0)
        distributions = inputs["cash_distributions"][j]
        for i in range(first + 1, len(days)):
            payouts[i, j] = sum(
                v for d, v in distributions.items() if days[i - 1] < d <= days[i]
            )
    events = {first + 1}
    events.update(
        i for i in range(first + 2, len(days)) if dates[i].month != dates[i - 1].month
    )
    values = np.zeros(len(assets))
    cash = request.initial_capital
    fees = turnover = exposure_days = 0.0
    curve, journal, allocations = [], [], []
    for i in range(first, len(days)):
        if i > first:
            if i > first + 1:
                exposure_days += (
                    (dates[i] - dates[i - 1]).days
                    * values.sum()
                    / (values.sum() + cash)
                )
            cash += float(np.sum(values / execution[i - 1] * payouts[i]))
            growth = np.where(
                whole, execution[i] / execution[i - 1], prices[i] / prices[i - 1]
            )
            values = values * growth
        if i in events:
            signal = i - 1
            eligible = matured[signal] & np.isfinite(adjusted[signal])
            weights = policy_weights(policy, prices[:i], dates[:i], signal, eligible)
            if (
                weights.sum() > 1 + 1e-10
                or weights.min() < 0
                or weights.max() > 0.25 + 1e-10
            ):
                raise ValueError("Invalid decision weights")
            allocations.append(
                {
                    "signal": days[signal],
                    "execution": days[i],
                    "weights": weights.tolist(),
                }
            )
            before, prior_cash = values.copy(), cash
            wealth = float(values.sum() + cash)
            values, cash, cost, turn = validation.rebalance(
                values, cash, weights, request.fee_rate
            )
            values[whole] = (
                np.floor(values[whole] / execution[i, whole] + 1e-10)
                * execution[i, whole]
            )
            # Keep the intended risk reserve: do not reinvest intentional cash.
            delta = values - before
            cost = float(np.abs(delta).sum()) * request.fee_rate
            cash = wealth - float(values.sum()) - cost
            trade_cash = prior_cash
            for j in np.argsort(delta):
                if abs(delta[j]) <= 1e-8:
                    continue
                amount = float(abs(delta[j]))
                trade_cash -= float(delta[j]) + amount * request.fee_rate
                journal.append(
                    {
                        "signal": days[signal],
                        "execution": days[i],
                        "asset_id": assets[j]["id"],
                        "side": "buy" if delta[j] > 0 else "sell",
                        "amount": amount,
                        "quantity": amount / execution[i, j],
                        "fee": amount * request.fee_rate,
                        "cash_after": trade_cash,
                    }
                )
                if trade_cash < -1e-7:
                    raise ValueError("Unfunded order")
            if not np.isclose(trade_cash, cash, atol=1e-7):
                raise ValueError("Cash ledger mismatch")
            fees += cost
            turnover += float(np.abs(delta).sum()) / wealth
        if cash < -1e-7:
            raise ValueError("Negative cash")
        curve.append({"time": days[i], "value": float(values.sum() + cash)})
    equity = np.array([p["value"] for p in curve])
    benchmark_curve = np.array([benchmark[d] for d in days[first:]])
    changes = equity[1:] / equity[:-1] - 1
    metrics = curve_metrics(
        equity,
        changes,
        benchmark_curve[1:] / benchmark_curve[:-1] - 1,
        (dates[-1] - dates[first]).days / 365.25,
        252,
    )
    metrics.update(
        cost_eur=fees,
        market_exposure=exposure_days / (dates[-1] - dates[first + 1]).days,
    )
    if not np.isclose(sum(t["fee"] for t in journal), fees):
        raise ValueError("Fee ledger mismatch")
    return {
        "start": days[first],
        "end": days[-1],
        "metrics": metrics,
        "final_value": float(equity[-1]),
        "cash_final": float(cash),
        "transactions": len(journal),
        "turnover_including_entry": turnover,
        "equity": curve,
        "allocations": allocations,
        "journal": journal,
    }


def audit_ledger(inputs, request, result):
    """Reconstruct every close independently using quantities, cash and payouts."""
    assets = inputs["assets"]
    quantities = dict.fromkeys((a["id"] for a in assets), 0.0)
    cash = request.initial_capital
    previous = result["start"]
    by_day = {}
    for trade in result["journal"]:
        if trade["signal"] >= trade["execution"]:
            raise ValueError("Nonchronological order")
        by_day.setdefault(trade["execution"], []).append(trade)
    for point in result["equity"]:
        day = point["time"]
        for j, asset in enumerate(assets):
            whole = request.whole_shares and asset["category"] in ("stock", "etf")
            if whole:
                cash += quantities[asset["id"]] * sum(
                    v
                    for d, v in inputs["cash_distributions"][j].items()
                    if previous < d <= day
                )
        for trade in by_day.get(day, []):
            identifier = trade["asset_id"]
            j = next(j for j, a in enumerate(assets) if a["id"] == identifier)
            whole = request.whole_shares and assets[j]["category"] in ("stock", "etf")
            if whole and abs(trade["quantity"] - round(trade["quantity"])) > 1e-7:
                raise ValueError("Fractional stock in whole-share mode")
            history = (
                inputs["execution_histories"][j] if whole else inputs["histories"][j]
            )
            if day not in history:
                raise ValueError("Order before listing or without a quote")
            if not np.isclose(trade["amount"], trade["quantity"] * history[day]):
                raise ValueError("Order quantity/price mismatch")
            sign = 1 if trade["side"] == "buy" else -1
            quantities[identifier] += sign * trade["quantity"]
            cash -= sign * trade["amount"] + trade["fee"]
            if quantities[identifier] < -1e-7 or cash < -1e-7:
                raise ValueError("Short position or unfunded order")
            if not np.isclose(cash, trade["cash_after"], atol=1e-7):
                raise ValueError("Independent cash mismatch")
        total = cash
        for j, asset in enumerate(assets):
            if quantities[asset["id"]] <= 1e-10:
                continue
            whole = request.whole_shares and asset["category"] in ("stock", "etf")
            history = (
                inputs["execution_histories"][j] if whole else inputs["histories"][j]
            )
            total += quantities[asset["id"]] * history[day]
        if not np.isclose(total, point["value"], atol=1e-7):
            raise ValueError(f"Independent NAV mismatch on {day}")
        previous = day
    return "Every close reconstructed from quantities, distributions, cash and fees"


def acceptable(candidate, reference):
    c, r = candidate["metrics"], reference["metrics"]
    return (
        c["sharpe"] >= r["sharpe"] + 0.10
        and abs(c["max_drawdown"]) <= 0.80 * abs(r["max_drawdown"])
        and c["cagr"] >= 0.80 * r["cagr"]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/backtests/quantitative-strategies-study.json"),
    )
    parser.add_argument("--snapshot", type=Path, help="Read an existing SQLite archive")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source = args.snapshot or db.DATA_DIR / "investor.sqlite3"
    with tempfile.TemporaryDirectory(prefix="investor-quant-") as temporary:
        frozen = Path(temporary) / "investor.sqlite3"
        with (
            sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True) as src,
            sqlite3.connect(frozen) as dst,
        ):
            src.backup(dst)
        db.DATA_DIR = Path(temporary)
        result = {
            "snapshot_sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
            "criterion": CRITERION,
            "policy_parameters": {
                "lookback_months": 12,
                "variance_months": 1,
                "annual_risk_target": 0.15,
                "position_cap": 0.25,
                "fee_rate": 0.005,
                "whole_shares": True,
                "capital": 10000,
            },
            "results": {},
            "decisions": {},
        }
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        scenarios = [("journal_14", name, 0.005) for name in PERIODS]
        scenarios += [("journal_14", "recent", 0.01)]
        scenarios += [
            (universe, "five_years", 0.005) for universe in ("actions_11", "crypto_4")
        ]
        for universe, period, fee in scenarios:
            start, end = PERIODS[period]
            request = validation.ValidationRequest(
                asset_ids=UNIVERSES[universe],
                mode="mean_reversion",
                years=10,
                whole_shares=True,
                fee_rate=fee,
                start_date=start,
                end_date=end,
                reversion_entry_z=2,
                reversion_exit_z=2,
                reversion_exit_mode="trailing_z",
                reversion_trailing_gap=1,
                reversion_funding_min_z=0.3,
            )
            inputs = load_inputs(request)
            key = f"{universe}:{period}:{fee}"
            measured = {p: simulate(inputs, request, p) for p in POLICIES}
            for measured_policy in measured.values():
                measured_policy["audit"] = audit_ledger(
                    inputs, request, measured_policy
                )
            current = validation.validation_data(
                inputs["assets"],
                inputs["histories"],
                inputs["benchmark"],
                request,
                **{
                    k: inputs[k]
                    for k in (
                        "signal_histories",
                        "execution_histories",
                        "cash_distributions",
                        "benchmark_asset",
                    )
                },
            )
            if current["status"] != "ready":
                raise ValueError(current)
            measured["current_reversion"] = {
                "metrics": current["metrics"]["strategy"],
                "final_value": current["final_portfolio"]["total"],
                "transactions": len(current["transactions"]),
            }
            for name in ("equal", "buy_hold", "benchmark"):
                measured[name] = {
                    "metrics": current["metrics"][name],
                    "final_value": current["equity"][-1][name] * 100,
                }
            result["results"][key] = measured
            for policy in (
                "equal_monthly",
                "variance_managed",
                "time_series_momentum",
                "current_reversion",
            ):
                m = measured[policy]["metrics"]
                print(
                    f"{key} {policy}: return={m['total_return']:.2%} DD={m['max_drawdown']:.2%} Sharpe={m['sharpe']:.3f} fees={m['cost_eur']:.2f}",
                    flush=True,
                )
            args.output.write_text(json.dumps(result, indent=2) + "\n")
        for policy in POLICIES[1:]:
            checks = {}
            for period in ("middle", "recent"):
                sample = result["results"][f"journal_14:{period}:0.005"]
                checks[period] = acceptable(sample[policy], sample["equal_monthly"])
            stress = result["results"]["journal_14:recent:0.01"]
            checks["fees_1pct"] = acceptable(stress[policy], stress["equal_monthly"])
            for period in ("early", "five_years"):
                sample = result["results"][f"journal_14:{period}:0.005"]
                c, r = sample[policy]["metrics"], sample["equal_monthly"]["metrics"]
                checks[period] = (
                    c["cagr"] > 0 and c["max_drawdown"] >= r["max_drawdown"]
                )
            result["decisions"][policy] = {
                "checks": checks,
                "retain": all(checks.values()),
            }
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result["decisions"], indent=2), flush=True)


if __name__ == "__main__":
    main()
