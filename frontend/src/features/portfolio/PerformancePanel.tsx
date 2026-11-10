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
  dataRevision = "",
}: {
  holdings: string;
  lockedAssetIds?: string[];
  dataRevision?: string;
}) {
  const locks = JSON.stringify(
    lockedAssetIds.filter((id) =>
      JSON.parse(holdings).some((h: { asset_id: string }) => h.asset_id === id),
    ),
  );
  const [years, setYears] = useState(3);
  const [history, setHistory] = useState("extended");
  const [feeRate, setFeeRate] = useState(0.005);
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
        dataRevision={dataRevision}
        holdings={holdings}
        locks={locks}
        years={years}
        history={history}
        feeRate={feeRate}
        setFeeRate={setFeeRate}
      />
    </section>
  );
}

function PerformanceView({
  holdings,
  locks,
  years,
  history,
  feeRate,
  setFeeRate,
  dataRevision,
}: {
  holdings: string;
  locks: string;
  years: number;
  history: string;
  feeRate: number;
  setFeeRate: (value: number) => void;
  dataRevision: string;
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
  } = usePerformance({
    holdings,
    locks,
    years,
    history,
    feeRate,
    dataRevision,
  });
  const ready = useMemo(() => {
    if (result?.status !== "ready") return null;
    if (
      !result.mode ||
      (result.mode === mode &&
        (mode !== "equal" || result.fee_rate === feeRate))
    )
      return result;
    return {
      ...result,
      mode: null,
      allocations: {},
      unavailable: {},
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
  }, [result, mode, feeRate]);
  const calculated = ready?.mode === mode;
  const hasAllocation =
    !!ready &&
    series.some(
      (s) =>
        s.key !== "portfolio" && s.key !== "benchmark" && ready.metrics[s.key],
    );
  const lines = useMemo(
    () =>
      ready
        ? series
            .filter((s) => ready.metrics[s.key])
            .map((s) => ({
              title: s.title,
              color:
                hasAllocation &&
                (s.key === "portfolio" || s.key === "benchmark")
                  ? `${s.color}55`
                  : s.color,
              lineWidth: (hasAllocation
                ? s.key !== "portfolio" && s.key !== "benchmark"
                  ? 4
                  : 1
                : 2) as 1 | 2 | 4,
              points: ready.equity.map((p) => ({
                time: p.time,
                value: p[s.key]!,
              })),
            }))
        : [],
    [ready, hasAllocation],
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
                Les pondérations actuelles et optimisées sont simulées sur les
                mêmes dates journalières, en EUR, avec dividendes réinvestis.
                L’équipondération évolue entre deux rééquilibrages annuels et
                inclut les frais d’achat et de vente choisis, y compris l’achat
                initial, sans vente fictive à la fin. Les autres allocations
                gardent des poids constants, hors frais et fiscalité. Avant le
                début d’un historique, la part correspondante reste en
                liquidités. Les poids optimisés sont calculés et évalués sur la
                même période. Un ratio non mesurable est affiché « — ».
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
                    {mode === "equal"
                      ? " Tous les actifs ont le même poids ; déverrouillez les quantités incompatibles. Les seuils de 3 % et 35 % ne s’appliquent pas à l’équipondération."
                      : ` Les quantités verrouillées sont conservées, même en dehors
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
                    performances futures.`}
                  </Tooltip>
                </h2>
                <p>
                  Choisissez l’objectif de votre simulation sur la période
                  affichée.{" "}
                  {mode === "equal" ? (
                    "Tous les actifs sont équipondérés, avec rééquilibrage annuel."
                  ) : (
                    <>
                      Au moins {Math.ceil(ready.positions.length / 2)}{" "}
                      {ready.positions.length <= 2 ? "actif" : "actifs"} sur{" "}
                      {ready.positions.length} · 3 % minimum par position
                      retenue · plafond de 35 % dès trois actifs.{" "}
                      {JSON.parse(locks).length > 0 &&
                        `${JSON.parse(locks).length} quantité(s) verrouillée(s), prioritaires sur ces seuils.`}
                    </>
                  )}
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
                disabled={loading || calculated}
                onClick={() => {
                  setOptimize(mode);
                  retry();
                }}
              >
                {loading && optimize
                  ? "Optimisation en cours…"
                  : calculated
                    ? "Optimisation calculée"
                    : "Optimiser les poids"}
              </button>
            </div>
            {mode === "equal" && (
              <label className="portfolio-period">
                Frais par achat et par vente (%)
                <input
                  type="number"
                  aria-label="Frais par achat et par vente (%)"
                  min="0"
                  max="10"
                  step="0.1"
                  value={Number((feeRate * 100).toFixed(4))}
                  onChange={(e) => {
                    const value = Number(e.target.value);
                    if (Number.isFinite(value) && value >= 0 && value <= 10)
                      setFeeRate(value / 100);
                  }}
                />
              </label>
            )}
            {Object.entries(ready.unavailable ?? {}).map(([key, message]) => (
              <p className="fine-print" role="status" key={key}>
                {series.find((s) => s.key === key)?.title} : {message}
              </p>
            ))}
            {ready.allocations && Object.keys(ready.allocations).length > 0 && (
              <div className="table-scroll">
                <table className="positions-table performance-weights">
                  <thead>
                    <tr>
                      <th>Actif</th>
                      <th>Poids actuel</th>
                      {series
                        .filter((s) => s.key in ready.allocations!)
                        .map((s) => (
                          <th key={s.key}>{s.title}</th>
                        ))}
                    </tr>
                  </thead>
                  <tbody>
                    {ready.positions.map((p, i) => (
                      <tr key={p.id}>
                        <th>{p.name}</th>
                        <td>{percent(p.weight)}</td>
                        {series
                          .filter((s) => s.key in ready.allocations!)
                          .map(({ key }) => {
                            const weights =
                              ready.allocations![
                                key as keyof typeof ready.allocations
                              ]!;
                            return (
                              <td key={key} className="recommended-weight">
                                <span className="allocation-recommendation">
                                  {percent(weights[i])}
                                  <AllocationSignal
                                    current={p.weight}
                                    recommended={weights[i]}
                                  />
                                </span>
                              </td>
                            );
                          })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
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

                <p className="fine-print">
                  Deux chevrons : écart d’au moins 5 points de pourcentage.
                  Quantités indicatives calculées à valeur totale constante, aux
                  derniers cours de l’onglet Positions ; fractions d’actif
                  incluses. Une pondération nulle est possible.
                </p>
              </>
            )}
            {hasAllocation && (
              <>
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
                {mode === "beta_sharpe" && (
                  <p className="fine-print">
                    Deux chevrons : écart d’au moins 5 points de pourcentage par
                    rapport au poids actuel.
                  </p>
                )}
              </>
            )}
          </div>
        </>
      )}
    </>
  );
}
