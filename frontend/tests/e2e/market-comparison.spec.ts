import { test, expect } from "@playwright/test";
import { mockApi, stock } from "./fixtures";

for (const id of ["yf-test", "yf-btc-usd", "wb-gold", "yf-etf"]) {
  test(`market comparison follows selected duration for ${id}`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const { comparisonRequests } = await mockApi(page);
    if (id === "yf-etf") {
      await page.route("**/api/assets", (route) =>
        route.fulfill({
          json: [{ ...stock, id, name: "ETF test", category: "etf" }],
        }),
      );
    }
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
    const table = region.getByRole("table", {
      name: "Indicateurs de comparaison",
    });
    await expect(table.getByRole("columnheader")).toHaveText([
      "Indicateur",
      "S&P 500",
      id === "yf-test"
        ? "Action test"
        : id === "yf-btc-usd"
          ? "Bitcoin"
          : id === "yf-etf"
            ? "ETF test"
            : "Or",
    ]);
    await expect(table.locator("tbody tr")).toHaveCount(8);
    await expect(table).toContainText("30,98 %");
    await expect(table).toContainText("21,33 %");
    await expect(table.getByRole("row", { name: /^Bêta/ })).toContainText(
      "0,61",
    );
    await expect(region).not.toContainText("Ma stratégie");
    const cagr = table.getByRole("row", { name: /^CAGR/ });
    await expect(cagr.locator("td").last()).toHaveAttribute(
      "data-comparison",
      "better",
    );
    await expect(
      table
        .getByRole("row", { name: /^Volatilité annualisée/ })
        .locator("td")
        .last(),
    ).toHaveAttribute("data-comparison", "worse");
    await expect(region).toContainText("+20 %");
    await expect(region).toContainText("+10 %");
    await expect(region).toContainText("dividendes réinvestis");
    await expect(
      page.getByRole("button", { name: "Dividendes réinvestis", exact: true }),
    ).toHaveCount(0);
    await expect
      .poll(() =>
        new URL(comparisonRequests.at(-1)!).searchParams.get("reinvest"),
      )
      .toBe("true");
    await expect(
      region.locator(".comparison-caption, .metric-signals-legend"),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "1A", exact: true }).click();
    await expect
      .poll(() => new URL(comparisonRequests.at(-1)!).searchParams.get("start"))
      .toBe("2021-03-10");
    await expect(region.locator("canvas").first()).toBeVisible();
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

test("market tabs keep regression and bond yields cannot masquerade as returns", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto("/assets/yf-test");
  await expect(page.getByRole("tab")).toHaveText([
    "Vue du marché",
    "Régression",
    "Momentum",
    "Prédiction",
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
