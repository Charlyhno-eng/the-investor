import { test, expect } from "@playwright/test";
import { mockApi, stock } from "./fixtures";

test("watchlist exposes regression deviations and new categories", async ({
  page,
}) => {
  await mockApi(page);
  await page.addInitScript(() =>
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "silver" }),
    ),
  );
  await page.route("**/api/portfolio/regression", (route) =>
    route.fulfill({ json: { positions: [{ id: stock.id, z: 1.25 }] } }),
  );
  await page.goto("/markets/watchlist");
  await expect(
    page.getByRole("heading", { name: "Watchlist", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("cell", { name: "+1,25 σ" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "ETF", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Devises", exact: true }),
  ).toBeVisible();
});

test("market regime trains on selected dates and renders four colored regimes", async ({
  page,
}, testInfo) => {
  await mockApi(page);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let request: Record<string, string> | undefined;
  const points = Array.from({ length: 40 }, (_, i) => ({
    time: new Date(Date.UTC(2021, 9, 1 + i)).toISOString().slice(0, 10),
    value: 100 + i + Math.sin(i),
    state: i % 4,
    confidence: 0.75,
  }));
  await page.route("**/api/assets/*/regime", (route) => {
    expect(route.request().method()).toBe("POST");
    request = route.request().postDataJSON();
    return route.fulfill({
      json: {
        current: "Régime 3",
        date: points.at(-1)!.time,
        observations: points.length,
        train_observations: 500,
        actual_train: ["2020-01-01", "2021-09-01"],
        actual_test: [points[0].time, points.at(-1)!.time],
        points,
        states: [
          { name: "Baisse · volatilité élevée", mean: -0.02, volatility: 0.04 },
          {
            name: "Baisse · volatilité faible",
            mean: -0.005,
            volatility: 0.01,
          },
          {
            name: "Hausse · volatilité faible",
            mean: 0.001,
            volatility: 0.005,
          },
          { name: "Hausse · volatilité élevée", mean: 0.01, volatility: 0.02 },
        ].map((state) => ({
          ...state,
          probability: 0.25,
          next_probability: 0.25,
        })),
      },
    });
  });
  await page.goto(`/assets/${stock.id}`);
  await page.getByRole("tab", { name: "HMM", exact: true }).click();
  await expect(page.getByLabel("Début entraînement")).toBeVisible();
  await page
    .getByRole("button", { name: "Entraîner et tester", exact: true })
    .click();
  await expect(page.locator(".regime-legend span")).toHaveText([
    "Hausse · volatilité faible",
    "Hausse · volatilité élevée",
    "Baisse · volatilité faible",
    "Baisse · volatilité élevée",
  ]);
  await expect(page.locator(".regime-separator")).toHaveCount(1);
  await expect(page.locator(".regime-results")).toBeInViewport();
  await expect(page.locator(".regime-legend i").first()).toHaveCSS(
    "background-color",
    "rgb(51, 153, 255)",
  );
  expect(request!.train_end < request!.test_start).toBe(true);
  const chart = page.locator(".regime-panel .history-chart");
  await expect(chart.locator("canvas").first()).toBeVisible();
  await page
    .locator(".regime-panel")
    .screenshot({ path: testInfo.outputPath("market-regimes.png") });
  await page.getByText("Probabilités et paramètres", { exact: true }).click();
  await expect(page.locator(".regime-panel tbody tr")).toHaveCount(4);
  await expect(page.getByText("Stratégie nette", { exact: true })).toHaveCount(
    0,
  );
  await page.getByLabel("Début test").fill("2020-02-01");
  await expect(
    page.getByRole("button", { name: "Entraîner et tester", exact: true }),
  ).toBeDisabled();
  await expect(page.locator(".regime-legend")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("sector colors, allocation and correlation metadata stay consistent", async ({
  page,
}) => {
  await mockApi(page);
  await page.route("**/api/assets", (route) =>
    route.fulfill({ json: [{ ...stock, sector: "Technology" }] }),
  );
  await page.route("**/api/portfolio/analytics", (route) => {
    expect(route.request().postDataJSON().include_benchmark).toBe(true);
    return route.fulfill({
      json: {
        status: "ready",
        positions: [
          {
            id: stock.id,
            name: stock.name,
            value: 100,
            weight: 1,
            date: stock.last_date,
          },
        ],
        total: 100,
        excluded: [],
        correlation: {
          assets: [
            { id: stock.id, name: stock.name },
            { id: "^SP500TR", name: "S&P 500" },
          ],
          matrix: [
            [1, 0.8],
            [0.8, 1],
          ],
          observations: 492,
          minimum: 20,
          frequency: "daily",
          start: "2024-11-29",
          end: "2026-11-06",
        },
      },
    });
  });
  await page.addInitScript(() => {
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold" }),
    );
    localStorage.setItem(
      "investor-quantities",
      JSON.stringify({ "yf-test": 1 }),
    );
  });
  await page.goto(`/assets/${stock.id}`);
  await expect(page.locator(".sector-badge")).toHaveText("Technologie");
  await expect(
    page
      .locator(".category-rail button", { hasText: "Actions" })
      .locator(".rail-count"),
  ).toHaveText("1");
  const badgeColor = await page
    .locator(".sector-badge")
    .evaluate((el) => getComputedStyle(el).borderColor);
  await expect(page.locator(".list-symbol.stock")).toHaveCSS(
    "border-color",
    badgeColor,
  );
  await page.getByRole("button", { name: "Portfolio", exact: true }).click();
  await page.getByRole("tab", { name: "Répartition", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Répartition par", exact: true })
    .selectOption("sectors");
  await expect(page.locator(".allocation-legend-item")).toContainText(
    "Technologie",
  );
  await page.getByRole("tab", { name: "Corrélations", exact: true }).click();
  await expect(page.locator(".correlation-table thead")).toContainText(
    "S&P 500",
  );
  await expect(page.locator(".correlation-meta")).toContainText(
    "492 rendements sur dates communes",
  );
  await expect(
    page.locator(".correlation-meta .correlation-scale"),
  ).toBeVisible();
});

test("watchlist groups classes in rail order and only computes stock and crypto deviations", async ({
  page,
}) => {
  await mockApi(page);
  const assets = [
    { ...stock, id: "yf-spy", name: "ETF test", category: "etf" },
    { ...stock, id: "wb-gold", name: "Or", category: "commodity" },
    { ...stock, id: "yf-btc-usd", name: "Bitcoin", category: "crypto" },
    stock,
  ];
  await page.route("**/api/assets", (route) => route.fulfill({ json: assets }));
  await page.route("**/api/portfolio/regression", (route) => {
    if (!route.request().postDataJSON().asset_ids.length)
      return route.fulfill({ json: { positions: [] } });
    expect(route.request().postDataJSON().asset_ids.sort()).toEqual(
      ["yf-btc-usd", stock.id].sort(),
    );
    return route.fulfill({
      json: {
        positions: [
          { id: stock.id, z: 1 },
          { id: "yf-btc-usd", z: -1 },
        ],
      },
    });
  });
  await page.addInitScript(
    (ids) =>
      localStorage.setItem(
        "investor-favorites",
        JSON.stringify(Object.fromEntries(ids.map((id) => [id, "silver"]))),
      ),
    assets.map((a) => a.id),
  );
  await page.goto("/markets/watchlist");
  await expect(page.locator(".watchlist-class-heading")).toHaveText([
    "Actions",
    "Cryptomonnaies",
    "Matières premières",
    "ETF",
  ]);
  await expect(
    page.locator(".positions-table .regression-deviation"),
  ).toHaveCount(2);
  await expect(
    page
      .locator(".positions-table tr", { hasText: "ETF test" })
      .locator("td")
      .last(),
  ).toHaveText("—");
  await expect(
    page.getByText("Vos actifs suivis", { exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".portfolio-summary")).toHaveCount(0);
});
