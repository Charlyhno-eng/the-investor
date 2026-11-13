import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

test("bank accounts persist, update the optional total and stay outside analytics", async ({
  page,
}) => {
  await mockApi(page);
  await page.addInitScript(() => {
    if (!localStorage.getItem("investor-favorites")) {
      localStorage.setItem(
        "investor-favorites",
        JSON.stringify({ "yf-test": "gold" }),
      );
      localStorage.setItem(
        "investor-quantities",
        JSON.stringify({ "yf-test": 2.5 }),
      );
    }
  });
  const holdings: unknown[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/portfolio/analytics"))
      holdings.push(request.postDataJSON().holdings);
  });
  await page.goto("/markets/portfolio");
  const total = page.locator(".portfolio-total-toggle");
  await expect(total).toContainText(/200,00\s*€/);
  await page.getByRole("tab", { name: "Comptes bancaires" }).click();
  await page.getByLabel("Nom du compte").fill("Compte courant");
  await page.getByLabel("Solde (€)").fill("1250.50");
  await page.getByRole("button", { name: "Ajouter le compte" }).click();
  await page.getByLabel("Nom du compte").fill("Découvert");
  await page.getByLabel("Solde (€)").fill("-50");
  await page.getByRole("button", { name: "Ajouter le compte" }).click();
  await total.click();
  await expect(total).toContainText("Patrimoine total");
  await expect(total).toContainText(/1\s*400,50\s*€/);
  await total.click();
  await expect(total).toContainText(/200,00\s*€/);
  await page.reload();
  await page.getByRole("tab", { name: "Comptes bancaires" }).click();
  await expect(page.locator(".bank-account-list li")).toHaveCount(2);
  await page
    .getByRole("button", { name: "Modifier Compte courant", exact: true })
    .click();
  await page.getByLabel("Solde (€)").fill("2000");
  await page.getByRole("button", { name: "Enregistrer", exact: true }).click();
  await page
    .getByRole("button", { name: "Supprimer Découvert", exact: true })
    .click();
  await total.click();
  await expect(total).toContainText(/2\s*200,00\s*€/);
  expect(holdings).toContainEqual([{ asset_id: "yf-test", quantity: 2.5 }]);
  for (const value of holdings as { asset_id: string; quantity: number }[][])
    for (const position of value)
      expect(position).toEqual({ asset_id: "yf-test", quantity: 2.5 });
});
