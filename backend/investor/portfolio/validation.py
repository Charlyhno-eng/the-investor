"""Chronological allocation validation; signals at t, execution at t+1 close."""

import math
from bisect import bisect_left
from datetime import date
from typing import Literal

import numpy as np
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator

from investor.assets.momentum import months_before
from investor.db import connect
from investor.portfolio.performance import optimize_weights
from investor.portfolio.reversion import regression_z, reversion_exits, reversion_orders
from investor.portfolio.statistics import curve_metrics, factor_regression
from investor.portfolio.validation_history import align, history_notices, maturities
from investor.portfolio.volatility import load_histories, observations


class ValidationRequest(BaseModel):
    asset_ids: list[str] = Field(min_length=1, max_length=20)
    mode: Literal["volatility", "mean_reversion", "correlation"] = "volatility"
    years: Literal[1, 3, 5, 10] = 5
    fee_rate: float = Field(default=0.005, ge=0, le=0.1, allow_inf_nan=False)
    initial_capital: float = Field(default=10000, ge=1, le=1e12, allow_inf_nan=False)
    benchmark_asset_id: str | None = None
    whole_shares: bool = False
    reversion_entry_z: float = Field(default=1.4, ge=0.5, le=4, allow_inf_nan=False)
    reversion_exit_z: float = Field(default=1.4, ge=0, le=4, allow_inf_nan=False)
    reversion_exit_mode: Literal["threshold", "trailing_z"] = "threshold"
    reversion_trailing_gap: float = Field(
        default=0.5, ge=0.1, le=2, allow_inf_nan=False
    )
    reversion_funding_min_z: float = Field(default=0, ge=0, le=2, allow_inf_nan=False)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def chronological_dates(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValueError("La date de début doit précéder la date de fin.")
        return self


def rebalance(values, cash, target, fee):
    """Self-financing trade, charging both purchases and sales, including entry."""
    wealth = float(values.sum() + cash)
    low, high = 0.0, wealth
    for _ in range(60):
        net = (low + high) / 2
        if net + fee * np.abs(net * target - values).sum() > wealth:
            high = net
        else:
            low = net
    net = (low + high) / 2
    volume = float(np.abs(net * target - values).sum())
    return net * target, net * (1 - target.sum()), fee * volume, volume / wealth


def invest_remainder(values, previous, wealth, target, units, mask, fee):
    """Use affordable whole securities with positive optimizer target weights."""
    while True:
        cost = float(np.abs(values - previous).sum()) * fee
        cash = wealth - float(values.sum()) - cost
        eligible = mask & (target > 1e-12) & (units * (1 + fee) <= cash + 1e-10)
        if not np.any(eligible):
            return values, max(0.0, cash), cost
        budgets = cash * target[eligible] / target[eligible].sum()
        additions = np.floor(budgets / (units[eligible] * (1 + fee)))
        if not np.any(additions):
            indices = np.flatnonzero(eligible)
            # Prefer the line furthest below its continuous target.
            j = indices[np.argmax((wealth * target - values)[indices])]
            values[j] += units[j]
        else:
            values[eligible] += additions * units[eligible]


def validation_data(
    assets,
    histories,
    benchmark,
    request,
    *,
    signal_histories=None,
    execution_histories=None,
    cash_distributions=None,
    benchmark_asset=None,
):
    """Pure engine: only training slices ever reach the allocation optimizer."""
    assets = [dict(a) for a in assets]
    if not benchmark:
        return {
            "status": "insufficient",
            "message": "Historique absent pour les actifs ou la référence.",
        }
    if any(
        not math.isfinite(value) or value <= 0
        for h in [*histories, benchmark]
        for value in h.values()
    ):
        return {
            "status": "insufficient",
            "message": "Les prix doivent être positifs et finis.",
        }
    if signal_histories is not None and any(
        not math.isfinite(value) or value <= 0
        for h in signal_histories
        for value in h.values()
    ):
        return {
            "status": "insufficient",
            "message": "Les cours de signal doivent être positifs et finis.",
        }
    nonempty = [h for h in histories if h] or [benchmark]
    end = min(max(benchmark), max(max(h) for h in nonempty))
    if request.end_date:
        end = min(end, request.end_date.isoformat())
    daily = [
        (min(h), h)
        for a, h in zip(assets, histories, strict=True)
        if h and a.get("frequency", "daily") == "daily"
    ]
    days = sorted(
        d
        for d in benchmark
        if d <= end and all(d < start or d in h for start, h in daily)
    )
    if len(days) < 2:
        return {"status": "insufficient", "message": "Pas assez de dates communes."}
    dates = [date.fromisoformat(d) for d in days]
    earliest = months_before(dates[0], -36)
    requested = request.start_date or months_before(dates[-1], request.years * 12)
    first = bisect_left(dates, max(earliest, requested))
    if first + 2 >= len(days):
        return {
            "status": "insufficient",
            "message": "Il faut trois ans d’apprentissage puis une période de validation pour au moins un actif.",
        }
    used_start = months_before(dates[first], 36).isoformat()
    for a, h in zip(
        [*assets, {"frequency": "daily"}], [*histories, benchmark], strict=True
    ):
        quotes = sorted(d for d in h if used_start <= d <= days[-1])
        if a.get("frequency", "daily") == "daily" and any(
            (date.fromisoformat(b) - date.fromisoformat(a)).days > 10
            for a, b in zip(quotes, quotes[1:], strict=False)
        ):
            return {
                "status": "insufficient",
                "message": "Un trou de plus de dix jours existe dans les historiques. Vérifiez les données.",
            }
    aligned = np.column_stack([align(h, days) for h in [*histories, benchmark]])
    # Unit placeholders are never tradable or used to train a new listing.
    prices = np.where(np.isfinite(aligned), aligned, 1.0)
    if not np.all(np.isfinite(prices)) or np.any(prices <= 0):
        return {
            "status": "insufficient",
            "message": "Les prix doivent être positifs et finis.",
        }
    signal_prices = np.column_stack(
        [
            align(h, days)
            for h in (signal_histories if signal_histories is not None else histories)
        ]
    )
    if np.any(np.isfinite(signal_prices) & (signal_prices <= 0)):
        return {
            "status": "insufficient",
            "message": "Les cours de signal doivent être positifs et finis.",
        }
    tradable = np.array(
        [
            [
                d in h
                if a.get("frequency", "daily") == "daily"
                else bool(h) and min(h) <= d
                for a, h in zip(assets, histories, strict=True)
            ]
            for d in days
        ]
    )
    passive = np.array(
        [
            request.mode == "mean_reversion"
            and a.get("category", "stock") not in ("stock", "crypto")
            for a in assets
        ]
    )
    matured = maturities(histories, days)
    scale = request.initial_capital / 100
    instruments = [
        *[dict(a) for a in assets],
        dict(benchmark_asset) if benchmark_asset is not None else {"category": "index"},
    ]
    whole = np.array(
        [
            request.whole_shares and a.get("category") in ("stock", "etf")
            for a in instruments
        ]
    )
    execution_prices = prices.copy()
    distributions = np.zeros_like(prices)
    for j in np.flatnonzero(whole):
        history = execution_histories[j] if execution_histories else {}
        raw_prices = align(history, days)
        needed = np.isfinite(aligned[:, j])
        observed = [*histories, benchmark][j]
        if any(d not in history for d in observed if days[first] <= d <= days[-1]):
            raw_prices[:] = np.nan
        if np.any(
            needed[first:]
            & (~np.isfinite(raw_prices[first:]) | (raw_prices[first:] <= 0))
        ):
            return {
                "status": "insufficient",
                "message": f"Cours non ajustés des dividendes manquants pour {instruments[j]['name']} : le mode titres entiers nécessite ces cours.",
            }
        for i in range(first, len(days)):
            if needed[i]:
                execution_prices[i, j] = raw_prices[i]
        payouts = sorted((cash_distributions or [{} for _ in instruments])[j].items())
        k = 0
        for i in range(first + 1, len(days)):
            while k < len(payouts) and payouts[k][0] <= days[i]:
                day, amount = payouts[k]
                if day > days[i - 1]:
                    distributions[i, j] += amount
                k += 1
    # Anchor all quarter anniversaries to the initial signal, avoiding calendar drift.
    signals = []
    quarter = 0
    while True:
        i = bisect_left(dates, months_before(dates[first], -3 * quarter))
        if i + 1 >= len(days):
            break
        signals.append(i)
        quarter += 1
    events = {i + 1: i for i in signals}
    keys = ("strategy", "equal", "buy_hold", "benchmark")
    count = len(assets)
    books = {key: (np.zeros(1 if key == "benchmark" else count), 100.0) for key in keys}
    costs = dict.fromkeys(keys, 0.0)
    turnovers = dict.fromkeys(keys, 0.0)
    initial_turnover = dict.fromkeys(keys, 0.0)
    exposed_capital_days = dict.fromkeys(keys, 0.0)
    equity, folds, active = [], [], None
    transactions = []
    cost_basis = np.zeros(count)
    received_dividends = np.zeros(count)
    strategy_entered = False
    reversion_peaks = np.full(count, np.nan)
    passive_entered = np.zeros(count, dtype=bool)
    buy_hold_entered = np.zeros(count, dtype=bool)

    def record_trades(before, after, execution, signal, scores=None, reasons=None):
        delta = after - before
        trade_cash = float(books["strategy"][1] * scale)
        portfolio_before = float(before.sum() * scale + trade_cash)
        if scores is None and np.any(np.abs(delta) > 1e-9):
            scores = regression_z(signal_prices, dates, signal)
        # Sales precede purchases, matching the self-financing rebalance.
        for j in np.argsort(delta):
            amount = float(abs(delta[j]))
            if amount <= 1e-9:
                continue
            quantity = amount * scale / execution_prices[execution, j]
            cash_before = trade_cash
            trade_cash -= float(delta[j] * scale + amount * request.fee_rate * scale)
            profit_return = None
            if delta[j] > 0:
                cost_basis[j] += amount * scale * (1 + request.fee_rate)
            else:
                fraction = min(1.0, amount / before[j])
                basis = cost_basis[j] * fraction
                dividend = received_dividends[j] * fraction
                if basis > 0:
                    profit_return = (
                        amount * scale * (1 - request.fee_rate) + dividend
                    ) / basis - 1
                cost_basis[j] -= basis
                received_dividends[j] -= dividend
            transactions.append(
                {
                    "reason": reasons[j] if reasons is not None else "rebalance",
                    "profit_return": profit_return,
                    "asset_id": assets[j]["id"],
                    "name": assets[j]["name"],
                    "signal": days[signal],
                    "execution": days[execution],
                    "side": "buy" if delta[j] > 0 else "sell",
                    "quantity": int(
                        round(amount * scale / execution_prices[execution, j])
                    )
                    if whole[j]
                    else quantity,
                    "price": float(execution_prices[execution, j]),
                    "amount": amount * scale,
                    "fee": amount * request.fee_rate * scale,
                    "cash_before": cash_before,
                    "cash_after": trade_cash,
                    "portfolio_before": portfolio_before,
                    "z": scores[j] if scores is not None else None,
                }
            )

    def wealths():
        return {key: float(v.sum() + cash) for key, (v, cash) in books.items()}

    def finish(end, complete):
        if active is None:
            return
        active["end"] = end
        active["complete"] = complete
        active["returns"] = {
            key: wealths()[key] / active["capital_before"][key] - 1 for key in keys
        }
        folds.append(active.copy())

    for i in range(first, len(days)):
        # Snapshot the previous close BEFORE applying the execution-day return.
        signal_values, signal_cash = books["strategy"]
        signal_total = float(signal_values.sum() + signal_cash)
        current = (
            signal_values / signal_total
            if signal_values.sum() > 0
            else np.full(count, 1 / count)
        )
        if i > first:
            interval_days = (dates[i] - dates[i - 1]).days
            # Exclude the shared wait from the signal to the first execution.
            if i > first + 1:
                for key, (values, cash) in books.items():
                    total = float(values.sum() + cash)
                    exposed_capital_days[key] += interval_days * float(
                        np.clip(values.sum() / total, 0, 1)
                    )
            growth = prices[i] / prices[i - 1]
            raw_growth = execution_prices[i] / execution_prices[i - 1]
            for key, (values, cash) in books.items():
                columns = slice(-1, None) if key == "benchmark" else slice(None, -1)
                mask = whole[columns]
                previous_units = values * scale / execution_prices[i - 1, columns]
                payout = previous_units * distributions[i, columns] / scale
                new_values = values * np.where(
                    mask, raw_growth[columns], growth[columns]
                )
                books[key] = new_values, cash + float(payout.sum())
                if key == "strategy":
                    received_dividends += payout * scale
        if i in events:
            finish(days[i], True)  # End the preceding holding period BEFORE trading.
            signal = events[i]
            lower = bisect_left(dates, months_before(dates[signal], 36))
            if (
                signal - lower < 500
                or (dates[lower] - months_before(dates[signal], 36)).days > 7
            ):
                return {
                    "status": "insufficient",
                    "message": f"Trois ans et au moins 500 variations communes sont nécessaires au {days[signal]}.",
                }
            training = prices[lower + 1 : signal + 1] / prices[lower:signal] - 1
            eligible = matured[signal] & tradable[signal] & tradable[i]
            try:
                target = np.zeros(count)
                if request.mode == "mean_reversion":
                    target = signal_values / signal_total
                elif np.any(eligible):
                    subset = current[eligible]
                    subset = (
                        subset / subset.sum()
                        if subset.sum() > 0
                        else np.full(eligible.sum(), 1 / eligible.sum())
                    )
                    target[eligible] = optimize_weights(
                        training[:, :-1][:, eligible],
                        subset,
                        request.mode,
                        elapsed_years=(dates[signal] - dates[lower]).days / 365.25,
                    )
            except HTTPException as error:
                return {
                    "status": "insufficient",
                    "message": f"Validation interrompue au {days[signal]} : {error.detail} Aucun trimestre n’est ignoré.",
                }
            active = {
                "signal": days[signal],
                "execution": days[i],
                "train_start": days[lower],
                "train_end": days[signal],
                "observations": len(training),
                "weights": (
                    signal_values / signal_total
                    if request.mode == "mean_reversion"
                    else target
                ).tolist(),
                "training_beta": factor_regression(
                    training[:, :-1] @ target, training[:, -1], 252
                )[1],
                "capital_before": wealths(),
                "costs": {},
                "turnover": {},
            }
            for key in keys:
                if key == "strategy" and request.mode == "mean_reversion":
                    active["costs"][key] = active["turnover"][key] = 0.0
                    continue
                if key == "buy_hold" or (key == "benchmark" and len(folds) > 0):
                    active["costs"][key] = active["turnover"][key] = 0.0
                    continue
                weights = (
                    target
                    if key == "strategy"
                    else np.ones(1)
                    if key == "benchmark"
                    else (tradable[signal] & tradable[i]).astype(float) / count
                )
                values, remaining, cost, turnover = rebalance(
                    *books[key], weights, request.fee_rate
                )
                columns = slice(-1, None) if key == "benchmark" else slice(None, -1)
                mask = whole[columns]
                if np.any(mask):
                    units = execution_prices[i, columns] / scale
                    values[mask] = (
                        np.floor(values[mask] / units[mask] + 1e-10) * units[mask]
                    )
                    previous, cash = books[key]
                    volume = float(np.abs(values - previous).sum())
                    cost = volume * request.fee_rate
                    remaining = float(previous.sum() + cash - values.sum() - cost)
                    if key == "strategy":
                        values, remaining, cost = invest_remainder(
                            values,
                            previous,
                            float(previous.sum() + cash),
                            weights,
                            units,
                            mask,
                            request.fee_rate,
                        )
                        volume = float(np.abs(values - previous).sum())
                    turnover = volume / float(previous.sum() + cash)
                if key == "strategy":
                    record_trades(books[key][0], values, i, signal)
                books[key] = values, remaining
                costs[key] += cost
                if not folds:
                    initial_turnover[key] += turnover
                else:
                    turnovers[key] += turnover
                active["costs"][key], active["turnover"][key] = cost, turnover
        if i > first:
            # Each buy-and-hold sleeve retains its initial budget until listing.
            before, cash = books["buy_hold"]
            values = before.copy()
            for j in np.flatnonzero(~buy_hold_entered & tradable[i - 1] & tradable[i]):
                amount = min(100 / count, cash) / (1 + request.fee_rate)
                if whole[j]:
                    unit = execution_prices[i, j] / scale
                    amount = np.floor(amount / unit + 1e-10) * unit
                values[j] += amount
                cash -= amount * (1 + request.fee_rate)
                buy_hold_entered[j] = True
                costs["buy_hold"] += amount * request.fee_rate
                initial_turnover["buy_hold"] += amount / 100
                if active is not None:
                    active["costs"]["buy_hold"] += amount * request.fee_rate
                    active["turnover"]["buy_hold"] += amount / 100
            books["buy_hold"] = values, cash
        if request.mode == "mean_reversion" and i > first:
            scores = regression_z(signal_prices, dates, i - 1)
            before, cash = books["strategy"]
            values = before.copy()
            for j in np.flatnonzero(
                passive & ~passive_entered & tradable[i - 1] & tradable[i]
            ):
                amount = (100 / count) / (1 + request.fee_rate)
                if whole[j]:
                    unit = execution_prices[i, j] / scale
                    amount = np.floor(amount / unit + 1e-10) * unit
                values[j] += amount
                cash -= amount * (1 + request.fee_rate)
                passive_entered[j] = True
            reserved = float(np.sum(passive & ~passive_entered)) * 100 / count
            order_scores = [
                score
                if not passive[j]
                and tradable[i - 1, j]
                and tradable[i, j]
                and matured[i - 1, j]
                else None
                for j, score in enumerate(scores)
            ]
            exits = reversion_exits(
                before,
                order_scores,
                reversion_peaks,
                exit_z=request.reversion_exit_z,
                mode=request.reversion_exit_mode,
                gap=request.reversion_trailing_gap,
            )
            values, remaining_cash = reversion_orders(
                values,
                max(0.0, cash - reserved),
                order_scores,
                request.fee_rate,
                unit_prices=execution_prices[i, :-1] / scale,
                whole=whole[:-1],
                active=(~passive & tradable[i - 1] & tradable[i]),
                portfolio_value=float(values.sum() + cash),
                entry_z=request.reversion_entry_z,
                exit_z=request.reversion_exit_z,
                funding_min_z=request.reversion_funding_min_z,
                exits=exits,
            )
            for j in range(count):
                if values[j] <= 1e-12:
                    reversion_peaks[j] = np.nan
                elif before[j] <= 1e-12 and order_scores[j] is not None:
                    reversion_peaks[j] = order_scores[j]
            volume = float(np.abs(values - before).sum())
            capital_before = float(before.sum() + books["strategy"][1])
            cost = volume * request.fee_rate
            turn = volume / capital_before
            reasons = [
                "buy_hold"
                if passive[j]
                else "entry"
                if values[j] > before[j]
                else "trailing_z"
                if exits[j] and request.reversion_exit_mode == "trailing_z"
                else "threshold"
                if exits[j]
                else "funding"
                for j in range(count)
            ]
            record_trades(before, values, i, i - 1, scores, reasons)
            books["strategy"] = values, remaining_cash + reserved
            costs["strategy"] += cost
            if volume > 1e-9 and not strategy_entered:
                initial_turnover["strategy"] += turn
                strategy_entered = True
            else:
                turnovers["strategy"] += turn
            if active is not None:
                active["costs"]["strategy"] += cost
                active["turnover"]["strategy"] += turn
        equity.append({"time": days[i], **wealths()})
    finish(days[-1], False)
    elapsed = (dates[-1] - dates[first]).days / 365.25
    curves = {key: np.array([p[key] for p in equity]) for key in keys}
    if any(not np.all(np.isfinite(c)) or np.any(c <= 0) for c in curves.values()):
        return {
            "status": "insufficient",
            "message": "Les valeurs simulées dépassent les limites du calcul.",
        }
    changes = {key: c[1:] / c[:-1] - 1 for key, c in curves.items()}
    completed = [f for f in folds if f["complete"]]
    metrics = {}
    for key in keys:
        metrics[key] = {
            **curve_metrics(
                curves[key],
                changes[key],
                changes["benchmark"],
                elapsed,
                252,
                benchmark=key == "benchmark",
            ),
            "cost_base_100": costs[key],
            "cost_eur": costs[key] * scale,
            "market_exposure": exposed_capital_days[key]
            / (dates[-1] - dates[first + 1]).days,
            "annual_turnover": turnovers[key] / elapsed,
            "initial_turnover": initial_turnover[key],
            "positive_quarters": sum(f["returns"][key] > 0 for f in completed),
            "winning_quarters": sum(
                f["returns"][key] > f["returns"]["benchmark"] for f in completed
            ),
            "worst_quarter": min((f["returns"][key] for f in completed), default=None),
        }
    return {
        "status": "ready",
        "start": days[first],
        "end": days[-1],
        "requested_start": requested.isoformat(),
        "training_years": 3,
        "holding_months": None if request.mode == "mean_reversion" else 3,
        "reporting_months": 3,
        "fee_rate": request.fee_rate,
        "parameters": request.model_dump(mode="json"),
        "protocol": {
            "execution": "next_common_close",
            "annualization": 252,
            "survivorship_and_selection_bias": True,
            "cash_return": 0,
            "exposure_basis": "invested_capital_calendar_time_after_first_execution",
            "whole_shares": request.whole_shares,
            "dividends_paid_as_cash": bool(np.any(whole)),
            "signal_frequency": "daily"
            if request.mode == "mean_reversion"
            else "quarterly",
            "reversion_sizing": "capped_entry_single_highest_z_funding_sale"
            if request.mode == "mean_reversion"
            else None,
            "reversion_threshold": request.reversion_entry_z
            if request.mode == "mean_reversion"
            and request.reversion_entry_z == request.reversion_exit_z
            else None,
            "reversion_entry_z": request.reversion_entry_z,
            "reversion_exit_z": request.reversion_exit_z,
            "reversion_exit_mode": request.reversion_exit_mode,
            "reversion_trailing_gap": request.reversion_trailing_gap,
            "reversion_entry_cap": 0.25 if request.mode == "mean_reversion" else None,
            "reversion_entry_floor": "min(0.10, 1/tradable_active_assets)"
            if request.mode == "mean_reversion"
            else None,
            "reversion_funding_target": "minimum_entry"
            if request.mode == "mean_reversion"
            else None,
            "reversion_funding_min_z": request.reversion_funding_min_z
            if request.mode == "mean_reversion"
            else None,
            "reversion_cash_first_sizing": request.mode == "mean_reversion",
            "reversion_max_funding_positions": 1
            if request.mode == "mean_reversion"
            else None,
            "tax_spread_and_market_impact_included": False,
        },
        "mode": request.mode,
        "notices": history_notices(assets, histories, request, days[first]),
        "final_portfolio": {
            "date": days[-1],
            "initial_capital": request.initial_capital,
            "total": wealths()["strategy"] * scale,
            "cash": books["strategy"][1] * scale,
            "positions": [
                {
                    "id": a["id"],
                    "name": a["name"],
                    "whole_shares": bool(whole[j]),
                    "quantity": int(
                        round(books["strategy"][0][j] * scale / execution_prices[-1, j])
                    )
                    if whole[j]
                    else float(
                        books["strategy"][0][j] * scale / execution_prices[-1, j]
                    ),
                    "value": float(books["strategy"][0][j] * scale),
                    "weight": float(books["strategy"][0][j] / wealths()["strategy"]),
                }
                for j, a in enumerate(assets)
            ],
        },
        "transactions": transactions,
        "assets": [{"id": a["id"], "name": a["name"]} for a in assets],
        "observations": len(equity) - 1,
        "completed_quarters": len(completed),
        "equity": equity,
        "metrics": metrics,
        "folds": folds,
    }


def portfolio_validation(request):
    if len(set(request.asset_ids)) != len(request.asset_ids):
        raise HTTPException(422, "Un actif ne peut figurer qu’une fois.")
    with connect() as connection:
        ids = [*request.asset_ids]
        if request.benchmark_asset_id and request.benchmark_asset_id not in ids:
            ids.append(request.benchmark_asset_id)
        assets = []
        for identifier in ids:
            asset = connection.execute(
                "SELECT * FROM assets WHERE id=?", (identifier,)
            ).fetchone()
            if asset is None:
                raise HTTPException(404, f"Actif introuvable : {identifier}")
            if (
                request.mode != "mean_reversion"
                or identifier == request.benchmark_asset_id
            ) and (
                asset["category"] not in ("stock", "etf", "crypto")
                or asset["frequency"] != "daily"
            ):
                raise HTTPException(
                    422,
                    f"{asset['name']} : seuls les actions, ETF et cryptos à historique quotidien sont admis.",
                )
            assets.append(asset)
        loaded = load_histories(
            connection,
            assets,
            include_benchmark=not request.benchmark_asset_id,
            allow_cached=True,
        )
        if loaded is None:
            return {"status": "pending"}
        histories, benchmark = loaded
        histories = [
            h if a["metric"] == "price" else {}
            for a, h in zip(assets, histories, strict=True)
        ]
        signal_histories = [
            observations(connection, a) if a["metric"] == "price" else {}
            for a in assets[: len(request.asset_ids)]
        ]
        if request.benchmark_asset_id:
            benchmark = histories[ids.index(request.benchmark_asset_id)]
        execution_histories = None
        cash_distributions = None
        benchmark_asset = (
            assets[ids.index(request.benchmark_asset_id)]
            if request.benchmark_asset_id
            else None
        )
        if request.whole_shares:
            execution_histories, cash_distributions = [], []
            # Convert raw closes and dividend payments with the same historical FX.
            for j, a in enumerate(assets):
                native = observations(connection, a)
                fx = {
                    d: histories[j][d] / value
                    for d, value in native.items()
                    if d in histories[j]
                }
                raw = {
                    r["date"]: r["value"] * fx[r["date"]]
                    for r in connection.execute(
                        "SELECT date,value FROM price_observations WHERE asset_id=?",
                        (a["id"],),
                    )
                    if r["date"] in fx and math.isfinite(r["value"]) and r["value"] > 0
                }
                payouts = {
                    r["date"]: r["amount"] * fx[r["date"]]
                    for r in connection.execute(
                        "SELECT date,amount FROM dividends WHERE asset_id=?", (a["id"],)
                    )
                    if r["date"] in fx
                    and math.isfinite(r["amount"])
                    and r["amount"] > 0
                }
                execution_histories.append(raw)
                cash_distributions.append(payouts)
            benchmark_index = (
                ids.index(request.benchmark_asset_id)
                if request.benchmark_asset_id
                else None
            )
            execution_histories = execution_histories[: len(request.asset_ids)] + [
                execution_histories[benchmark_index]
                if benchmark_index is not None
                else {}
            ]
            cash_distributions = cash_distributions[: len(request.asset_ids)] + [
                cash_distributions[benchmark_index]
                if benchmark_index is not None
                else {}
            ]
        result = validation_data(
            assets[: len(request.asset_ids)],
            histories[: len(request.asset_ids)],
            benchmark,
            request,
            signal_histories=signal_histories,
            execution_histories=execution_histories,
            cash_distributions=cash_distributions,
            benchmark_asset=benchmark_asset,
        )
        result["benchmark_name"] = (
            assets[ids.index(request.benchmark_asset_id)]["name"]
            if request.benchmark_asset_id
            else "S&P 500 · dividendes réinvestis"
        )
        return result
