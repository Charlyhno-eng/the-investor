import { test, expect } from "@playwright/test";
import { mockApi } from "./fixtures";

test("stock chart automatically reinvests dividends without a toggle", async ({
  page,
}) => {
  await mockApi(page);
  const requests: URL[] = [];
  await page.route("**/api/assets/yf-test/history?**", async (route) => {
    const url = new URL(route.request().url());
    requests.push(url);
    const adjusted = url.searchParams.get("reinvest") === "true";
    await route.fulfill({
      json: [
        { time: "2022-03-08", value: adjusted ? 90 : 100 },
        { time: "2022-03-09", value: 90 },
        { time: "2022-03-10", value: 99 },
      ],
    });
  });
  await page.goto("/assets/yf-test");
  const button = page.getByRole("button", {
    name: "Dividendes réinvestis",
    exact: true,
  });
  await expect(button).toHaveCount(0);
  await expect(page.locator(".quote-change")).toContainText("+10 %");
  await expect(page.locator(".asset-subtitle")).toContainText(
    "dividendes réinvestis",
  );
  expect(requests.at(-1)!.searchParams.get("reinvest")).toBe("true");
  await page.getByRole("tab", { name: "Régression", exact: true }).click();
  await expect
    .poll(() => requests.at(-1)!.searchParams.get("reinvest"))
    .toBe("true");
  await page.getByRole("tab", { name: "Vue du marché", exact: true }).click();
  await expect(page.locator(".quote-change")).toContainText("+10 %");
  await page.getByRole("button", { name: "Comparer au S&P 500" }).click();
  await expect(
    page.getByRole("region", { name: "Comparaison au S&P 500", exact: true }),
  ).toContainText("sans double comptage");
  await expect(button).toHaveCount(0);
});
