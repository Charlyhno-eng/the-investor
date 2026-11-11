import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

async function prepare(page: import("@playwright/test").Page) {
  await mockApi(page);
  await page.addInitScript(() => {
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold", "yf-btc-usd": "gold" }),
    );
    localStorage.setItem(
      "investor-quantities",
      JSON.stringify({ "yf-test": 2, "yf-btc-usd": 0.5 }),
    );
  });
}

test("allocation is below positions and portfolio prediction uses the shared model in euros", async ({
  page,
}) => {
  await prepare(page);
  const requests: unknown[] = [];
  const history = Array.from({ length: 180 }, (_, i) => ({
    time: new Date(Date.UTC(2026, 0, 1 + i)).toISOString().slice(0, 10),
    value: 1000 * Math.exp(i * 0.0008 + 0.06 * Math.sin(i / 14)),
  }));
  await page.route("**/api/portfolio/prediction", (route) => {
    requests.push(route.request().postDataJSON());
    return route.fulfill({
      json: {
        status: "ready",
        series: [
          {
            id: "test",
            name: "Test",
            points: history,
            crypto: false,
            value: 1500,
            price_date: history.at(-1)!.time,
          },
        ],
        current_total: 1500,
        current_price_dates: [history.at(-1)!.time, "2026-06-30"],
      },
    });
  });
  await page.goto("/markets/portfolio");
  await expect(
    page.getByRole("tab", { name: "Positions", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("tab", { name: "Répartition", exact: true }),
  ).toHaveCount(0);
  const allocation = page.getByRole("region", {
    name: "Répartition du portefeuille",
    exact: true,
  });
  await expect(allocation.locator(".allocation-slice")).toHaveCount(2);
  const positionsBounds = (await page
    .locator(".positions-table")
    .boundingBox())!;
  const allocationBounds = (await allocation.boundingBox())!;
  expect(allocationBounds.y).toBeGreaterThan(
    positionsBounds.y + positionsBounds.height,
  );
  await expect(allocation).toHaveCSS("border-top-width", "2px");
  await page.getByRole("tab", { name: "Prédiction", exact: true }).click();
  const panel = page.getByRole("region", {
    name: "Prédiction du portefeuille",
    exact: true,
  });
  await expect(panel.getByRole("img")).toBeVisible();
  expect(requests.length).toBeGreaterThan(0);
  for (const request of requests)
    expect(request).toEqual({
      holdings: [
        { asset_id: "yf-test", quantity: 2 },
        { asset_id: "yf-btc-usd", quantity: 0.5 },
      ],
    });
  await expect(panel).not.toContainText("Historique partiel :");
  await expect(panel).toContainText("Médiane à 6 mois");
  const projection = page.getByRole("region", {
    name: "Projection du portefeuille",
    exact: true,
  });
  await expect(projection).not.toContainText("Historique commun du");
  await expect(panel).toContainText("EUR");
  await expect(panel.locator("select")).toHaveCount(0);
  const paths = panel.locator("svg path");
  const original = (await paths.nth(4).getAttribute("d"))!;
  const forecast = (await paths.nth(5).getAttribute("d"))!;
  expect(forecast.split(" L")[0].slice(1)).toBe(original.split(" L").at(-1));
  await panel.getByRole("slider").focus();
  await panel.getByRole("slider").press("End");
  await expect(panel.locator(".prediction-readout")).toContainText("Zone 90 %");
  await expect(
    page.getByRole("region", {
      name: "Projection du portefeuille",
      exact: true,
    }),
  ).toContainText("Quantités et taux de change constants");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: test.info().outputPath("portfolio-prediction.png"),
    fullPage: true,
  });
  await page.getByRole("tab", { name: "Positions", exact: true }).click();
  await page.getByLabel("Quantité Action test", { exact: true }).fill("3");
  await page.getByRole("tab", { name: "Prédiction", exact: true }).click();
  await expect
    .poll(() => requests.at(-1))
    .toEqual({
      holdings: [
        { asset_id: "yf-test", quantity: 3 },
        { asset_id: "yf-btc-usd", quantity: 0.5 },
      ],
    });
});

test("portfolio prediction explains missing positions and retries API failures", async ({
  page,
}) => {
  await prepare(page);
  let fail = true;
  await page.route("**/api/portfolio/prediction", (route) => {
    if (fail)
      return route.fulfill({
        status: 500,
        json: { detail: "Historique indisponible" },
      });
    return route.fulfill({
      json: {
        status: "insufficient",
        message:
          "La prédiction du portefeuille entier nécessite un prix exploitable pour chaque position.",
        excluded: [
          {
            id: "missing",
            name: "Actif manquant",
            reason: "Prix actuel indisponible.",
          },
        ],
      },
    });
  });
  await page.goto("/markets/portfolio");
  await page.getByRole("tab", { name: "Prédiction", exact: true }).click();
  const projection = page.getByRole("region", {
    name: "Projection du portefeuille",
    exact: true,
  });
  await expect(projection.getByRole("alert")).toContainText(
    "Historique indisponible",
  );
  fail = false;
  await projection
    .getByRole("button", { name: "Réessayer", exact: true })
    .click();
  await expect(projection).toContainText(
    "Actif manquant : Prix actuel indisponible.",
  );
  await expect(projection.getByRole("img")).toHaveCount(0);
});
