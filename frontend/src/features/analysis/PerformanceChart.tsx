import { HistoryChart } from "../../components/HistoryChart";
import type { Analysis } from "../../lib/types";

export function PerformanceChart({ equity }: { equity: Analysis["equity"] }) {
  if (!equity.length) return null;
  return (
    <section
      aria-label="Comparaison des performances"
      className="performance-chart"
    >
      <div className="equity-heading">
        <span className="field-label">Capital · base 100 · frais inclus</span>
        <div className="chart-legend">
          <span>
            <i className="strategy-dot" />
            Stratégie HMM
          </span>
          <span>
            <i className="market-dot" />
            Actif · achat et conservation
          </span>
        </div>
      </div>
      <HistoryChart comparison={equity} compact />
    </section>
  );
}
