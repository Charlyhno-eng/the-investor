import { number, percent } from "../../lib/format";
import { Tooltip } from "../../components/Tooltip";
import {
  series,
  type Metrics,
  type PerformanceResult,
} from "./performanceTypes";

const metricRows: {
  key: Exclude<keyof Metrics, "total_return" | "alpha">;
  label: string;
  explanation: string;
  lower?: boolean;
  ratio?: boolean;
}[] = [
  {
    key: "cagr",
    label: "CAGR",
    explanation:
      "Le rendement moyen par an, en tenant compte des gains réinvestis.",
  },
  {
    key: "volatility",
    label: "Volatilité annualisée",
    lower: true,
    explanation:
      "L’ampleur des variations du portefeuille, à la hausse comme à la baisse. Une valeur élevée indique un parcours plus mouvementé.",
  },
  {
    key: "downside_volatility",
    label: "Volatilité à la baisse",
    lower: true,
    explanation:
      "L’ampleur des rendements négatifs, ramenée sur un an. Les hausses ne comptent pas comme risque. Plus elle est faible, plus les baisses sont limitées.",
  },
  {
    key: "max_drawdown",
    label: "Drawdown maximal",
    lower: true,
    explanation:
      "La plus forte baisse entre un sommet et le creux qui suit sur la période affichée.",
  },
  {
    key: "sharpe",
    label: "Ratio de Sharpe",
    ratio: true,
    explanation:
      "Le rendement obtenu par rapport aux variations du portefeuille, à la hausse comme à la baisse. Plus il est élevé, mieux le risque est rémunéré. Le taux de référence est fixé à 0 %.",
  },
  {
    key: "sortino",
    label: "Ratio de Sortino",
    ratio: true,
    explanation:
      "Comme le Sharpe, mais seules les variations à la baisse comptent comme risque. La volatilité à la hausse n’est pas pénalisée. Plus il est élevé, mieux c’est.",
  },
  {
    key: "calmar",
    label: "Ratio de Calmar",
    ratio: true,
    explanation:
      "Le rendement annualisé rapporté à la plus forte baisse historique, le drawdown maximal. Plus il est élevé, mieux c’est.",
  },
  {
    key: "beta",
    label: "Bêta",
    ratio: true,
    explanation:
      "La sensibilité aux mouvements du S&P 500, dont le bêta vaut 1. Un bêta de 0,5 indique des mouvements en moyenne deux fois moins marqués face au marché. Ce n’est pas une mesure de toutes les variations du portefeuille.",
  },
];

export function PerformanceMetrics({
  result: ready,
}: {
  result: PerformanceResult;
}) {
  const columns = series.filter(
    (s) => s.key !== "optimized" && ready.metrics[s.key],
  );
  if (!columns.some((s) => s.key.startsWith("beta_")))
    columns.push(series.find((s) => s.key === "optimized")!);
  columns.sort((a, b) =>
    a.key === "benchmark" ? -1 : b.key === "benchmark" ? 1 : 0,
  );
  return (
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
              {columns.map((s) => (
                <th scope="col" key={s.key}>
                  {s.key === "portfolio"
                    ? "Ma stratégie"
                    : s.key === "optimized"
                      ? "Ma stratégie optimisée"
                      : s.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metricRows.map((metric) => (
              <tr key={metric.key}>
                <th scope="row">
                  {metric.label}{" "}
                  <Tooltip label={metric.label} floating question>
                    {metric.explanation}
                  </Tooltip>
                  <small>
                    {metric.key === "beta"
                      ? "Sensibilité au marché"
                      : metric.lower
                        ? "Plus faible"
                        : "Plus élevé"}
                  </small>
                </th>
                {columns.map(({ key }) => {
                  const raw = ready.metrics[key]?.[metric.key];
                  const normalize = (raw: number | null | undefined) =>
                    raw == null
                      ? null
                      : metric.key === "max_drawdown"
                        ? Math.abs(raw)
                        : raw;
                  const value = normalize(raw);
                  const compare = (reference: number | null, name: string) => {
                    const delta =
                      value == null || reference == null
                        ? null
                        : (value - reference) * (metric.lower ? -1 : 1);
                    const state =
                      delta == null || metric.key === "beta"
                        ? "unavailable"
                        : Math.abs(delta) < 1e-10
                          ? "equal"
                          : delta > 0
                            ? "better"
                            : "worse";
                    const status =
                      metric.key === "beta"
                        ? "Sensibilité au S&P 500 ; un bêta plus élevé n’est pas nécessairement meilleur"
                        : delta == null
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
                      : key === "optimized" || key.startsWith("beta_")
                        ? [benchmark, current]
                        : [benchmark];
                  const status = markers.map((m) => m.status).join(" · ");
                  return (
                    <td
                      key={key}
                      data-comparison={
                        key === "benchmark" ? "reference" : benchmark.state
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
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="metric-signals-legend">
        Allocation optimisée : premier trait comparé au S&amp;P 500, second à la
        stratégie de base. Vert : meilleur · Rouge : moins bon · Gris : égal ou
        indisponible.
      </p>
    </details>
  );
}
