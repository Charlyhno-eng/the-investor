import { test, expect } from "@playwright/test";

test("real GTT analysis, dividend persistence and library restoration", async ({
  page,
  request,
}) => {
  test.skip(
    !process.env.INVESTOR_LIVE_HMM,
    "Requires an isolated snapshot API on port 8000",
  );
  test.setTimeout(60000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await request.patch("/api/assets/yf-gtt.pa/dividend-status", {
    data: { is_dividend: false },
  });
  await page.goto("/assets/yf-gtt.pa");
  await expect(page.locator(".asset-detail h1")).toContainText("Gaztransport");
  await page.getByRole("tab", { name: "HMM", exact: true }).click();
  const response = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/assets/yf-gtt.pa/analysis") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Lancer la simulation" }).click();
  const analysisResponse = await response;
  expect(analysisResponse.status()).toBe(200);
  const result = await analysisResponse.json();
  expect(result.model_version).toBe("hmm-two-state-dominant-filtered-live-v3");
  expect(result.states).toHaveLength(2);
  expect(result.trades).toHaveLength(34);
  expect(result.strategy_metrics.total_return).toBeCloseTo(
    0.40320584794628034,
    6,
  );
  expect(result.diagnostics.entry_reachable).toBe(true);
  await expect(page.locator(".performance-summary")).toContainText("+40,32");
  await expect(page.locator(".performance-summary")).toContainText("34");
  await expect(page.getByText(/Aucun achat possible/)).toHaveCount(0);
  await expect(page.getByText(/Deux états fixes/)).toHaveCount(0);
  await page.locator(".performance-chart").scrollIntoViewIfNeeded();
  await page.screenshot({ path: test.info().outputPath("gtt-real-hmm.png") });
  await page
    .getByRole("button", { name: "Action à dividende", exact: true })
    .click();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Action à dividende", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: /Retirer Gaztransport.*de la liste/ })
    .click();
  await page.getByRole("button", { name: "Actions", exact: true }).click();
  await expect(
    page.locator('.asset-list a[href="/assets/yf-gtt.pa"]'),
  ).toHaveCount(0);
  await page.reload();
  // Discovery alone is stubbed so this local regression never depends on Yahoo.
  await page.route("**/api/stocks/search?*", (route) =>
    route.fulfill({
      json: {
        results: [
          {
            symbol: "GTT.PA",
            name: "Gaztransport & Technigaz SA",
            exchange: "Paris",
            imported: true,
          },
        ],
        warning: null,
      },
    }),
  );
  await page
    .locator(".library-heading")
    .getByRole("button", { name: "Ajouter une action" })
    .click();
  await page.getByRole("textbox", { name: "Nom ou symbole" }).fill("GTT.PA");
  await page.getByRole("button", { name: /Gaztransport.*Réajouter/ }).click();
  await page.getByRole("button", { name: "Réajouter à la liste" }).click();
  await expect(page.locator(".asset-detail h1")).toContainText("Gaztransport");
  await expect(
    page.getByRole("button", { name: "Action à dividende", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  expect(errors).toEqual([]);
});
