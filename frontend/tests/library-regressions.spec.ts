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

test("dividend classification persists independently of favorites and excludes removed stocks", async ({
  page,
}) => {
  await mockApi(page);
  let enabled = false;
  await page.route("**/api/assets", (route) =>
    route.fulfill({
      json: [
        { ...stock, is_dividend: enabled },
        { ...stock, id: "yf-other", name: "Autre action", is_dividend: false },
      ],
    }),
  );
  await page.route("**/api/assets/yf-test/dividend-status", (route) => {
    expect(route.request().method()).toBe("PATCH");
    enabled = route.request().postDataJSON().is_dividend;
    return route.fulfill({ json: { id: stock.id, is_dividend: enabled } });
  });
  await page.goto(`/assets/${stock.id}`);
  const toggle = page.getByRole("button", {
    name: "Action à dividende",
    exact: true,
  });
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  expect(
    await page.evaluate(() => localStorage.getItem("investor-favorites")),
  ).toBeNull();
  await page.reload();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Dividendes uniquement" }).click();
  await expect(page.locator(".asset-list a")).toHaveCount(1);
  await expect(page.locator(".asset-list a")).toContainText("Action test");
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: test.info().outputPath("dividend-enabled.png"),
  });
  await toggle.click();
  await expect(page.locator(".asset-list a")).toHaveCount(0);
  await toggle.click();
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Retirer Action test de la liste" })
    .click();
  await expect(page.locator(".asset-list a")).toHaveCount(0);
  expect(enabled).toBe(true);
});

test("a failed dividend save leaves the classification unchanged", async ({
  page,
}) => {
  await mockApi(page);
  await page.route("**/api/assets/yf-test/dividend-status", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Enregistrement indisponible" },
    }),
  );
  await page.goto(`/assets/${stock.id}`);
  const toggle = page.getByRole("button", {
    name: "Action à dividende",
    exact: true,
  });
  await toggle.click();
  await expect(page.getByRole("alert")).toHaveText(
    "Enregistrement indisponible",
  );
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await expect(toggle).toBeEnabled();
});

test("dividend classification is available only on stocks", async ({
  page,
}) => {
  await mockApi(page);
  for (const id of ["yf-btc-usd", "wb-gold", "bond-fr"]) {
    await page.goto(`/assets/${id}`);
    await expect(page.locator(".asset-detail h1")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Action à dividende", exact: true }),
    ).toHaveCount(0);
  }
});
