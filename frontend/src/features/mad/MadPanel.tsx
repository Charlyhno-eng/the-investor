import { useMemo, useState } from "react";
import { HistoryChart } from "../../components/HistoryChart";
import { date, number, percent } from "../../lib/format";
import type { Asset, Point } from "../../lib/types";
import { FeeControl } from "../reversion/FeeControl";
import { simulateMad } from "./strategy";

export function MadPanel({ asset, points }: { asset: Asset; points: Point[] }) {
  const earliest = points[200]?.time;
  const [start, setStart] = useState(() => {
    const cutoff = new Date(`${points.at(-1)!.time}T00:00:00Z`);
    cutoff.setUTCFullYear(cutoff.getUTCFullYear() - 5);
    return (
      points.find(
        (p, i) => i >= 200 && p.time >= cutoff.toISOString().slice(0, 10),
      )?.time ??
      earliest ??
      ""
    );
  });
  const [end, setEnd] = useState(points.at(-1)!.time);
  const [fee, setFee] = useState(asset.category === "crypto" ? 0.01 : 0.5);
  const result = useMemo(() => {
    try {
      return { data: simulateMad(points, start, end, fee / 100) };
    } catch (e) {
      return { error: (e as Error).message };
    }
  }, [points, start, end, fee]);
  const data = result.data;
  const overlays = useMemo(
    () =>
      data
        ? [
            { title: "MM21", color: "#edb786", points: data.short },
            { title: "MM200", color: "#65c7a5", points: data.long },
          ]
        : [],
    [data],
  );

  return (
    <section
      className="analysis-panel reversion-panel"
      aria-label="Stratégie MAD 21/200"
    >
      <div className="reversion-heading">
        <h2>Moving Average Distance · 21 / 200</h2>
        <p>
          Investi lorsque la MM21 dépasse la MM200, en liquidités sinon. Signal
          à la clôture, exécution à la clôture suivante.
        </p>
      </div>
      {points.length < 202 ? (
        <p className="error" role="alert">
          Historique insuffisant : 202 observations au minimum, dont 200 avant
          la simulation.
        </p>
      ) : (
        <>
          <div className="reversion-controls">
            <label>
              Début de période
              <input
                type="date"
                min={earliest}
                max={points.at(-1)!.time}
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label>
              Fin de période
              <input
                type="date"
                min={earliest}
                max={points.at(-1)!.time}
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
            <FeeControl
              label="Frais par opération"
              value={fee}
              onChange={setFee}
            />
          </div>
          {result.error && (
            <p className="error" role="alert">
              {result.error}
            </p>
          )}
          {data && (
            <>
              <div className="reversion-heading">
                <h3>Prix de l’actif et moyennes mobiles</h3>
                <p>
                  Du {date(data.points[0].time)} au{" "}
                  {date(data.points.at(-1)!.time)} · {data.points.length}{" "}
                  observations · {asset.unit}
                </p>
              </div>
              <div className="reversion-legend">
                <span>━ Prix de l’actif</span>
                <span style={{ color: "#edb786" }}>━ MM21</span>
                <span className="positive">━ MM200</span>
              </div>
              <HistoryChart
                accessibleLabel="Prix de l’actif et moyennes mobiles 21 et 200"
                linesCaption={asset.unit}
                lines={[
                  {
                    title: "Prix de l’actif",
                    color: "#8390a7",
                    points: data.points,
                  },
                  ...overlays,
                ]}
              />
              <section aria-label="Comparaison des performances MAD">
                <div className="reversion-heading">
                  <h3>Performance sur la même période</h3>
                  <p>
                    Capital initial de 100 · performances cumulées nettes de
                    frais · positions finales valorisées au dernier cours.
                  </p>
                </div>
                <div className="reversion-summary">
                  <div>
                    <span>Stratégie MAD 21/200</span>
                    <strong
                      className={
                        data.strategyReturn >= 0 ? "positive" : "negative"
                      }
                    >
                      {percent(data.strategyReturn, true)}
                    </strong>
                    <small>
                      {data.purchases} achats · {data.sales} ventes
                    </small>
                  </div>
                  <div>
                    <span>Actif · achat-conservation</span>
                    <strong
                      className={
                        data.benchmarkReturn >= 0 ? "positive" : "negative"
                      }
                    >
                      {percent(data.benchmarkReturn, true)}
                    </strong>
                    <small>
                      Variation du cours hors frais :{" "}
                      {percent(data.assetReturn, true)}
                    </small>
                  </div>
                  <div>
                    <span>Écart de performance</span>
                    <strong
                      className={
                        data.strategyReturn >= data.benchmarkReturn
                          ? "positive"
                          : "negative"
                      }
                    >
                      {number(
                        100 * (data.strategyReturn - data.benchmarkReturn),
                      )}{" "}
                      points
                    </strong>
                    <small>Stratégie moins achat-conservation</small>
                  </div>
                  <div>
                    <span>Temps d’exposition</span>
                    <strong>{percent(data.exposure)}</strong>
                    <small>
                      Position finale :{" "}
                      {data.invested ? "investi" : "liquidités"}
                    </small>
                  </div>
                </div>
                <div className="reversion-legend">
                  <span className="trend-key">━ Stratégie MAD 21/200</span>
                  <span>━ Actif · achat-conservation</span>
                </div>
                <HistoryChart
                  comparison={data.equity}
                  comparisonLabels={{
                    strategy: "Stratégie MAD 21/200",
                    benchmark: "Actif · achat-conservation",
                    accessible: "Capital MAD et achat-conservation, base 100",
                  }}
                />
              </section>
              <p className="muted">
                Distance MM21 / MM200 − 1 au {date(data.points.at(-1)!.time)} :{" "}
                {percent(data.distance, true)}. Ce signal ne peut être exécuté
                qu’à la prochaine observation, hors de cette simulation.
              </p>
            </>
          )}
        </>
      )}
      <details className="reversion-method">
        <summary>Comprendre la stratégie et les pourcentages</summary>
        <p>
          Les moyennes simples utilisent les 21 et 200 dernières clôtures
          observées. Pour les actions, ce sont des séances ; pour les cryptos,
          des jours disponibles. Les 200 observations précédant la période
          servent uniquement au calcul et ne contribuent pas à la performance.
          Les dates réellement comparées sont affichées au-dessus du graphique.
        </p>
        <p>
          À chaque clôture, la cible est 100 % investi si MM21 &gt; MM200, 100 %
          liquidités sinon (égalité comprise). L’ordre est exécuté à la clôture
          observée suivante ; les mouvements de prix avant cette exécution
          restent subis par la position précédente. Le premier ordre peut
          utiliser le signal de la veille du début choisi. Aucun ordre
          supplémentaire si la cible ne change pas, aucune vente à découvert ni
          effet de levier.
        </p>
        <p>
          Le capital commence à 100. À l’achat, la quantité vaut capital / (prix
          × (1 + frais)) ; à la vente, le capital vaut quantité × prix × (1 −
          frais). Le pourcentage affiché est (capital final / 100 − 1) × 100,
          avec réinvestissement de tout le capital. L’achat-conservation achète
          à la première clôture de la même période, avec les mêmes frais
          d’achat. Aucune vente finale forcée pour les deux approches ; les
          positions ouvertes sont valorisées sans frais de sortie.
        </p>
        <p>
          Liquidités non rémunérées ; hors fiscalité, spread et glissement
          d’exécution. Les clôtures ajustées des actions intègrent déjà les
          dividendes selon le fournisseur, sans ajout supplémentaire. Les frais
          sont réglables, par défaut 0,5 % pour les actions et 0,01 % pour les
          cryptos, à chaque achat et vente.
        </p>
        <p>
          Cette règle est une adaptation de suivi de tendance sur un seul actif.
          L’étude MAD d’Avramov, Kaplanski et Subrahmanyam classe plusieurs
          actions selon leur ratio MM21 / MM200 ; ses résultats ne valident pas
          directement cette simulation ni son application aux cryptos. Les
          performances historiques affichées ne garantissent pas les
          performances futures.{" "}
          <a
            href="https://onlinelibrary.wiley.com/doi/10.1002/rfe.1118"
            target="_blank"
            rel="noreferrer"
          >
            Étude originale · Review of Financial Economics (2021)
          </a>
          .
        </p>
      </details>
    </section>
  );
}
