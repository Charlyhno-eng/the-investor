"""Audit healthcare stress responses against observed windows, not a backtest.

Run: PYTHONPATH=backend .venv/bin/python scripts/audit_health_simulation.py
Downloads adjusted closes; recent coefficients intentionally differ from event-era
business exposures. XLV/XBI augmentation is experimental and not deployed.
"""

import json
from datetime import date

import numpy as np
import yfinance as yf

from investor.db import connect
from investor.simulation.router import FACTORS, changes, fit, month_shift, monthly


def main():
    with connect() as c:
        levels = {
            s: monthly(
                c.execute(
                    "SELECT date,value FROM reference_observations WHERE symbol=? ORDER BY date",
                    (s,),
                )
            )
            for s in FACTORS
        }
    fx = levels["EURUSD=X"]
    raw = {}
    for symbol in ["XLV", "XBI", "PFE", "MRNA", "BNTX", "JNJ", "UNH", "SAN.PA"]:
        try:
            frame = yf.Ticker(symbol).history(
                period="max", auto_adjust=True, timeout=20
            )
            raw[symbol] = monthly(
                [
                    (stamp.date().isoformat(), float(v))
                    for stamp, v in frame["Close"].items()
                ]
            )
            print(symbol, len(raw[symbol]), flush=True)
        except Exception as e:
            raise RuntimeError(f"Historique indisponible pour {symbol}") from e
    rets = {s: changes(v) for s, v in levels.items()}
    extra = {s: changes(raw[s]) for s in ["XLV", "XBI"]}
    rows = []
    for symbol in ["XLV", "XBI", "PFE", "MRNA", "BNTX", "JNJ", "UNH", "SAN.PA"]:
        eur = {
            m: v if symbol == "SAN.PA" else v / fx[m]
            for m, v in raw[symbol].items()
            if m in fx
        }
        yrets = changes(eur)
        common = sorted(
            set(yrets).intersection(
                *(set(v) for v in [*rets.values(), *extra.values()])
            )
        )
        common = [
            m for m in common if m >= month_shift(date.today().isoformat()[:7], -61)
        ]
        if len(common) < 36:
            continue
        y = np.array([[yrets[m]] for m in common])
        row = {"symbol": symbol, "months": len(common)}
        for label, factors in [("current", rets), ("sector", {**rets, **extra})]:
            x = np.array([[f[m] for f in factors.values()] for m in common])
            beta = fit(x, y)
            row[label + "_validation_rmse"] = float(
                np.sqrt(np.mean((y[-12:] - x[-12:] @ fit(x[:-12], y[:-12])) ** 2))
            )
            for name, start in [("covid", "2020-01"), ("reopening", "2020-10")]:
                months = [month_shift(start, i + 1) for i in range(12)]
                if not all(m in yrets for m in months):
                    continue
                shock = np.array([[f[m] for f in factors.values()] for m in months])
                row[name + "_actual"] = float(np.expm1(sum(yrets[m] for m in months)))
                row[name + "_" + label] = float(np.expm1((shock @ beta).sum()))
        rows.append(row)
    print(json.dumps(rows, indent=2), flush=True)


if __name__ == "__main__":
    main()
