"""Historical block resampling; both portfolios trade the identical synthetic path."""

import secrets
from datetime import date, timedelta
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from investor.assets.momentum import months_before
from investor.db import connect
from investor.portfolio import etf_switch, psp5_agreement, psp5_downside
from investor.portfolio.validation import ValidationRequest, validation_data

BLOCK_SESSIONS = 63
NOISE_SCALE = 0.05


class Sp500SimulationRequest(BaseModel):
    strategy: Literal["regression", "downside"] = "regression"
    years: Literal[1, 3, 5, 10] = 5
    initial_capital: float = Field(default=10000, ge=1, le=1e12, allow_inf_nan=False)
    fee_rate: float = Field(default=0.0012, ge=0, le=0.1, allow_inf_nan=False)
    whole_shares: bool = True
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)


def sampled_returns(returns, count, seed):
    """Stationary blocks, restarting at history's end; never stitch end to start."""
    returns = np.asarray(returns, dtype=float)
    if returns.ndim != 1 or len(returns) < 2 or not np.all(np.isfinite(returns)):
        raise ValueError("Rendements historiques invalides.")
    # Independent streams keep a seeded path's prefix unchanged when its horizon
    # is extended; future draws must not alter earlier perturbations.
    blocks_seed, noise_seed = np.random.SeedSequence(seed).spawn(2)
    rng = np.random.default_rng(blocks_seed)
    noise_rng = np.random.default_rng(noise_seed)
    sampled = np.empty(count)
    index = len(returns)
    for i in range(count):
        if index >= len(returns) or rng.random() < 1 / BLOCK_SESSIONS:
            index = int(rng.integers(len(returns)))
        sampled[i] = returns[index]
        index += 1
    # Small zero-mean perturbation, not a Gaussian replacement for historical tails.
    return sampled + noise_rng.normal(0, NOISE_SCALE * returns.std(ddof=1), count)


def future_sessions(start, years):
    end = months_before(start, -12 * years)
    day = start + timedelta(days=1)
    days = []
    while day <= end:
        if day.weekday() < 5:
            days.append(day.isoformat())
        day += timedelta(days=1)
    return days


def prepare_history(rows, years, downside=False):
    """Validate one immutable source snapshot and prepare the shared calendar."""
    if downside and len(rows) < psp5_agreement.WINDOW + 1:
        return dict(
            status="insufficient", message="33 clôtures de PSP5 sont nécessaires."
        )
    if not downside and len(rows) < etf_switch.SLOW_MIN_OBSERVATIONS + 2:
        return {
            "status": "insufficient",
            "message": "Importez au moins cinq ans de cours S&P 500 PEA (PSP5) pour simuler la stratégie complète.",
        }
    days = [r[0] for r in rows]
    adjusted = np.array([r[1] for r in rows], dtype=float)
    if (
        not np.all(np.isfinite(adjusted))
        or np.any(adjusted <= 0)
        or days != sorted(set(days))
        or any(date.fromisoformat(d).isoformat() != d for d in days)
    ):
        return {"status": "insufficient", "message": "Historique PSP5 invalide."}
    start = date.fromisoformat(days[-1])
    if any(
        (date.fromisoformat(b) - date.fromisoformat(a)).days > 10
        for a, b in zip(days, days[1:], strict=False)
    ):
        return {
            "status": "insufficient",
            "message": "Un trou de plus de dix jours existe dans l’historique PSP5. Actualisez ses données.",
        }
    if not downside and date.fromisoformat(days[0]) > months_before(start, 60):
        return {
            "status": "insufficient",
            "message": "Cinq années calendaires d’historique PSP5 sont nécessaires.",
        }
    anchor = rows[-1][2]
    if anchor is None or not np.isfinite(anchor) or anchor <= 0:
        return {
            "status": "insufficient",
            "message": "Cours de clôture PSP5 absent : actualisez ses données.",
        }
    return dict(
        status="ready",
        days=days,
        adjusted=adjusted,
        anchor=anchor,
        start=start,
        synthetic_days=future_sessions(start, years),
        returns=np.diff(np.log(adjusted)),
        prices=adjusted / adjusted[-1] * anchor,
    )


