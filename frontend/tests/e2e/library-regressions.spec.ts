import { test, expect } from "@playwright/test";
import { mockApi, stock } from "./fixtures";

test("a removed imported stock can be restored repeatedly and after reload", async ({
  page,
}) => {
  await mockApi(page);
  await page.route("**/api/stocks/search?*", (route) =>
    route.fulfill({
      json: {
        results: [
          {
            symbol: "TEST",
            name: "Action test",
            exchange: "Paris",
            imported: true,
          },
        ],
        warning: null,
      },
    }),
  );
  const imports: unknown[] = [];
  await page.route("**/api/asset-imports", (route) => {
    imports.push(route.request().postDataJSON());
    return route.fulfill({
      status: 202,
      json: { status: "completed", asset_id: stock.id, id: null },
    });
  });
  await page.goto(`/assets/${stock.id}`);
  for (let i = 0; i < 2; i++) {
    page.once("dialog", (dialog) => dialog.accept());
    await page
      .getByRole("button", { name: "Retirer Action test de la liste" })
      .click();
    await page.getByRole("button", { name: "Actions", exact: true }).click();
    await expect(page.locator(".asset-list a")).toHaveCount(0);
    await page.reload();
    await page
      .locator(".library-heading")
      .getByRole("button", { name: "Ajouter une action" })
      .click();
    await page.getByRole("textbox", { name: "Nom ou symbole" }).fill("TEST");
    await page.getByRole("button", { name: /Action test.*Réajouter/ }).click();
    await page.getByRole("button", { name: "Réajouter à la liste" }).click();
    await expect(page.locator(".asset-detail h1")).toContainText("Action test");
    await expect(page.locator(".asset-list a")).toHaveCount(1);
    await page.reload();
    await expect(page.locator(".asset-detail h1")).toContainText("Action test");
    expect(
      await page.evaluate(() =>
        JSON.parse(localStorage.getItem("investor-removed-assets") ?? "[]"),
      ),
    ).toEqual([]);
  }
  expect(imports).toEqual([
    { symbol: "TEST", category: "stock" },
    { symbol: "TEST", category: "stock" },
  ]);
});
