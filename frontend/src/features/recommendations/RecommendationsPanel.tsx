import { useEffect, useState } from "react";
import { Link } from "react-router";
import { post } from "../../lib/api";
import { date, number } from "../../lib/format";
import type { Asset } from "../../lib/types";
import { useMomentumScores } from "../momentum/useMomentumScores";
import { weightedScore, partialHistory } from "../momentum/score";
import {
  RegressionDeviation,
  type Deviation,
} from "../portfolio/RegressionDeviation";
import { recommendation } from "./model";
import { RecommendationMethod } from "./RecommendationMethod";

export function RecommendationsPanel({
  assets,
  heldAssetIds,
}: {
  assets: Asset[];
  heldAssetIds: string[];
}) {
  const stocks = assets.filter((a) => a.category === "stock");
  const momentum = useMomentumScores(stocks);
  const [deviations, setDeviations] = useState<Deviation[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const revision = JSON.stringify(
    stocks.map((a) => [a.id, a.last_date, a.last_value, a.points]),
  );
  useEffect(() => {
    const controller = new AbortController();
    setDeviations([]);
    setError("");
    setLoading(true);
    const ids = (
      JSON.parse(revision) as [string, string, number, number][]
    ).map(([id]) => id);
    if (!ids.length) {
      setLoading(false);
      return () => controller.abort();
    }
    post<{ positions: Deviation[] }>(
      "/portfolio/regression",
      { asset_ids: ids },
      controller.signal,
    )
      .then((data) => {
        if (!controller.signal.aborted) setDeviations(data.positions);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError((e as Error).message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [revision]);
  const rows = stocks
    .map((asset) => {
      const held = heldAssetIds.includes(asset.id);
      const source = momentum.stocks.find((s) => s.id === asset.id);
      const m = weightedScore(source?.scores ?? null, momentum.weights);
      const deviation = deviations.find((d) => d.id === asset.id);
      const unaligned =
        !deviation?.end ||
        !momentum.asOf ||
        Math.abs(Date.parse(deviation.end) - Date.parse(momentum.asOf)) >
          7 * 86400000;
      const result = recommendation({
        momentum: m,
        z: deviation?.z ?? null,
        held,
        unavailable:
          error ||
          momentum.error ||
          (unaligned
            ? "Dates des indicateurs indisponibles ou décalées de plus de sept jours."
            : (source?.reason ?? undefined)),
      });
      return {
        asset,
        held,
        m,
        partial: partialHistory(source?.scores ?? null),
        deviation,
        ...result,
      };
    })
    .sort((a, b) => {
      const priority = {
        Acheter: 0,
        Renforcer: 0,
        Vendre: 1,
        Alléger: 2,
        Conserver: 3,
        Attendre: 4,
        Indisponible: 5,
      };
      return (
        priority[a.action] - priority[b.action] ||
        (b.priority ?? -1) - (a.priority ?? -1) ||
        a.asset.name.localeCompare(b.asset.name)
      );
    });
  const pending = loading || (stocks.length > 0 && momentum.pending);
  return (
    <section
      className="portfolio-content recommendations-panel"
      aria-label="Recommandation action"
    >
      <div className="portfolio-section-heading">
        <div>
          <h2>Recommandation action</h2>
          <p>
            Vos actions détenues et votre watchlist · Momentum et position face
            à la tendance
          </p>
        </div>
      </div>
      {pending && <p role="status">Calcul des recommandations…</p>}
      {(error || momentum.error) && (
        <p role="alert" className="error">
          {error || momentum.error}
        </p>
      )}
      {!stocks.length && (
        <p className="portfolio-empty">
          Ajoutez des actions aux actifs détenus ou à la watchlist pour obtenir
          des recommandations.
        </p>
      )}
      {!pending && stocks.length > 0 && (
        <div className="table-scroll">
          <table className="positions-table recommendation-table">
            <thead>
              <tr>
                <th>Action</th>
                <th>Statut</th>
                <th>Momentum</th>
                <th>Écart à la régression</th>
                <th>Priorité d’entrée</th>
                <th>Recommandation</th>
                <th>Motif</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.asset.id}>
                  <th>
                    <Link
                      to={`/assets/${row.asset.id}?library=${row.held ? "portfolio" : "watchlist"}`}
                    >
                      {row.asset.name}
                    </Link>
                    <small>
                      {row.asset.unit} ·{" "}
                      {row.deviation?.start && row.deviation.end
                        ? `${date(row.deviation.start)} → ${date(row.deviation.end)}`
                        : "Régression indisponible"}
                    </small>
                  </th>
                  <td>{row.held ? "Détenue" : "Watchlist"}</td>
                  <td>
                    {row.m === null ? "—" : `${number(row.m, 1)} / 100`}
                    {row.partial && (
                      <small className="momentum-partial">
                        Historique partiel
                      </small>
                    )}
                  </td>
                  <td>
                    <RegressionDeviation deviation={row.deviation} />
                  </td>
                  <td>
                    {row.priority === null
                      ? "—"
                      : `${number(row.priority, 1)} / 100`}
                  </td>
                  <td>
                    <span
                      className={`recommendation-badge recommendation-${row.action.toLowerCase()}`}
                    >
                      {row.action}
                    </span>
                  </td>
                  <td className="recommendation-reason">{row.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <RecommendationMethod />
    </section>
  );
}
