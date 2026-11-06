import type { Page } from "@playwright/test";
import type { Analysis, Asset, Parameters } from "../src/lib/types";

const points = Array.from({ length: 800 }, (_, i) => ({
  time: new Date(Date.UTC(2020, 0, 1 + i)).toISOString().slice(0, 10),
  value: 100 * Math.exp(i * 0.0005 + Math.sin(i / 20) * 0.05),
}));
const stock: Asset = {
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
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/assets") {
      await route.fulfill({
        json: [
          stock,
          { ...stock, id: "wb-gold", name: "Or", category: "commodity" },
        ],
      });
    } else if (path.endsWith("/history")) {
      historyRequests.push(path);
      await route.fulfill({ json: points });
    } else if (path.endsWith("/dividends")) {
      await route.fulfill({
        json: { currency: "USD", coverage: null, events: [] },
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
  return { analysisRequests, historyRequests };
}
