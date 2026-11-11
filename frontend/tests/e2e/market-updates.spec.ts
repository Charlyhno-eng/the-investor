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
  await page
    .getByRole("region", { name: "Répartition du portefeuille", exact: true })
    .scrollIntoViewIfNeeded();
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

test("watchlist groups classes in rail order and computes stock, ETF and crypto deviations", async ({
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
      ["yf-btc-usd", "yf-spy", stock.id].sort(),
    );
    return route.fulfill({
      json: {
        positions: [
          { id: stock.id, z: 1 },
          { id: "yf-btc-usd", z: -1 },
          { id: "yf-spy", z: 0.5 },
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
  ).toHaveCount(3);
  await expect(
    page
      .locator(".positions-table tr", { hasText: "ETF test" })
      .locator(".regression-deviation"),
  ).toContainText("+0,5 σ");
  await expect(
    page.getByText("Vos actifs suivis", { exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".portfolio-summary")).toHaveCount(0);
});

test("an open chart reloads corrected history after the catalogue refresh", async ({
  page,
}) => {
  const { historyRequests } = await mockApi(page);
  let revision = "first";
  await page.route("**/api/assets", (route) =>
    route.fulfill({ json: [{ ...stock, data_revision: revision }] }),
  );
  await page.clock.install();
  await page.goto(`/assets/${stock.id}`);
  await expect(page.locator(".history-chart")).toBeVisible();
  const initial = historyRequests.length;
  revision = "corrected";
  await page.clock.fastForward(15000);
  await expect.poll(() => historyRequests.length).toBe(initial + 1);
  // An unchanged catalogue must not trigger another full history download.
  await page.clock.fastForward(15000);
  expect(historyRequests).toHaveLength(initial + 1);
});

test("portfolio analytics refresh when provider data changes without a quantity edit", async ({
  page,
}) => {
  await mockApi(page);
  let revision = "first";
  let analyticsRequests = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/portfolio/analytics")
      analyticsRequests++;
  });
  await page.route("**/api/assets", (route) =>
    route.fulfill({ json: [{ ...stock, data_revision: revision }] }),
  );
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
  await page.clock.install();
  await page.goto("/markets/portfolio");
  await expect.poll(() => analyticsRequests).toBeGreaterThan(0);
  await expect(page.locator(".portfolio-total strong")).not.toHaveText("—");
  const previous = analyticsRequests;
  revision = "updated";
  await page.clock.fastForward(15000);
  await expect.poll(() => analyticsRequests).toBeGreaterThan(previous);
});
