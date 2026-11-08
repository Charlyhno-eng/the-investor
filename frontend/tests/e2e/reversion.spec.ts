import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

for (const id of ["yf-test", "yf-btc-usd"]) {
  test(`regression controls, chart and invalid period for ${id}`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await mockApi(page);
    await page.goto(`/assets/${id}`);
    await page.getByRole("tab", { name: "Régression", exact: true }).click();
    const panel = page.getByRole("region", { name: "Retour à la tendance" });
    await expect(
      panel.getByRole("img", {
        name: "Prix, tendance ajustée et zones de retour à la tendance",
        exact: true,
      }),
    ).toBeVisible();
    await expect(panel.locator("canvas").first()).toBeVisible();
    await expect(page.getByLabel("Diagnostic de la régression")).toContainText(
      "800 observations",
    );
    await expect(page.getByLabel("Seuil des zones")).toHaveValue("1.5");
    const comparison = page.getByRole("region", {
      name: "Comparaison des stratégies de régression",
    });
    await expect(
      comparison.getByRole("img", {
        name: "Capital des bandes de régression et de l’achat-conservation, base 100",
        exact: true,
      }),
    ).toBeVisible();
    await expect(comparison).toContainText("Achat à −1,5 σ · vente à +1,5 σ");
    await page.getByLabel("Seuil des zones").selectOption("2");
    await expect(comparison).toContainText("0 achats · 0 ventes");
    const canvas = panel.locator("canvas").first();
    await canvas.scrollIntoViewIfNeeded();
    const bounds = await canvas.boundingBox();
    await page.mouse.move(
      bounds!.x + bounds!.width / 2,
      bounds!.y + bounds!.height / 2,
    );
    await expect(panel.locator(".chart-trend-tooltip")).toContainText(
      "Écart :",
    );
    await expect(panel.locator(".chart-trend-tooltip")).toContainText("%");
    const tooltip = await panel.locator(".chart-trend-tooltip").boundingBox();
    expect(tooltip!.y).toBeLessThan(bounds!.y + bounds!.height);
    expect(Math.abs(tooltip!.x - (bounds!.x + bounds!.width / 2))).toBeLessThan(
      230,
    );
    await page.getByLabel("Seuil des zones").selectOption("1");
    await expect(comparison).toContainText("Achat à −1 σ · vente à +1 σ");
    await expect(comparison).not.toContainText("0 achats · 0 ventes");
    await page.getByLabel("Ajustement", { exact: true }).selectOption("linear");
    await page.getByLabel("Début de période").fill("2021-01-01");
    await expect(page.getByLabel("Diagnostic de la régression")).toContainText(
      "434 observations",
    );
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
    await page.screenshot({ path: test.info().outputPath("regression.png") });
    await page.getByLabel("Fin de période").fill("2020-01-02");
    await expect(panel.getByRole("alert")).toContainText("début doit précéder");
    await expect(panel.locator("canvas")).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test("regression exposes time invested and editable fees with two decimal places", async ({
  page,
}, testInfo) => {
  await mockApi(page);
  await page.goto("/assets/yf-test");
  await page.getByRole("tab", { name: "Régression", exact: true }).click();
  const comparison = page.getByRole("region", {
    name: "Comparaison des stratégies de régression",
  });
  await expect(comparison.locator(".reversion-summary > div")).toHaveCount(4);
  await expect(comparison).toContainText("Temps d’exposition");
  const fee = comparison.getByRole("spinbutton", {
    name: "Frais (%)",
    exact: true,
  });
  await expect(comparison.getByRole("spinbutton")).toHaveCount(1);
  await expect(comparison).not.toContainText("Capital final");
  const options = page.getByLabel("Seuil des zones").locator("option");
  expect(
    await options.evaluateAll((items) =>
      items.map((item) => (item as HTMLOptionElement).value),
    ),
  ).toEqual(["0", "0.5", "1", "1.2", "1.4", "1.5", "1.6", "1.8", "2"]);
  await page.getByLabel("Seuil des zones").selectOption("1.2");
  await expect(comparison).toContainText("Achat à −1,2 σ");
  await expect(fee).toHaveValue("0,10");
  const before = await comparison.locator(".reversion-summary").textContent();
  await fee.fill("0,00");
  await fee.blur();
  await expect(fee).toHaveValue("0,00");
  await expect(comparison.locator(".reversion-summary")).not.toHaveText(
    before!,
  );
  await comparison
    .getByRole("button", { name: "Augmenter frais", exact: true })
    .click();
  await expect(fee).toHaveValue("0,01");
  await fee.press("ArrowUp");
  await expect(fee).toHaveValue("0,02");
  await comparison
    .getByRole("button", { name: "Diminuer frais", exact: true })
    .click();
  await expect(fee).toHaveValue("0,01");
  await expect(comparison).not.toContainText(
    "Simulation rétrospective : les bandes",
  );
  await comparison.screenshot({
    path: testInfo.outputPath("regression-fees-exposure.png"),
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
