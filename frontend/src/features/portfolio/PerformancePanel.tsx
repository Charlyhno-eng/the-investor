import { useEffect, useMemo, useState } from "react";
import { Icon } from "../../components/Icon";
import { HistoryChart } from "../../components/HistoryChart";
import { Tooltip } from "../../components/Tooltip";
import { post } from "../../lib/api";
import { date, number, percent } from "../../lib/format";

type SeriesKey = "portfolio" | "benchmark" | "optimized";
type Mode =
  "balanced" | "volatility" | "performance" | "drawdown" | "correlation";
const modes: { key: Mode; title: string; description: string }[] = [
  {
    key: "balanced",
    title: "Équilibre",
    description: "Meilleur ratio rendement / volatilité (Sharpe).",
  },
  {
    key: "volatility",
    title: "Volatilité minimale",
    description: "Réduire au maximum les variations du portefeuille.",
  },
  {
    key: "performance",
    title: "Performance maximale",
    description: "Maximiser le rendement cumulé historique.",
  },
  {
    key: "drawdown",
    title: "Drawdown minimal",
    description: "Limiter la plus forte baisse depuis un sommet.",
  },
  {
    key: "correlation",
    title: "Corrélations minimales",
    description:
      "Minimiser le risque des rendements standardisés pour favoriser des corrélations faibles ou négatives.",
  },
];
type Metrics = {
  alpha: number | null;
  beta: number | null;
  total_return: number;
  cagr: number;
  sortino: number | null;
  calmar: number | null;
  volatility: number;
  max_drawdown: number;
  sharpe: number | null;
};
export type PerformanceResult = {
  status: "ready";
  currency: "EUR";
  start: string;
  end: string;
  frequency: "daily";
  observations: number;
  mode?: Mode | null;
  history?: "common" | "extended";
  requested_start?: string;
  cash_until?: { id: string; name: string; date: string }[];
  equity: {
    time: string;
    portfolio: number;
    benchmark: number;
    optimized?: number;
  }[];
  metrics: { portfolio: Metrics; benchmark: Metrics; optimized?: Metrics };
  positions: {
    id: string;
    name: string;
    quantity: number;
    weight: number;
    date: string;
    recommended_quantity: number | null;
    recommended_weight: number | null;
  }[];
};
type Result =
  | PerformanceResult
  | {
      status: "insufficient";
      message: string;
      excluded?: { id: string; name: string; reason: string }[];
    };
const series: { key: SeriesKey; title: string; color: string }[] = [
  { key: "portfolio", title: "Portfolio actuel", color: "#edb786" },
  { key: "benchmark", title: "S&P 500", color: "#65b9ff" },
  { key: "optimized", title: "Allocation optimisée", color: "#a4d8b6" },
];

