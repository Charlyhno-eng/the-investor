import { expect, test } from "@playwright/test";
import { mockApi, stock } from "./fixtures";

const etfs = ["Monde", "Europe", "Inverse"].map((name, i) => ({
  ...stock,
  id: `etf-${i}`,
  name: `ETF ${name}`,
  category: "etf" as const,
}));

for (const selected of [etfs[0], etfs[1]]) {
  test(`ETF matrix starts with ${selected.name} and uses only listed ETFs`, async ({
    page,
  }) => {
    await mockApi(page);
    await page.route("**/api/assets", (route) =>
      route.fulfill({ json: [stock, ...etfs] }),
    );
    await page.addInitScript(() => {
      localStorage.setItem(
        "investor-removed-assets",
        JSON.stringify(["etf-2"]),
      );
    });
    const requests: {
      holdings: { asset_id: string; quantity: number }[];
      years: number;
      include_benchmark: boolean;
    }[] = [];
    let pending = true;
    await page.route("**/api/portfolio/analytics", (route) => {
      const body = route.request().postDataJSON();
      requests.push(body);
      if (pending) {
        pending = false;
        return route.fulfill({ json: { status: "pending" } });
      }
      const assets = body.holdings.map(({ asset_id }: { asset_id: string }) =>
        etfs.find((a) => a.id === asset_id)!,
      );
      return route.fulfill({
        json: {
          status: "ready",
          correlation: {
            assets,
            matrix: [
              [1, -0.5],
              [-0.5, 1],
            ],
            observations: 100,
            minimum: 20,
            frequency: "daily",
            start: "2022-01-01",
            end: "2022-03-10",
          },
        },
      });
    });
    await page.goto(`/assets/${selected.id}`);
    await expect(
      page.getByRole("tab", { name: "Frontières d’efficience" }),
    ).toHaveCount(0);
    await page.getByRole("tab", { name: "Corrélations", exact: true }).click();
    const panel = page.getByRole("region", { name: "Corrélations des ETF" });
    const table = panel.getByRole("table");
    await expect(table.locator("thead th").nth(1)).toHaveText(selected.name);
    await expect(table.locator("tbody th").first()).toHaveText(selected.name);
    await expect(
      table.locator("tbody tr").nth(0).locator("td").nth(0),
    ).toHaveText("1");
    await expect(
      table.locator("tbody tr").nth(1).locator("td").nth(1),
    ).toHaveText("1");
    await expect(
      table.locator("tbody tr").nth(0).locator("td").nth(1),
    ).toHaveText("-0,5");
    expect(requests.at(-1)?.holdings.map((h) => h.asset_id)).toEqual([
      selected.id,
      ...etfs
        .filter((a) => a.id !== selected.id && a.id !== "etf-2")
        .map((a) => a.id),
    ]);
    expect(requests.at(-1)?.include_benchmark).toBe(false);
    await panel
      .getByLabel("Période de corrélation", { exact: true })
      .selectOption("5");
    await expect.poll(() => requests.at(-1)?.years).toBe(5);
    await expect(table).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });
}
