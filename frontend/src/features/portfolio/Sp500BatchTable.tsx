import { number, percent } from "../../lib/format";

type Row = {
  valid: number;
  benchmark_wins: number;
  strategy_wins: number;
  ties: number;
  benchmark_mean: number | null;
  strategy_mean: number | null;
  lower_is_better: boolean;
};
export type BatchResult = {
  status: "running" | "complete";
  completed: number;
  joint_wins?: number;
  total: number;
  seed: number;
  metrics: Record<string, Row>;
};
const metrics = [
  ["total_return", "Rendement net", "percent"],
  ["cagr", "CAGR net", "percent"],
  ["max_drawdown", "Drawdown maximal", "percent"],
  ["volatility", "Volatilité annualisée", "percent"],
  ["downside_volatility", "Volatilité baissière", "percent"],
  ["sharpe", "Sharpe · taux de référence 0 %", "number"],
  ["sortino", "Sortino", "number"],
  ["calmar", "Calmar", "number"],
  ["worst_quarter", "Pire trimestre complet", "percent"],
  ["positive_quarters", "Trimestres complets positifs", "number"],
  ["annual_turnover", "Rotation annuelle hors entrée", "percent"],
  ["cost_eur", "Frais payés (€)", "number"],
] as const;

export function Sp500BatchTable({
  result,
  running,
  strategyName = "Régression",
}: {
  result: BatchResult;
  running: boolean;
  strategyName?: string;
}) {
  return (
    <>
      <p role="status" aria-live="polite">
        {result.completed} / {result.total} parcours calculés
        {result.status === "complete"
          ? " · Terminé"
          : running
            ? " · En cours"
            : " · Arrêté — résultats partiels"}{" "}
        · Graine du lot : {result.seed}
      </p>
      {result.joint_wins !== undefined && (
        <p>
          Rendement supérieur et drawdown moins profond que PSP5 :{" "}
          {result.joint_wins} / {result.completed} parcours.
        </p>
      )}
      <progress
        className="sp500-batch-progress"
        value={result.completed}
        max={result.total}
        aria-label="Progression des simulations"
      />
      <div className="table-scroll">
        <table
          className="positions-table performance-metrics validation-metrics sp500-batch-metrics"
          aria-label="Comparaison des simulations multiples"
        >
          <thead>
            <tr>
              <th scope="col">Indicateur</th>
              <th scope="col">Buy & Hold · moyenne</th>
              <th scope="col">{strategyName} · moyenne</th>
              <th scope="col">Buy & Hold gagne</th>
              <th scope="col">{strategyName} gagne</th>
              <th scope="col">Égalités</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map(([key, label, format]) => {
              const row = result.metrics[key];
              const display = (value: number | null) =>
                value == null
                  ? "—"
                  : format === "percent"
                    ? percent(value)
                    : number(value, 2);
              const winRate = (wins: number) =>
                row?.valid ? percent(wins / row.valid) : "—";
              return (
                <tr key={key}>
                  <th scope="row">
                    {label}
                    <small>
                      {row?.lower_is_better ? "Plus faible" : "Plus élevé"}
                    </small>
                  </th>
                  <td>{display(row?.benchmark_mean ?? null)}</td>
                  <td>{display(row?.strategy_mean ?? null)}</td>
                  <td
                    data-best={
                      row?.benchmark_wins > row?.strategy_wins || undefined
                    }
                  >
                    {winRate(row?.benchmark_wins ?? 0)}
                  </td>
                  <td
                    data-best={
                      row?.strategy_wins > row?.benchmark_wins || undefined
                    }
                  >
                    {winRate(row?.strategy_wins ?? 0)}
                  </td>
                  <td>{winRate(row?.ties ?? 0)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