const metricRows: {
  key: Exclude<keyof Metrics, "total_return" | "alpha" | "beta">;
  label: string;
  lower?: boolean;
  ratio?: boolean;
}[] = [
  { key: "cagr", label: "CAGR" },
  { key: "volatility", label: "Volatilité annualisée", lower: true },
  { key: "max_drawdown", label: "Drawdown maximal", lower: true },
  { key: "sharpe", label: "Ratio de Sharpe", ratio: true },
  { key: "sortino", label: "Ratio de Sortino", ratio: true },
  { key: "calmar", label: "Ratio de Calmar", ratio: true },
];

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
  const [result, setResult] = useState<Result | null>(null);
  const [mode, setMode] = useState<Mode>("balanced");
  const [optimize, setOptimize] = useState<Mode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    setLoading(true);
    setError("");
    async function load() {
      try {
        const data = await post<Result | { status: "pending" }>(
          optimize ? "/portfolio/optimize" : "/portfolio/performance",
          {
            holdings: JSON.parse(holdings),
            locked_asset_ids: JSON.parse(locks),
            years,
            history,
            mode: optimize ?? "balanced",
          },
          controller.signal,
        );
        if (controller.signal.aborted) return;
        if (data.status === "pending") {
          if (++attempts >= 90)
            throw new Error(
              "Les données prennent plus de temps que prévu. Réessayez dans un instant.",
            );
          timer = setTimeout(load, 2000);
        } else {
          setResult(data);
          setLoading(false);
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          setError((e as Error).message);
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [holdings, locks, years, history, optimize, revision]);
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
          <button
            className="secondary-button"
            onClick={() => setRevision((v) => v + 1)}
          >
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
            <details className="performance-metrics-panel" open>
              <summary>Indicateurs de performance</summary>
              <div className="table-scroll">
                <table
                  className="positions-table performance-metrics"
                  aria-label="Indicateurs de comparaison"
                >
                  <thead>
                    <tr>
                      <th scope="col">Indicateur</th>
                      <th scope="col">S&amp;P 500</th>
                      <th scope="col">Ma stratégie</th>
                      <th scope="col">Ma stratégie optimisée</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metricRows.map((metric) => (
                      <tr key={metric.key}>
                        <th scope="row">
                          {metric.label}
                          <small>
                            {metric.lower ? "Plus faible" : "Plus élevé"}
                          </small>
                        </th>
                        {(["benchmark", "portfolio", "optimized"] as const).map(
                          (key) => {
                            const raw = ready.metrics[key]?.[metric.key];
                            const normalize = (
                              raw: number | null | undefined,
                            ) =>
                              raw == null
                                ? null
                                : metric.key === "max_drawdown"
                                  ? Math.abs(raw)
                                  : raw;
                            const value = normalize(raw);
                            const compare = (
                              reference: number | null,
                              name: string,
                            ) => {
                              const delta =
                                value == null || reference == null
                                  ? null
                                  : (value - reference) *
                                    (metric.lower ? -1 : 1);
                              const state =
                                delta == null
                                  ? "unavailable"
                                  : Math.abs(delta) < 1e-10
                                    ? "equal"
                                    : delta > 0
                                      ? "better"
                                      : "worse";
                              const status =
                                delta == null
                                  ? `Comparaison indisponible avec ${name}`
                                  : state === "equal"
                                    ? `Équivalent ${name === "le S&P 500" ? "au S&P 500" : `à ${name}`}`
                                    : state === "better"
                                      ? `Meilleur que ${name}`
                                      : `Moins bon que ${name}`;
                              return { state, status };
                            };
                            const benchmark = compare(
                              normalize(ready.metrics.benchmark[metric.key]),
                              "le S&P 500",
                            );
                            const current = compare(
                              normalize(ready.metrics.portfolio[metric.key]),
                              "la stratégie de base",
                            );
                            const markers =
                              key === "benchmark"
                                ? [
                                    {
                                      state: "reference",
                                      status: "Référence S&P 500",
                                    },
                                  ]
                                : key === "optimized"
                                  ? [benchmark, current]
                                  : [benchmark];
                            const status = markers
                              .map((m) => m.status)
                              .join(" · ");
                            return (
                              <td
                                key={key}
                                data-comparison={
                                  key === "benchmark"
                                    ? "reference"
                                    : benchmark.state
                                }
                                title={status}
                              >
                                <span className="metric-value">
                                  <span className="metric-signals">
                                    {markers.map((marker, i) => (
                                      <i
                                        key={i}
                                        data-comparison={marker.state}
                                        role="img"
                                        aria-label={marker.status}
                                        title={marker.status}
                                      />
                                    ))}
                                  </span>
                                  {value == null
                                    ? "—"
                                    : metric.ratio
                                      ? number(value, 2)
                                      : percent(value)}
                                </span>
                              </td>
                            );
                          },
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="metric-signals-legend">
                Allocation optimisée : premier trait comparé au S&amp;P 500,
                second à la stratégie de base. Vert : meilleur · Rouge : moins
                bon · Gris : égal ou indisponible.
              </p>
            </details>
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
                  setRevision((v) => v + 1);
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

function AllocationSignal({
  current,
  recommended,
}: {
  current: number;
  recommended: number | null;
}) {
  if (recommended == null) return null;
  const delta = recommended - current;
  // Ignore numerical solver noise, retaining changes below the display precision.
  const unchanged = Math.abs(delta) < 1e-8;
  const exit = !unchanged && recommended <= 1e-8;
  const strong = Math.abs(delta) >= 0.05 - 1e-8;
  const label = unchanged
    ? "Conserver la position"
    : exit
      ? "Sortir de la position"
      : delta > 0
        ? strong
          ? "Renforcer fortement la position"
          : "Renforcer la position"
        : strong
          ? "Alléger fortement la position"
          : "Alléger la position";
  const icon = unchanged
    ? "equal"
    : exit
      ? "close"
      : delta > 0
        ? strong
          ? "chevrons-up"
          : "chevron-up"
        : strong
          ? "chevrons-down"
          : "chevron-down";
  return (
    <span
      className={`allocation-signal ${unchanged ? "hold" : delta > 0 ? "increase" : "decrease"}`}
      role="img"
      aria-label={label}
      title={label}
    >
      <Icon name={icon} size={18} />
    </span>
  );
}
