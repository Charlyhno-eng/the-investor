import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

test("simulation opens below strategy, uses current quantities and preserves independent draft", async ({
  page,
}, testInfo) => {
  await mockApi(page);
  await page.addInitScript(() => {
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold" }),
    );
    localStorage.setItem(
      "investor-quantities",
      JSON.stringify({ "yf-test": 9 }),
    );
  });
  await page.route("**/api/simulation/scenarios", (route) =>
    route.fulfill({
      json: [
        {
          id: "covid",
          name: "Pandémie · Covid-like",
          start: "2020-01",
          tone: "stress",
          description: "Choc de pandémie",
        },
      ],
    }),
  );
  const requests: {
    holdings: { asset_id: string; quantity: number }[];
    months: number;
  }[] = [];
  await page.route("**/api/simulation/run", async (route) => {
    const body = route.request().postDataJSON();
    requests.push(body);
    await route.fulfill({
      json: {
        status: "ready",
        scenario: { id: "covid", name: "Pandémie · Covid-like" },
        total: 900,
        coverage: 1,
        excluded: [],
        historical_start: "2020-01",
        historical_end: "2021-01",
        paths: 600,
        seed: 42,
        calibration: { start: "2021-10", end: "2026-10", months: 61 },
        equity: Array.from({ length: 13 }, (_, i) => ({
          month: i,
          time: `2027-${String(i + 1).padStart(2, "0")}`,
          central: 900 - i * 10,
          p05: 900 - i * 20,
          p50: 900 - i * 9,
          p95: 900 + i * 10,
        })),
        metrics: {
          return: -0.13,
          p05_return: -0.26,
          p95_return: 0.13,
          drawdown: -0.13,
          drawdown_p05: -0.3,
          conditional_loss_share: 0.8,
        },
        positions: [
          {
            id: "yf-test",
            name: "Action test",
            value: 900,
            date: "2026-11-10",
            simulated_value: 780,
            simulated_return: -0.13,
            contribution: -0.13,
            r2: 0.6,
            validation_rmse: 0.04,
            betas: { SPY: 1.2 },
          },
        ],
        factors: [
          {
            symbol: "SPY",
            name: "Actions américaines",
            shock: -0.2,
            first: "1993-01",
            last: "2026-10",
            source: "https://finance.yahoo.com/quote/SPY/history/",
          },
        ],
        warnings: ["Scénario conditionnel, pas une prévision."],
      },
    });
  });
  await page.goto("/");
  const rail = page.locator(".category-rail");
  const names = await rail.getByRole("button").allTextContents();
  expect(names.findIndex((x) => x.includes("Simulation"))).toBe(
    names.findIndex((x) => x.includes("Stratégie")) + 1,
  );
  await rail.getByRole("button", { name: "Simulation", exact: true }).click();
  await expect(page).toHaveURL(/markets\/simulation/);
  await page.getByRole("button", { name: "Simuler ce portefeuille" }).click();
  await expect(
    page.getByRole("img", { name: /Évolution mensuelle/ }),
  ).toBeVisible();
  expect(requests[0].holdings).toEqual([{ asset_id: "yf-test", quantity: 9 }]);
  await expect(
    page.getByRole("heading", {
      name: "Impact par actif et qualité du modèle",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Hypothèses, incertitude et limites", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Valeurs mensuelles et médiane des trajectoires", {
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(
    page.locator(".simulation-scenario-list").getByRole("button"),
  ).toHaveCount(1);
  await expect(
    page.getByRole("heading", { name: "Sensibilités estimées par facteur" }),
  ).toBeVisible();
  expect(requests[0].months).toBe(12);
  const chart = page.getByRole("img", { name: /Évolution mensuelle/ });
  await chart.scrollIntoViewIfNeeded();
  const box = await chart.boundingBox();
  if (box)
    await page.mouse.move(
      box.x + box.width * (230 / 900),
      box.y + box.height / 2,
    );
  await expect(page.locator(".stress-readout")).toContainText("M+2");
  await expect(page.locator(".stress-readout")).toContainText("880");
  await page
    .getByRole("button", { name: "Définition : Variation", exact: true })
    .hover();
  await expect(page.getByRole("tooltip")).toContainText("Gain ou perte simulé");
  await page.screenshot({
    path: testInfo.outputPath("simulation.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Sur mesure", exact: true }).click();
  await page.getByRole("button", { name: "Copier mon portefeuille" }).click();
  await page.getByLabel("Quantité Action test", { exact: true }).fill("3");
  await page
    .getByLabel("Actif à ajouter", { exact: true })
    .selectOption("yf-btc-usd");
  await page.getByRole("button", { name: "Ajouter", exact: true }).click();
  await page.getByRole("button", { name: "Simuler ce portefeuille" }).click();
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[1].holdings).toEqual([
    { asset_id: "yf-test", quantity: 3 },
    { asset_id: "yf-btc-usd", quantity: 1 },
  ]);
  expect(
    await page.evaluate(() =>
      JSON.parse(localStorage.getItem("investor-quantities")!),
    ),
  ).toEqual({ "yf-test": 9 });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Simulation", exact: true, level: 1 }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sur mesure", exact: true }).click();
  await expect(
    page.getByLabel("Quantité Action test", { exact: true }),
  ).toHaveValue("3");
});

test("unavailable data produces a useful error without fabricated results", async ({
  page,
}) => {
  await mockApi(page);
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
  await page.route("**/api/simulation/scenarios", (route) =>
    route.fulfill({
      json: [
        {
          id: "covid",
          name: "Covid",
          start: "2020-01",
          tone: "stress",
          description: "Pandémie",
        },
      ],
    }),
  );
  await page.route("**/api/simulation/run", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Référence de marché indisponible" },
    }),
  );
  await page.goto("/markets/simulation");
  await page.getByRole("button", { name: "Simuler ce portefeuille" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Référence de marché indisponible",
  );
  await expect(
    page.getByRole("button", { name: "Simuler ce portefeuille" }),
  ).toBeEnabled();
  await expect(
    page.getByRole("img", { name: /Évolution mensuelle/ }),
  ).toHaveCount(0);
});

