import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

for (const id of ["yf-test", "yf-btc-usd"]) {
  test(`prediction tab, continuous history, fixed model and probabilities for ${id}`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await mockApi(page);
    const history = Array.from({ length: 1200 }, (_, i) => ({
      time: new Date(Date.UTC(2023, 0, 1 + i)).toISOString().slice(0, 10),
      value:
        100 *
        Math.exp(i * 0.0003 + 0.08 * Math.sin(i / 15) + 0.01 * Math.sin(i * 2)),
    }));
    await page.route(`**/api/assets/${id}/history?*`, (route) =>
      route.fulfill({ json: history }),
    );
    await page.goto(`/assets/${id}`);
    const tab = page.getByRole("tab", { name: "Prédiction", exact: true });
    await tab.click();
    await expect(tab).toHaveAttribute("aria-selected", "true");
    const panel = page.getByRole("region", {
      name: "Prédiction de l’actif",
      exact: true,
    });
    await expect(panel.getByRole("img")).toBeVisible();
    await expect(panel.locator("select")).toHaveCount(0);
    await expect(panel.getByRole("heading")).toHaveCount(0);
    await expect(panel).not.toContainText("Projection au");
    await expect(panel.getByLabel("Résultats de la projection")).toContainText(
      "Médiane à 6 mois",
    );
    await expect(panel).toContainText("Zone centrale 90 % (P5–P95)");
    const paths = panel.locator("svg path");
    expect(await paths.count()).toBe(6);
    // History and every projection must share the exact same anchor coordinates.
    const historicalPath = await paths.nth(4).getAttribute("d");
    const medianPath = await paths.nth(5).getAttribute("d");
    expect(medianPath!.split(" L")[0].slice(1)).toBe(
      historicalPath!.split(" L").at(-1),
    );
    const explorer = panel.getByRole("slider");
    await explorer.focus();
    await explorer.press("End");
    await expect(panel.locator(".prediction-readout")).toContainText(
      "Zone 90 %",
    );
    await expect(panel).toContainText(
      "GARCH(1,1) · régression sur 3 ans · projection sur 6 mois",
    );
    await panel
      .getByText("Modèle quantitatif et limites", { exact: true })
      .click();
    await expect(panel).toContainText("4096 trajectoires gaussiennes");
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
    await page.screenshot({
      path: test.info().outputPath("prediction.png"),
      fullPage: true,
    });
    await page.getByRole("tab", { name: "Vue du marché", exact: true }).click();
    await expect(panel).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test("prediction reports insufficient history and stays limited to stocks and crypto", async ({
  page,
}) => {
  await mockApi(page);
  await page.route("**/api/assets/yf-test/history?*", (route) =>
    route.fulfill({
      json: [{ time: "2024-01-01", value: 100 }],
    }),
  );
  await page.goto("/assets/yf-test");
  await expect(
    page.getByRole("button", { name: "Dividendes uniquement", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("tab", { name: "Prédiction", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("61 cours");
  await expect(
    page.getByRole("region", { name: "Prédiction de l’actif" }).locator("svg"),
  ).toHaveCount(0);
  await page.goto("/assets/bond-fr");
  await expect(
    page.getByText("Dernier rendement annualisé décroissant"),
  ).toHaveCount(0);
  await expect(
    page.getByRole("tab", { name: "Prédiction", exact: true }),
  ).toHaveCount(0);
});

test("prediction exposes a history request failure", async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/assets/yf-test/history?*", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Historique temporairement indisponible" },
    }),
  );
  await page.goto("/assets/yf-test");
  await page.getByRole("tab", { name: "Prédiction", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Historique temporairement indisponible",
  );
});

for (const id of ["yf-test", "yf-btc-usd"]) {
  test(`prediction uses all short history for ${id}`, async ({ page }) => {
    await mockApi(page);
    await page.goto(`/assets/${id}`);
    await page.getByRole("tab", { name: "Prédiction", exact: true }).click();
    const panel = page.getByRole("region", { name: "Prédiction de l’actif" });
    await expect(panel.getByRole("img")).toBeVisible();
    await expect(panel).toContainText("Historique partiel : 800 cours");
    await expect(panel).toContainText("régression sur l’historique disponible");
    await expect(panel.getByRole("alert")).toHaveCount(0);
    await expect(panel.getByLabel("Résultats de la projection")).toContainText(
      "Médiane à 6 mois",
    );
  });
}