def simulate_history(rows, request):
    """Pure comparison using the unchanged production validation engine."""
    prepared = prepare_history(rows, request.years, request.strategy == "downside")
    if prepared["status"] != "ready":
        return prepared
    days = prepared["days"]
    anchor = prepared["anchor"]
    start = prepared["start"]
    synthetic_days = prepared["synthetic_days"]
    seed = request.seed if request.seed is not None else secrets.randbits(32)
    if request.strategy == "downside":
        return psp5_downside.DownsideSimulation(prepared, request).path(
            seed, equity=True
        )
    increments = sampled_returns(prepared["returns"], len(synthetic_days), seed)
    values = anchor * np.exp(np.cumsum(increments))
    # Scale the historical adjusted series to the latest raw unit price. The
    # constant scale leaves all historical log-regression scores unchanged.
    history = dict(zip(days, prepared["prices"].tolist(), strict=True))
    history.update(zip(synthetic_days, values.tolist(), strict=True))
    asset = dict(
        id="yf-psp5.pa",
        name="S&P 500 simulé",
        category="etf",
        metric="price",
        unit="EUR",
        frequency="daily",
    )
    result = validation_data(
        [asset],
        [history],
        history,
        ValidationRequest(
            asset_ids=["yf-psp5.pa"],
            mode="etf_switch",
            years=request.years,
            initial_capital=request.initial_capital,
            fee_rate=request.fee_rate,
            whole_shares=request.whole_shares,
            start_date=start,
            end_date=date.fromisoformat(synthetic_days[-1]),
        ),
        benchmark_asset=asset,
        signal_histories=[history],
        execution_histories=[history, history],
        cash_distributions=[{}, {}],
    )
    if result["status"] != "ready":
        return result
    result["benchmark_name"] = "S&P 500 · Buy & Hold"
    # Expose only the requested two curves, never legacy equal-weight controls.
    result["metrics"] = {k: result["metrics"][k] for k in ("benchmark", "strategy")}
    result["equity"] = [
        {k: p[k] for k in ("time", "benchmark", "strategy")} for p in result["equity"]
    ]
    return {
        "status": "ready",
        "comparison": result,
        "simulation": {
            "seed": seed,
            "method": "stationary_block_bootstrap",
            "mean_block_sessions": BLOCK_SESSIONS,
            "noise_volatility_ratio": NOISE_SCALE,
            "source_asset_id": "yf-psp5.pa",
            "source_currency": "EUR",
            "source_start": days[0],
            "source_end": days[-1],
            "source_observations": len(days),
            "synthetic_sessions": len(synthetic_days),
            "historical_warmup": True,
            "cash_return": 0,
            "calendar": "weekdays_without_exchange_holidays",
            "synthetic_total_return": True,
        },
    }


def load_simulation_history():
    # Read local data only: no imports, cache population or synthetic DB writes.
    with connect() as connection:
        rows = connection.execute(
            "SELECT o.date,o.value,p.value FROM observations o "
            "LEFT JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date "
            "WHERE o.asset_id='yf-psp5.pa' ORDER BY o.date"
        ).fetchall()
    return rows


def sp500_simulation(request):
    return simulate_history(load_simulation_history(), request)


class Sp500BatchRequest(Sp500SimulationRequest):
    count: int = Field(default=1000, ge=1, le=10000)


# All comparisons are paired on the same path. Exclude beta/alpha, exposure and
# winning_quarters: these are contextual or defined relative to the benchmark,
# rather than symmetric measures of performance.
BATCH_METRICS = {
    "total_return": False,
    "cagr": False,
    "max_drawdown": False,  # signed loss: -5% is better than -30%
    "volatility": True,
    "downside_volatility": True,
    "sharpe": False,
    "sortino": False,
    "calmar": False,
    "worst_quarter": False,
    "positive_quarters": False,
    "annual_turnover": True,
    "cost_eur": True,
}


