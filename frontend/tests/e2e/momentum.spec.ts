import { test, expect } from "@playwright/test";
import { mockApi, stock } from "./fixtures";

const rows = Array.from({ length: 180 }, (_, i) => ({
  time: new Date(Date.UTC(2021, 6, 1 + i)).toISOString().slice(0, 10),
  value: 100 * Math.exp(i * 0.001 + 0.02 * Math.sin(i / 9)),
  trend: 100 * Math.exp(i * 0.001),
  residual: 0.02 * Math.sin(i / 9),
}));
const ready = {
  status: "ready",
  as_of: "2022-03-10",
  benchmark_name: "S&P 500 · dividendes réinvestis",
  benchmarks: [{ id: "europe", name: "ETF Europe" }],
  recent_return: -0.15,
  drawdown: -0.2,
  universe: [
    { id: "yf-test", name: "Action test", scores: [90, 70, 20] },
    { id: "peer", name: "Autre action", scores: [60, 60, 60] },
    { id: "short", name: "Historique court", scores: null },
    { id: "taiwan", name: "Action Taïwan", scores: [55, 55, 55] },
  ],
  horizons: [36, 12, 6].map((months, i) => ({
    months,
    start: rows[0].time,
    end: rows.at(-1)!.time,
    observations: 180,
    performance: i === 0 ? 2 : -0.1,
    annual_performance: 0.2,
    annual_trend: 0.18,
    slope: 0.16,
    r2: 0.85,
    sigma: 0.04,
    relative_performance: 0.1,
    score: [90, 70, 20][i],
    rows,
  })),
};

