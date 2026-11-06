import { HistoryChart } from "../../components/HistoryChart";
import { Tooltip } from "../../components/Tooltip";
import { date, number, percent } from "../../lib/format";
import type { Analysis } from "../../lib/types";
import { MetricCards } from "./MetricCard";
export function AnalysisResults({ result: r }: { result: Analysis }) {
  const strategy = r.strategy_metrics,
    benchmark = r.benchmark_metrics;
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
                    liquidation finale comprise. Frais et glissement
                    s’appliquent à chaque transaction. Le benchmark supporte
                    aussi une entrée et une sortie.
                  </span>
                </Tooltip>
              </span>
              <strong>
                {r.trades.length}
                <span className="summary-unit">
                  {" "}
                  / {r.parameters.max_trades}
                </span>
              </strong>
              <small>Exposition {percent(r.exposure)}</small>
            </div>
          </div>
          <div className="equity-heading">
            <span className="field-label">Évolution du capital · base 100</span>
            <div className="chart-legend">
              <span>
                <i className="strategy-dot" />
                Stratégie
              </span>
              <span>
                <i className="market-dot" />
                Marché
              </span>
            </div>
          </div>
          <HistoryChart comparison={r.equity} compact />
          <MetricCards strategy={strategy} benchmark={benchmark} />
        </>
      )}
      <div className="regimes-section">
        <div className="equity-heading">
          <span className="field-label">Régimes détectés · période 2</span>
          <div className="chart-legend">
            {r.states.map((s, i) => (
              <span key={s.name}>
                <i className={`regime-${i}`} />
                {s.name}
              </span>
            ))}
          </div>
        </div>
        <div className="regime-strip" aria-label="Chronologie des régimes">
          {r.regimes.map((p) => (
            <span
              key={p.time}
              className={`regime-${r.states.findIndex((s) => s.name === p.state)}`}
              title={`${date(p.time)} · ${p.state} · ${percent(Math.max(...p.probabilities))}`}
            />
          ))}
        </div>
        <div className="timeline-dates">
          <span>{date(r.actual_test[0])}</span>
          <span>{date(r.actual_test[1])}</span>
        </div>
      </div>
      <details className="model-details">
        <summary>
          Modèle & transactions{" "}
          <span>
            {r.train_points} points d’entraînement · 3 états gaussiens
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
                        <th>Prob. porteuse</th>
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
      <div className="analysis-notes">
        {r.warnings.map((note) => (
          <p key={note}>{note}</p>
        ))}
        <p>
          Simulation historique, sans garantie de surperformance. Réutiliser la
          période 2 pour ajuster les paramètres crée un biais de sélection.
        </p>
      </div>
    </div>
  );
}
