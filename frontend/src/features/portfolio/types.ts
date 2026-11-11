type Position = {
  id: string;
  name: string;
  quantity: number;
  price: number;
  value: number;
  fx_date: string | null;
  weight: number;
  date: string;
};
export type PortfolioResult = {
  status: "ready";
  positions: Position[];
  total: number;
  currency: "EUR";
  excluded: { id: string; name: string; reason: string }[];
  correlation: {
    assets: { id: string; name: string }[];
    matrix: (number | null)[][];
    observations: number;
    minimum: number;
    frequency: string;
    start: string | null;
    end: string | null;
  } | null;
};
