import { usePerformance } from "./usePerformance";
import { PerformanceMetrics } from "./PerformanceMetrics";
import { AllocationSignal } from "./AllocationSignal";
import { modes, series, type PerformanceResult } from "./performanceTypes";
import { useMemo, useState } from "react";
import { HistoryChart } from "../../components/HistoryChart";
import { Tooltip } from "../../components/Tooltip";
import { date, number, percent } from "../../lib/format";

export function PerformancePanel({
  holdings,
  lockedAssetIds = [],
}: {
  holdings: string;
  lockedAssetIds?: string[];
}) {
  const locks = JSON.stringify(
    lockedAssetIds.filter((id) =>
      JSON.parse(holdings).some((h: { asset_id: string }) => h.asset_id === id),
    ),
  );
  const [years, setYears] = useState(3);
  const [history, setHistory] = useState("extended");
  return (
    <section
      className="portfolio-content portfolio-performance"
      aria-label="Performance du Portfolio"
    >
      <div className="portfolio-section-heading">
        <div>
          <h2>Comparaison et optimisation du portefeuille</h2>
          <p>
            Comparez votre allocation actuelle au marché et simulez une nouvelle
            répartition.
          </p>
        </div>
        <div className="performance-period-controls">
          <label className="portfolio-period">
            Historique
            <select
              aria-label="Historique"
              value={history}
              onChange={(e) => setHistory(e.target.value)}
            >
              <option value="extended">Étendu · réserve en liquidités</option>
              <option value="common">Dates communes uniquement</option>
            </select>
          </label>
          <label className="portfolio-period">
            Période
            <select
              aria-label="Période"
              value={years}
              onChange={(e) => setYears(Number(e.target.value))}
            >
              {[1, 3, 5, 10].map((y) => (
                <option key={y} value={y}>
                  {y} an{y > 1 ? "s" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      <PerformanceView
        key={`${holdings}:${years}:${history}:${locks}`}
        holdings={holdings}
        locks={locks}
        years={years}
        history={history}
      />
    </section>
  );
}

function PerformanceView({
  holdings,
  locks,
  years,
  history,
}: {
  holdings: string;
  locks: string;
  years: number;
  history: string;
}) {
  const {
    result,
    mode,
    setMode,
    optimize,
    setOptimize,
    loading,
    error,
    retry,
  } = usePerformance({ holdings, locks, years, history });
  const ready = useMemo(() => {
    if (result?.status !== "ready") return null;
    if (!result.mode || result.mode === mode) return result;
    return {
      ...result,
      metrics: {
        portfolio: result.metrics.portfolio,
        benchmark: result.metrics.benchmark,
      },
      equity: result.equity.map(({ time, portfolio, benchmark }) => ({
        time,
        portfolio,
        benchmark,
      })),
    } as PerformanceResult;
  }, [result, mode]);
  const lines = useMemo(
    () =>
      ready
        ? series
            .filter((s) => ready.metrics[s.key])
            .map((s) => ({
              title: s.title,
              color:
                ready.metrics.optimized && s.key !== "optimized"
                  ? `${s.color}55`
                  : s.color,
              lineWidth: (ready.metrics.optimized
                ? s.key === "optimized"
                  ? 4
                  : 1
                : 2) as 1 | 2 | 4,
              points: ready.equity.map((p) => ({
                time: p.time,
                value: p[s.key]!,
              })),
            }))
        : [],
    [ready],
  );
  return (
    <>
      {error && (
        <p className="error" role="alert">
          {error}{" "}
          <button className="secondary-button" onClick={() => retry()}>
            Réessayer
          </button>
        </p>
      )}
      {loading && (
        <p className="performance-loading" role="status">
          <span className="spinner" />
          {optimize
            ? "Calcul de l’allocation optimale…"
            : "Chargement des performances communes…"}
        </p>
      )}
      {result?.status === "insufficient" && (
        <div className="portfolio-empty" role="status">
          {result.message}
          {result.excluded?.map((p) => (
            <p key={p.id}>
              {p.name} : {p.reason}
            </p>
          ))}
        </div>
      )}
      {ready && (
        <>
          <div className="performance-card">
            <div className="performance-series-summary">
              {series
                .filter((s) => ready.metrics[s.key])
                .map((s) => (
                  <div key={s.key} style={{ color: s.color }}>
                    <span>
                      <i style={{ background: s.color }} />
                      {s.title}
                    </span>
                    <strong>
                      {percent(ready.metrics[s.key]!.total_return, true)}
                    </strong>
                  </div>
                ))}
            </div>
            <PerformanceMetrics result={ready} />
            <HistoryChart lines={lines} />
            <div className="performance-caption">
              <span>
                Base 100 · EUR · Données journalières ·{" "}
                {number(ready.observations, 0)} séances · Dividendes réinvestis
                · {date(ready.start)} — {date(ready.end)}
              </span>
              <Tooltip label="Méthode de comparaison">
                Simulation de vos pondérations actuelles, rééquilibrées à chaque
                séance observée. Les courbes et les cinq optimisations utilisent
                toutes les observations journalières communes, sans regroupement
                mensuel. Ce n’est pas l’historique de votre compte : les dates
                d’achat ne sont pas connues. Actions et S&P 500 à dividendes
                réinvestis ; matières premières selon leur série de prix. Hors
                frais et fiscalité. Sharpe : rendement simple moyen annualisé
                divisé par la volatilité annuelle, taux de référence fixé à 0 %.
                Drawdown : baisse maximale depuis le plus haut de chaque courbe,
                capital initial inclus, affiché en amplitude positive dans le
                tableau. CAGR : croissance composée annualisée sur la durée
                calendaire réelle. Sortino : rendement moyen annualisé rapporté
                à la déviation des rendements sous 0 %, calculée sur toutes les
                observations. Calmar : CAGR divisé par l’amplitude du drawdown
                maximal. Annualisation : 252 séances. Un ratio sans dénominateur
                mesurable est affiché « — ».
              </Tooltip>
            </div>
          </div>
          {history === "common" &&
            ready.requested_start &&
            Date.parse(ready.start) - Date.parse(ready.requested_start) >
              14 * 86400000 && (
              <p className="performance-history-note">
                La période commune commence le {date(ready.start)} : certains
                actifs ont un historique plus court. Choisissez l’historique
                étendu pour afficher les dates antérieures.
              </p>
            )}
          <div className="performance-optimization">
            <div className="portfolio-section-heading">
              <div>
                <h2>
                  Optimiser la répartition{" "}
                  <Tooltip label="Méthode d’optimisation">
                    {modes.find((m) => m.key === mode)?.description}
                    Les quantités verrouillées sont conservées, même en dehors
                    des seuils de pondération. Les seuils s’appliquent aux
                    positions libres. Des contraintes incompatibles empêchent le
                    calcul. Au moins la moitié des actifs détenus, arrondie au
                    supérieur. Chaque position retenue pèse au moins 3 %, avec
                    un plafond de 35 % dès trois actifs disponibles. Total 100
                    %, sans emprunt ni vente à découvert. La sélection des
                    positions est approchée au-delà de huit actifs ; les
                    contraintes restent strictes. Le Sharpe utilise un taux de
                    référence de 0 %. Chaque mode peut sacrifier un autre
                    indicateur. Les poids sont calculés et évalués sur le même
                    historique : simulation rétrospective, sans prévision des
                    performances futures.
                  </Tooltip>
                </h2>
                <p>
                  Choisissez l’objectif de votre simulation sur la période
                  affichée. Au moins {Math.ceil(ready.positions.length / 2)}{" "}
                  {ready.positions.length <= 2 ? "actif" : "actifs"} sur{" "}
                  {ready.positions.length} · 3 % minimum par position retenue ·
                  plafond de 35 % dès trois actifs.{" "}
                  {JSON.parse(locks).length > 0 &&
                    `${JSON.parse(locks).length} quantité(s) verrouillée(s), prioritaires sur ces seuils.`}
                </p>
              </div>
            </div>
            <div className="optimization-actions">
              <fieldset className="optimization-modes">
                <legend className="sr-only">Objectif d’optimisation</legend>
                {modes.map((m) => (
                  <label
                    key={m.key}
                    className={mode === m.key ? "selected" : ""}
                    title={m.description}
                  >
                    <input
                      type="radio"
                      name="optimization-mode"
                      value={m.key}
                      checked={mode === m.key}
                      onChange={() => {
                        setMode(m.key);
                        setOptimize(null);
                      }}
                    />
                    <strong>{m.title}</strong>
                  </label>
                ))}
              </fieldset>
              <button
                className="primary-button"
                disabled={loading || !!ready.metrics.optimized}
                onClick={() => {
                  setOptimize(mode);
                  retry();
                }}
              >
                {loading && optimize
                  ? "Optimisation en cours…"
                  : ready.metrics.optimized
                    ? "Optimisation calculée"
                    : "Optimiser les poids"}
              </button>
            </div>
            {ready.metrics.optimized && (
              <>
                <div className="table-scroll">
                  <table className="positions-table performance-weights">
                    <thead>
                      <tr>
                        <th>Actif</th>
                        <th>Quantité actuelle</th>
                        <th>Poids actuel</th>
                        <th>Poids recommandé</th>
                        <th>Quantité indicative</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ready.positions.map((p) => (
                        <tr key={p.id}>
                          <th>{p.name}</th>
                          <td>{number(p.quantity, 8)}</td>
                          <td>{percent(p.weight)}</td>
                          <td className="recommended-weight">
                            <span className="allocation-recommendation">
                              {percent(p.recommended_weight)}
                              <AllocationSignal
                                current={p.weight}
                                recommended={p.recommended_weight}
                              />
                            </span>
                          </td>
                          <td title={`Au cours du ${date(p.date)}`}>
                            {p.recommended_quantity == null
                              ? "—"
                              : number(p.recommended_quantity, 8)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div
                  className="allocation-legend"
                  aria-label="Légende des recommandations"
                >
                  <span>
                    <AllocationSignal current={0.1} recommended={0.12} />{" "}
                    Renforcer
                  </span>
                  <span>
                    <AllocationSignal current={0.1} recommended={0.2} />{" "}
                    Renforcer fortement
                  </span>
                  <span>
                    <AllocationSignal current={0.12} recommended={0.1} />{" "}
                    Alléger
                  </span>
                  <span>
                    <AllocationSignal current={0.2} recommended={0.1} /> Alléger
                    fortement
                  </span>
                  <span>
                    <AllocationSignal current={0.1} recommended={0} /> Sortir
                  </span>
                  <span>
                    <AllocationSignal current={0.1} recommended={0.1} />{" "}
                    Conserver
                  </span>
                </div>
                <p className="fine-print">
                  Deux chevrons : écart d’au moins 5 points de pourcentage.
                  Quantités indicatives calculées à valeur totale constante, aux
                  derniers cours de l’onglet Positions ; fractions d’actif
                  incluses. Une pondération nulle est possible.
                </p>
              </>
            )}
          </div>
        </>
      )}
    </>
  );
}
