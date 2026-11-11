"""Current exposures to observed market regimes; no invented crisis returns."""

import math
from bisect import bisect_right
from datetime import date

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from investor.assets.comparison import ensure_references
from investor.db import connect
from investor.portfolio.service import Holding, PortfolioRequest, portfolio

router = APIRouter(prefix="/api/simulation", tags=["simulation"])
FACTORS = {
    "SPY": "Actions américaines",
    "QQQ": "Nasdaq-100 · technologie et croissance",
    "EFA": "Actions développées hors États-Unis",
    "TLT": "Obligations US longues (sensibilité aux taux)",
    "HYG": "Crédit à haut rendement",
    "GLD": "Or",
    "USO": "Pétrole via futures (roulement inclus)",
    "EURUSD=X": "EUR / USD",
}
SCENARIOS = [
    dict(
        id="ai",
        name="Crise de l’IA · dégonflement des valorisations",
        start="2021-12",
        tone="stress",
        description="Scénario hypothétique IA, analogue au recul technologique de 2022. Nasdaq-100, crédit et taux observés ; ce n’est pas une crise IA historique ni un choc spécifique aux revenus de l’IA.",
    ),
    dict(
        id="covid",
        name="Pandémie · Covid-like",
        start="2020-01",
        tone="stress",
        description="Arrêt de l’activité, fuite vers la liquidité puis soutien monétaire et réouverture.",
    ),
    dict(
        id="credit",
        name="Crise bancaire · 2008-like",
        start="2008-08",
        tone="stress",
        description="Faillites bancaires, contraction du crédit et récession mondiale.",
    ),
    dict(
        id="war",
        name="Guerre et choc énergétique",
        start="2022-01",
        tone="stress",
        description="Invasion de l’Ukraine, flambée énergétique, inflation et hausse des taux. Effets indissociables sur cette fenêtre.",
    ),
    dict(
        id="euro",
        name="Crise des dettes européennes",
        start="2011-06",
        tone="stress",
        description="Tensions souveraines et bancaires, aversion au risque et interventions des banques centrales.",
    ),
    dict(
        id="tightening",
        name="Resserrement monétaire · 2018",
        start="2018-01",
        tone="stress",
        description="Hausse des taux et tensions commerciales ; correction des actifs risqués.",
    ),
    dict(
        id="reopening",
        name="Réouverture et relance",
        start="2020-10",
        tone="positive",
        description="Vaccins, relance et reprise de l’activité ; hausse des actifs cycliques.",
    ),
    dict(
        id="disinflation",
        name="Désinflation et reprise · 2023",
        start="2022-12",
        tone="positive",
        description="Reflux de l’inflation et reprise des marchés actions, avec divergence sectorielle.",
    ),
]


class SimulationRequest(PortfolioRequest):
    holdings: list[Holding] = Field(max_length=100)
    scenario: str = "covid"
    months: int = Field(default=12, ge=3, le=12)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)


def month_shift(month, offset):
    year, number = map(int, month[:7].split("-"))
    count = year * 12 + number - 1 + offset
    return f"{count // 12:04d}-{count % 12 + 1:02d}"


def monthly(rows):
    """Last actual observation in completed months; never fill missing months."""
    result = {}
    for day, value in rows:
        if (
            day[:7] < date.today().isoformat()[:7]
            and value > 0
            and math.isfinite(value)
        ):
            result[day[:7]] = float(value)
    return result


def changes(levels):
    return {
        m: math.log(v / levels[month_shift(m, -1)])
        for m, v in levels.items()
        if month_shift(m, -1) in levels
    }


def contiguous_recent(months):
    """Use a contiguous suffix so blocks never bridge missing calendar months."""
    months = sorted(months)
    if not months:
        return []
    start = len(months) - 1
    while start > 0 and month_shift(months[start], -1) == months[start - 1]:
        start -= 1
    return months[start:]


