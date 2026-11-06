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
    page.getByRole("heading", { name: "Portfolio", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator(".asset-list [aria-current]")).toHaveCount(0);
  expect(historyRequests).toHaveLength(0);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Portfolio", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
  expect(historyRequests).toHaveLength(0);
});

test("selects assets explicitly and returns home via the brand", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/");
  await expect(
    page
      .locator(".header-actions")
      .getByRole("button", { name: "Ajouter une action" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Actions", exact: true }).click();
  await page.getByRole("link", { name: /Action test/ }).click();
  await expect(page).toHaveURL(/\/assets\/yf-test$/);
  await expect(page.locator(".chart-panel canvas").first()).toBeVisible();
  await expect(page.locator(".asset-subtitle")).toContainText("France");
  await page.getByRole("link", { name: /the investor/ }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator(".asset-detail")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Portfolio", exact: true }),
  ).toBeVisible();
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
  await expect(inputs).toHaveCount(1);
  const fee = inputs.first();
  await expect(fee).toHaveValue("0.5");
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
  expect(Object.keys(analysisRequests[0]).sort()).toEqual(
    ["train_start", "train_end", "test_start", "test_end", "fee_bps"].sort(),
  );
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

test("HMM exposes near-conservation behavior and separates regimes from positions", async ({
  page,
}) => {
  const days = ["2022-01-01", "2022-01-02", "2022-01-03", "2022-01-04"];
  await mockApi(page, {
    exposure: 0.9967,
    strategy_metrics: { total_return: 0.3068 },
    benchmark_metrics: { total_return: 0.2999 },
    regimes: days.map((time, i) => ({
      time,
      state: i < 2 ? "Hausse" : "Neutre / baisse",
      probabilities: i < 2 ? [0, 1] : [1, 0],
    })),
    positions: days.map((time, i) => ({ time, position: i === 3 ? 0 : 1 })),
    diagnostics: {
      exit_reachable: false,
      negative_states: 1,
      negative_dominant_observations: 2,
      negative_dominant_while_held: 2,
      negative_dominant_without_exit_while_held: 2,
      exit_signal_observations: 0,
      net_excess_return: 0.0069,
      nearly_always_invested: true,
      nearly_always_cash: false,
    },
  });
  await page.goto("/assets/yf-test");
  await page.getByRole("tab", { name: "HMM", exact: true }).click();
  await page.getByRole("button", { name: "Lancer la simulation" }).click();
  const assessment = page.getByLabel("Évaluation face à la conservation");
  await expect(assessment).toContainText("+0,69 points");
  await expect(assessment).toContainText("Exposition presque permanente");
  await expect(assessment).toContainText("Aucune sortie de régime possible");
  const timeline = page.getByRole("region", {
    name: "Régimes détectés et positions",
  });
  await expect(timeline).toBeVisible();
  await expect(
    timeline
      .getByRole("img", { name: "Régime dominant", exact: true })
      .locator("span"),
  ).toHaveCount(2);
  await expect(
    timeline
      .getByRole("img", { name: "Position après clôture", exact: true })
      .locator("span")
      .first(),
  ).toHaveAttribute("title", /Investi · 3 observations/);
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
});

for (const [id, fee, bps] of [
  ["yf-test", "0.5", 50],
  ["yf-btc-usd", "0.01", 1],
] as const) {
  test(`HMM defaults and compact controls for ${id}`, async ({
    page,
    isMobile,
  }) => {
    const { analysisRequests } = await mockApi(page);
    await page.goto(`/assets/${id}`);
    await page.getByRole("tab", { name: "HMM", exact: true }).click();
    const input = page.locator(".parameters input");
    const launch = page.getByRole("button", { name: "Lancer la simulation" });
    await expect(input).toHaveValue(fee);
    if (!isMobile) {
      const field = (await input.boundingBox())!;
      const button = (await launch.boundingBox())!;
      const row = (await page.locator(".analysis-settings-row").boundingBox())!;
      expect(button.x).toBeGreaterThan(field.x + field.width);
      expect(
        Math.abs(button.y + button.height - field.y - field.height),
      ).toBeLessThan(3);
      expect(
        Math.abs(button.x + button.width - row.x - row.width),
      ).toBeLessThan(3);
    }
    await launch.click();
    await expect.poll(() => analysisRequests.at(-1)?.fee_bps).toBe(bps);
    await expect(
      page.getByRole("region", { name: "Comparaison des performances" }),
    ).toBeVisible();
    await expect(page.getByText(/stop.*10 %|Achats suspendus/i)).toHaveCount(0);
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
  });
}
