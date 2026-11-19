import { test, expect, type Page } from "@playwright/test";
import { mockApi, stock } from "./fixtures";
import type { RiskResult } from "../../src/features/volatility/types";

function model(rates = false, portfolio = false): RiskResult {
  const points: RiskResult["points"] = [
    ...(rates
      ? []
      : [
          {
            id: "yf-test",
            name: "Airbus SE",
            kind: "asset" as const,
            return: 19.8,
            volatility: 27.2,
            sharpe: 0.73,
          },
        ]),
    ...(portfolio
      ? [
          {
            id: "yf-btc-usd",
            name: "Bitcoin",
            kind: "asset" as const,
            return: 35,
            volatility: 48,
            sharpe: 0.73,
          },
        ]
      : []),
    {
      id: "sp500",
      name: "S&P 500 PEA · PSP5",
      kind: "benchmark",
      return: 19.4,
      volatility: 16.6,
      sharpe: 1.17,
    },
  ];
  const curve = Array.from({ length: 81 }, (_, i) => ({
    volatility: 15.5 + 11.7 * (i / 80) ** 2,
    return: 19.45 + (0.35 * i) / 80,
    sharpe: null,
  }));
  return {
    status: "ready",
    currency: "EUR",
    frequency: "daily",
    annualization: 252,
    observations: 743,
    start: "2023-11-07",
    end: "2026-11-06",
    points,
    frontier: rates ? [] : curve,
    lower_frontier: rates
      ? []
      : [
          { return: 19.45, volatility: 15.5, sharpe: null },
          { return: 19.4, volatility: 16.6, sharpe: null },
        ],
    frontier_assets: rates
      ? []
      : portfolio
        ? ["yf-test", "yf-btc-usd"]
        : ["yf-test", "sp500"],
    excluded: rates
      ? [
          {
            id: "bond-fr",
            name: "France",
            reason: "Taux souverain : aucun prix obligataire.",
          },
        ]
      : [],
  };
}
async function assertCleanChart(page: Page, count: number, portfolio = false) {
  await expect(
    page.getByRole("img", { name: /Frontière de Markowitz/ }),
  ).toBeVisible();
  await expect(page.locator(".risk-marker")).toHaveCount(count);
  await expect(page.locator(".risk-marker circle")).toHaveCount(
    portfolio ? 0 : count - 1,
  );
  await expect(page.locator(".risk-table tbody tr")).toHaveCount(
    portfolio ? 3 : count,
  );
  await expect(page.locator(".risk-table")).toBeHidden();
  await expect(page.locator(".risk-benchmark-star")).toHaveCount(1);
  await expect(page.locator(".vol-panel .vol-heading")).toHaveCount(0);
  await expect(page.locator(".vol-panel")).not.toContainText(
    "RENDEMENT & RISQUE",
  );
  await expect(
    page.locator(".vol-chart-card").getByLabel("Période de comparaison"),
  ).toBeVisible();

  await expect(
    page.locator(".risk-point-label, .risk-marker line"),
  ).toHaveCount(0);
  await expect(page.getByText("Stockage local")).toHaveCount(0);
  await expect(page.locator(".risk-table")).toContainText("S&P 500 PEA · PSP5");
  await expect(
    page.locator(".risk-readout, .risk-scale, .vol-selection, .vol-note"),
  ).toHaveCount(0);
  await expect(page.locator(".vol-panel").getByRole("checkbox")).toHaveCount(0);
  await expect(page.locator(".vol-panel")).not.toContainText(
    /simulé|variations sur|Meilleur Sharpe|Minimum de volatilité/,
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
}
for (const id of ["yf-test", "yf-btc-usd", "wb-gold", "bond-fr"]) {
  test(`Markowitz chart has only real points for ${id}`, async ({
    page,
  }, testInfo) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await mockApi(page);
    const requests: string[] = [];
    await page.route("**/api/assets/*/volatility?*", (r) => {
      requests.push(r.request().url());
      return r.fulfill({ json: model(id === "bond-fr") });
    });
    await page.goto(`/assets/${id}`);
    await page
      .getByRole("tab", { name: "Frontières d’efficience", exact: true })
      .click();
    await assertCleanChart(page, id === "bond-fr" ? 1 : 2);
    if (id === "bond-fr")
      await expect(page.locator(".vol-exclusions")).toContainText(
        "aucun prix obligataire",
      );
    else {
      await expect(page.locator(".risk-frontier")).toBeVisible();
      const point = page.locator('.risk-marker[data-kind="asset"]').first();
      await point.focus();
      await expect(page.getByRole("tooltip")).toContainText("Airbus SE");
      await point.press("Escape");
      await expect(page.locator(".risk-tooltip")).toHaveCount(0);
      // Similar returns must use a tight y range instead of flattening against zero.
      const ticks = await page.locator(".risk-grid text").allTextContents();
      expect(ticks).not.toContain("0 %");
    }
    await page.getByRole("button", { name: "5A", exact: true }).click();
    await expect.poll(() => requests.at(-1)).toContain("years=5");
    await assertCleanChart(page, id === "bond-fr" ? 1 : 2);
    if (id === "yf-test")
      await page
        .locator(".vol-panel")
        .screenshot({ path: testInfo.outputPath("markowitz-asset.png") });
    expect(errors).toEqual([]);
  });
}

