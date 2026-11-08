import { useEffect, useMemo, useState } from "react";
import { HistoryChart } from "../../components/HistoryChart";
import { Tooltip } from "../../components/Tooltip";
import { post } from "../../lib/api";
import { date, number, percent } from "../../lib/format";

type SeriesKey = "portfolio" | "benchmark" | "optimized";
type Mode = "balanced" | "volatility" | "performance" | "drawdown";
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
];
type Metrics = {
  total_return: number;
  volatility: number;
  max_drawdown: number;
  sharpe: number | null;
};
export type PerformanceResult = {
  status: "ready";
  currency: "EUR";
  start: string;
  end: string;
  frequency: "daily" | "monthly";
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

export function PerformancePanel({ holdings }: { holdings: string }) {
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
        key={`${holdings}:${years}:${history}`}
        holdings={holdings}
        years={years}
        history={history}
      />
    </section>
  );
}

function PerformanceView({
  holdings,
  years,
  history,
}: {
  holdings: string;
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
  }, [holdings, years, history, optimize, revision]);
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
                    <small>
                      Volatilité annuelle{" "}
                      {percent(ready.metrics[s.key]!.volatility)}
                    </small>
                    <small>
                      Drawdown maximal{" "}
                      {percent(ready.metrics[s.key]!.max_drawdown)}
                    </small>
                    <small>
                      Sharpe{" "}
                      {ready.metrics[s.key]!.sharpe == null
                        ? "—"
                        : number(ready.metrics[s.key]!.sharpe!, 2)}
                    </small>
                  </div>
                ))}
            </div>
            <HistoryChart lines={lines} />
            <div className="performance-caption">
              <span>
                Base 100 · EUR · {date(ready.start)} — {date(ready.end)}
              </span>
              <Tooltip label="Méthode de comparaison">
                Simulation de vos pondérations actuelles, rééquilibrées à chaque{" "}
                {ready.frequency === "monthly"
                  ? "mois observé"
                  : "séance observée"}
                . Ce n’est pas l’historique de votre compte : les dates d’achat
                ne sont pas connues. Actions et S&P 500 à dividendes réinvestis
                ; matières premières selon leur série de prix. Hors frais et
                fiscalité. Sharpe : rendement simple moyen annualisé divisé par
                la volatilité annuelle, taux de référence fixé à 0 %. Drawdown :
                baisse maximale depuis le plus haut de chaque courbe, capital
                initial inclus.
              </Tooltip>
            </div>
          </div>
          {!!ready.cash_until?.length && (
            <p className="performance-history-note">
              Historique étendu : la part de chaque actif récent reste en
              liquidités avant sa première observation, sans rendement.
              {ready.cash_until.map((p) => (
                <span key={p.id}>
                  {" "}
                  {p.name} : jusqu’au {date(p.date)}.
                </span>
              ))}
            </p>
          )}
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
                    Mêmes actifs, poids plafonnés à 35 % à partir de trois
                    actifs, total 100 %, sans emprunt ni vente à découvert. Le
                    Sharpe utilise un taux de référence de 0 %. Chaque mode peut
                    sacrifier un autre indicateur. Les poids sont calculés et
                    évalués sur le même historique : simulation rétrospective,
                    sans prévision des performances futures.
                  </Tooltip>
                </h2>
                <p>
                  Choisissez l’objectif de votre simulation sur la période
                  affichée. Plafond de 35 % par actif dès trois actifs détenus.
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
                    <span>{m.description}</span>
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
                <p className="performance-simulation-note">
                  Simulation rétrospective sur la période affichée, hors frais.
                  Vos positions restent inchangées.
                </p>
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
                            {percent(p.recommended_weight)}
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
