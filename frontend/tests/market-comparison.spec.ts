import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

for (const id of ["yf-test", "yf-btc-usd", "wb-gold"]) {
  test(`market comparison follows selected duration for ${id}`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const { comparisonRequests } = await mockApi(page);
    await page.goto(`/assets/${id}`);
    await expect(page.locator(".chart-panel canvas").first()).toBeVisible();
    expect(comparisonRequests).toHaveLength(0);
    await page.getByRole("button", { name: "Comparer au S&P 500" }).click();
    const region = page.getByRole("region", {
      name: "Comparaison au S&P 500",
      exact: true,
    });
    await expect(
      region.getByRole("img", {
        name: "Performance de l’actif et du S&P 500, base 100 en dollars",
      }),
    ).toBeVisible();
    await expect(region).toContainText("+20 %");
    await expect(region).toContainText("+10 %");
    await expect(region).toContainText("hors dividendes");
    const reinvestButton = page.getByRole("button", {
      name: "Dividendes réinvestis",
      exact: true,
    });
    const priceButton = page.getByRole("button", { name: "Revenir au prix" });
    const left = (await reinvestButton.boundingBox())!;
    const right = (await priceButton.boundingBox())!;
    expect(left.x + left.width).toBeLessThanOrEqual(right.x);
    expect(Math.abs(left.y - right.y)).toBeLessThan(2);
    await reinvestButton.click();
    await expect
      .poll(() =>
        new URL(comparisonRequests.at(-1)!).searchParams.get("reinvest"),
      )
      .toBe("true");
    if (id === "yf-test")
      await expect(region).toContainText("sans double comptage");
    await page.getByRole("button", { name: "1A", exact: true }).click();
    await expect
      .poll(() => new URL(comparisonRequests.at(-1)!).searchParams.get("start"))
      .toBe("2021-03-10");
    await expect(region.locator("canvas").first()).toBeVisible();
    await page.getByRole("button", { name: "Tout", exact: true }).click();
    await expect
      .poll(() => new URL(comparisonRequests.at(-1)!).searchParams.has("start"))
      .toBe(false);
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
    await region.scrollIntoViewIfNeeded();
    await page.screenshot({
      path: test.info().outputPath("market-comparison.png"),
    });
    await page.getByRole("button", { name: "Revenir au prix" }).click();
    await expect(region).toHaveCount(0);
    await expect(page.locator(".chart-panel canvas").first()).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test("regression precedes HMM and bond yields cannot masquerade as returns", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/assets/yf-test");
  await expect(page.getByRole("tab")).toHaveText([
    "Vue du marché",
    "Régression",
    "HMM",
    "Frontières d’efficience",
  ]);
  await page.goto("/assets/bond-fr");
  await expect(
    page.getByRole("button", { name: "Comparer au S&P 500" }),
  ).toBeDisabled();
});

test("comparison waits for imports and displays provider errors", async ({
  page,
}) => {
  await mockApi(page);
  let fail = false;
  await page.route("**/comparison?**", async (route) => {
    if (!fail) await route.fulfill({ json: { status: "pending" } });
    else
      await route.fulfill({
        status: 503,
        json: { detail: "Référence indisponible" },
      });
  });
  await page.goto("/assets/yf-test");
  await page.getByRole("button", { name: "Comparer au S&P 500" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Chargement de la comparaison",
  );
  fail = true;
  await expect(page.getByRole("alert")).toContainText("Référence indisponible");
  await expect(
    page.getByRole("button", { name: "Réessayer", exact: true }),
  ).toBeVisible();
});
