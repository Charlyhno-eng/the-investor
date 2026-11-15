"""Independent native-currency histories for joint portfolio simulations."""

import math
from datetime import date

from investor.assets.momentum import months_before
from investor.db import connect
from investor.portfolio.service import PortfolioRequest, portfolio


def prediction_history(request: PortfolioRequest):
    valuation = portfolio(
        request.model_copy(
            update={"include_benchmark": False, "include_correlation": False}
        )
    )
    if valuation["status"] == "pending":
        return valuation
    excluded = valuation["excluded"]

    def insufficient(message):
        return {"status": "insufficient", "message": message, "excluded": excluded}

    if excluded:
        return insufficient(
            "La prédiction du portefeuille entier nécessite un prix exploitable pour chaque position."
        )
    if not valuation["positions"]:
        return insufficient(
            "Renseignez vos quantités dans Positions pour afficher la prédiction."
        )
    series = []
    with connect() as connection:
        for position in valuation["positions"]:
            asset = connection.execute(
                "SELECT * FROM assets WHERE id=?", (position["id"],)
            ).fetchone()
            if asset["frequency"] != "daily":
                return insufficient(
                    "La prédiction nécessite un historique quotidien pour chaque position."
                )
            latest = connection.execute(
                "SELECT date FROM observations WHERE asset_id=? AND value>0 ORDER BY date DESC LIMIT 1",
                (asset["id"],),
            ).fetchone()
            cutoff = (
                months_before(date.fromisoformat(latest["date"]), 36).isoformat()
                if latest
                else "0001-01-01"
            )
            history = {
                row["date"]: row["value"]
                for row in connection.execute(
                    "SELECT date,value FROM observations WHERE asset_id=? AND date>=? ORDER BY date",
                    (asset["id"], cutoff),
                )
                if math.isfinite(row["value"]) and row["value"] > 0
            }
            if not history:
                return insufficient("Historique indisponible : " + asset["name"] + ".")
            series.append(
                {
                    "id": asset["id"],
                    "name": asset["name"],
                    "crypto": asset["category"] == "crypto",
                    "value": position["value"],
                    "price_date": position["date"],
                    "points": [
                        {"time": d, "value": v} for d, v in sorted(history.items())
                    ],
                }
            )
    return {
        "status": "ready",
        "series": series,
        "currency": "EUR",
        "current_total": valuation["total"],
    }
