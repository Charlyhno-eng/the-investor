import { useMemo } from "react";
import { date, number, percent } from "../../lib/format";
import type { Asset, Point } from "../../lib/types";
import { predict } from "./model";
import { PredictionChart } from "./PredictionChart";

export function PredictionPanel({
  asset,
  points,
  portfolio = false,
}: {
  asset: Pick<Asset, "frequency" | "category" | "unit">;
  portfolio?: boolean;
  points: Point[];
}) {
  const result = useMemo(() => {
    if (asset.frequency !== "daily")
      return { error: "Cette projection nécessite un historique quotidien." };
    try {
      return { model: predict(points, asset.category === "crypto") };
    } catch (error) {
      return { error: (error as Error).message };
    }
  }, [asset.category, asset.frequency, points]);
  const model = result.model;
  const last = model?.history.at(-1);
  const terminal = model?.forecast.at(-1);
  const price = (value: number) =>
    `${number(value, value < 1 ? 4 : 2)} ${asset.unit}`;
  return (
    <section
      className="analysis-panel prediction-panel"
      aria-label={
        portfolio ? "Prédiction du portefeuille" : "Prédiction de l’actif"
      }
    >
      {result.error && (
        <p className="error" role="alert">
          {result.error}
        </p>
      )}
      {model && terminal && last && (
        <>
          <div
            className="reversion-legend prediction-legend"
            aria-label="Légende des projections"
          >
            <span className="prediction-history-key">━ Historique observé</span>
            <span className="prediction-median-key">
              ┄ Médiane projetée (P50)
            </span>
            <span>
              <i className="prediction-swatch central" />
              Zone centrale 50 % (P25–P75)
            </span>
            <span>
              <i className="prediction-swatch" />
              Zone centrale 90 % (P5–P95)
            </span>
          </div>
          <PredictionChart
            key={`${last.time}-${last.value}`}
            history={model.history}
            forecast={model.forecast}
            unit={asset.unit}
          />
          <div
            className="reversion-summary"
            aria-label="Résultats de la projection"
          >
            <div>
              <span>
                {portfolio
                  ? "Dernière valeur reconstituée"
                  : "Dernier cours observé"}
              </span>
              <strong>{price(last.value)}</strong>
              <small>{date(last.time)}</small>
            </div>
            <div>
              <span>Médiane à 6 mois · P50</span>
              <strong className="prediction-median-key">
                {price(terminal.p50)}
              </strong>
              <small>
                {percent(terminal.p50 / last.value - 1, true)} par rapport{" "}
                {portfolio ? "à la dernière valeur" : "au dernier cours"}
              </small>
            </div>
            <div>
              <span>Zone centrale à 50 % à l’échéance</span>
              <strong>
                {price(terminal.p25)} – {price(terminal.p75)}
              </strong>
              <small>25 % de probabilité de chaque côté, sous le modèle</small>
            </div>
            <div>
              <span>Zone centrale à 90 % à l’échéance</span>
              <strong>
                {price(terminal.p05)} – {price(terminal.p95)}
              </strong>
              <small>5 % de probabilité de chaque côté, sous le modèle</small>
            </div>
          </div>
          {!portfolio && (
            <>
              <p className="fine-print prediction-model-stats">
                GARCH(1,1) · régression sur{" "}
                {model.partialHistory ? "l’historique disponible" : "3 ans"} ·
                projection sur 6 mois · écart actuel à la tendance :{" "}
                {model.currentZ === null ? "—" : `${number(model.currentZ)} σ`}{" "}
                · volatilité conditionnelle annualisée :{" "}
                {percent(model.volatility)}.
              </p>
              {model.partialHistory && (
                <p className="fine-print">
                  Historique partiel : {model.observations} cours du{" "}
                  {date(model.history[0].time)} au {date(last.time)}, utilisés
                  en totalité.
                </p>
              )}
              <p className="prediction-limit">
                Probabilités conditionnelles au modèle, sans fiabilité démontrée
                hors échantillon. Les zones concernent le cours à chaque date,
                pas toute la trajectoire.
              </p>
            </>
          )}
          <details className="reversion-method">
            <summary>Modèle quantitatif et limites</summary>
            <p>
              Réglages fixes : jusqu’à trois ans d’historique quotidien, ou tout
              l’historique disponible s’il est plus court, et six mois depuis le
              dernier cours disponible. La régression logarithmique reprend
              exactement la pente, les résidus et leur écart-type σ de l’onglet
              Régression, sur cette même période. Les actions et ETF conservent
              les cours ajustés avec dividendes réinvestis.
            </p>
            <p>
              Le logarithme du cours est décomposé en tendance prolongée et
              écart normalisé u = (log(cours) − log(tendance)) / σ. Cet écart
              suit uₜ = φ uₜ₋₁ + εₜ, avec φ estimé par moindres carrés et borné
              entre 0 et 1. Cela suppose un retour progressif vers la tendance
              lorsque φ est inférieur à 1 ; sa validité économique n’est pas
              démontrée par la régression. Le départ reste exactement le dernier
              cours observé.
            </p>
            <p>
              Les innovations ε alimentent GARCH(1,1) : hₜ₊₁ = ω + α εₜ² + β hₜ.
              Ajustement par quasi-vraisemblance gaussienne, avec ciblage de
              variance : ω = variance empirique des innovations × (1 − α − β), α
              ≥ 0, β ≥ 0 et α + β &lt; 0,995. Une recherche sur grille suivie
              d’un raffinement local inclut la variance constante comme
              référence ; elle ne garantit pas l’optimum global.
            </p>
            <p>
              Les quantiles proviennent de {model.paths} trajectoires
              gaussiennes avec chocs opposés par paires et graine fixe pour un
              affichage reproductible. La médiane suit la tendance prolongée et
              la décroissance de l’écart initial ; les zones à 50 % et 90 % sont
              des estimations de simulation. L’écart-type descriptif de la
              régression n’est pas assimilé à un intervalle prédictif : les
              bandes futures sont calculées avec les innovations GARCH.
            </p>
            <p>
              Paramètres estimés : φ = {number(model.phi, 4)}, α ={" "}
              {number(model.garch.alpha, 4)}, β = {number(model.garch.beta, 4)}{" "}
              ; {model.observations} cours du {date(model.history[0].time)} au{" "}
              {date(last.time)}. Une étape correspond à une observation : séance
              pour les actions, jour pour les cryptomonnaies. Les jours fériés
              ne sont pas modélisés et une échéance de week-end est ramenée au
              vendredi pour les actions. Échéance affichée sur l’axe :{" "}
              {date(terminal.time)}.
            </p>
            <p>
              Les paramètres, la pente et le retour à la tendance restent
              incertains. Leurs erreurs d’estimation, les ruptures de régime,
              l’asymétrie et les sauts extrêmes ne sont pas intégrés. Aucune
              validation prédictive hors échantillon n’a été réalisée. Un
              minimum de 61 cours est nécessaire pour ajuster les modèles. Un
              historique court rend leur estimation plus incertaine.
            </p>
            <p>
              Référence :{" "}
              <a
                href="https://arch.readthedocs.io/en/stable/univariate/forecasting.html"
                target="_blank"
                rel="noreferrer"
              >
                prévisions GARCH et simulation · projet arch
              </a>
              .
            </p>
          </details>
        </>
      )}
    </section>
  );
}
