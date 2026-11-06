import { Tooltip } from "../../components/Tooltip";
import { date, number, percent } from "../../lib/format";
import type { Analysis } from "../../lib/types";
import { PerformanceChart } from "./PerformanceChart";
import { MetricCards } from "./MetricCard";
import { RegimeTimeline } from "./RegimeTimeline";
export function AnalysisResults({ result: r }: { result: Analysis }) {
  const strategy = r.strategy_metrics,
    benchmark = r.benchmark_metrics;
  const excess =
    strategy?.total_return != null && benchmark?.total_return != null
      ? strategy.total_return - benchmark.total_return
      : null;
  return (
    <div className="analysis-results">
      <div className="section-heading">
        <div>
          <span className="eyebrow">RÉSULTATS HORS ÉCHANTILLON</span>
          <h3>
            {date(r.actual_test[0])} <span className="muted">—</span>{" "}
            {date(r.actual_test[1])}
          </h3>
        </div>
        <span className="badge">{number(r.test_points, 0)} observations</span>
      </div>
      {strategy && benchmark && (
        <>
          <div className="performance-summary">
            <div>
              <span className="field-label">Stratégie nette</span>
              <strong
                className={
                  (strategy.total_return ?? 0) >= 0 ? "positive" : "negative"
                }
              >
                {percent(strategy.total_return, true)}
              </strong>
              <small>{percent(strategy.annualized_return, true)} / an</small>
            </div>
            <div>
              <span className="field-label">Achat & conservation</span>
              <strong>{percent(benchmark.total_return, true)}</strong>
              <small>{percent(benchmark.annualized_return, true)} / an</small>
            </div>
            <div>
              <span className="field-label">
                Transactions{" "}
                <Tooltip label="Transactions">
                  <span>
                    Chaque achat et chaque vente compte pour une transaction,
                    liquidation finale comprise. Le même taux de frais
                    s’applique à chaque transaction. Le benchmark supporte aussi
                    une entrée et une sortie.
                  </span>
                </Tooltip>
              </span>
              <strong>{r.trades.length}</strong>
              <small>Exposition {percent(r.exposure)}</small>
            </div>
          </div>
          <div
            className="analysis-assessment"
            aria-label="Évaluation face à la conservation"
          >
            {excess != null && (
              <p>
                Écart net face à la conservation :{" "}
                <strong className={excess >= 0 ? "positive" : "negative"}>
                  {excess > 0 ? "+" : ""}
                  {number(excess * 100, 2)} points
                </strong>
              </p>
            )}
            {r.exposure != null && r.exposure >= 0.95 && (
              <p>
                Exposition presque permanente ({percent(r.exposure)}) : ce
                résultat reste proche de l’achat-conservation.
              </p>
            )}
            {r.diagnostics?.exit_reachable === false && (
              <p>
                Aucune sortie de régime possible avec ce modèle et sa règle de
                frais. La vente finale est la seule sortie possible.
              </p>
            )}
          </div>
          <PerformanceChart equity={r.equity} />
          <RegimeTimeline result={r} />
          <MetricCards strategy={strategy} benchmark={benchmark} />
        </>
      )}
      <details className="model-details">
        <summary>
          Modèle & transactions{" "}
          <span>
            {r.train_points} points d’entraînement · {r.states.length} états
            gaussiens
          </span>
        </summary>
        <div className="model-tables">
          <div>
            <h4>Matrice de transition</h4>
            <p className="fine-print">
              Probabilité de l’état suivant, depuis chaque ligne.
            </p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Depuis / vers</th>
                    {r.states.map((s) => (
                      <th key={s.name}>{s.name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {r.states.map((s, i) => (
                    <tr key={s.name}>
                      <th>{s.name}</th>
                      {r.transition_matrix[i].map((v, j) => (
                        <td key={j}>{percent(v)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {r.mode === "backtest" && (
            <div>
              <h4>Journal des transactions</h4>
              <div className="trade-list">
                {!r.trades.length ? (
                  <p className="muted">Aucune transaction.</p>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Ordre</th>
                        <th>Prob. des régimes favorables</th>
                        <th>Motif</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.trades.map((t, i) => (
                        <tr key={i}>
                          <td>{date(t.time)}</td>
                          <td
                            className={t.side === "buy" ? "positive" : "muted"}
                          >
                            {t.side === "buy" ? "Achat" : "Vente"}
                          </td>
                          <td>{percent(t.probability)}</td>
                          <td>
                            {t.reason === "final_liquidation"
                              ? "Fin de simulation"
                              : "Régime"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </div>
      </details>
      <details className="analysis-notes">
        <summary>Hypothèses et limites</summary>
        {r.warnings.map((note) => (
          <p key={note}>{note}</p>
        ))}
        <p>
          Simulation historique, sans garantie de surperformance. Réutiliser la
          période 2 pour ajuster les paramètres crée un biais de sélection.
        </p>
      </details>
    </div>
  );
}
