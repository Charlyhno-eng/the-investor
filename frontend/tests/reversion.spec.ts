import { test, expect } from "@playwright/test";
import { fitRegression } from "../src/features/reversion/regression";
import { mockApi } from "./fixtures";

const series = (values: number[]) =>
  values.map((value, i) => ({
    time: new Date(Date.UTC(2020, 0, 1 + i)).toISOString().slice(0, 10),
    value,
  }));

test("OLS recovers a known straight line and handles zero residual variance", () => {
  const fit = fitRegression(
    series(Array.from({ length: 60 }, (_, i) => 10 + 2 * i)),
    "linear",
    1,
  );
  expect(fit.slope).toBeCloseTo(2 * 365.25, 8);
  expect(fit.r2).toBeCloseTo(1, 10);
  expect(fit.rows[59].trend).toBeCloseTo(128, 10);
  expect(fit.degenerate).toBe(true);
  expect(fit.rows.every((p) => p.z === null && p.zone === "neutral")).toBe(
    true,
  );
});

test("log regression recovers compound growth and is invariant to price units", () => {
  const values = Array.from({ length: 80 }, (_, i) =>
    Math.exp(2 + 0.002 * i + 0.03 * Math.sin(i)),
  );
  const fit = fitRegression(series(values), "log", 1);
  const scaled = fitRegression(series(values.map((v) => v * 1000)), "log", 1);
  expect(fit.slope).toBeCloseTo(0.002 * 365.25, 2);
  expect(fit.rows.some((p) => p.zone === "entry")).toBe(true);
  expect(fit.rows.some((p) => p.zone === "exit")).toBe(true);
  for (let i = 0; i < values.length; i++) {
    expect(scaled.rows[i].z).toBeCloseTo(fit.rows[i].z!, 8);
    expect(scaled.rows[i].trend / 1000).toBeCloseTo(fit.rows[i].trend, 8);
  }
  const wider = fitRegression(series(values), "log", 2);
  expect(wider.rows.filter((p) => p.zone !== "neutral").length).toBeLessThan(
    fit.rows.filter((p) => p.zone !== "neutral").length,
  );
});

test("rejects insufficient and invalid prices; flat prices produce no spurious zones", () => {
  expect(() => fitRegression(series([1, 2]), "linear", 0)).toThrow(
    /30 observations/,
  );
  expect(() => fitRegression(series(Array(40).fill(0)), "log", 0)).toThrow(
    /positifs/,
  );
  const fit = fitRegression(series(Array(40).fill(100)), "log", 0);
  expect(fit.r2).toBeNull();
  expect(fit.rows.every((p) => p.zone === "neutral")).toBe(true);
});

for (const id of ["yf-test", "yf-btc-usd"]) {
  test(`regression controls, chart and invalid period for ${id}`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const { analysisRequests } = await mockApi(page);
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
    await expect(page.getByLabel("Seuil des zones")).toHaveValue("2");
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
    expect(analysisRequests).toHaveLength(0);
    expect(errors).toEqual([]);
  });
}
