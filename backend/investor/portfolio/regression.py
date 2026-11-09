"""Latest log-price OLS deviation, matching the asset regression defaults."""

from datetime import date

import numpy as np
from pydantic import BaseModel, Field

from investor.db import connect


class RegressionRequest(BaseModel):
    asset_ids: list[str] = Field(max_length=1000)


def regression_deviations(request):
    positions = []
    with connect() as connection:
        for asset_id in dict.fromkeys(request.asset_ids):
            latest = connection.execute(
                "SELECT MAX(date) FROM observations WHERE asset_id=?", (asset_id,)
            ).fetchone()[0]
            if not latest:
                positions.append(
                    {"id": asset_id, "z": None, "reason": "Historique indisponible."}
                )
                continue
            end = date.fromisoformat(latest)
            try:
                cutoff = end.replace(year=end.year - 5)
            except ValueError:  # JavaScript's setUTCFullYear maps Feb 29 to March 1.
                cutoff = date(end.year - 5, 3, 1)
            rows = connection.execute(
                "SELECT date,value FROM observations WHERE asset_id=? AND date>=? ORDER BY date",
                (asset_id, cutoff.isoformat()),
            ).fetchall()
            values = np.array([r["value"] for r in rows])
            if len(rows) < 30 or not np.all(np.isfinite(values)) or np.min(values) <= 0:
                positions.append(
                    {
                        "id": asset_id,
                        "z": None,
                        "reason": "Au moins 30 prix positifs sont nécessaires sur les cinq dernières années.",
                    }
                )
                continue
            x = np.array(
                [
                    (
                        date.fromisoformat(r["date"])
                        - date.fromisoformat(rows[0]["date"])
                    ).days
                    / 365.25
                    for r in rows
                ]
            )
            y = np.log(values)
            centered = x - x.mean()
            slope = float(centered @ (y - y.mean()) / (centered @ centered))
            residuals = y - (y.mean() + slope * centered)
            sigma = float(np.sqrt(residuals @ residuals / (len(rows) - 2)))
            degenerate = sigma <= 1e-10 * max(1, abs(float(y.mean())))
            positions.append(
                {
                    "id": asset_id,
                    "z": None if degenerate else float(residuals[-1] / sigma),
                    "start": rows[0]["date"],
                    "end": latest,
                    "observations": len(rows),
                    "reason": "Dispersion résiduelle quasi nulle."
                    if degenerate
                    else None,
                }
            )
    return {"positions": positions}
