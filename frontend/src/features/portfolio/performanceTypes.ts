type BetaKey = "beta_03" | "beta_04" | "beta_05" | "beta_06" | "beta_07";
export type SeriesKey = "portfolio" | "benchmark" | "optimized" | BetaKey;
type Mode = "equal" | "sortino" | "downside" | "drawdown" | "beta_sharpe";
export type Metrics = {
  alpha: number | null;
  beta: number | null;
  total_return: number;
  cagr: number | null;
  sortino: number | null;
  calmar: number | null;
  volatility: number | null;
  downside_volatility?: number;
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
  fee_rate?: number | null;
  cash_until?: { id: string; name: string; date: string }[];
  equity: {
    time: string;
    portfolio: number;
    benchmark: number;
    optimized?: number;
    beta_03?: number;
    beta_04?: number;
    beta_05?: number;
    beta_06?: number;
    beta_07?: number;
  }[];
  metrics: { portfolio: Metrics; benchmark: Metrics } & Partial<
    Record<SeriesKey, Metrics>
  >;
  allocations?: Partial<Record<BetaKey, number[]>>;
  unavailable?: Partial<Record<BetaKey, string>>;
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
export const series: { key: SeriesKey; title: string; color: string }[] = [
  { key: "portfolio", title: "Portfolio actuel", color: "#edb786" },
  { key: "benchmark", title: "S&P 500", color: "#65b9ff" },
  { key: "optimized", title: "Allocation optimisée", color: "#a4d8b6" },
  { key: "beta_03", title: "Sharpe · bêta 0,3", color: "#f58caf" },
  { key: "beta_04", title: "Sharpe · bêta 0,4", color: "#62d4cf" },
  { key: "beta_05", title: "Sharpe · bêta 0,5", color: "#a4d8b6" },
  { key: "beta_06", title: "Sharpe · bêta 0,6", color: "#d7b5fa" },
  { key: "beta_07", title: "Sharpe · bêta 0,7", color: "#f3d477" },
];