class BatchSummary:
    def __init__(self):
        self.completed = 0
        self.metrics = {
            key: dict(
                valid=0,
                benchmark_wins=0,
                strategy_wins=0,
                ties=0,
                benchmark_sum=0.0,
                strategy_sum=0.0,
            )
            for key in BATCH_METRICS
        }

    def add(self, comparison):
        self.completed += 1
        for key, lower in BATCH_METRICS.items():
            a = comparison["metrics"]["benchmark"].get(key)
            b = comparison["metrics"]["strategy"].get(key)
            if a is None or b is None or not np.isfinite(a) or not np.isfinite(b):
                continue
            row = self.metrics[key]
            row["valid"] += 1
            row["benchmark_sum"] += a
            row["strategy_sum"] += b
            if np.isclose(a, b, rtol=1e-9, atol=1e-10):
                row["ties"] += 1
            elif (a < b) if lower else (a > b):
                row["benchmark_wins"] += 1
            else:
                row["strategy_wins"] += 1

    def snapshot(self, total, seed):
        return dict(
            status="complete" if self.completed == total else "running",
            completed=self.completed,
            total=total,
            seed=seed,
            metrics={
                key: {
                    **{
                        k: row[k]
                        for k in ("valid", "benchmark_wins", "strategy_wins", "ties")
                    },
                    "benchmark_mean": row["benchmark_sum"] / row["valid"]
                    if row["valid"]
                    else None,
                    "strategy_mean": row["strategy_sum"] / row["valid"]
                    if row["valid"]
                    else None,
                    "lower_is_better": BATCH_METRICS[key],
                }
                for key, row in self.metrics.items()
            },
        )


async def stream_sp500_batch(request, disconnected):
    """Bounded vectorized groups; preserve seed order and every progress prefix.

    A seed plus count reconstructs the full batch, including interrupted prefixes.
    No database writes, retained curves, omitted failures or winner selection.
    """
    import asyncio
    import json

    from investor.portfolio.sp500_batch import CHUNK_SIZE, PreparedBatch

    rows = await asyncio.to_thread(load_simulation_history)
    seed = request.seed if request.seed is not None else secrets.randbits(32)
    summary = BatchSummary()
    joint_wins = 0

    def snapshot():
        result = summary.snapshot(request.count, seed)
        if request.strategy == "downside":
            result["joint_wins"] = joint_wins
        return json.dumps(result, allow_nan=False) + "\n"

    yield snapshot()
    if await disconnected():
        return
    source = await asyncio.to_thread(
        prepare_history, rows, request.years, request.strategy == "downside"
    )
    if source["status"] != "ready":
        yield (
            json.dumps(dict(status="error", message=source["message"], completed=0))
            + "\n"
        )
        return
    engine = (
        psp5_downside.DownsideSimulation
        if request.strategy == "downside"
        else PreparedBatch
    )
    prepared = await asyncio.to_thread(engine, source, request)
    while summary.completed < request.count:
        if await disconnected():
            return
        # A single first path makes the initial feedback and stop responsive.
        size = 1 if summary.completed == 0 else CHUNK_SIZE
        seeds = [
            (seed + i) % 2**32
            for i in range(
                summary.completed, min(request.count, summary.completed + size)
            )
        ]
        results = await asyncio.to_thread(prepared.simulate, seeds)
        for result in results:
            if await disconnected():
                return
            if result["status"] != "ready":
                yield (
                    json.dumps(
                        dict(
                            status="error",
                            message=result.get("message", "Calcul impossible."),
                            completed=summary.completed,
                        )
                    )
                    + "\n"
                )
                return
            comparison = result["comparison"]
            summary.add(comparison)
            if request.strategy == "downside":
                passive = comparison["metrics"]["benchmark"]
                strategy = comparison["metrics"]["strategy"]
                joint_wins += int(
                    all(
                        strategy[k] > passive[k] + 1e-10
                        for k in ("cagr", "max_drawdown")
                    )
                )
            yield snapshot()
