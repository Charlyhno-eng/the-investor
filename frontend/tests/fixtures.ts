import type { Page } from "@playwright/test";
import type { Analysis, Asset, Parameters } from "../src/lib/types";

const points = Array.from({ length: 800 }, (_, i) => ({
  time: new Date(Date.UTC(2020, 0, 1 + i)).toISOString().slice(0, 10),
  value: 100 * Math.exp(i * 0.0005 + Math.sin(i / 20) * 0.05),
}));
export const stock: Asset = {
  id: "yf-test",
  name: "Action test",
  category: "stock",
  metric: "price",
  unit: "USD",
  frequency: "daily",
  source: "yahoo",
  source_url: "https://example.com",
  points: points.length,
  first_date: points[0].time,
  last_date: points.at(-1)!.time,
  last_value: points.at(-1)!.value,
  country_code: null,
  benchmark_years: null,
  year_average_yield: null,
  year_yield_samples: 0,
  bond_ranking_date: null,
};

function result(parameters: Parameters): Analysis {
  const test = points.filter(
    (p) => p.time >= parameters.test_start && p.time <= parameters.test_end,
  );
  return {
    id: "test-analysis",
    mode: "backtest",
    parameters,
    warnings: [],
    train_points: 500,
    test_points: test.length,
    periods_per_year: 252,
    actual_train: [parameters.train_start, parameters.train_end],
    actual_test: [test[0].time, test.at(-1)!.time],
    equity: test.map((p, i) => ({
      time: p.time,
      strategy: 100 + i * 0.1,
      benchmark: 100 + i * 0.05,
    })),
    strategy_metrics: {
      total_return: (test.length - 1) * 0.001,
      annualized_return:
        (1 + (test.length - 1) * 0.001) ** (252 / test.length) - 1,
    },
    benchmark_metrics: {
      total_return: (test.length - 1) * 0.0005,
      annualized_return:
        (1 + (test.length - 1) * 0.0005) ** (252 / test.length) - 1,
    },
    positions: [],
    regimes: [],
    exposure: 0.5,
    trades: [],
    states: [
      { name: "Neutre / baisse", mean_change: -0.01, persistence: 0.9 },
      { name: "Hausse", mean_change: 0.01, persistence: 0.9 },
    ],
    transition_matrix: [
      [0.9, 0.1],
      [0.1, 0.9],
    ],
  };
}

export async function mockApi(page: Page) {
  const analysisRequests: Parameters[] = [];
  const historyRequests: string[] = [];
  const comparisonRequests: string[] = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/assets") {
      await route.fulfill({
        json: [
          stock,
          { ...stock, id: "wb-gold", name: "Or", category: "commodity" },
          {
            ...stock,
            id: "bond-fr",
            name: "France",
            category: "bond",
            metric: "yield",
          },
          { ...stock, id: "yf-btc-usd", name: "Bitcoin", category: "crypto" },
        ],
      });
    } else if (path.endsWith("/history")) {
      historyRequests.push(path);
      await route.fulfill({ json: points });
    } else if (path.endsWith("/dividends")) {
      await route.fulfill({
        json: { currency: "USD", coverage: null, events: [] },
      });
    } else if (path === "/api/portfolio/analytics") {
      const body = route.request().postDataJSON();
      const positions = body.holdings.map(
        (h: { asset_id: string; quantity: number }) => ({
          id: h.asset_id,
          name: h.asset_id === "yf-test" ? "Action test" : "Bitcoin",
          quantity: h.quantity,
          price_usd: 100,
          value_usd: h.quantity * 100,
          date: "2022-03-10",
          weight:
            h.quantity /
            body.holdings.reduce(
              (sum: number, other: { quantity: number }) =>
                sum + other.quantity,
              0,
            ),
        }),
      );
      await route.fulfill({
        json: {
          status: "ready",
          total_usd: positions.reduce(
            (sum: number, p: { value_usd: number }) => sum + p.value_usd,
            0,
          ),
          positions,
          excluded: [],
          correlation: {
            assets: positions,
            matrix: positions.map((_: unknown, i: number) =>
              positions.map((_: unknown, j: number) => (i === j ? 1 : -0.5)),
            ),
            observations: 300,
            minimum: 20,
            frequency: "daily",
            start: "2021-01-01",
            end: "2022-03-10",
          },
        },
      });
    } else if (path.endsWith("/comparison")) {
      comparisonRequests.push(route.request().url());
      const query = new URL(route.request().url()).searchParams;
      const selected = points.filter(
        (p) =>
          p.time >= (query.get("start") ?? "") &&
          p.time <= (query.get("end") ?? "9999"),
      );
      await route.fulfill({
        json: {
          status: "ready",
          currency: "USD",
          start: selected[0].time,
          end: selected.at(-1)!.time,
          asset_return: 0.2,
          index_return: 0.1,
          converted: false,
          dividends_reinvested:
            path.includes("yf-test") && query.get("reinvest") === "true",
          price_proxy: path.includes("wb-gold"),
          equity: selected.map((p, i) => ({
            time: p.time,
            strategy: (100 * p.value) / selected[0].value,
            benchmark: 100 + i * 0.01,
          })),
        },
      });
    } else if (path.endsWith("/analysis")) {
      const parameters = route.request().postDataJSON() as Parameters;
      analysisRequests.push(parameters);
      await route.fulfill({ json: result(parameters) });
    } else
      await route.fulfill({
        status: 404,
        json: { detail: "Unexpected test request" },
      });
  });
  return { analysisRequests, historyRequests, comparisonRequests };
}
