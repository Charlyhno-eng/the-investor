"""Audit local mean-reversion results, without searching for winning parameters.

Run: PYTHONPATH=backend uv run python scripts/audit_validation.py
Custom universe: ... --assets yf-ucb.br yf-argx.br yf-tte.pa --output /tmp/audit.json
"""

import argparse
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

from investor.assets.momentum import months_before
from investor.portfolio.validation import ValidationRequest, portfolio_validation

UNIVERSES = {
    "journal_14": [
        "yf-gtt.pa",
        "yf-enx.pa",
        "yf-pry.mi",
        "yf-ai.pa",
        "yf-te.pa",
        "yf-ho.pa",
        "yf-ucb.br",
        "yf-air.pa",
        "yf-tte.pa",
        "yf-asml.as",
        "yf-btc-usd",
        "yf-saf.pa",
        "yf-su.pa",
        "yf-argx.br",
    ],
    "extrait_3": ["yf-ucb.br", "yf-argx.br", "yf-tte.pa"],
    "actions_11": [
        "yf-air.pa",
        "yf-asml.as",
        "yf-gtt.pa",
        "yf-enx.pa",
        "yf-ai.pa",
        "yf-saf.pa",
        "yf-argx.br",
        "yf-pry.mi",
        "yf-ucb.br",
        "yf-tte.pa",
        "yf-te.pa",
    ],
    "crypto_4": ["yf-btc-usd", "yf-eth-usd", "yf-sol-usd", "yf-bnb-usd"],
}


def summarize(result):
    if result["status"] != "ready":
        return result
    funding = Counter()
    for trade in result["transactions"]:
        if not trade["signal"] < trade["execution"]:
            raise ValueError("Exécution antérieure au signal")
        amount, fee = trade["amount"], trade["fee"]
        signed = amount if trade["side"] == "buy" else -amount
        if (
            not math.isclose(
                trade["cash_after"], trade["cash_before"] - signed - fee, abs_tol=1e-7
            )
            or trade["cash_after"] < -1e-7
        ):
            raise ValueError("Liquidités incohérentes")
        if not math.isclose(
            fee, amount * result["parameters"]["fee_rate"], abs_tol=1e-7
        ):
            raise ValueError("Frais incohérents")
        if (
            trade["reason"] == "entry"
            and amount + fee > 0.25 * trade["portfolio_before"] + 1e-7
        ):
            raise ValueError("Plafond de 25 % dépassé")
        if trade["reason"] == "funding":
            funding[trade["execution"]] += 1
            if trade["z"] is None or trade["z"] < 0 or funding[trade["execution"]] > 1:
                raise ValueError("Financement hors règles")
    if not math.isclose(
        sum(t["fee"] for t in result["transactions"]),
        result["metrics"]["strategy"]["cost_eur"],
        abs_tol=1e-7,
    ):
        raise ValueError("Frais du journal et du récapitulatif différents")
    cutoff = months_before(date.fromisoformat(result["end"]), 24).isoformat()
    split = next(
        (p for p in result["equity"] if p["time"] >= cutoff), result["equity"][0]
    )
    first, last = result["equity"][0], result["equity"][-1]
    entries = [t for t in result["transactions"] if t["reason"] == "entry"]
    return {
        "status": "ready",
        "parameters": result["parameters"],
        "start": result["start"],
        "end": result["end"],
        "split": split["time"],
        "metrics": result["metrics"],
        "transactions": len(result["transactions"]),
        "funding_sales": sum(funding.values()),
        "cash_final": result["final_portfolio"]["cash"],
        "smallest_entry_eur": min((t["amount"] for t in entries), default=None),
        "smallest_entry_share_including_fees": min(
            ((t["amount"] + t["fee"]) / t["portfolio_before"] for t in entries),
            default=None,
        ),
        "segments": {
            k: {
                "before_split": split[k] / first[k] - 1,
                "last_two_years": last[k] / split[k] - 1,
            }
            for k in result["metrics"]
        },
        "checks": "chronology, cash, fees, entry cap, single nonnegative funding holding",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", nargs="+")
    parser.add_argument("--years", type=int, choices=[1, 3, 5, 10], default=5)
    parser.add_argument("--capital", type=float, default=10000)
    parser.add_argument("--fees", nargs="+", type=float, default=[0.005, 0.0])
    parser.add_argument(
        "--whole-shares", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = {}
    for name, identifiers in (
        {"custom": args.assets} if args.assets else UNIVERSES
    ).items():
        for fee in args.fees:
            request = ValidationRequest(
                asset_ids=identifiers,
                mode="mean_reversion",
                years=args.years,
                initial_capital=args.capital,
                fee_rate=fee,
                whole_shares=args.whole_shares,
            )
            results[f"{name}:{fee}"] = summarize(portfolio_validation(request))
    encoded = json.dumps(results, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
