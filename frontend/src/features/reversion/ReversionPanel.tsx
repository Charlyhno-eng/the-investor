import { Tooltip } from "../../components/Tooltip";
import { useMemo, useState } from "react";
import { FeeControl } from "./FeeControl";
import { HistoryChart } from "../../components/HistoryChart";
import { date, number, percent } from "../../lib/format";
import type { Asset, Point } from "../../lib/types";
import {
  compareRegressionStrategy,
  fitRegression,
  type RegressionScale,
} from "./regression";

export function ReversionPanel({
  asset,
  points,
}: {
  asset: Asset;
  points: Point[];
}) {
  const [start, setStart] = useState(() => {
    const end = new Date(`${points.at(-1)!.time}T00:00:00Z`);
    end.setUTCFullYear(end.getUTCFullYear() - 5);
    return points.find((p) => p.time >= end.toISOString().slice(0, 10))!.time;
  });
  const [end, setEnd] = useState(points.at(-1)!.time);
  const [scale, setScale] = useState<RegressionScale>("log");
  const [threshold, setThreshold] = useState(1.5);
  const [fee, setFee] = useState(0.1);
  const result = useMemo(() => {
    if (!start || !end || start >= end)
      return { error: "Le début doit précéder la fin de la période." };
    try {
      return {
        fit: fitRegression(
          points.filter((p) => p.time >= start && p.time <= end),
          scale,
          threshold,
        ),
      };
    } catch (e) {
      return { error: (e as Error).message };
    }
  }, [points, start, end, scale, threshold]);
  const fit = result.fit;
  const comparison = useMemo(
    () =>
      fit ? compareRegressionStrategy(fit.rows, fee / 100, fee / 100) : null,
    [fit, fee],
  );
  const last = fit?.rows.at(-1);
  const overlays = useMemo(
    () =>
      fit
        ? [
            {
              title: "Tendance",
              color: "#edb786",
              points: fit.rows.map((p) => ({ time: p.time, value: p.trend })),
            },
            ...(threshold > 0
              ? [
                  {
                    title: "Seuil d’entrée",
                    color: "#65c7a5",
                    points: fit.rows.map((p) => ({
                      time: p.time,
                      value: p.lower,
                    })),
                  },
                  {
                    title: "Seuil de vente",
                    color: "#ee8190",
                    points: fit.rows.map((p) => ({
                      time: p.time,
                      value: p.upper,
                    })),
                  },
                ]
              : []),
          ]
        : [],
    [fit, threshold],
  );
  const colors = useMemo(
    () =>
      fit?.rows.map((p) =>
        p.zone === "entry"
          ? "#65c7a5"
          : p.zone === "exit"
            ? "#ee8190"
            : "#8390a7",
      ),
    [fit],
  );
  return (
    <section
      className="analysis-panel reversion-panel"
      aria-label="Retour à la tendance"
    >
      <div className="reversion-controls">
        <label>
          Début de période
          <input
            type="date"
            min={points[0].time}
            max={points.at(-1)!.time}
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          Fin de période
          <input
            type="date"
            min={points[0].time}
            max={points.at(-1)!.time}
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <label>
          Ajustement
          <select
            aria-label="Ajustement"
            value={scale}
            onChange={(e) => setScale(e.target.value as RegressionScale)}
          >
            <option value="log">Logarithme du prix</option>
            <option value="linear">Prix linéaire</option>
          </select>
        </label>
        <label>
          Seuil des zones
          <select
            aria-label="Seuil des zones"
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
          >
            <option value={0}>Sous / au-dessus de la tendance</option>
            {[0.5, 1, 1.2, 1.4, 1.5, 1.6, 1.8, 2].map((value) => (
              <option key={value} value={value}>
                ± {number(value, 1)} écart{value > 1 ? "s" : ""}-type
                {value > 1 ? "s" : ""}
              </option>
            ))}
          </select>
        </label>
      </div>
      {result.error && (
        <p className="error" role="alert">
          {result.error}
        </p>
      )}
      {fit && last && (
        <>
          <div
            className="reversion-summary"
            aria-label="Diagnostic de la régression"
          >
            <div>
              <span>Zone au {date(last.time)}</span>
              <strong
                className={
                  last.zone === "entry"
                    ? "positive"
                    : last.zone === "exit"
                      ? "negative"
                      : ""
                }
              >
                {last.zone === "entry"
                  ? "Entrée potentielle"
                  : last.zone === "exit"
                    ? "Vente potentielle"
                    : "Zone neutre"}
              </strong>
              <small>
                Écart à la tendance :{" "}
                {percent(last.value / last.trend - 1, true)}
              </small>
            </div>
            <div>
              <span>Prix de tendance</span>
              <strong>
                {number(last.trend, last.trend < 1 ? 4 : 2)} {asset.unit}
              </strong>
              <small>
                Prix observé : {number(last.value, last.value < 1 ? 4 : 2)}
              </small>
            </div>
            <div>
              <span>Écart normalisé</span>
              <strong>{last.z === null ? "—" : `${number(last.z)} σ`}</strong>
              <small>Dispersion propre à cet actif</small>
            </div>
            <div>
              <span>Pente annualisée de la tendance</span>
              <strong>
                {Number.isFinite(fit.annualTrend)
                  ? `${percent(fit.annualTrend, true)} / an`
                  : "—"}
              </strong>
              <small>
                {fit.rows.length} observations · R²{" "}
                {fit.r2 === null ? "—" : number(fit.r2, 3)}
                <Tooltip label="Pente annualisée">
                  En logarithmique : exp(pente) − 1. En linéaire : variation
                  annuelle divisée par le prix initial de la droite ajustée.
                  Mesure descriptive de la période sélectionnée, hors prévision.
                </Tooltip>
              </small>
            </div>
          </div>
          <div className="reversion-legend">
            <span className="positive">● Entrée potentielle</span>
            <span className="negative">● Vente potentielle</span>
            <span>● Neutre</span>
            <span className="trend-key">━ Tendance ajustée</span>
          </div>
          <HistoryChart
            points={fit.rows}
            overlays={overlays}
            pointColors={colors}
            logarithmic={scale === "log"}
          />
          {comparison && (
            <section aria-label="Comparaison des stratégies de régression">
              <div className="reversion-heading">
                <h3>Achat-conservation vs bandes de régression</h3>
                <p>
                  Achat à −{number(threshold, 1)} σ · vente à +
                  {number(threshold, 1)} σ · capital initial de 100.
                </p>
              </div>
              <div className="regression-comparison-summary">
                <div className="reversion-summary">
                  {(
                    [
                      ["Bandes de régression", comparison.strategy],
                      ["Achat-conservation", comparison.benchmark],
                    ] as const
                  ).map(([label, metrics]) => (
                    <div key={label}>
                      <span>{label}</span>
                      <strong
                        className={
                          metrics.totalReturn >= 0 ? "positive" : "negative"
                        }
                      >
                        {percent(metrics.totalReturn, true)}
                      </strong>
                      <small>
                        Baisse maximale : {percent(metrics.maxDrawdown)}
                      </small>
                    </div>
                  ))}
                  <div>
                    <span>Opérations sur les bandes</span>
                    <strong>
                      {comparison.purchases} achats · {comparison.sales} ventes
                    </strong>
                    <small>
                      Position finale :{" "}
                      {comparison.invested ? "investi" : "liquidités"}
                    </small>
                  </div>
                  <div>
                    <span>Temps d’exposition</span>
                    <strong>{percent(comparison.exposure)}</strong>
                    <small>Durée investie sur la période</small>
                  </div>
                </div>
                <div
                  className="regression-summary-fee"
                  aria-label="Frais de simulation"
                >
                  <FeeControl label="Frais" value={fee} onChange={setFee} />
                </div>
              </div>
              <div className="reversion-legend">
                <span className="trend-key">━ Bandes de régression</span>
                <span>━ Achat-conservation</span>
              </div>
              <HistoryChart
                comparison={comparison.equity}
                comparisonLabels={{
                  strategy: "Bandes de régression",
                  benchmark: "Achat-conservation",
                  accessible:
                    "Capital des bandes de régression et de l’achat-conservation, base 100",
                }}
              />
            </section>
          )}
          <div className="reversion-notes" role="status">
            {fit.slope <= 0 && (
              <p>
                Tendance stable ou baissière : une entrée sous la tendance peut
                accompagner une baisse durable.
              </p>
            )}
            {fit.reversal && (
              <p>
                La pente change de signe entre les deux moitiés de la période :
                une droite unique résume mal les changements de cycle.
              </p>
            )}
            {fit.r2 !== null && fit.r2 < 0.5 && (
              <p>
                La droite explique moins de la moitié de la variation des prix{" "}
                {scale === "log" ? "logarithmiques" : "linéaires"} sur cette
                période.
              </p>
            )}
            {fit.degenerate && (
              <p>
                Dispersion résiduelle quasi nulle : les zones et l’écart
                normalisé ne sont pas interprétables.
              </p>
            )}
          </div>
          <details className="reversion-method">
            <summary>Comprendre l’ajustement</summary>
            <p>
              La régression minimise la somme des carrés des écarts sur les
              observations de la période choisie. Chaque observation a le même
              poids ; le temps est mesuré en jours calendaires. Le mode
              logarithmique ajuste une croissance en pourcentage (droite sur le
              graphique logarithmique). Le mode linéaire ajuste une progression
              en prix ; son taux annuel affiché rapporte la pente au premier
              prix observé.
            </p>
            <p>
              Les seuils utilisent l’écart-type des résidus, calculé avec n − 2
              degrés de liberté. À zéro, tout prix inférieur à la tendance est
              une entrée potentielle, tout prix supérieur une vente potentielle.
              Le contact avec une borne est inclus dans le signal. Un seuil
              positif laisse une zone neutre. Ces bandes décrivent la dispersion
              passée, pas un intervalle de confiance.
            </p>
            <p>
              La droite utilise toute la période sélectionnée : modifier sa fin
              recalcule aussi les zones et la simulation passées. Le comparatif
              utilise donc des informations futures : il ne mesure pas une
              performance hors échantillon. Un R² élevé ne démontre ni un retour
              à la moyenne ni une rentabilité.
            </p>
            <p>
              Simulation rétrospective avec départ en liquidités pour les bandes
              ; achat-conservation dès la première observation. Frais identiques
              à l’achat et à la vente, appliqués à chaque opération, achat
              initial inclus pour l’achat-conservation. Positions ouvertes
              valorisées au dernier cours sans vente forcée. Exposition mesurée
              en durée calendaire entre observations, selon la position détenue
              après le signal. Liquidités non rémunérées ; hors fiscalité.
            </p>
            <p>
              Méthode :{" "}
              <a
                href="https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd431.htm"
                target="_blank"
                rel="noreferrer"
              >
                moindres carrés et dispersion résiduelle · NIST
              </a>
              .
            </p>
          </details>
        </>
      )}
    </section>
  );
}
