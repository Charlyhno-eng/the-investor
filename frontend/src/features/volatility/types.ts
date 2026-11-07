export type MapPoint = {
  return: number;
  volatility: number;
  sharpe: number | null;
};
export type NamedPoint = MapPoint & {
  id: string;
  name: string;
  kind: "asset" | "benchmark";
};
export type RiskResult = {
  status: "ready" | "pending" | "insufficient";
  message?: string;
  currency: "EUR";
  frequency: "daily" | "monthly";
  annualization: number;
  observations: number;
  start: string;
  end: string;
  points: NamedPoint[];
  frontier: MapPoint[];
  lower_frontier: MapPoint[];
  frontier_assets: string[];
  positions?: { id: string; name: string; weight: number; date: string }[];
  excluded?: { id: string; name: string; reason: string }[];
};