test("changing scenarios clears results and watchlist uses the same shock", async ({
  page,
}) => {
  await mockApi(page);
  await page.addInitScript(() => {
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold", "yf-btc-usd": "silver" }),
    );
    localStorage.setItem(
      "investor-quantities",
      JSON.stringify({ "yf-test": 2 }),
    );
  });
  const scenarios = ["covid", "ai"].map((id) => ({
    id,
    name: id === "ai" ? "Crise IA" : "Pandémie",
    start: "2021-12",
    tone: "stress",
    description: "Choc empirique",
  }));
  await page.route("**/api/simulation/scenarios", (route) =>
    route.fulfill({ json: scenarios }),
  );
  function result(scenario: string, watch = false) {
    return {
      status: "ready",
      scenario: scenarios.find((s) => s.id === scenario),
      total: 10000,
      coverage: 1,
      excluded: [],
      historical_start: "2021-12",
      historical_end: "2022-12",
      paths: 600,
      seed: 42,
      calibration: { start: "2021-10", end: "2026-10", months: 61 },
      equity: Array.from({ length: 13 }, (_, month) => ({
        month,
        time: "2027-01",
        central: 10000 - month * 100,
        p05: 10000 - month * 200,
        p50: 10000 - month * 90,
        p95: 10000 + month * 100,
      })),
      metrics: {
        return: -0.12,
        p05_return: -0.24,
        p95_return: 0.12,
        drawdown: -0.12,
        drawdown_p05: -0.24,
        conditional_loss_share: 0.8,
      },
      positions: [
        {
          id: watch ? "yf-btc-usd" : "yf-test",
          name: watch ? "Bitcoin" : "Action test",
          value: 10000,
          date: "2026-11-10",
          simulated_value: 8800,
          simulated_return: -0.12,
          contribution: -0.12,
          r2: 0.7,
          validation_rmse: 0.03,
          betas: { SPY: 1 },
        },
      ],
      factors: [
        {
          symbol: "SPY",
          name: "Actions américaines",
          shock: -0.12,
          first: "1993-01",
          last: "2026-10",
          source: "https://finance.yahoo.com/quote/SPY/history/",
        },
      ],
      warnings: [],
    };
  }
  const watchRequests: { scenario: string; asset_ids: string[] }[] = [];
  await page.route("**/api/simulation/run", (route) =>
    route.fulfill({ json: result(route.request().postDataJSON().scenario) }),
  );
  await page.route("**/api/simulation/watchlist", (route) => {
    const body = route.request().postDataJSON();
    watchRequests.push(body);
    return route.fulfill({
      json: {
        status: "ready",
        results: [result(body.scenario, true)],
        excluded: [],
      },
    });
  });
  await page.goto("/markets/simulation");
  await page.getByRole("button", { name: "Simuler ce portefeuille" }).click();
  const target = page.locator(".simulation-chart-target");
  await expect(target).toBeVisible();
  await expect
    .poll(async () => {
      const box = await target.boundingBox();
      return box !== null && box.y >= -5 && box.y < 150;
    })
    .toBe(true);
  const watch = page.getByRole("region", {
    name: "Résistance de la watchlist",
  });
  await expect(
    watch.getByRole("cell", { name: "Bitcoin", exact: true }),
  ).toBeVisible();
  await expect(watch.getByRole("img")).toHaveCount(0);
  expect(watchRequests[0]).toMatchObject({
    scenario: "covid",
    asset_ids: ["yf-btc-usd"],
  });
  await expect(
    watch.getByText("Ce qui explique la réaction estimée", { exact: true }),
  ).toHaveCount(0);
  await page
    .locator(".simulation-scenario-list")
    .getByRole("button", { name: /Crise IA/ })
    .click();
  await expect(
    page.getByRole("region", { name: "Résultats de simulation" }),
  ).toHaveCount(0);
  await expect(watch).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Simuler ce portefeuille" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Simuler ce portefeuille" }).click();
  await expect
    .poll(() => watchRequests.some((r) => r.scenario === "ai"))
    .toBe(true);
});
