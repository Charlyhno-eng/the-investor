import { number, percent } from "../../lib/format";
import type { Metrics, PerformanceResult } from "./performanceTypes";

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

export function PerformanceMetrics({
  result: ready,
}: {
  result: PerformanceResult;
}) {
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
                  <small>{metric.lower ? "Plus faible" : "Plus élevé"}</small>
                </th>
                {(["benchmark", "portfolio", "optimized"] as const).map(
                  (key) => {
                    const raw = ready.metrics[key]?.[metric.key];
                    const normalize = (raw: number | null | undefined) =>
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
                          : (value - reference) * (metric.lower ? -1 : 1);
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
                  },
                )}
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
