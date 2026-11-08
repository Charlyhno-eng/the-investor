import { test, expect } from "@playwright/test";
import {
  compareRegressionStrategy,
  fitRegression,
} from "../src/features/reversion/regression";
import { mockApi } from "./fixtures";

const series = (values: number[]) =>
  values.map((value, i) => ({
    time: new Date(Date.UTC(2020, 0, 1 + i)).toISOString().slice(0, 10),
    value,
  }));

const bandRows = (values: number[]) =>
  series(values).map((point) => ({
    ...point,
    lower: 90,
    upper: 110,
    z: (point.value - 100) / 10,
  }));

test("band strategy includes touches, holds between signals and reinvests sale proceeds", () => {
  const result = compareRegressionStrategy(
    bandRows([100, 90, 80, 100, 110, 120, 90, 95]),
  );
  expect(result.purchases).toBe(2);
  expect(result.sales).toBe(1);
  expect(result.invested).toBe(true);
  expect(result.equity.map((p) => p.strategy)).toEqual([
    100,
    100,
    (100 / 90) * 80,
    (100 / 90) * 100,
    (100 / 90) * 110,
    (100 / 90) * 110,
    (100 / 90) * 110,
    (((100 / 90) * 110) / 90) * 95,
  ]);
  expect(result.benchmark.capital).toBeCloseTo(95);
  expect(result.strategy.totalReturn).toBeCloseTo((110 / 90) * (95 / 90) - 1);
  expect(result.strategy.maxDrawdown).toBeCloseTo(80 / 90 - 1);
  expect(result.exposure).toBeCloseTo(4 / 7);
});

test("fees apply to executed notional and exposure measures calendar holding time", () => {
  const rows = bandRows([80, 120, 130]);
  rows[1].time = "2020-01-04";
  rows[2].time = "2020-01-05";
  const result = compareRegressionStrategy(rows, 0.001, 0.002);
  expect(result.strategy.capital).toBeCloseTo(
    (100 / (80 * 1.001)) * 120 * 0.998,
    10,
  );
  expect(result.benchmark.capital).toBeCloseTo((100 / (80 * 1.001)) * 130, 10);
  expect(result.exposure).toBe(0.75);
  const noEntry = compareRegressionStrategy(
    bandRows([100, 105, 110]),
    0.001,
    0.002,
  );
  expect(noEntry.exposure).toBe(0);
  expect(noEntry.strategy.capital).toBe(100);
  const lastEntry = compareRegressionStrategy(bandRows([100, 105, 80]));
  expect(lastEntry.invested).toBe(true);
  expect(lastEntry.exposure).toBe(0);
});

test("overshoots execute at observed prices and no entry stays in cash", () => {
  const result = compareRegressionStrategy(bandRows([80, 120, 130]));
  expect(result.strategy.capital).toBe(150);
  expect(result.sales).toBe(1);
  expect(result.invested).toBe(false);
  const noEntry = compareRegressionStrategy(bandRows([100, 110, 105]));
  expect(noEntry.strategy.capital).toBe(100);
  expect(noEntry.purchases).toBe(0);
  expect(noEntry.sales).toBe(0);
  expect(noEntry.benchmark.capital).toBe(105);
});

test("zero dispersion produces no trades, and threshold changes the comparison", () => {
  const flat = fitRegression(series(Array(40).fill(100)), "log", 0);
  expect(compareRegressionStrategy(flat.rows).purchases).toBe(0);
  const points = series(
    Array.from({ length: 80 }, (_, i) => 100 + 5 * Math.sin(i)),
  );
  expect(
    compareRegressionStrategy(fitRegression(points, "linear", 2).rows)
      .purchases,
  ).toBe(0);
  expect(
    compareRegressionStrategy(fitRegression(points, "linear", 0.5).rows).sales,
  ).toBeGreaterThan(0);
});

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
