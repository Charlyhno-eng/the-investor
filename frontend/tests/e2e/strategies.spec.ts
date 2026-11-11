import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

test("independent strategies persist, switch, remove assets and delete", async ({
  page,
}, testInfo) => {
  await mockApi(page);
  await page.goto("/");
  await page.evaluate(() => {
    localStorage.setItem(
      "investor-quantities",
      JSON.stringify({ "yf-test": 9 }),
    );
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({
        "yf-test": "silver",
        "yf-btc-usd": "gold",
        "wb-gold": "silver",
      }),
    );
  });
  await page.reload();
  await page.getByRole("button", { name: "Stratégie", exact: true }).click();
  await expect(
    page.getByText("Créez une stratégie pour simuler", { exact: false }),
  ).toBeVisible();
  await page
    .getByLabel("Nouvelle stratégie", { exact: true })
    .fill("Simulation A");
  await page
    .getByRole("button", { name: "Créer une stratégie", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Simulation A", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".positions-table tbody tr")).toHaveCount(0);
  await expect(
    page.getByLabel("Ajouter un actif", { exact: true }).locator("option"),
  ).toHaveText(["Action test", "Bitcoin", "Or"]);
  await page
    .getByLabel("Ajouter un actif", { exact: true })
    .selectOption("yf-test");
  await page.getByRole("button", { name: "Ajouter", exact: true }).click();
  const quantity = page.locator(".positions-table input").first();
  await expect(quantity).toHaveValue("0");
  await quantity.fill("3");
  await quantity.blur();
  await page.screenshot({
    path: testInfo.outputPath("strategy.png"),
    fullPage: true,
  });
  await page
    .getByLabel("Nouvelle stratégie", { exact: true })
    .fill("Simulation B");
  await page
    .getByRole("button", { name: "Créer une stratégie", exact: true })
    .click();
  await expect(page.locator(".positions-table tbody tr")).toHaveCount(0);
  await page
    .locator(".strategy-list")
    .getByRole("button", { name: "Simulation A", exact: false })
    .click();
  await expect(quantity).toHaveValue("3");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Simulation A", exact: true }),
  ).toBeVisible();
  await expect(quantity).toHaveValue("3");
  expect(
    await page.evaluate(() =>
      JSON.parse(localStorage.getItem("investor-quantities")!),
    ),
  ).toEqual({ "yf-test": 9 });
  expect(
    await page.evaluate(() =>
      JSON.parse(localStorage.getItem("investor-favorites")!),
    ),
  ).toEqual({ "yf-test": "silver", "yf-btc-usd": "gold", "wb-gold": "silver" });
  await page
    .getByRole("button", { name: "Action test Retirer de la stratégie" })
    .click();
  await expect(page.locator(".positions-table tbody tr")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Supprimer la stratégie", exact: true })
    .click();
  await page.getByRole("button", { name: "Annuler", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Simulation A", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Supprimer la stratégie", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirmer la suppression", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Simulation B", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Supprimer la stratégie", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirmer la suppression", exact: true })
    .click();
  await expect(
    page.getByText("Créez une stratégie pour simuler", { exact: false }),
  ).toBeVisible();
  await page.reload();
  await expect(page.locator(".strategy-list button")).toHaveCount(0);
});

test("simulated portfolio sends its own holdings to the comparison", async ({
  page,
}) => {
  await mockApi(page);
  let holdings: unknown;
  await page.route("**/api/portfolio/performance", async (route) => {
    holdings = route.request().postDataJSON().holdings;
    await route.fulfill({
      json: { status: "insufficient", message: "Simulation reçue" },
    });
  });
  await page.addInitScript(() =>
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold" }),
    ),
  );
  await page.goto("/markets/strategy");
  await page
    .getByLabel("Nouvelle stratégie", { exact: true })
    .fill("Comparaison simulée");
  await page
    .getByRole("button", { name: "Créer une stratégie", exact: true })
    .click();
  await page
    .getByLabel("Ajouter un actif", { exact: true })
    .selectOption("yf-test");
  await page.getByRole("button", { name: "Ajouter", exact: true }).click();
  await page.locator(".positions-table input").first().fill("4");
  await page
    .getByRole("tab", { name: "Comparaison & optimisation", exact: true })
    .click();
  await expect(
    page.getByText("Simulation reçue", { exact: true }),
  ).toBeVisible();
  expect(holdings).toEqual([{ asset_id: "yf-test", quantity: 4 }]);
  for (const name of [
    "Comparaison & optimisation",
    "Corrélations",
    "Frontières d’efficience",
  ]) {
    await page.getByRole("tab", { name, exact: true }).click();
    await expect(page.locator(".strategy-toolbar")).toHaveCount(0);
    await expect(
      page.getByLabel("Actifs de la stratégie", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: "Comparaison simulée", exact: true }),
    ).toBeVisible();
  }
  await page.getByRole("tab", { name: "Positions", exact: true }).click();
  await expect(page.locator(".strategy-toolbar")).toBeVisible();
  await expect(
    page.getByLabel("Actifs de la stratégie", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".positions-table input").first()).toHaveValue("4");
  for (const name of ["Positions", "Corrélations", "Frontières d’efficience"]) {
    await expect(page.getByRole("tab", { name, exact: true })).toBeVisible();
  }
});

