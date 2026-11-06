import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

for (const [id, available] of [
  ["yf-test", true],
  ["yf-btc-usd", true],
  ["wb-gold", false],
  ["bond-fr", false],
] as const) {
  test(`HMM availability for ${id}`, async ({ page }) => {
    const { analysisRequests } = await mockApi(page);
    await page.goto(`/assets/${id}`);
    await expect(page.locator(".chart-panel canvas").first()).toBeVisible();
    await expect(
      page.getByRole("tab", { name: "HMM", exact: true }),
    ).toHaveCount(available ? 1 : 0);
    await expect(
      page.getByRole("tab", { name: "Régression", exact: true }),
    ).toHaveCount(available ? 1 : 0);
    expect(analysisRequests).toHaveLength(0);
  });
}

test("opens the workspace without selecting an asset, including after reload", async ({
  page,
}) => {
  const { historyRequests } = await mockApi(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Votre espace de recherche" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator(".asset-list [aria-current]")).toHaveCount(0);
  expect(historyRequests).toHaveLength(0);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Votre espace de recherche" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
  expect(historyRequests).toHaveLength(0);
});

test("selects assets explicitly and returns home via the brand", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("link", { name: /Action test/ }).click();
  await expect(page).toHaveURL(/\/assets\/yf-test$/);
  await expect(page.locator(".chart-panel canvas").first()).toBeVisible();
  await page.getByRole("link", { name: /the investor/ }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator(".asset-detail")).toHaveCount(0);
  await page.getByRole("button", { name: "Matières", exact: true }).click();
  await expect(page).toHaveURL(/\/markets\/commodity$/);
  await expect(page.locator(".asset-detail")).toHaveCount(0);
});

test("HMM keeps date selection and shows the comparison only after running", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const { analysisRequests } = await mockApi(page);
  await page.goto("/assets/yf-test");
  await page.getByRole("tab", { name: "HMM", exact: true }).click();
  await expect(page.locator(".timeline-selector svg")).toBeVisible();
  const chart = page.getByRole("region", {
    name: "Comparaison des performances",
  });
  await expect(chart).toHaveCount(0);
  const inputs = page.locator(".parameters input");
  await expect(inputs).toHaveCount(5);
  const fee = inputs.first();
  await expect(fee).toHaveValue("0.1");
  await expect(inputs.nth(1)).toHaveValue("80");
  await expect(inputs.nth(2)).toHaveValue("50");
  await expect(inputs.nth(3)).toHaveValue("5");
  await expect(inputs.nth(4)).toHaveValue("3");
  await inputs.nth(3).fill("");
  await expect(inputs.nth(3)).toHaveValue("");
  await inputs.nth(3).fill("4");
  await inputs.nth(3).press("Tab");
  await expect(inputs.nth(4)).toHaveValue("3");
  await inputs.nth(4).fill("2");
  await inputs.nth(4).press("Tab");
  await expect(inputs.nth(3)).toHaveValue("4");
  await expect(
    page.getByText("LABORATOIRE QUANTITATIF", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Écart de prix estimé", { exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText("Confirmation", { exact: true })).toHaveCount(0);
  await expect(
    page.locator(
      ".model-badge,.lab-description,.analysis-duration,.run-bar .fine-print",
    ),
  ).toHaveCount(0);
  await fee.fill("");
  await expect(fee).toHaveValue("");
  await fee.fill("0.2");
  await fee.press("Tab");
  await expect(fee).toHaveValue("0.2");
  await page.getByRole("button", { name: "Lancer la simulation" }).click();
  await expect(chart).toBeVisible();
  await expect(chart.getByText("Stratégie HMM", { exact: true })).toBeVisible();
  await expect(
    chart.getByText("Actif · achat et conservation", { exact: true }),
  ).toBeVisible();
  await expect(
    chart.getByRole("img", {
      name: "Capital de la stratégie et du marché, base 100",
    }),
  ).toBeVisible();
  await expect(chart.locator("canvas").first()).toBeVisible();
  expect(analysisRequests[0].fee_bps).toBe(20);
  expect(analysisRequests[0].entry_confirmation).toBe(4);
  expect(analysisRequests[0].exit_confirmation).toBe(2);
  expect(analysisRequests[0].slippage_bps).toBe(0);
  expect(analysisRequests[0].entry_probability).toBe(0.8);
  expect(analysisRequests[0].exit_probability).toBe(0.5);
  await chart.scrollIntoViewIfNeeded();
  await page.screenshot({ path: test.info().outputPath("comparison.png") });
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.getByLabel("Fin entraînement").fill("2021-05-01");
  await expect(chart).toBeVisible();
  await expect.poll(() => analysisRequests.length).toBe(2);
  await expect
    .poll(() => analysisRequests.at(-1)?.train_end)
    .toBe("2021-05-01");
  await expect(page.locator(".analysis-output")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await fee.fill("0.3");
  // No blur or manual launch: valid input must refresh the retained chart.
  await expect.poll(() => analysisRequests.at(-1)?.fee_bps).toBe(30);
  await expect(chart).toBeVisible();
  expect(errors).toEqual([]);
});

test("HMM serializes rapid edits and displays the latest result", async ({
  page,
}) => {
  const { analysisRequests } = await mockApi(page);
  let inFlight = 0,
    maxInFlight = 0,
    started = 0;
  await page.route("**/api/assets/*/analysis", async (route) => {
    inFlight++;
    started++;
    maxInFlight = Math.max(maxInFlight, inFlight);
    await new Promise((resolve) => setTimeout(resolve, 900));
    await route.fallback();
    inFlight--;
  });
  await page.goto("/assets/yf-test");
  await page.getByRole("tab", { name: "HMM", exact: true }).click();
  await page.getByRole("button", { name: "Lancer la simulation" }).click();
  await expect.poll(() => started).toBe(1);
  const fee = page.locator(".parameters input").first();
  await fee.fill("0.3");
  await fee.fill("0.4");
  await expect.poll(() => analysisRequests.at(-1)?.fee_bps).toBe(40);
  await expect(page.locator(".analysis-output")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  expect(maxInFlight).toBe(1);
  expect(analysisRequests).toHaveLength(2);
  await expect(
    page.getByRole("region", { name: "Comparaison des performances" }),
  ).toBeVisible();
});
