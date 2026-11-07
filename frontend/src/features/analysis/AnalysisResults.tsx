import { Tooltip } from "../../components/Tooltip";
import { date, number, percent } from "../../lib/format";
import type { Analysis } from "../../lib/types";
import { PerformanceChart } from "./PerformanceChart";
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
            {r.diagnostics?.entry_reachable === false && (
              <p className="error" role="status">
                Aucun achat possible : même la meilleure prévision du modèle (
                {percent(r.diagnostics.maximum_state_forecast ?? null)}) reste
                sous le seuil des frais aller-retour (
                {percent(r.diagnostics.round_trip_threshold ?? null)}). La règle
                de décision est bloquée en liquidités.
              </p>
            )}
            {r.model_selection &&
              r.model_selection.method !==
                "fixed_two_states_training_likelihood" && (
                <p>
                  {r.model_selection.regimes_supported
                    ? `${r.model_selection.selected_states} états retenus par validation chronologique.`
                    : "La validation ne justifie pas plusieurs régimes : modèle sans changement d’état retenu."}{" "}
                  Ce diagnostic ne valide pas la rentabilité de la stratégie.
                </p>
              )}
            {r.exposure != null && r.exposure >= 0.95 && (
              <p>
                Exposition presque permanente ({percent(r.exposure)}) : ce
                résultat reste proche de l’achat-conservation.
              </p>
            )}
            {r.exposure != null && r.exposure <= 0.05 && (
              <p>
                Exposition faible ({percent(r.exposure)}) : cette simulation
                reste essentiellement en liquidités.
              </p>
            )}
            {r.diagnostics?.exit_reachable === false &&
              (r.exposure ?? 0) > 0 && (
                <p>
                  Aucune sortie de régime possible avec les prévisions et frais
                  actuels. Toute position ouverte sera liquidée en fin de
                  simulation.
                </p>
              )}
          </div>
          <PerformanceChart equity={r.equity} />
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
        {r.model_selection?.method ===
          "fixed_two_states_training_likelihood" && (
          <p className="fine-print">
            Rendements seuls · deux états gaussiens · initialisation choisie par
            vraisemblance d’entraînement. Paramètres figés pendant le test,
            probabilités filtrées sans données futures. Signal à la clôture,
            exécution à la clôture suivante.
          </p>
        )}
        {r.model_selection &&
          r.model_selection.method !==
            "fixed_two_states_training_likelihood" && (
            <p className="fine-print">
              Rendements seuls · validation sur{" "}
              {r.model_selection.validation_points} observations d’entraînement
              · comparaison de 1, 2 et 3 états, avec préférence pour le modèle
              le plus simple lorsque les scores sont proches. Paramètres figés
              pendant le test. Prévision de décision sur 5 observations après
              exécution.
            </p>
          )}
        {r.model_selection &&
          r.model_selection.method !==
            "fixed_two_states_training_likelihood" && (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>États candidats</th>
                    <th>Log-densité prédictive moyenne en validation</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(r.model_selection.validation_scores).map(
                    ([count, score]) => (
                      <tr key={count}>
                        <th>
                          {count}
                          {Number(count) === r.model_selection!.selected_states
                            ? " · retenu"
                            : ""}
                        </th>
                        <td>{number(score, 4)}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
              <p className="fine-print">
                Un score plus élevé est préférable. La sélection privilégie
                moins d’états lorsque les écarts sont faibles ; ces scores ne
                mesurent pas la rentabilité.
              </p>
            </div>
          )}
        <div className="model-tables">
          <div>
            <h4>Distributions apprises</h4>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>État</th>
                    <th>Moyenne géométrique / observation</th>
                    <th>Volatilité logarithmique</th>
                    <th>Persistance</th>
                  </tr>
                </thead>
                <tbody>
                  {r.states.map((state) => (
                    <tr key={state.name}>
                      <th>{state.name}</th>
                      <td>{percent(state.mean_change)}</td>
                      <td>{percent(state.volatility ?? null)}</td>
                      <td>{percent(state.persistence)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
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