test("portfolio shows two stars and feasible allocations, and keeps the selected period", async ({
  page,
}, testInfo) => {
  await mockApi(page);
  const quantities = { "yf-test": 2, "yf-btc-usd": 1, "bond-fr": 3 };
  await page.addInitScript(
    ({ quantities }) => {
      localStorage.setItem(
        "investor-favorites",
        JSON.stringify(
          Object.fromEntries(Object.keys(quantities).map((id) => [id, "gold"])),
        ),
      );
      localStorage.setItem("investor-quantities", JSON.stringify(quantities));
    },
    { quantities },
  );
  const bodies: {
    holdings: { asset_id: string; quantity: number }[];
    years: number;
  }[] = [];
  await page.route("**/api/portfolio/volatility", (r) => {
    bodies.push(r.request().postDataJSON());
    return r.fulfill({
      json: {
        ...model(false, true),
        portfolio_point: {
          id: "current-portfolio",
          name: "Portefeuille actuel",
          kind: "portfolio",
          return: 25,
          volatility: 29,
          sharpe: 0.86,
        },
        cloud: [
          { return: 20, volatility: 25, sharpe: 0.8 },
          { return: 23, volatility: 27, sharpe: 0.85 },
        ],
        excluded: [
          {
            id: "bond-fr",
            name: "France",
            reason: "Taux souverain : aucun prix de titre disponible.",
          },
        ],
      },
    });
  });
  await page.goto("/markets/portfolio");
  await page
    .getByRole("tab", { name: "Frontières d’efficience", exact: true })
    .click();
  await assertCleanChart(page, 2, true);
  const star = page.locator(".risk-portfolio-star");
  await expect(star).toBeVisible();
  expect(await star.getAttribute("fill")).not.toBe(
    await page.locator(".risk-benchmark-star").getAttribute("fill"),
  );
  await expect(page.locator(".risk-allocation-cloud circle")).toHaveCount(2);
  await expect(page.locator(".risk-map-legend")).toContainText(
    "2 allocations · Sharpe",
  );
  await expect(
    page.locator(".vol-portfolio > .portfolio-section-heading h2"),
  ).toHaveCount(0);
  await page.getByText("Détail des actifs", { exact: true }).click();
  await expect(page.locator(".risk-table")).toBeVisible();
  await page.getByText("Détail des actifs", { exact: true }).click();
  await expect(page.locator(".risk-table")).toBeHidden();
  await expect(page.locator(".risk-table")).toContainText("Bitcoin");
  await expect(page.locator(".vol-exclusions")).toContainText("France");
  await page
    .locator(".vol-panel")
    .screenshot({ path: testInfo.outputPath("markowitz-portfolio.png") });
  let finishRefresh = () => {};
  const refresh = new Promise<void>((resolve) => {
    finishRefresh = resolve;
  });
  await page.route(
    "**/api/portfolio/volatility",
    async (route) => {
      await refresh;
      await route.fallback();
    },
    { times: 1 },
  );
  await page.getByRole("button", { name: "1A", exact: true }).click();
  try {
    await expect(page.getByText("Mise à jour du graphique…")).toBeVisible();
    await expect(star).toBeVisible();
    await expect(page.locator(".risk-allocation-cloud circle")).toHaveCount(2);
  } finally {
    finishRefresh();
  }
  await expect.poll(() => bodies.at(-1)?.years).toBe(1);
  expect(bodies.at(-1)?.holdings).toEqual(
    Object.entries(quantities).map(([asset_id, quantity]) => ({
      asset_id,
      quantity,
    })),
  );
  expect(
    JSON.parse(
      (await page.evaluate(() =>
        localStorage.getItem("investor-quantities"),
      )) ?? "{}",
    ),
  ).toEqual(quantities);
  await assertCleanChart(page, 2, true);
  await page.getByRole("tab", { name: "Positions", exact: true }).click();
  await page
    .getByRole("tab", { name: "Frontières d’efficience", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "1A", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await assertCleanChart(page, 2, true);
  expect(bodies.at(-1)?.years).toBe(1);
});

test("pending references, retry and insufficient sample", async ({ page }) => {
  await mockApi(page);
  let n = 0;
  await page.route("**/api/assets/*/volatility?*", (r) => {
    n++;
    if (n === 1) return r.fulfill({ json: { status: "pending" } });
    if (n === 2)
      return r.fulfill({
        status: 503,
        json: { detail: "Référence temporairement indisponible" },
      });
    if (n === 3)
      return r.fulfill({
        json: {
          status: "insufficient",
          message: "Il faut au moins 21 variations quotidiennes communes.",
        },
      });
    return r.fulfill({ json: model() });
  });
  await page.goto(`/assets/${stock.id}`);
  await page
    .getByRole("tab", { name: "Frontières d’efficience", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("S&P 500");
  await expect(page.getByRole("alert")).toContainText(
    "temporairement indisponible",
  );
  await page.getByRole("button", { name: "Réessayer" }).click();
  await expect(page.getByRole("status")).toContainText("21 variations");
  await page.getByRole("button", { name: "5A", exact: true }).click();
  await assertCleanChart(page, 2);
});
