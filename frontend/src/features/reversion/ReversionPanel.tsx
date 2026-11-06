import { useMemo, useState } from "react";
import { HistoryChart } from "../../components/HistoryChart";
import { date, number, percent } from "../../lib/format";
import type { Asset, Point } from "../../lib/types";
import { fitRegression, type RegressionScale } from "./regression";

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
  const [threshold, setThreshold] = useState(2);
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
      <div className="reversion-heading">
        <h2>Retour à la tendance</h2>
        <p>
          Repérez les écarts du prix à sa trajectoire sur la période de votre
          choix.
        </p>
      </div>
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
            <option value={0.5}>± 0,5 écart-type</option>
            <option value={1}>± 1 écart-type</option>
            <option value={1.5}>± 1,5 écart-type</option>
            <option value={2}>± 2 écarts-types</option>
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
              <span>Qualité de l’ajustement · R²</span>
              <strong>{fit.r2 === null ? "—" : number(fit.r2, 3)}</strong>
              <small>
                {fit.rows.length} observations · tendance annuelle{" "}
                {Number.isFinite(fit.annualTrend)
                  ? percent(fit.annualTrend, true)
                  : "—"}
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
              Un seuil positif laisse une zone neutre. Ces bandes décrivent la
              dispersion passée, pas un intervalle de confiance.
            </p>
            <p>
              La droite utilise toute la période sélectionnée : modifier sa fin
              recalcule aussi les zones passées. Cette vue descriptive ne
              constitue pas un backtest. Un R² élevé ne démontre ni un retour à
              la moyenne ni une rentabilité ; les frais et l’exécution des
              ordres ne sont pas simulés.
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