test("momentum weights, benchmark, regression, residuals and responsive layout", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await mockApi(page);
  await page.route("**/api/assets", (route) =>
    route.fulfill({
      json: [
        stock,
        { ...stock, id: "peer", name: "Autre action", unit: "EUR" },
        { ...stock, id: "taiwan", name: "Action Taïwan", unit: "TWD" },
        { ...stock, id: "short", name: "Historique court" },
        { ...stock, id: "europe", name: "ETF Europe", category: "etf" },
      ],
    }),
  );
  await page.route("**/api/assets/yf-test/momentum*", (route) =>
    route.fulfill({ json: ready }),
  );
  await page.goto("/assets/yf-test");
  await page.getByRole("tab", { name: "Momentum", exact: true }).click();
  const panel = page.getByRole("region", { name: "Momentum de l’action" });
  const summary = panel.getByLabel("Synthèse momentum");
  await expect(summary).toContainText("65,5 / 100");
  await expect(summary).toContainText("1 / 3");
  await expect(summary).toContainText("-15 %");
  await expect(panel.getByLabel("Référence momentum")).toHaveValue("");
  await expect(
    panel.getByLabel("Référence momentum").locator("option"),
  ).toContainText(["S&P 500", "CAC 40", "ETF Europe"]);
  await expect(
    panel.getByRole("heading", { name: "Momentum", exact: true }),
  ).toHaveCount(0);
  await expect(panel.locator("caption, details")).toHaveCount(0);
  await expect(panel).not.toContainText("Poids normalisés à 100 %");
  for (const name of [
    "Horizon",
    "Poids effectif",
    "Rendement",
    "Pente / an",
    "R²",
    "Dispersion log",
    "Force relative",
    "Score / 100",
  ]) {
    const help = panel.getByRole("button", {
      name: `Définition : ${name}`,
      exact: true,
    });
    await help.focus();
    await expect(page.getByRole("tooltip")).toContainText(name);
    await help.press("Escape");
  }
  if (testInfo.project.name === "desktop") {
    const fields = await panel
      .locator(".reversion-controls input, .reversion-controls select")
      .evaluateAll((labels) =>
        labels.map((label) => Math.round(label.getBoundingClientRect().top)),
      );
    expect(new Set(fields).size).toBe(1);
  }

  await expect(
    panel.getByRole("img", {
      name: "Momentum : prix et régression logarithmique",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    panel.getByRole("img", {
      name: "Momentum : résidus logarithmiques autour de zéro",
      exact: true,
    }),
  ).toBeVisible();
  await panel.getByLabel("Poids 36 mois (%)", { exact: true }).fill("0");
  await panel.getByLabel("Poids 12 mois (%)", { exact: true }).fill("0");
  await expect(summary).toContainText("20 / 100");
  await expect(summary).toContainText("3 / 3");
  await panel.getByLabel("Poids 6 mois (%)", { exact: true }).fill("0");
  await expect(panel.getByRole("alert")).toContainText("poids positif");
  await panel.getByLabel("Poids 36 mois (%)", { exact: true }).fill("100");
  await expect(summary).toContainText("90 / 100");
  await panel.getByRole("button", { name: "6 mois", exact: true }).click();
  await expect(
    panel.getByRole("button", { name: "6 mois", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await panel.getByLabel("Référence momentum").selectOption("europe");
  await expect(summary).toContainText("90 / 100");
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("momentum.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("incomplete history has no combined score; unsupported assets do not expose momentum", async ({
  page,
}) => {
  await mockApi(page);
  await page.route("**/api/assets/yf-test/momentum*", (route) =>
    route.fulfill({
      json: {
        ...ready,
        universe: [{ id: "yf-test", name: "Action test", scores: null }],
        horizons: ready.horizons.map((h) => ({
          months: h.months,
          error: "Historique commun insuffisant ou discontinu.",
        })),
      },
    }),
  );
  await page.goto("/assets/yf-test");
  await page.getByRole("tab", { name: "Momentum", exact: true }).click();
  await expect(page.getByLabel("Synthèse momentum")).toContainText(
    "Non classée",
  );
  await expect(
    page.getByRole("img", {
      name: "Momentum : prix et régression logarithmique",
      exact: true,
    }),
  ).toHaveCount(0);
  await page.goto("/assets/wb-gold");
  await expect(
    page.getByRole("tab", { name: "Momentum", exact: true }),
  ).toHaveCount(0);
});

test("reference loading and API errors", async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/assets", (route) =>
    route.fulfill({
      json: [
        stock,
        { ...stock, id: "europe", name: "ETF Europe", category: "etf" },
      ],
    }),
  );
  let fail = false;
  await page.route("**/api/assets/yf-test/momentum*", (route) =>
    fail
      ? route.fulfill({
          status: 503,
          json: { detail: "Référence indisponible" },
        })
      : route.fulfill({
          json: { status: "pending", benchmarks: ready.benchmarks },
        }),
  );
  await page.goto("/assets/yf-test");
  await page.getByRole("tab", { name: "Momentum", exact: true }).click();
  await expect(page.getByRole("status")).toContainText(
    "Import de la référence",
  );
  fail = true;
  await page.getByLabel("Référence momentum").selectOption("europe");
  await expect(page.getByRole("alert")).toContainText("Référence indisponible");
});

for (const library of ["portfolio", "watchlist"]) {
  test(`weighted momentum settings are shared with ${library} and survive reload`, async ({
    page,
  }) => {
    await mockApi(page);
    await page.addInitScript(
      ({ library }) =>
        localStorage.setItem(
          "investor-favorites",
          JSON.stringify({
            "yf-test": library === "portfolio" ? "gold" : "silver",
            "yf-btc-usd": library === "portfolio" ? "gold" : "silver",
          }),
        ),
      { library },
    );
    await page.route("**/api/assets/yf-test/momentum*", (route) =>
      route.fulfill({ json: ready }),
    );
    const requests: string[] = [];
    await page.route("**/api/momentum*", (route) => {
      requests.push(route.request().url());
      return route.fulfill({ json: ready });
    });
    await page.goto("/assets/yf-test");
    await page.getByRole("tab", { name: "Momentum", exact: true }).click();
    await page.getByLabel("Poids 36 mois (%)", { exact: true }).fill("100");
    await page.getByLabel("Poids 12 mois (%)", { exact: true }).fill("0");
    await page.getByLabel("Poids 6 mois (%)", { exact: true }).fill("0");
    await page.getByLabel("Référence momentum").selectOption("^FCHI");
    await expect(page.getByLabel("Synthèse momentum")).toContainText(
      "90 / 100",
    );
    await page
      .getByRole("button", {
        name: library === "portfolio" ? "Portfolio" : "Watchlist",
        exact: true,
      })
      .click();
    const table = page.locator(".positions-table");
    await expect(
      table.getByRole("columnheader", { name: /Momentum/ }),
    ).toBeVisible();
    await expect(
      table
        .locator("tbody tr")
        .filter({ hasText: "Action test" })
        .locator(".momentum-cell"),
    ).toHaveText("90 / 100");
    await expect
      .poll(() =>
        requests.some(
          (url) =>
            url.includes("category=stock") && url.includes("benchmark=%5EFCHI"),
        ),
      )
      .toBe(true);
    await page.reload();
    await expect(
      table
        .locator("tbody tr")
        .filter({ hasText: "Action test" })
        .locator(".momentum-cell"),
    ).toHaveText("90 / 100");
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
  });
}

test("crypto momentum ranks only cryptos and shares its own settings with portfolio scores", async ({
  page,
}) => {
  await mockApi(page);
  const cryptoAssets = [
    { ...stock, id: "yf-btc-usd", name: "Bitcoin", category: "crypto" },
    { ...stock, id: "yf-eth-usd", name: "Ethereum", category: "crypto" },
  ];
  await page.route("**/api/assets", (r) =>
    r.fulfill({ json: [stock, ...cryptoAssets] }),
  );
  const cryptoReady = {
    ...ready,
    category: "crypto",
    benchmark_name: "Bitcoin",
    universe: cryptoAssets.map((a) => ({
      id: a.id,
      name: a.name,
      scores: [80, 60, 40],
    })),
  };
  await page.route("**/api/assets/yf-btc-usd/momentum*", (r) =>
    r.fulfill({ json: cryptoReady }),
  );
  await page.route("**/api/momentum*", (r) =>
    r.fulfill({
      json:
        new URL(r.request().url()).searchParams.get("category") === "crypto"
          ? cryptoReady
          : ready,
    }),
  );
  await page.addInitScript(() =>
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold", "yf-btc-usd": "gold" }),
    ),
  );
  await page.goto("/assets/yf-btc-usd");
  await page.getByRole("tab", { name: "Momentum", exact: true }).click();
  const panel = page.getByRole("region", {
    name: "Momentum de la cryptomonnaie",
  });
  await expect(panel).toContainText("Toutes les cryptomonnaies");
  await expect(panel.getByLabel("Synthèse momentum")).toContainText("63 / 100");
  await expect(panel.getByLabel("Synthèse momentum")).toContainText("1 / 2");
  await expect(
    panel.getByLabel("Référence momentum").locator("option"),
  ).toContainText(["Bitcoin", "Ethereum"]);
  await panel.getByLabel("Poids 36 mois (%)", { exact: true }).fill("100");
  await panel.getByLabel("Poids 12 mois (%)", { exact: true }).fill("0");
  await panel.getByLabel("Poids 6 mois (%)", { exact: true }).fill("0");
  await panel.getByLabel("Référence momentum").selectOption("yf-eth-usd");
  await expect(panel.getByLabel("Synthèse momentum")).toContainText("80 / 100");
  await panel
    .getByRole("button", { name: "Définition : Horizon", exact: true })
    .focus();
  await expect(page.getByRole("tooltip")).toContainText(
    "dernier mois est exclu",
  );
  await page.goto("/markets/portfolio");
  const rows = page.locator(".positions-table tbody tr");
  await expect(
    rows.filter({ hasText: "Bitcoin" }).locator(".momentum-cell"),
  ).toHaveText("80 / 100");
  await expect(
    rows.filter({ hasText: "Action test" }).locator(".momentum-cell"),
  ).toHaveText("65,5 / 100");
  await page.reload();
  await expect(
    rows.filter({ hasText: "Bitcoin" }).locator(".momentum-cell"),
  ).toHaveText("80 / 100");
});

test("Hyperliquid uses available horizons with recalculated weights and partial history labels", async ({
  page,
}) => {
  await mockApi(page);
  const hype = {
    ...stock,
    id: "yf-hype32196-usd",
    name: "Hyperliquid",
    category: "crypto",
  };
  const btc = {
    ...stock,
    id: "yf-btc-usd",
    name: "Bitcoin",
    category: "crypto",
  };
  await page.route("**/api/assets", (r) =>
    r.fulfill({ json: [stock, hype, btc] }),
  );
  const partial = {
    ...ready,
    category: "crypto",
    benchmark_name: "Bitcoin",
    universe: [
      { id: hype.id, name: hype.name, scores: [null, 70, 50], partial: true },
      { id: btc.id, name: btc.name, scores: [60, 60, 60] },
    ],
    horizons: ready.horizons.map((h) =>
      h.months === 36
        ? { months: 36, error: "Historique commun insuffisant ou discontinu." }
        : h,
    ),
  };
  await page.route("**/api/assets/yf-hype32196-usd/momentum*", (r) =>
    r.fulfill({ json: partial }),
  );
  await page.route("**/api/momentum*", (r) => r.fulfill({ json: partial }));
  await page.addInitScript(() =>
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-hype32196-usd": "gold" }),
    ),
  );
  await page.goto("/assets/yf-hype32196-usd");
  await page.getByRole("tab", { name: "Momentum", exact: true }).click();
  const summary = page.getByLabel("Synthèse momentum");
  await expect(summary).toContainText("61,7 / 100");
  await expect(summary).toContainText("1 / 2");
  await expect(summary).toContainText("Historique partiel · 12 / 6 mois");
  const table = page.locator(".momentum-table tbody tr");
  await expect(table.nth(0).locator("td").first()).toHaveText("0 %");
  await expect(table.nth(1).locator("td").first()).toHaveText("58,33 %");
  await expect(table.nth(2).locator("td").first()).toHaveText("41,67 %");
  await page.getByLabel("Poids 12 mois (%)", { exact: true }).fill("0");
  await page.getByLabel("Poids 6 mois (%)", { exact: true }).fill("0");
  await expect(summary).toContainText("Non classée");
  await page.getByLabel("Poids 12 mois (%)", { exact: true }).fill("35");
  await page.getByLabel("Poids 6 mois (%)", { exact: true }).fill("25");
  await page.goto("/markets/portfolio");
  const cell = page
    .locator(".positions-table tbody tr")
    .filter({ hasText: "Hyperliquid" })
    .locator(".momentum-cell");
  await expect(cell).toContainText("61,7 / 100");
  await expect(cell).toContainText("Historique partiel");
});

