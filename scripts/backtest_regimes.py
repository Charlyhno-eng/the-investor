"""Fixed design, all listed local stocks/crypto, causal train/validation/test."""

import csv
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
from investor.analysis.metrics import equity, metrics
from investor.analysis.model import features, fit_model, forward_filter
from investor.analysis.reentry import model_signals, simulate_reentry
from investor.analysis.schemas import AnalysisRequest
from investor.analysis.service import calculate
from investor.market_catalog import REMOVED_CRYPTO

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/backtests/hmm-directional-final"


def previous(asset, rows, request, stopped):
    dates = np.array([r["date"] for r in rows[1:]])
    values = np.array([r["value"] for r in rows])
    changes, x = features(values, False)
    train = (dates > request.train_start.isoformat()) & (
        dates <= request.train_end.isoformat()
    )
    test = (dates >= request.test_start.isoformat()) & (
        dates <= request.test_end.isoformat()
    )
    model, mean, scale, _ = fit_model(x[train])
    p = forward_filter(model, (x - mean) / scale)
    means = model.means_[:, 0] * scale[0] + mean[0]
    annual = 365 if asset["category"] == "crypto" else 252
    forecast, band = model_signals(model, p, means, request.fee_bps, annual)
    low_risk = int(np.argmin(model.covars_[:, 0, 0]))
    if stopped:
        from investor.analysis.bars import enrich_rows

        enriched = enrich_rows(asset["id"], rows)
        bars = [
            {"open_ratio": row["open"] / prev, "low_ratio": row["low"] / prev}
            if "open" in row and "low" in row
            else None
            for row, prev in zip(enriched[1:], values[:-1])
        ]
        net, market, trades, positions = simulate_reentry(
            changes[test],
            p[test],
            dates[test].tolist(),
            low_risk,
            request,
            forecast[test],
            band[test],
            bars=[b for b, selected in zip(bars, test) if selected],
        )
    else:
        market = np.expm1(changes[test])
        fee = request.fee_bps / 10000
        market[0] = (1 + market[0]) * (1 - fee) - 1
        market[-1] = (1 + market[-1]) * (1 - fee) - 1
        position, pending = 0, None
        net, trades, positions = np.zeros(test.sum()), [], []
        f, b = forecast[test], band[test]
        days, returns = dates[test].tolist(), changes[test]
        fee = request.fee_bps / 10000
        for i, change in enumerate(returns):
            net[i] = np.expm1(change) if position else 0
            target = 0 if i == len(returns) - 1 else pending
            if target is not None and target != position:
                net[i] = (1 + net[i]) * (1 - fee) - 1
                position = target
                trades.append({"time": days[i], "side": "buy" if target else "sell"})
            positions.append(position)
            pending = None
            if position and f[i] < -b[i]:
                pending = 0
            elif not position and f[i] > b[i]:
                pending = 1
    return {
        "strategy_metrics": metrics(net, market, annual, 0),
        "benchmark_metrics": metrics(market, market, annual, 0),
        "trades": trades,
        "exposure": float(np.mean(positions)),
        "capital": equity(net).tolist(),
        "states": 2,
    }