def eur_monthly(connection, asset, currency):
    rows = connection.execute(
        "SELECT date,value FROM observations WHERE asset_id=? ORDER BY date",
        (asset["id"],),
    ).fetchall()
    rates = {}
    for curr in {currency, "EUR"} - {"USD"}:
        rates[curr] = dict(
            connection.execute(
                "SELECT date,value FROM reference_observations WHERE symbol=? AND value>0 ORDER BY date",
                (f"{curr}USD=X",),
            ).fetchall()
        )
    calendars = {curr: list(values) for curr, values in rates.items()}

    def rate(curr, day):
        if curr == "USD":
            return 1.0
        index = bisect_right(calendars[curr], day) - 1
        if index < 0:
            return None
        stamp = calendars[curr][index]
        if (date.fromisoformat(day) - date.fromisoformat(stamp)).days > 7:
            return None
        return rates[curr][stamp]

    converted = []
    for row in rows:
        day, value = row["date"], row["value"]
        if currency == "EUR":
            converted.append((day, value))
            continue
        local_rate, eur_rate = rate(currency, day), rate("EUR", day)
        if local_rate and eur_rate:
            converted.append((day, value * local_rate / eur_rate))
    return monthly(converted)


def fit(x, y):
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale = np.maximum(scale, 1e-6)
    z = (x - mean) / scale
    # Modest ridge stabilizes highly correlated equity and credit factors.
    beta = (
        np.linalg.solve(z.T @ z + np.eye(x.shape[1]) * 3, z.T @ (y - y.mean(axis=0)))
        / scale[:, None]
    )
    return beta


@router.get("/scenarios")
def scenarios():
    return SCENARIOS


@router.post("/run")
def simulate(request: SimulationRequest):
    scenario = next((s for s in SCENARIOS if s["id"] == request.scenario), None)
    if scenario is None:
        raise HTTPException(422, "Scénario inconnu.")
    valuation = portfolio(
        PortfolioRequest(holdings=request.holdings, include_correlation=False)
    )
    if valuation["status"] == "pending":
        return valuation
    if not valuation["positions"]:
        return {
            "status": "insufficient",
            "message": "Ajoutez des positions avec des quantités positives et des prix valorisables.",
            "excluded": valuation["excluded"],
        }
    with connect() as c:
        if ensure_references(c, list(FACTORS), allow_cached=True):
            return {"status": "pending"}
        levels = {
            s: monthly(
                c.execute(
                    "SELECT date,value FROM reference_observations WHERE symbol=? ORDER BY date",
                    (s,),
                )
            )
            for s in FACTORS
        }
        factor_returns = {s: changes(v) for s, v in levels.items()}
        shock_months = [
            month_shift(scenario["start"], i + 1) for i in range(request.months)
        ]
        missing = [
            f"{s} ({m})"
            for s in FACTORS
            for m in shock_months
            if m not in factor_returns[s]
        ]
        if missing:
            return {
                "status": "insufficient",
                "message": "Historique du scénario incomplet : "
                + ", ".join(missing[:8]),
                "excluded": valuation["excluded"],
            }
        histories, positions, excluded = [], [], list(valuation["excluded"])
        for position in valuation["positions"]:
            asset = c.execute(
                "SELECT * FROM assets WHERE id=?", (position["id"],)
            ).fetchone()
            price_age = (date.today() - date.fromisoformat(position["date"])).days
            if price_age > (70 if asset["frequency"] == "monthly" else 45):
                excluded.append(
                    dict(
                        id=position["id"],
                        name=position["name"],
                        reason=f"Dernier prix trop ancien : {position['date']}.",
                    )
                )
                continue
            currency = (
                asset["unit"]
                if asset["category"] in ("stock", "etf", "currency")
                else "USD"
            )
            currency = "GBP" if currency == "GBp" else currency
            eur = eur_monthly(c, asset, currency)
            returns = changes({m: v for m, v in eur.items() if v > 0})
            common = sorted(
                set(returns).intersection(*(set(r) for r in factor_returns.values()))
            )
            common = [
                m for m in common if m >= month_shift(date.today().isoformat()[:7], -61)
            ]
            common = contiguous_recent(common)
            if len(common) < 36:
                excluded.append(
                    dict(
                        id=position["id"],
                        name=position["name"],
                        reason=f"Historique récent insuffisant : {len(common)} mois communs, 36 requis.",
                    )
                )
            else:
                histories.append(returns)
                positions.append(position)
        common = (
            sorted(
                set.intersection(
                    *(set(h) for h in histories),
                    *(set(r) for r in factor_returns.values()),
                )
            )
            if histories
            else []
        )
        common = [
            m for m in common if m >= month_shift(date.today().isoformat()[:7], -61)
        ]
        common = contiguous_recent(common)
        if len(common) < 36:
            return {
                "status": "insufficient",
                "message": "Il faut 36 mois récents communs pour estimer les sensibilités conjointes.",
                "excluded": excluded,
            }
        if common[-1] < month_shift(date.today().isoformat()[:7], -3):
            return {
                "status": "insufficient",
                "message": "Historiques trop anciens : actualisez les actifs et les références.",
                "excluded": excluded,
            }
        x = np.array([[factor_returns[s][m] for s in FACTORS] for m in common])
        y = np.array([[h[m] for h in histories] for m in common])
        shock = np.array(
            [[factor_returns[s][m] for s in FACTORS] for m in shock_months]
        )
        return project(
            request,
            scenario,
            valuation,
            positions,
            excluded,
            x,
            y,
            shock,
            common,
            levels,
        )