test("empty watchlist explains availability and keeps import accessible", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/markets/strategy");
  await page
    .getByLabel("Nouvelle stratégie", { exact: true })
    .fill("Watchlist vide");
  await page
    .getByRole("button", { name: "Créer une stratégie", exact: true })
    .click();
  await expect(
    page.getByLabel("Ajouter un actif", { exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Ajouter", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText("Votre watchlist et votre portfolio sont vides.", {
      exact: false,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Importer un actif", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
});

test("locked quantities persist and are sent to every simulation", async ({
  page,
}) => {
  await mockApi(page);
  await page.addInitScript(() => {
    if (!localStorage.getItem("investor-strategies"))
      localStorage.setItem(
        "investor-strategies",
        JSON.stringify([
          {
            id: "locked-test",
            name: "Quantités fixes",
            quantities: { "yf-btc-usd": 1, "yf-test": 4 },
          },
        ]),
      );
  });
  await page.goto("/markets/strategy");
  const quantity = page.getByRole("spinbutton", {
    name: "Quantité Bitcoin",
    exact: true,
  });
  await expect(quantity).toHaveValue("1");
  await page
    .getByRole("button", { name: "Verrouiller Bitcoin", exact: true })
    .click();
  await expect(quantity).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Bitcoin Retirer de la stratégie" }),
  ).toBeDisabled();
  await page.reload();
  await expect(quantity).toHaveValue("1");
  await expect(quantity).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Déverrouiller Bitcoin" }),
  ).toHaveAttribute("aria-pressed", "true");
  const comparison = page.waitForRequest(
    (request) =>
      request.url().endsWith("/portfolio/performance") &&
      request.method() === "POST",
  );
  await page
    .getByRole("tab", { name: "Comparaison & optimisation", exact: true })
    .click();
  expect((await comparison).postDataJSON().locked_asset_ids).toEqual([
    "yf-btc-usd",
  ]);
  const frontier = page.waitForRequest(
    (request) =>
      request.url().endsWith("/portfolio/volatility") &&
      request.method() === "POST",
  );
  await page
    .getByRole("tab", { name: "Frontières d’efficience", exact: true })
    .click();
  expect((await frontier).postDataJSON().locked_asset_ids).toEqual([
    "yf-btc-usd",
  ]);
  await page.getByRole("tab", { name: "Positions", exact: true }).click();
  await page.getByRole("button", { name: "Déverrouiller Bitcoin" }).click();
  await expect(quantity).toBeEnabled();
  await quantity.fill("2");
  await quantity.blur();
  await expect(quantity).toHaveValue("2");
});
