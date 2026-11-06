export type Category = "commodity" | "bond" | "stock" | "crypto";
export type Asset = {
  id: string;
  name: string;
  category: Category;
  metric: string;
  unit: string;
  frequency: string;
  source: string;
  source_url: string;
  points: number;
  first_date: string;
  last_date: string;
  last_value: number;
  country_code: string | null;
  country?: string | null;
  benchmark_years: number | null;
  year_average_yield: number | null;
  year_yield_samples: number;
  bond_ranking_date: string | null;
};
export type Point = { time: string; value: number };
export type Periods = {
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
};
export type Parameters = Periods & {
  fee_bps: number;
};
export type Metrics = Record<string, number | null>;
export type Analysis = {
  id: string;
  mode: "backtest" | "regimes";
  warnings: string[];
  train_points: number;
  test_points: number;
  periods_per_year: number;
  actual_train: string[];
  actual_test: string[];
  parameters: Parameters;
  equity: { time: string; strategy: number; benchmark: number }[];
  strategy_metrics: Metrics | null;
  benchmark_metrics: Metrics | null;
  positions: { time: string; position: 0 | 1 }[];
  regimes: { time: string; state: string; probabilities: number[] }[];
  states: { name: string; mean_change: number; persistence: number }[];
  transition_matrix: number[][];
  diagnostics?: {
    exit_reachable: boolean;
    negative_states: number;
    negative_dominant_observations: number;
    negative_dominant_while_held: number;
    negative_dominant_without_exit_while_held: number;
    exit_signal_observations: number;
    net_excess_return: number;
    nearly_always_invested: boolean;
    nearly_always_cash: boolean;
  };
  trades: {
    time: string;
    side: string;
    probability: number | null;
    reason?: string;
  }[];
  exposure: number | null;
};
export type ImportJob = {
  id: number | null;
  status: string;
  asset_id?: string;
  error?: string;
};

export type DividendEvent = {
  time: string;
  amount: number;
  yield_percent: number | null;
};
export type DividendHistory = {
  currency: string;
  coverage: {
    first_date: string;
    last_date: string;
    updated_at: string;
  } | null;
  events: DividendEvent[];
};