def project(
    request, scenario, valuation, positions, excluded, x, y, shock, common, levels
):
    beta = fit(x, y)
    residual = y - x @ beta
    residual -= residual.mean(axis=0)  # no extrapolated alpha in a crisis
    values = np.array([p["value"] for p in positions])
    total = float(values.sum())
    central_assets = (
        np.exp(np.vstack([np.zeros(len(values)), np.cumsum(shock @ beta, axis=0)]))
        * values
    )
    central = central_assets.sum(axis=1)
    rng = np.random.default_rng(request.seed)
    paths = []
    # Shared three-month blocks preserve cross-asset residual dependence and clustering.
    for _ in range(600):
        indices = np.concatenate(
            [
                (rng.integers(len(x)) + np.arange(3)) % len(x)
                for _ in range((len(x) + 2) // 3)
            ]
        )[: len(x)]
        sampled_beta = fit(x[indices], y[indices])
        noise_idx = np.concatenate(
            [
                (rng.integers(len(x)) + np.arange(3)) % len(x)
                for _ in range((request.months + 2) // 3)
            ]
        )[: request.months]
        log_returns = shock @ sampled_beta + residual[noise_idx]
        path = (
            np.exp(np.vstack([np.zeros(len(values)), np.cumsum(log_returns, axis=0)]))
            @ values
        )
        paths.append(path)
    paths = np.array(paths)
    low, median, high = np.quantile(paths, [0.05, 0.5, 0.95], axis=0)
    drawdowns = (paths / np.maximum.accumulate(paths, axis=1) - 1).min(axis=1)
    train = len(x) - 12
    validation_error = y[train:] - x[train:] @ fit(x[:train], y[:train])
    unexplained = (residual**2).sum(axis=0)
    variance = ((y - y.mean(axis=0)) ** 2).sum(axis=0)
    r2 = 1 - unexplained / np.maximum(variance, 1e-12)
    today = date.today().isoformat()[:7]
    return {
        "status": "ready",
        "scenario": scenario,
        "currency": "EUR",
        "seed": request.seed,
        "paths": len(paths),
        "total": total,
        "valued_total": valuation["total"],
        "coverage": total / valuation["total"],
        "excluded": excluded,
        "calibration": {
            "start": common[0],
            "end": common[-1],
            "months": len(common),
            "frequency": "monthly",
        },
        "historical_start": scenario["start"],
        "historical_end": month_shift(scenario["start"], request.months),
        "equity": [
            dict(
                month=i,
                time=month_shift(today, i),
                central=float(central[i]),
                p05=float(low[i]),
                p50=float(median[i]),
                p95=float(high[i]),
            )
            for i in range(request.months + 1)
        ],
        "metrics": {
            "return": float(central[-1] / total - 1),
            "p05_return": float(low[-1] / total - 1),
            "p95_return": float(high[-1] / total - 1),
            "drawdown": float((central / np.maximum.accumulate(central) - 1).min()),
            "drawdown_p05": float(np.quantile(drawdowns, 0.05)),
            "conditional_loss_share": float(np.mean(paths[:, -1] < total)),
        },
        "positions": [
            dict(
                **p,
                simulated_value=float(central_assets[-1, i]),
                simulated_return=float(central_assets[-1, i] / p["value"] - 1),
                contribution=float((central_assets[-1, i] - p["value"]) / total),
                r2=float(r2[i]),
                validation_rmse=float(np.sqrt(np.mean(validation_error[:, i] ** 2))),
                betas={s: float(beta[j, i]) for j, s in enumerate(FACTORS)},
            )
            for i, p in enumerate(positions)
        ],
        "factors": [
            dict(
                symbol=s,
                name=name,
                shock=float(np.expm1(shock[:, j].sum())),
                first=min(levels[s]),
                last=max(levels[s]),
                source=f"https://finance.yahoo.com/quote/{s}/history/",
            )
            for j, (s, name) in enumerate(FACTORS.items())
        ],
        "warnings": [
            "Scénario conditionnel, pas une prévision ni une probabilité de survenue. L’intensité des facteurs suit une seule fenêtre historique.",
            "Modèle mensuel linéaire à sensibilités récentes : il ne reproduit ni défauts, ni suspensions, ni réactions politiques futures, ni les ruptures de régime.",
            "Les creux intramensuels (notamment mars 2020) ne sont pas mesurés : le drawdown mensuel sous-estime potentiellement la perte maximale.",
            "Fourchette P5–P95 conditionnelle aux facteurs fixés : résidus conjoints et incertitude des coefficients, sans incertitude sur le scénario macro lui-même.",
            "Quantités constantes, dividendes réinvestis selon les séries ajustées ; sans frais, impôts, apports ni rééquilibrage. Change inclus dans les rendements en EUR.",
            "Taux souverains sans prix exclus. Matières premières : proxy de prix, pas rendement investissable garanti. USO inclut le roulement des futures.",
            "Biais de survivance et de sélection ; absence de garantie hors échantillon. Les données publiques peuvent être retardées ou révisées.",
        ],
    }


class WatchlistRequest(BaseModel):
    asset_ids: list[str] = Field(max_length=100)
    scenario: str = "covid"
    seed: int = Field(default=42, ge=0, le=2**32 - 1)


@router.post("/watchlist")
def watchlist_simulation(request: WatchlistRequest):
    if request.scenario not in {s["id"] for s in SCENARIOS}:
        raise HTTPException(422, "Scénario inconnu.")
    results, excluded = [], []
    pending = False
    for asset_id in dict.fromkeys(request.asset_ids):
        try:
            result = simulate(
                SimulationRequest(
                    holdings=[Holding(asset_id=asset_id, quantity=1)],
                    scenario=request.scenario,
                    seed=request.seed,
                )
            )
        except HTTPException as error:
            if error.status_code == 422 and request.scenario not in {
                s["id"] for s in SCENARIOS
            }:
                raise
            excluded.append(dict(id=asset_id, name=asset_id, reason=str(error.detail)))
            continue
        if result["status"] == "pending":
            pending = True
        elif result["status"] == "ready":
            results.append(result)
        else:
            excluded.extend(
                result.get("excluded")
                or [dict(id=asset_id, name=asset_id, reason=result["message"])]
            )
    return {
        "status": "pending" if pending else "ready",
        "results": results,
        "excluded": excluded,
    }
