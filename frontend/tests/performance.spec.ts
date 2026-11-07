import { test, expect, type Page } from "@playwright/test";
import { mockApi } from "./fixtures";
import type { PerformanceResult } from "../src/features/portfolio/PerformancePanel";

function model(
  optimized = false,
  mode: PerformanceResult["mode"] = "balanced",
): PerformanceResult {
  return {
    status: "ready",
    mode: optimized ? mode : null,
    currency: "EUR",
    frequency: "daily",
    observations: 119,
    start: "2025-01-01",
    end: "2025-04-30",
    equity: Array.from({ length: 120 }, (_, i) => ({
      time: new Date(Date.UTC(2025, 0, i + 1)).toISOString().slice(0, 10),
      portfolio: 100 + i * 0.1 + Math.sin(i) * 0.1,
      benchmark: 100 + i * 0.08,
      ...(optimized ? { optimized: 100 + i * 0.12 } : {}),
    })),
    metrics: {
      portfolio: {
        total_return: 0.12,
        volatility: 0.2,
        max_drawdown: -0.25,
        sharpe: 0.6,
      },
      benchmark: {
        total_return: 0.09,
        volatility: 0.16,
        max_drawdown: -0.15,
        sharpe: 0.56,
      },
      ...(optimized
        ? {
            optimized: {
              total_return: 0.14,
              volatility: 0.1,
              max_drawdown: -0.1,
              sharpe: 1.4,
            },
          }
        : {}),
    },
    positions: [
      {
        id: "yf-test",
        name: "Action test",
        quantity: 2,
        weight: 0.7,
        date: "2025-04-30",
        recommended_weight: optimized ? 0.6 : null,
        recommended_quantity: optimized ? 1.714 : null,
      },
      {
        id: "yf-btc-usd",
        name: "Bitcoin",
        quantity: 1,
        weight: 0.3,
        date: "2025-04-30",
        recommended_weight: optimized ? 0.4 : null,
        recommended_quantity: optimized ? 1.333 : null,
      },
    ],
  };
}

async function setup(page: Page) {
  await mockApi(page);
  await page.addInitScript(() => {
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold", "yf-btc-usd": "gold" }),
    );
    localStorage.setItem(
      "investor-quantities",
      JSON.stringify({ "yf-test": 2, "yf-btc-usd": 1 }),
    );
  });
}

test("portfolio comparison, explicit optimization, hover names and unchanged holdings", async ({
  page,
  isMobile,
}, testInfo) => {
  await setup(page);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const comparisons: { years: number; holdings: unknown }[] = [];
  const optimizations: unknown[] = [];
  await page.route("**/api/portfolio/performance", (r) => {
    comparisons.push(r.request().postDataJSON());
    return r.fulfill({ json: model() });
  });
  await page.route("**/api/portfolio/optimize", (r) => {
    optimizations.push(r.request().postDataJSON());
    return r.fulfill({ json: model(true) });
  });
  await page.goto("/markets/portfolio");
  await page.getByRole("tab", { name: "Performance", exact: true }).click();
  const panel = page.getByRole("region", { name: "Performance du Portfolio" });
  await expect(
    panel.locator(".portfolio-section-heading h2").first(),
  ).toHaveText("Performance face au S&P 500");
  await expect(panel.locator(".performance-series-summary > div")).toHaveCount(
    2,
  );
  expect(optimizations).toHaveLength(0);
  await expect(panel.locator(".performance-weights")).toHaveCount(0);
  const chart = panel.getByRole("img", { name: /base 100 en euros/ });
  await expect(chart.locator("canvas").first()).toBeVisible();
  await chart.scrollIntoViewIfNeeded();
  const bounds = (await chart.boundingBox())!;
  if (isMobile)
    await page.touchscreen.tap(
      bounds.x + bounds.width * 0.6,
      bounds.y + bounds.height * 0.4,
    );
  else
    await page.mouse.move(
      bounds.x + bounds.width * 0.6,
      bounds.y + bounds.height * 0.4,
    );
  await expect(page.locator(".chart-lines-tooltip")).toContainText(
    "Portfolio actuel",
  );
  await expect(page.locator(".chart-lines-tooltip")).toContainText("S&P 500");
  await panel
    .getByRole("button", { name: "Optimiser les poids", exact: true })
    .click();
  await expect(panel.locator(".performance-series-summary > div")).toHaveCount(
    3,
  );
  await expect(panel.locator(".performance-weights tbody tr")).toHaveCount(2);
  await expect(panel.locator(".performance-weights")).toContainText("60 %");
  await expect(panel.locator(".performance-simulation-note")).toContainText(
    "rétrospective",
  );
  expect(optimizations).toHaveLength(1);
  expect(optimizations[0]).toEqual(comparisons[0]);
  await chart.scrollIntoViewIfNeeded();
  const updatedBounds = (await chart.boundingBox())!;
  if (isMobile)
    await page.touchscreen.tap(
      updatedBounds.x + updatedBounds.width * 0.7,
      updatedBounds.y + updatedBounds.height * 0.3,
    );
  else
    await page.mouse.move(
      updatedBounds.x + updatedBounds.width * 0.7,
      updatedBounds.y + updatedBounds.height * 0.3,
    );
  await expect(page.locator(".chart-lines-tooltip")).toContainText(
    "Allocation optimisée",
  );
  await panel.screenshot({
    path: testInfo.outputPath("portfolio-performance.png"),
  });
  expect(
    await page.locator(".app-header").evaluate((el) => el.clientHeight),
  ).toBeLessThanOrEqual(60);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    await page.evaluate(() =>
      JSON.parse(localStorage.getItem("investor-quantities")!),
    ),
  ).toEqual({ "yf-test": 2, "yf-btc-usd": 1 });
  await panel.getByLabel("Période").selectOption("5");
  await expect(panel.locator(".performance-series-summary > div")).toHaveCount(
    2,
  );
  await expect(panel.locator(".performance-weights")).toHaveCount(0);
  await expect.poll(() => comparisons.at(-1)?.years).toBe(5);
  expect(errors).toEqual([]);
});

