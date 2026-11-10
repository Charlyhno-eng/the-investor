import { useEffect, useMemo, useState } from "react";
import { Tooltip } from "../../components/Tooltip";
import {
  weightedScore,
  effectiveWeights,
  partialHistory,
  MOMENTUM_HORIZONS,
  type MomentumStock,
} from "./score";
import { useMomentumSettings } from "./useMomentumSettings";
import { HistoryChart } from "../../components/HistoryChart";
import { api } from "../../lib/api";
import { date, number, percent } from "../../lib/format";
import type { Asset } from "../../lib/types";

type Horizon = {
  months: number;
  error?: string;
  start: string;
  end: string;
  observations: number;
  performance: number;
  annual_performance: number;
  annual_trend: number;
  slope: number;
  r2: number;
  sigma: number;
  relative_performance: number;
  score: number;
  rows: { time: string; value: number; trend: number; residual: number }[];
};
type Result = {
  status: "ready" | "pending";
  as_of: string;
  benchmark_name: string;
  benchmarks: { id: string; name: string }[];
  horizons: Horizon[];
  universe: MomentumStock[];
  recent_return: number | null;
  drawdown: number | null;
};

export function MomentumPanel({
  asset,
  assets,
}: {
  asset: Asset;
  assets: Asset[];
}) {
  const isCrypto = asset.category === "crypto";
  const category = isCrypto ? "crypto" : "stock";
  const { benchmark, weights, update } = useMomentumSettings(category);
  const [horizon, setHorizon] = useState(12);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const benchmarks = assets.filter(
    (item) =>
      item.category === (isCrypto ? "crypto" : "etf") &&
      (!isCrypto || item.id !== "yf-btc-usd"),
  );
  const historyRevision = JSON.stringify(
    assets
      .filter((a) => a.category === category)
      .map((a) => [a.id, a.data_revision, a.last_date, a.last_value, a.points]),
  );
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setLoading(true);
    setError("");
    setResult(null);
    let attempts = 0;
    async function fetchResult() {
      try {
        const data = await api<Result>(
          `/assets/${encodeURIComponent(asset.id)}/momentum${benchmark ? `?benchmark=${encodeURIComponent(benchmark)}` : ""}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        setResult(data);
        setLoading(false);
        if (data.status === "pending") {
          if (++attempts < 30) timer = setTimeout(fetchResult, 2000);
          else
            setError(
              "La référence est toujours en cours de chargement. Rouvrez cet onglet pour réessayer.",
            );
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          setError((e as Error).message);
          setLoading(false);
        }
      }
    }
    void fetchResult();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [
    asset.id,
    asset.data_revision,
    asset.last_date,
    asset.last_value,
    asset.points,
    benchmark,
    historyRevision,
  ]);
  const total = weights.reduce((a, b) => a + b, 0);
  const universe = useMemo(
    () =>
      result?.status === "ready"
        ? result.universe.filter((stock) =>
            assets.some((item) => item.id === stock.id),
          )
        : [],
    [result, assets],
  );
  const ranking = useMemo(() => {
    if (result?.status !== "ready" || total <= 0) return [];
    return universe
      .flatMap((stock) => {
        const score = weightedScore(stock.scores, weights);
        return score === null ? [] : [{ ...stock, score }];
      })
      .sort((a, b) => b.score - a.score || a.name.localeCompare(b.name));
  }, [result, weights, total, universe]);
  const selected =
    result?.status === "ready"
      ? result.horizons.find((h) => h.months === horizon)
      : null;
  const fit = selected && !selected.error ? selected : null;
  const overlays = useMemo(
    () =>
      fit
        ? [
            {
              title: "Tendance",
              color: "#edb786",
              points: fit.rows.map((p) => ({ time: p.time, value: p.trend })),
            },
          ]
        : [],
    [fit],
  );
  const residualLines = useMemo(
    () =>
      fit
        ? [
            {
              title: "Résidu logarithmique × 100",
              color: "#91c9c2",
              points: fit.rows.map((p) => ({
                time: p.time,
                value: p.residual * 100,
              })),
            },
            {
              title: "Zéro",
              color: "#65738e",
              points: fit.rows.map((p) => ({ time: p.time, value: 0 })),
            },
          ]
        : [],
    [fit],
  );
  const rank = ranking.findIndex((s) => s.id === asset.id);
  const score = rank >= 0 ? ranking[rank].score : null;
  const source = universe.find((item) => item.id === asset.id);
  const effective = effectiveWeights(source?.scores ?? null, weights);
  const partial = partialHistory(source?.scores ?? null);
  const available = MOMENTUM_HORIZONS.filter(
    (_, i) => source?.scores?.[i] != null,
  );
  return (
    <section
      className="analysis-panel momentum-panel"
      aria-label={
        isCrypto ? "Momentum de la cryptomonnaie" : "Momentum de l’action"
      }
    >
      <div
        className="reversion-controls momentum-weights"
        aria-label="Pondération des horizons"
      >
        {MOMENTUM_HORIZONS.map((months, i) => (
          <label key={months}>
            Poids {months} mois (%)
            <input
              aria-label={`Poids ${months} mois (%)`}
              type="number"
              min="0"
              max="100"
              step="1"
              value={weights[i]}
              onChange={(e) =>
                update({
                  benchmark,
                  weights: weights.map((v, j) =>
                    j === i
                      ? Math.min(100, Math.max(0, Number(e.target.value) || 0))
                      : v,
                  ),
                })
              }
            />
          </label>
        ))}
        <label>
          Indice de référence
          <select
            aria-label="Référence momentum"
            value={benchmark}
            onChange={(e) => update({ weights, benchmark: e.target.value })}
          >
            <option value="">{isCrypto ? "Bitcoin" : "S&P 500"}</option>
            {!isCrypto && <option value="^FCHI">CAC 40</option>}
            {benchmarks.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {total === 0 && (
        <p role="alert" className="error">
          Choisissez au moins un poids positif.
        </p>
      )}
      {loading && (
        <div className="chart-placeholder" role="status">
          Chargement du momentum…
        </div>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {result?.status === "pending" && (
        <p role="status">Import de la référence en cours…</p>
      )}
      {result?.status === "ready" && (
        <>
          <p className="fine-print">
            Au {date(result.as_of)} · référence : {result.benchmark_name}.
            Toutes les {isCrypto ? "cryptomonnaies" : "actions"} de la liste ·
            variations en devise de cotation, hors effet de change.
          </p>
          <div className="reversion-summary" aria-label="Synthèse momentum">
            <div>
              <span>Score pondéré</span>
              <strong>
                {score === null ? "—" : `${number(score, 1)} / 100`}
              </strong>
              <small>50 : neutre · au-dessus : momentum positif</small>
              {partial && (
                <small className="momentum-partial">
                  Historique partiel · {available.join(" / ")} mois
                </small>
              )}
            </div>
            <div>
              <span>Classement</span>
              <strong>
                {rank < 0 ? "Non classée" : `${rank + 1} / ${ranking.length}`}
              </strong>
              <small>
                {universe.length - ranking.length}{" "}
                {isCrypto
                  ? "crypto(s) non classée(s)"
                  : "action(s) non classée(s)"}{" "}
                · horizons disponibles
              </small>
            </div>
            <div>
              <span>Variation du mois exclu</span>
              <strong
                className={
                  (result.recent_return ?? 0) < 0 ? "negative" : "positive"
                }
              >
                {percent(result.recent_return, true)}
              </strong>
              <small>Diagnostic récent, hors score Momentum</small>
            </div>
            <div>
              <span>Écart au sommet sur 36 mois</span>
              <strong className="negative">{percent(result.drawdown)}</strong>
              <small>Dernier cours / sommet − 1</small>
            </div>
          </div>
          <div className="table-scroll">
            <table className="risk-table momentum-table">
              <thead>
                <tr>
                  {[
                    [
                      "Horizon",
                      "Fenêtre allant de 36, 12 ou 6 mois avant l’analyse jusqu’à un mois avant celle-ci. Le dernier mois est exclu des rendements et de la régression.",
                    ],
                    [
                      "Poids effectif",
                      "Part de cet horizon dans le score global. Seuls les horizons disponibles comptent : leurs poids sont divisés par leur somme. Un horizon manquant a un poids effectif nul.",
                    ],
                    [
                      "Rendement",
                      "Variation cumulée du cours ajusté entre les bornes de la fenêtre, dans la devise de cotation. Non annualisée.",
                    ],
                    [
                      "Pente / an",
                      "Vitesse de la tendance : exp(pente de la régression logarithmique sur les années écoulées) − 1. Une pente positive décrit une hausse.",
                    ],
                    [
                      "R²",
                      "Part de la variation des logarithmes des prix expliquée par la droite, entre 0 et 1. Un R² élevé décrit une tendance régulière, sans prédire sa poursuite.",
                    ],
                    [
                      "Dispersion log",
                      "Écart-type des résidus logarithmiques : √[somme des résidus² / (n − 2)]. Plus il est faible, plus les prix suivent la tendance.",
                    ],
                    [
                      "Force relative",
                      isCrypto
                        ? "Ratio de la progression de la cryptomonnaie à celle de Bitcoin ou de la référence choisie, moins 1, sur les mêmes dates, week-ends compris lorsque disponibles. Comparaison en pourcentage sans conversion de devise."
                        : "Ratio de la progression de l’action à celle de la référence, moins 1, sur les mêmes dates. Comparaison des variations en pourcentage sans conversion de devise. S&P 500 : dividendes réinvestis ; CAC 40 : hors dividendes.",
                    ],
                    [
                      "Score / 100",
                      "50 est neutre. Le score combine rendement (40 %), pente (30 %) et force relative (30 %), puis les pondère par √R² / (1 + dispersion / 0,10). Les contributions sont bornées par tanh avec des échelles 0,30 / 0,30 / 0,20. Le score global combine les horizons disponibles et renormalise leurs poids. Indicateur descriptif, sans garantie prédictive.",
                    ],
                  ].map(([label, explanation]) => (
                    <th key={label}>
                      {label}{" "}
                      <Tooltip floating question label={label}>
                        {explanation}
                      </Tooltip>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.horizons.map((h, i) => (
                  <tr key={h.months}>
                    <th>{h.months} mois</th>
                    <td>{percent(effective[i])}</td>
                    {h.error ? (
                      <td colSpan={6}>{h.error}</td>
                    ) : (
                      <>
                        <td>{percent(h.performance, true)}</td>
                        <td>{percent(h.annual_trend, true)}</td>
                        <td>{number(h.r2, 3)}</td>
                        <td>{number(h.sigma, 4)}</td>
                        <td>{percent(h.relative_performance, true)}</td>
                        <td>{number(h.score, 1)}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="momentum-heading">
            <h3>Tendance et résidus</h3>
            <div
              className="range-buttons"
              aria-label="Horizon de régression momentum"
            >
              {MOMENTUM_HORIZONS.map((m) => (
                <button
                  key={m}
                  aria-pressed={horizon === m}
                  onClick={() => setHorizon(m)}
                >
                  {m} mois
                </button>
              ))}
            </div>
          </div>
          {selected?.error && <p role="status">{selected.error}</p>}
          {fit && (
            <>
              <p className="fine-print">
                Du {date(fit.start)} au {date(fit.end)} · {fit.observations}{" "}
                observations communes. Prix ajustés en échelle logarithmique ;
                droite de tendance en orange.
              </p>
              <HistoryChart
                points={fit.rows}
                overlays={overlays}
                logarithmic
                accessibleLabel="Momentum : prix et régression logarithmique"
              />
              <h3>Résidus de la régression</h3>
              <p className="fine-print">
                100 × [ln(prix observé) − ln(prix ajusté)]. Au-dessus de zéro :
                le cours dépasse sa tendance.
              </p>
              <HistoryChart
                lines={residualLines}
                compact
                accessibleLabel="Momentum : résidus logarithmiques autour de zéro"
                valueLabel="Résidus log × 100"
              />
            </>
          )}
        </>
      )}
    </section>
  );
}