for (const library of ["portfolio", "watchlist"]) {
  test(`ETF regression and momentum share settings with ${library}`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await mockApi(page);
    const etf = { ...stock, id: "etf-test", name: "ETF test", category: "etf" };
    await page.route("**/api/assets", (route) =>
      route.fulfill({ json: [stock, etf] }),
    );
    const etfReady = {
      ...ready,
      category: "etf",
      universe: [
        { id: etf.id, name: etf.name, scores: [null, 70, 20], partial: true },
      ],
    };
    await page.route("**/api/assets/etf-test/momentum*", (route) =>
      route.fulfill({ json: etfReady }),
    );
    const requests: string[] = [];
    await page.route("**/api/momentum*", (route) => {
      requests.push(route.request().url());
      return route.fulfill({
        json:
          new URL(route.request().url()).searchParams.get("category") === "etf"
            ? etfReady
            : ready,
      });
    });
    const regressionRequests: string[][] = [];
    await page.route("**/api/portfolio/regression", (route) => {
      const ids = route.request().postDataJSON().asset_ids as string[];
      regressionRequests.push(ids);
      return route.fulfill({
        json: {
          positions: ids.map((id) => ({
            id,
            z: -1.8,
            start: "2020-01-01",
            end: "2022-03-10",
          })),
        },
      });
    });
    await page.addInitScript(
      ({ library }) => {
        localStorage.setItem(
          "investor-favorites",
          JSON.stringify({
            "etf-test": library === "portfolio" ? "gold" : "silver",
            "yf-test": library === "portfolio" ? "gold" : "silver",
          }),
        );
      },
      { library },
    );
    await page.goto("/assets/etf-test");
    await page.getByRole("tab", { name: "Régression", exact: true }).click();
    await expect(
      page
        .getByRole("region", { name: "Retour à la tendance" })
        .locator("canvas")
        .first(),
    ).toBeVisible();
    await page.getByRole("tab", { name: "Momentum", exact: true }).click();
    const panel = page.getByRole("region", { name: "Momentum de l’ETF" });
    await expect(panel).toContainText("Tous les ETF");
    await expect(panel.getByLabel("Synthèse momentum")).toContainText(
      "49,2 / 100",
    );
    await expect(panel.getByLabel("Synthèse momentum")).toContainText(
      "Historique partiel",
    );
    await expect(
      panel.getByRole("img", {
        name: "Momentum : prix et régression logarithmique",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      panel.getByRole("img", {
        name: "Momentum : résidus logarithmiques autour de zéro",
        exact: true,
      }),
    ).toBeVisible();
    await page.getByLabel("Poids 12 mois (%)", { exact: true }).fill("100");
    await page.getByLabel("Poids 6 mois (%)", { exact: true }).fill("0");
    await page.getByLabel("Référence momentum").selectOption("^FCHI");
    await expect(panel.getByLabel("Synthèse momentum")).toContainText(
      "70 / 100",
    );
    await page.goto(`/markets/${library}`);
    const etfRow = page
      .locator(".positions-table tbody tr")
      .filter({ hasText: "ETF test" });
    await expect(etfRow.locator(".momentum-cell")).toContainText("70 / 100");
    await expect(etfRow.locator(".momentum-cell")).toContainText(
      "Historique partiel",
    );
    await expect(etfRow.locator(".regression-deviation")).toHaveAttribute(
      "data-z",
      "-1.8",
    );
    await expect
      .poll(() => regressionRequests.some((ids) => ids.includes("etf-test")))
      .toBe(true);
    await expect
      .poll(() =>
        requests.some(
          (url) =>
            url.includes("category=etf") && url.includes("benchmark=%5EFCHI"),
        ),
      )
      .toBe(true);
    await expect(
      page
        .locator(".positions-table tbody tr")
        .filter({ hasText: "Action test" })
        .locator(".momentum-cell"),
    ).toContainText("65,5 / 100");
    await page.reload();
    await expect(etfRow.locator(".momentum-cell")).toContainText("70 / 100");
    await expect(etfRow.locator(".regression-deviation")).toHaveAttribute(
      "data-z",
      "-1.8",
    );
    expect(errors).toEqual([]);
  });
}
