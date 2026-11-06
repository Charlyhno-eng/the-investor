import { test, expect } from "@playwright/test";
import { mockApi, stock } from "./fixtures";

test("quantities persist and drive allocation and correlations", async ({
  page,
}) => {
  await mockApi(page);
  await page.addInitScript(() =>
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold", "yf-btc-usd": "gold" }),
    ),
  );
  await page.goto("/markets/portfolio");
  await page.getByLabel("Quantité Action test", { exact: true }).fill("2.5");
  await page.getByLabel("Quantité Bitcoin", { exact: true }).fill("1");
  await expect(
    page.getByRole("cell", { name: "250 $", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByLabel("Quantité Action test", { exact: true }),
  ).toHaveValue("2.5");
  await page.getByRole("tab", { name: "Répartition par actif" }).click();
  await expect(page.locator(".portfolio-total")).toContainText("350 USD");
  await expect(
    page.getByRole("progressbar", {
      name: "Poids de Action test",
      exact: true,
    }),
  ).toHaveAttribute("value", String(2.5 / 3.5));
  await page.getByRole("tab", { name: "Corrélations", exact: true }).click();
  await expect(page.locator(".correlation-table")).toContainText("-0,5");
  await expect(page.locator(".correlation-table")).toContainText(
    "300 rendements",
  );
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: test.info().outputPath("portfolio-correlation.png"),
  });
  await page
    .locator(".asset-list a")
    .filter({ hasText: "Action test" })
    .click();
  await expect(
    page.getByLabel("Quantité détenue", { exact: true }),
  ).toHaveValue("2.5");
  await page.getByLabel("Quantité détenue", { exact: true }).fill("3");
  await page
    .getByRole("link", { name: "Vue d’ensemble du Portfolio", exact: true })
    .click();
  await expect(
    page.getByLabel("Quantité Action test", { exact: true }),
  ).toHaveValue("3");
});

test("selecting assets preserves library scroll", async ({
  page,
  isMobile,
}) => {
  await mockApi(page);
  await page.route("**/api/assets", (route) =>
    route.fulfill({
      json: Array.from({ length: 100 }, (_, i) => ({
        ...stock,
        id: `yf-scroll-${i}`,
        name: `Action ${String(i).padStart(3, "0")}`,
      })),
    }),
  );
  await page.goto("/assets/yf-scroll-0");
  const list = page.locator(".asset-list");
  await expect(list.locator("a")).toHaveCount(100);
  await list.evaluate((element, mobile) => {
    if (mobile) element.scrollLeft = 800;
    else element.scrollTop = 800;
  }, isMobile);
  const before = await list.evaluate(
    (element, mobile) => (mobile ? element.scrollLeft : element.scrollTop),
    isMobile,
  );
  const target = await list.locator("a").evaluateAll((links) => {
    const bounds = links[0].closest(".asset-list")!.getBoundingClientRect();
    return links
      .find((link) => {
        const rect = link.getBoundingClientRect();
        return (
          rect.left >= bounds.left &&
          rect.right <= bounds.right &&
          rect.top >= bounds.top &&
          rect.bottom <= bounds.bottom
        );
      })!
      .getAttribute("href")!;
  });
  await list.locator(`a[href='${target}']`).click();
  await expect(page).toHaveURL(new RegExp(target + "$"));
  await expect
    .poll(() =>
      list.evaluate(
        (element, mobile) => (mobile ? element.scrollLeft : element.scrollTop),
        isMobile,
      ),
    )
    .toBe(before);
});
