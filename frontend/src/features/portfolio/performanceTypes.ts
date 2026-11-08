export type SeriesKey = "portfolio" | "benchmark" | "optimized";
export type Mode =
  "balanced" | "volatility" | "performance" | "drawdown" | "correlation";
export const modes: { key: Mode; title: string; description: string }[] = [
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
export type Metrics = {
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
export type PerformanceResponse =
  | PerformanceResult
  | {
      status: "insufficient";
      message: string;
      excluded?: { id: string; name: string; reason: string }[];
    };
export const series: { key: SeriesKey; title: string; color: string }[] = [
  { key: "portfolio", title: "Portfolio actuel", color: "#edb786" },
  { key: "benchmark", title: "S&P 500", color: "#65b9ff" },
  { key: "optimized", title: "Allocation optimisée", color: "#a4d8b6" },
];
