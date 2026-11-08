"""Train-only four-state Gaussian HMM and causal out-of-sample filtering."""

from datetime import date

import numpy as np
from fastapi import HTTPException
from hmmlearn.hmm import GaussianHMM
from pydantic import BaseModel, ConfigDict, model_validator

from investor.analysis.model import forward_filter
from investor.db import connect


class RegimeRequest(BaseModel):
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ordered_periods(self):
        if not self.train_start < self.train_end < self.test_start < self.test_end:
            raise ValueError(
                "Choisissez deux périodes sans chevauchement : entraînement puis test."
            )
        return self


def detect(asset_id, request=None):
    with connect() as db:
        rows = db.execute(
            "SELECT date,value FROM observations WHERE asset_id=? ORDER BY date",
            (asset_id,),
        ).fetchall()
    if not rows:
        raise HTTPException(404, "Historique introuvable.")
    if request is None:
        recent = rows[-2000:]
        split = max(1, int(len(recent) * 0.7))
        if split >= len(recent) - 1:
            raise HTTPException(422, "Historique insuffisant.")
        request = RegimeRequest(
            train_start=recent[0]["date"],
            train_end=recent[split - 1]["date"],
            test_start=recent[split]["date"],
            test_end=recent[-1]["date"],
        )
    rows = [
        r
        for r in rows
        if request.train_start.isoformat() <= r["date"] <= request.test_end.isoformat()
    ]
    train = [r for r in rows if r["date"] <= request.train_end.isoformat()]
    test = [r for r in rows if r["date"] >= request.test_start.isoformat()]
    if len(train) < 252 or len(test) < 2:
        raise HTTPException(
            422, "Il faut au moins 252 prix d’entraînement et 2 prix de test."
        )
    values = np.array([r["value"] for r in rows], dtype=float)
    if not np.isfinite(values).all() or np.any(values <= 0):
        raise HTTPException(422, "La détection nécessite des prix positifs et finis.")
    returns = np.diff(np.log(values))
    train_returns = returns[: len(train) - 1]
    scale = float(train_returns.std())
    if scale < 1e-10:
        raise HTTPException(
            422, "Variation insuffisante pour distinguer quatre régimes."
        )
    x = (returns / scale).reshape(-1, 1)
    models = []
    for seed in (7, 19, 42):
        model = GaussianHMM(
            n_components=4,
            covariance_type="diag",
            n_iter=200,
            random_state=seed,
            min_covar=1e-4,
        )
        try:
            model.fit(x[: len(train) - 1])
            score = model.score(x[: len(train) - 1])
            if np.isfinite(score):
                models.append((score, model))
        except (ValueError, FloatingPointError):
            continue
    if not models:
        raise HTTPException(
            422, "Le modèle ne peut pas être estimé sur cet entraînement."
        )
    model = max(models, key=lambda item: item[0])[1]
    order = np.argsort(model.means_[:, 0], kind="stable")
    probabilities = forward_filter(model, x)[:, order]
    # Volatility labels are relative to the four learned states, not fixed thresholds.
    volatilities = np.sqrt(model.covars_[:, 0, 0])
    volatility_ranks = np.argsort(
        np.argsort(volatilities, kind="stable"), kind="stable"
    )
    volatility_labels = ["faible", "modérée", "élevée", "très élevée"]
    names = [
        f"{'Hausse' if model.means_[j, 0] > 0 else 'Baisse' if model.means_[j, 0] < 0 else 'Stable'} · volatilité {volatility_labels[volatility_ranks[j]]}"
        for j in order
    ]
    points = []
    for i, row in enumerate(rows[1:]):
        if row["date"] >= request.test_start.isoformat():
            posterior = probabilities[i]
            state = int(posterior.argmax())
            points.append(
                {
                    "time": row["date"],
                    "value": row["value"],
                    "state": state,
                    "confidence": float(posterior[state]),
                }
            )
    last = probabilities[-1]
    forecast = (last[np.argsort(order)] @ model.transmat_)[order]
    return {
        "current": names[int(last.argmax())],
        "date": test[-1]["date"],
        "observations": len(points),
        "train_observations": len(train_returns),
        "actual_train": [train[0]["date"], train[-1]["date"]],
        "actual_test": [test[0]["date"], test[-1]["date"]],
        "points": points,
        "states": [
            {
                "name": names[i],
                "probability": float(last[i]),
                "next_probability": float(forecast[i]),
                "mean": float(model.means_[j, 0] * scale),
                "volatility": float(np.sqrt(model.covars_[j, 0, 0]) * scale),
            }
            for i, j in enumerate(order)
        ],
    }
