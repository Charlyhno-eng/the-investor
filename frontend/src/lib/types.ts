export type Category =
  "commodity" | "bond" | "stock" | "crypto" | "etf" | "currency";
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
  sector?: string | null;
  is_dividend?: boolean;
  benchmark_years: number | null;
  year_average_yield: number | null;
  year_yield_samples: number;
  bond_ranking_date: string | null;
};
export type Point = { time: string; value: number };
export type ComparisonEquity = {
  time: string;
  strategy: number;
  benchmark: number;
}[];
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
