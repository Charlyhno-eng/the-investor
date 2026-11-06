import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

test("favorites across categories persist, stay in the favorites library and can be removed", async ({
  page,
}) => {
  await mockApi(page);
  for (const id of ["yf-test", "yf-btc-usd", "wb-gold", "bond-fr"]) {
    await page.goto(`/assets/${id}`);
    await page
      .getByRole("button", { name: "Ajouter aux actifs détenus", exact: true })
      .click();
    await expect(
      page.getByRole("button", {
        name: "Détenu · Passer en watchlist",
        exact: true,
      }),
    ).toHaveAttribute("aria-pressed", "true");
  }
  await page.getByRole("button", { name: "Portfolio", exact: true }).click();
  await expect(page.locator(".asset-list a")).toHaveCount(4);
  await page.reload();
  await expect(page.locator(".asset-list a")).toHaveCount(4);
  await page.locator(".asset-list a").filter({ hasText: "Bitcoin" }).click();
  await expect(page.locator(".asset-library h2")).toContainText("Portfolio");
  await page
    .getByRole("button", { name: "Détenu · Passer en watchlist", exact: true })
    .click();
  await expect(page.locator(".asset-list a")).toHaveCount(3);
  await page.getByRole("button", { name: "Watchlist", exact: true }).click();
  await expect(page.locator(".asset-list a")).toHaveCount(1);
  await page.locator(".asset-list a").click();
  await page.reload();
  await expect(page.locator(".asset-library h2")).toContainText("Watchlist");
  await expect(
    page.getByRole("button", {
      name: "Watchlist · Retirer des favoris",
      exact: true,
    }),
  ).toHaveClass(/silver/);
  await page
    .getByRole("button", {
      name: "Watchlist · Retirer des favoris",
      exact: true,
    })
    .click();
  await expect(page.locator(".asset-list a")).toHaveCount(0);
  await page.getByRole("button", { name: "Portfolio", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Détenu : Or · Passer en watchlist",
      exact: true,
    })
    .click();
  await expect(page.locator(".asset-list a")).toHaveCount(2);
  await page.getByRole("button", { name: "Watchlist", exact: true }).click();
  await expect(page.locator(".asset-list a")).toHaveCount(1);
  await page
    .getByRole("button", {
      name: "Watchlist : Or · Retirer des favoris",
      exact: true,
    })
    .click();
  await expect(page.locator(".asset-list a")).toHaveCount(0);
});

test("favorite stocks are shown before other stocks", async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/assets", (route) =>
    route.fulfill({
      json: [
        {
          id: "yf-a",
          name: "Alpha",
          category: "stock",
          last_date: "2022-01-01",
          last_value: 100,
          unit: "EUR",
        },
        {
          id: "yf-z",
          name: "Zeta",
          category: "stock",
          last_date: "2022-01-01",
          last_value: 100,
          unit: "EUR",
        },
      ],
    }),
  );
  await page.goto("/markets/stock");
  await expect(page.locator(".asset-list a").first()).toContainText("Alpha");
  await page
    .getByRole("button", { name: "Ajouter Zeta aux actifs détenus" })
    .click();
  await expect(page.locator(".asset-list a").first()).toContainText("Zeta");
  await page
    .getByRole("button", { name: "Détenu : Zeta · Passer en watchlist" })
    .click();
  await expect(page.locator(".asset-list a").first()).toContainText("Zeta");
  await page
    .getByRole("button", { name: "Watchlist : Zeta · Retirer des favoris" })
    .click();
  await expect(page.locator(".asset-list a").first()).toContainText("Alpha");
});

test("existing favorites migrate to gold", async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("investor-favorites", JSON.stringify(["yf-test"])),
  );
  await mockApi(page);
  await page.goto("/assets/yf-test");
  await expect(
    page.getByRole("button", {
      name: "Détenu · Passer en watchlist",
      exact: true,
    }),
  ).toHaveClass(/gold/);
});
