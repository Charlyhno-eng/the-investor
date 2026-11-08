import type { Page } from "@playwright/test";
import type { Asset } from "../../src/lib/types";

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
  country: "France",
  benchmark_years: null,
  year_average_yield: null,
  year_yield_samples: 0,
  bond_ranking_date: null,
};

export async function mockApi(page: Page) {
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
    } else if (path === "/api/portfolio/regression") {
      const body = route.request().postDataJSON();
      await route.fulfill({
        json: {
          positions: body.asset_ids.map((id: string, i: number) => ({
            id,
            z: i % 2 === 0 ? -1.8 : 1.9,
            start: "2020-01-01",
            end: "2022-03-10",
            observations: 800,
          })),
        },
      });
    } else if (path === "/api/portfolio/analytics") {
      const body = route.request().postDataJSON();
      const currency = "EUR";
      const rate = 0.8;
      const positions = body.holdings.map(
        (h: { asset_id: string; quantity: number }) => ({
          id: h.asset_id,
          name: h.asset_id === "yf-test" ? "Action test" : "Bitcoin",
          quantity: h.quantity,
          price_usd: 100,
          value_usd: h.quantity * 100,
          price: 100 * rate,
          value: h.quantity * 100 * rate,
          fx_date: "2022-03-10",
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
          currency,
          total: positions.reduce(
            (sum: number, p: { value: number }) => sum + p.value,
            0,
          ),
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
    } else
      await route.fulfill({
        status: 404,
        json: { detail: "Unexpected test request" },
      });
  });
  return { historyRequests, comparisonRequests };
}