def windows(rows):
    common = [r for r in rows if "2015-01-01" <= r["date"] <= "2025-12-31"]
    yield (
        "continuous_2022_2025",
        common,
        ("2015-01-01", "2021-12-31", "2022-01-01", "2025-12-31"),
    )
    for year in range(2022, 2027):
        first, end = f"{year - 5}-01-01", f"{year}-12-31"
        yield (
            f"walk_{year}",
            [r for r in rows if first <= r["date"] <= end],
            (first, f"{year - 1}-12-31", f"{year}-01-01", min(end, rows[-1]["date"])),
        )
    screen = rows[-2016:]
    cut = int(len(screen) * 0.7)
    yield (
        "interface_default",
        screen,
        (
            screen[0]["date"],
            screen[cut]["date"],
            screen[cut + 1]["date"],
            screen[-1]["date"],
        ),
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "plan.json").exists():
        raise SystemExit("Refusing to overwrite a frozen experiment.")
    plan = {
        "rules_fixed_before_run": True,
        "models": ["previous_stop", "previous_without_stop", "directional_hmm"],
        "features": "log return, trailing 20-return mean, log trailing 20-return volatility",
        "selection": "2/3 states, returns alone or 20-day context; 3 seeds by training likelihood; structure selected by next-return predictive log density on final 20% of training, refit whole training",
        "trading": "Bellman continuation value with symmetric fees, next-close lag, no drawdown stop or transaction target",
        "fees": "defaults stock=50bps crypto=1bps, stress=twice default",
        "windows": "continuous 2022-25; annual 2022-26 with preceding five years training; current interface defaults",
        "limitations": "Reused research data, overlapping windows, survival bias. No untouched holdout. No tuning based on diagnostic returns.",
        "sources": {
            name: hashlib.sha256(
                (ROOT / f"backend/investor/analysis/{name}.py").read_bytes()
            ).hexdigest()
            for name in [
                "model",
                "regimes",
                "switching",
                "service",
                "reentry",
                "metrics",
            ]
        },
    }
    (OUT / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    results, skipped = [], []
    with sqlite3.connect(
        f"file:{ROOT / 'data/investor.sqlite3'}?mode=ro", uri=True
    ) as db:
        db.row_factory = sqlite3.Row
        assets = db.execute(
            "SELECT * FROM assets WHERE category IN ('stock','crypto') ORDER BY id"
        ).fetchall()
        for asset in assets:
            asset = dict(asset)
            if asset["id"] in REMOVED_CRYPTO:
                continue
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT date,value FROM observations WHERE asset_id=? ORDER BY date",
                    (asset["id"],),
                )
            ]
            for case, history, period in windows(rows):
                train_start, train_end, test_start, test_end = period
                if (
                    sum(train_start < r["date"] <= train_end for r in history) < 121
                    or sum(test_start <= r["date"] <= test_end for r in history) < 20
                ):
                    skipped.append([asset["id"], case])
                    continue
                digest = hashlib.sha256(
                    json.dumps(history, sort_keys=True).encode()
                ).hexdigest()
                for multiple in (1, 2):
                    fee = (1 if asset["category"] == "crypto" else 50) * multiple
                    request = AnalysisRequest(
                        train_start=train_start,
                        train_end=train_end,
                        test_start=test_start,
                        test_end=test_end,
                        fee_bps=fee,
                    )
                    for name in plan["models"]:
                        try:
                            if name == "directional_hmm":
                                output = calculate(asset, history, request)
                                output["capital"] = [
                                    r["strategy"] / 100 for r in output["equity"]
                                ]
                                output["selection"] = output["model_selection"]
                                output["states"] = len(output["states"])
                            else:
                                output = previous(
                                    asset, history, request, name == "previous_stop"
                                )
                            result = {
                                "asset": asset["id"],
                                "category": asset["category"],
                                "case": case,
                                "policy": name,
                                "fee_bps": fee,
                                "fee_multiple": multiple,
                                "parameters": request.model_dump(mode="json"),
                                "data_sha256": digest,
                                **{
                                    k: output[k]
                                    for k in (
                                        "strategy_metrics",
                                        "benchmark_metrics",
                                        "trades",
                                        "capital",
                                        "exposure",
                                        "states",
                                    )
                                },
                            }
                            if "selection" in output:
                                result["selection"] = output["selection"]
                            results.append(result)
                        except ValueError as exc:
                            results.append(
                                {
                                    "asset": asset["id"],
                                    "case": case,
                                    "policy": name,
                                    "fee_bps": fee,
                                    "error": str(exc),
                                }
                            )
                print(asset["id"], case, "completed", flush=True)
                (OUT / "progress.json").write_text(
                    json.dumps(
                        {"results": results, "skipped": skipped}, allow_nan=False
                    )
                )
    (OUT / "results.json").write_text(
        json.dumps(
            {"plan": plan, "results": results, "skipped": skipped}, allow_nan=False
        )
    )
    with (OUT / "summary.csv").open("w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "asset",
                "case",
                "policy",
                "fee_bps",
                "return",
                "hold_return",
                "drawdown",
                "orders",
                "exposure",
                "states",
                "error",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r["asset"],
                    r["case"],
                    r["policy"],
                    r["fee_bps"],
                    r.get("strategy_metrics", {}).get("total_return"),
                    r.get("benchmark_metrics", {}).get("total_return"),
                    r.get("strategy_metrics", {}).get("maximum_drawdown"),
                    len(r.get("trades", [])),
                    r.get("exposure"),
                    r.get("states"),
                    r.get("error"),
                ]
            )
    print(len(results), "diagnostics; skipped", skipped, flush=True)


if __name__ == "__main__":
    main()