test("pending data and failed optimization allow retry while retaining comparison", async ({
  page,
}) => {
  await setup(page);
  let pending = true;
  let solves = 0;
  await page.route("**/api/portfolio/performance", (r) =>
    r.fulfill({ json: pending ? { status: "pending" } : model() }),
  );
  await page.route("**/api/portfolio/optimize", (r) =>
    ++solves === 1
      ? r.fulfill({ status: 503, json: { detail: "Calcul indisponible" } })
      : r.fulfill({ json: model(true) }),
  );
  await page.goto("/markets/portfolio");
  await page.getByRole("tab", { name: "Performance", exact: true }).click();
  const panel = page.locator(".portfolio-performance");
  await expect(panel.getByRole("status")).toContainText("Chargement");
  pending = false;
  await panel
    .getByRole("button", { name: "Optimiser les poids", exact: true })
    .click();
  await expect(panel.getByRole("alert")).toContainText("Calcul indisponible");
  await expect(panel.locator(".performance-series-summary > div")).toHaveCount(
    2,
  );
  await panel.getByRole("button", { name: "Réessayer" }).click();
  await expect(panel.locator(".performance-series-summary > div")).toHaveCount(
    3,
  );
});

test("insufficient history and changes of quantities invalidate the simulation", async ({
  page,
}) => {
  await setup(page);
  await page.route("**/api/portfolio/performance", (r) =>
    r.fulfill({
      json:
        r.request().postDataJSON().holdings[0].quantity === 2
          ? {
              status: "insufficient",
              message: "Pas assez de dates communes pour tous les actifs.",
            }
          : model(),
    }),
  );
  await page.goto("/markets/portfolio");
  await page.getByRole("tab", { name: "Performance", exact: true }).click();
  await expect(
    page.locator(".portfolio-performance").getByRole("status"),
  ).toContainText("Pas assez");
  await expect(
    page.getByRole("button", { name: "Optimiser les poids", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("tab", { name: "Positions", exact: true }).click();
  await page.getByLabel("Quantité Action test", { exact: true }).fill("3");
  await page.getByRole("tab", { name: "Performance", exact: true }).click();
  await expect(page.locator(".performance-series-summary > div")).toHaveCount(
    2,
  );
});

test("all optimization modes, risk metrics and extended history remain explicit", async ({
  page,
}, testInfo) => {
  await setup(page);
  const solves: string[] = [];
  const histories: string[] = [];
  await page.route("**/api/portfolio/performance", (r) => {
    const body = r.request().postDataJSON();
    histories.push(body.history);
    return r.fulfill({
      json: {
        ...model(),
        requested_start: "2020-01-01",
        cash_until:
          body.history === "extended"
            ? [{ id: "yf-test", name: "Action test", date: "2025-01-01" }]
            : [],
      },
    });
  });
  await page.route("**/api/portfolio/optimize", (r) => {
    const body = r.request().postDataJSON();
    solves.push(body.mode);
    return r.fulfill({ json: model(true, body.mode) });
  });
  await page.goto("/markets/portfolio");
  const tabs = await page
    .locator('.portfolio-panel > .detail-tabs [role="tab"]')
    .allTextContents();
  expect(tabs.indexOf("Performance")).toBeLessThan(
    tabs.indexOf("Corrélations"),
  );
  await page.getByRole("tab", { name: "Performance", exact: true }).click();
  const panel = page.locator(".portfolio-performance");
  await expect(panel.getByLabel("Historique", { exact: true })).toHaveValue(
    "extended",
  );
  await expect(panel.locator(".performance-history-note")).toContainText(
    "liquidités",
  );
  await expect(panel.locator(".performance-series-summary")).toContainText(
    "Drawdown maximal -25 %",
  );
  await expect(panel.locator(".performance-series-summary")).toContainText(
    "Sharpe 0,6",
  );
  await expect(panel.locator(".performance-series-summary")).toContainText(
    "Sharpe 0,56",
  );
  for (const [label, mode] of [
    ["Équilibre", "balanced"],
    ["Volatilité minimale", "volatility"],
    ["Performance maximale", "performance"],
    ["Drawdown minimal", "drawdown"],
  ]) {
    await panel.getByRole("radio", { name: new RegExp(label) }).check();
    await panel
      .getByRole("button", { name: "Optimiser les poids", exact: true })
      .click();
    await expect(
      panel.locator(".performance-series-summary > div"),
    ).toHaveCount(3);
    await expect.poll(() => solves.at(-1)).toBe(mode);
  }
  await panel.screenshot({
    path: testInfo.outputPath("performance-modes.png"),
  });
  await panel.getByLabel("Historique", { exact: true }).selectOption("common");
  await expect(panel.locator(".performance-series-summary > div")).toHaveCount(
    2,
  );
  await expect.poll(() => histories.at(-1)).toBe("common");
  await expect(panel.locator(".performance-history-note")).toContainText(
    "historique plus court",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
