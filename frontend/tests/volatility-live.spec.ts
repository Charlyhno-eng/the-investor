import { test, expect } from "@playwright/test";

// Run against an isolated database snapshot with cached FX and ^SP500TR.
// INVESTOR_LIVE_VOLATILITY=1 npm test -- tests/volatility-live.spec.ts
// Never changes the user's portfolio: browser quantities belong to this test context.
test("real series and mixed portfolio have usable volatility charts", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.INVESTOR_LIVE_VOLATILITY !== "1",
    "Requires an isolated snapshot API on port 8000",
  );
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const quantities = {
    "yf-aapl": 4,
    "yf-msft": 2,
    "yf-btc-usd": 0.01,
    "wb-gold": 0.1,
    IRLTLT01FRM156N: 1,
  };
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
  for (const id of ["yf-aapl", "yf-btc-usd", "wb-gold", "IRLTLT01FRM156N"]) {
    await page.goto(`/assets/${id}`);
    await page
      .getByRole("tab", { name: "Frontières d’efficience", exact: true })
      .click();
    await expect(page.locator(".risk-table")).toContainText("S&P 500");
    await expect(
      page.getByRole("img", { name: /Frontière de Markowitz/ }),
    ).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
    if (id === "wb-gold") {
      const responsePromise = page.waitForResponse((r) =>
        r.url().includes("/volatility?years=1"),
      );
      await page.getByRole("button", { name: "1A", exact: true }).click();
      const result = await (await responsePromise).json();
      expect(result.observations).toBeGreaterThanOrEqual(12);
    }
  }
  await page.goto("/markets/portfolio");
  const responsePromise = page.waitForResponse((r) =>
    r.url().endsWith("/portfolio/volatility"),
  );
  await page
    .getByRole("tab", { name: "Frontières d’efficience", exact: true })
    .click();
  const initial = await (await responsePromise).json();
  expect(initial.status).toBe("ready");
  expect(initial.frequency).toBe("monthly");
  expect(initial.positions.length).toBe(4);
  expect(
    initial.positions.reduce(
      (sum: number, p: { weight: number }) => sum + p.weight,
      0,
    ),
  ).toBeCloseTo(1, 10);
  expect(initial.points.length).toBe(initial.positions.length + 1);
  expect(initial.frontier.length).toBeGreaterThan(1);
  expect(initial.frontier_assets).not.toContain("sp500");
  expect(
    initial.points.find((p: { id: string }) => p.id === "sp500").volatility,
  ).toBeGreaterThan(0);
  await expect(page.locator(".risk-marker")).toHaveCount(5);
  await expect(page.locator(".vol-panel").getByRole("checkbox")).toHaveCount(0);
  await expect(page.locator(".vol-exclusions")).toContainText(
    "aucun prix de titre",
  );
  await page
    .locator(".vol-panel")
    .screenshot({ path: testInfo.outputPath("markowitz-real-portfolio.png") });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  expect(
    JSON.parse(
      (await page.evaluate(() =>
        localStorage.getItem("investor-quantities"),
      )) ?? "{}",
    ),
  ).toEqual(quantities);
  expect(errors).toEqual([]);
});
