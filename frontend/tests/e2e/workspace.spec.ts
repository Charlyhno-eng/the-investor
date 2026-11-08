import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

for (const [id, available] of [
  ["yf-test", true],
  ["yf-btc-usd", true],
  ["wb-gold", false],
  ["bond-fr", false],
] as const) {
  test(`regression availability for ${id}`, async ({ page }) => {
    await mockApi(page);
    await page.goto(`/assets/${id}`);
    await expect(page.locator(".chart-panel canvas").first()).toBeVisible();
    await expect(
      page.getByRole("tab", { name: "HMM", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("tab", { name: "Régression", exact: true }),
    ).toHaveCount(available ? 1 : 0);
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
  await page
    .getByRole("button", { name: "Matières premières", exact: true })
    .click();
  await expect(page).toHaveURL(/\/markets\/commodity$/);
  await expect(page.locator(".asset-detail")).toHaveCount(0);
});
