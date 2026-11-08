import { test, expect } from "@playwright/test";
import { simulateMad } from "../src/features/mad/strategy";
import { mockApi } from "./fixtures";

const series = (values: number[]) =>
  values.map((value, i) => ({
    time: new Date(Date.UTC(2020, 0, 1 + i)).toISOString().slice(0, 10),
    value,
  }));
const simulate = (values: number[], fee = 0) => {
  const points = series(values);
  return simulateMad(points, points[200].time, points.at(-1)!.time, fee);
};

test("MAD uses simple 21/200 means, prior history and next-close execution", () => {
  const result = simulate([...Array(199).fill(100), 121, 1, 80, 90]);
  // Positive signal at 199 buys at 200, despite the crash at that close.
  // Negative signal at 200 sells at 201, after the rebound to 80.
  expect(result.equity.map((p) => p.strategy)).toEqual([100, 8000, 8000]);
  expect(result.purchases).toBe(1);
  expect(result.sales).toBe(1);
  expect(result.exposure).toBe(0.5);
  expect(result.invested).toBe(false);
  expect(result.short[0].value).toBeCloseTo((19 * 100 + 121 + 1) / 21);
  expect(result.long[0].value).toBeCloseTo((198 * 100 + 121 + 1) / 200);
});

test("MAD fees, compounded capital and matching benchmark use known values", () => {
  const result = simulate([...Array(199).fill(100), 121, 1, 80, 90], 0.01);
  expect(result.equity.at(-1)!.strategy).toBeCloseTo((100 / 1.01) * 80 * 0.99);
  expect(result.equity.at(-1)!.benchmark).toBeCloseTo((100 / 1.01) * 90);
  expect(result.strategyReturn).toBeCloseTo((80 * 0.99) / 1.01 - 1);
  expect(result.assetReturn).toBe(89);
  const hold = simulate([...Array(199).fill(100), 121, 200, 400], 0.01);
  expect(hold.purchases).toBe(1);
  expect(hold.sales).toBe(0);
  expect(hold.exposure).toBe(1);
  expect(hold.equity.at(-1)!.strategy).toBeCloseTo(200 / 1.01);
});

test("MAD does not capture a rise before entry and stays in cash at equality", () => {
  const flat = simulate(Array(205).fill(100));
  expect(flat.purchases).toBe(0);
  expect(flat.strategyReturn).toBe(0);
  expect(flat.exposure).toBe(0);
  const rise = simulate([...Array(200).fill(100), 1000, 100, 50]);
  expect(rise.equity.map((p) => p.strategy)).toEqual([100, 100, 50]);
  expect(rise.purchases).toBe(1);
  expect(rise.exposure).toBe(0.5);
});

test("MAD is causal, invariant to units and measures calendar exposure", () => {
  const points = series([...Array(199).fill(100), 121, 1, 80, 90]);
  points[201].time = "2020-07-25";
  points[202].time = "2020-07-26";
  const result = simulateMad(points, points[200].time, points[202].time, 0);
  expect(result.exposure).toBeCloseTo(6 / 7);
  const future = [...points, { time: "2020-07-27", value: 1000000 }];
  expect(simulateMad(future, points[200].time, points[202].time, 0)).toEqual(
    result,
  );
  const scaled = simulateMad(
    points.map((p) => ({ ...p, value: p.value * 10 })),
    points[200].time,
    points[202].time,
    0,
  );
  expect(scaled.equity).toEqual(result.equity);
  expect(scaled.distance).toBeCloseTo(result.distance);
});

test("MAD rejects insufficient warmup, invalid periods, prices and fees", () => {
  const points = series(Array(205).fill(100));
  expect(() =>
    simulateMad(points, points[199].time, points[204].time, 0),
  ).toThrow(/200 observations/);
  expect(() =>
    simulateMad(points, points[204].time, points[200].time, 0),
  ).toThrow(/début doit précéder/);
  expect(() => simulateMad(points, points[204].time, "2025-01-01", 0)).toThrow(
    /deux observations/,
  );
  expect(() =>
    simulateMad(points, points[200].time, points[204].time, 1),
  ).toThrow(/frais/);
  points[203].value = 0;
  expect(() =>
    simulateMad(points, points[200].time, points[204].time, 0),
  ).toThrow(/positifs/);
});

for (const id of ["yf-test", "yf-btc-usd"]) {
  test(`MAD charts, fees and period controls for ${id}`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await mockApi(page);
    await page.goto(`/assets/${id}`);
    const tabs = await page.getByRole("tab").allTextContents();
    expect(tabs.indexOf("MAD 21/200")).toBe(tabs.indexOf("HMM") + 1);
    await page.getByRole("tab", { name: "MAD 21/200", exact: true }).click();
    const panel = page.getByRole("region", {
      name: "Stratégie MAD 21/200",
      exact: true,
    });
    await expect(
      panel.getByRole("img", {
        name: "Prix de l’actif et moyennes mobiles 21 et 200",
        exact: true,
      }),
    ).toBeVisible();
    const comparison = page.getByRole("region", {
      name: "Comparaison des performances MAD",
    });
    await expect(
      comparison.getByRole("img", {
        name: "Capital MAD et achat-conservation, base 100",
        exact: true,
      }),
    ).toBeVisible();
    await expect(panel).toContainText("600 observations");
    const fee = panel.getByRole("spinbutton", {
      name: "Frais par opération (%)",
      exact: true,
    });
    await expect(fee).toHaveValue(id === "yf-test" ? "0,50" : "0,01");
    const before = await comparison.locator(".reversion-summary").textContent();
    await fee.fill("0,00");
    await expect(comparison.locator(".reversion-summary")).not.toHaveText(
      before!,
    );
    await panel.getByLabel("Début de période").fill("2021-01-01");
    await expect(panel).toContainText("434 observations");
    await panel
      .getByText("Comprendre la stratégie et les pourcentages", { exact: true })
      .click();
    await expect(panel).toContainText(
      "adaptation de suivi de tendance sur un seul actif",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: test.info().outputPath(`mad-${id}.png`),
      fullPage: true,
    });
    await panel.getByLabel("Fin de période").fill("2020-01-02");
    await expect(panel.getByRole("alert")).toContainText("début doit précéder");
    await expect(panel.locator("canvas")).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test("MAD is absent for commodities and bonds", async ({ page }) => {
  await mockApi(page);
  for (const id of ["wb-gold", "bond-fr"]) {
    await page.goto(`/assets/${id}`);
    await expect(
      page.getByRole("tab", { name: "Vue du marché" }),
    ).toBeVisible();
    await expect(page.getByRole("tab", { name: "MAD 21/200" })).toHaveCount(0);
  }
});

test("MAD handles short histories explicitly", async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/assets/yf-test/history", (route) =>
    route.fulfill({ json: series(Array(100).fill(100)) }),
  );
  await page.goto("/assets/yf-test");
  await page.getByRole("tab", { name: "MAD 21/200" }).click();
  await expect(page.getByRole("alert")).toContainText("202 observations");
});
