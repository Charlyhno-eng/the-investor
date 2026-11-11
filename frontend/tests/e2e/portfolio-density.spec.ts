import { test, expect } from "@playwright/test";
import { mockApi, stock } from "./fixtures";

for (const count of [9, 500]) {
  test(`${count} assets have separated chart colors and fit the allocation or correlation frame`, async ({
    page,
  }, testInfo) => {
    test.setTimeout(60000);
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const assets = Array.from({ length: count }, (_, i) => ({
      ...stock,
      id: `position-${i}`,
      name: `Action ${String(i + 1).padStart(3, "0")}`,
    }));
    await mockApi(page);
    await page.route("**/api/assets", (r) => r.fulfill({ json: assets }));
    await page.route("**/api/portfolio/analytics", async (route) => {
      const body = route.request().postDataJSON();
      const positions = body.holdings.map(
        (h: { asset_id: string; quantity: number }) => ({
          id: h.asset_id,
          name: assets.find((a) => a.id === h.asset_id)!.name,
          quantity: h.quantity,
          price: 80,
          value: h.quantity * 80,
          weight: 1 / count,
          date: "2022-03-10",
        }),
      );
      await route.fulfill({
        json: {
          status: "ready",
          currency: "EUR",
          total: count * 80,
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
    });
    await page.addInitScript(
      ({ assets }) => {
        localStorage.setItem(
          "investor-favorites",
          JSON.stringify(Object.fromEntries(assets.map((a) => [a.id, "gold"]))),
        );
        localStorage.setItem(
          "investor-quantities",
          JSON.stringify(Object.fromEntries(assets.map((a) => [a.id, 1]))),
        );
      },
      { assets },
    );
    await page.goto("/markets/portfolio");
    await page
      .getByRole("region", { name: "Répartition du portefeuille", exact: true })
      .scrollIntoViewIfNeeded();
    const slices = page.locator(".allocation-slice");
    await expect(slices).toHaveCount(count);
    const colors = await slices.evaluateAll((items) =>
      items.map((item) => item.getAttribute("data-color")),
    );
    expect(new Set(colors).size).toBe(count);
    await page.screenshot({
      path: testInfo.outputPath(`allocation-${count}.png`),
      fullPage: true,
    });
    if (count === 9) return;
    await page.getByLabel("Rechercher dans la répartition").fill("Action 250");
    await expect(page.locator(".allocation-legend-item")).toHaveCount(1);
    await page.locator(".allocation-legend-item").click();
    await expect(page.locator(".donut-center")).toContainText("Action 250");
    await page.getByRole("tab", { name: "Corrélations", exact: true }).click();
    const matrix = page.locator(".correlation-viewport");
    await expect(matrix.locator("canvas")).toBeVisible();
    const dimensions = await matrix.evaluate((el) => ({
      height: el.clientHeight,
      width: el.clientWidth,
      scrollHeight: el.scrollHeight,
      scrollWidth: el.scrollWidth,
    }));
    expect(dimensions.height).toBeLessThanOrEqual(480);
    expect(dimensions.scrollHeight).toBe(dimensions.height);
    expect(dimensions.scrollWidth).toBe(dimensions.width);
    await page.getByLabel("Actif en ligne").selectOption("0");
    await page.getByLabel("Actif en colonne").selectOption("499");
    await expect(page.locator(".correlation-readout")).toContainText(
      "Action 001 ↔ Action 500",
    );
    await expect(page.locator(".correlation-readout")).toContainText("-0,5");
    await matrix.locator("canvas").focus();
    await matrix.locator("canvas").press("ArrowLeft");
    await expect(page.getByLabel("Actif en colonne")).toHaveValue("498");
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
    await page.screenshot({
      path: testInfo.outputPath("matrix-500.png"),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  });
}
