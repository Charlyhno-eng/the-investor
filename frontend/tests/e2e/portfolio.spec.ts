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
  await expect(page.getByRole("cell", { name: /200,00\s*€/ })).toBeVisible();
  await page.reload();
  await expect(
    page.getByLabel("Quantité Action test", { exact: true }),
  ).toHaveValue("2.5");
  await page
    .getByRole("region", { name: "Répartition du portefeuille", exact: true })
    .scrollIntoViewIfNeeded();
  await expect(page.locator(".portfolio-total")).toContainText(/280,00\s*€/);
  const slice = page.locator(".allocation-slice").first();
  await expect(slice).toHaveAttribute("aria-label", /Action test/);
  await slice.focus();
  await expect(page.locator(".donut-center")).toContainText("Action test");
  await expect(page.locator(".donut-center")).toContainText("200");
  await page.screenshot({
    path: test.info().outputPath("portfolio-allocation.png"),
  });
  await page.getByRole("tab", { name: "Corrélations", exact: true }).click();
  await expect(page.locator(".correlation-table")).toContainText("-0,5");
  await expect(page.locator(".correlation-meta")).toContainText(
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
  ).toHaveCount(0);
  await page
    .getByRole("link", { name: "Vue d’ensemble du Portfolio", exact: true })
    .click();
  await expect(
    page.getByLabel("Quantité Action test", { exact: true }),
  ).toHaveValue("2.5");
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

test("portfolio tables expand to show every position and correlation row", async ({
  page,
}) => {
  await mockApi(page);
  await page.route("**/api/assets", (route) =>
    route.fulfill({
      json: Array.from({ length: 9 }, (_, i) => ({
        ...stock,
        id: `yf-position-${i}`,
        name: `Position ${i + 1}`,
      })),
    }),
  );
  await page.addInitScript(() => {
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify(
        Object.fromEntries(
          Array.from({ length: 9 }, (_, i) => [`yf-position-${i}`, "gold"]),
        ),
      ),
    );
    localStorage.setItem(
      "investor-quantities",
      JSON.stringify(
        Object.fromEntries(
          Array.from({ length: 9 }, (_, i) => [`yf-position-${i}`, 1]),
        ),
      ),
    );
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Portfolio", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".positions-table tbody tr")).toHaveCount(9);
  for (const selector of [".positions-table", ".correlation-table"]) {
    if (selector.includes("correlation"))
      await page
        .getByRole("tab", { name: "Corrélations", exact: true })
        .click();
    await expect(page.locator(`${selector} tbody tr`)).toHaveCount(9);
    expect(
      await page.locator(selector).evaluate((table) => {
        const wrapper = table.closest(".table-scroll")!;
        return wrapper.clientHeight >= table.clientHeight;
      }),
    ).toBe(true);
  }
  await expect(page.locator(".correlation-table td").first()).toHaveCSS(
    "background-color",
    "rgb(178, 24, 43)",
  );
  await page.screenshot({
    path: test.info().outputPath("portfolio-expanded.png"),
    fullPage: true,
  });
});

test("portfolio stays in euros and keeps summary at the right of its heading", async ({
  page,
  isMobile,
}) => {
  await mockApi(page);
  await page.addInitScript(() => {
    localStorage.setItem("investor-currency", "GBP");
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold" }),
    );
    localStorage.setItem(
      "investor-quantities",
      JSON.stringify({ "yf-test": 2.5 }),
    );
  });
  await page.goto("/");
  await expect(page.locator(".portfolio-total")).toContainText(/200,00\s*€/);
  await expect(
    page.getByRole("button", { name: "Paramètres", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Vos positions, leur répartition et leurs corrélations.", {
      exact: true,
    }),
  ).toHaveCount(0);
  const header = page.locator(".portfolio-heading");
  const summary = header.locator(".portfolio-summary");
  await expect(summary).toBeVisible();
  const headingBounds = (await header.boundingBox())!;
  const summaryBounds = (await summary.boundingBox())!;
  expect(
    Math.abs(
      headingBounds.x +
        headingBounds.width -
        summaryBounds.x -
        summaryBounds.width,
    ),
  ).toBeLessThan(2);
  if (!isMobile) {
    const titleBounds = (await header.locator(".asset-title").boundingBox())!;
    expect(summaryBounds.x).toBeGreaterThan(titleBounds.x + titleBounds.width);
    expect(summaryBounds.y).toBeLessThan(titleBounds.y + titleBounds.height);
  }
  await page.screenshot({
    path: test.info().outputPath("portfolio-heading.png"),
  });
  await page.getByRole("tab", { name: "Corrélations", exact: true }).click();
  await expect(
    page.getByText(
      "Les mouvements de vos actifs, comparés sur la même période.",
      { exact: true },
    ),
  ).toHaveCount(0);
  await expect(
    page.getByText(/Corrélation de Pearson des rendements/),
  ).not.toBeVisible();
  await page
    .getByRole("button", {
      name: "Définition : Méthode de corrélation",
      exact: true,
    })
    .focus();
  await expect(page.getByRole("tooltip")).toBeVisible();
  await page.reload();
  await expect(page.locator(".portfolio-total")).toContainText(/200,00\s*€/);
});

test("positions display colored regression deviations with their actual dates", async ({
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
  const deviations = page.locator(".regression-deviation");
  await expect(deviations).toHaveCount(2);
  await expect(deviations.first()).toContainText("-1,8 σ");
  await expect(deviations.last()).toContainText("+1,9 σ");
  await expect(deviations.first()).toHaveAttribute("title", /2020.*2022/);
  expect(
    await deviations.first().evaluate((el) => getComputedStyle(el).color),
  ).not.toBe(
    await deviations.last().evaluate((el) => getComputedStyle(el).color),
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("regression column tooltip escapes the table clipping and stays on screen", async ({
  page,
}, testInfo) => {
  await mockApi(page);
  await page.addInitScript(() =>
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold" }),
    ),
  );
  await page.goto("/markets/portfolio");
  const button = page.getByRole("button", {
    name: "Définition : Écart à la régression sur cinq ans",
    exact: true,
  });
  await button.scrollIntoViewIfNeeded();
  await button.focus();
  const tooltip = page.getByRole("tooltip");
  await expect(tooltip).toContainText("cinq dernières années");
  await expect(tooltip).toHaveCSS("position", "fixed");
  expect(
    await tooltip.evaluate(
      (element) => element.parentElement === document.body,
    ),
  ).toBe(true);
  const bounds = (await tooltip.boundingBox())!;
  expect(bounds.x).toBeGreaterThanOrEqual(0);
  expect(bounds.y).toBeGreaterThanOrEqual(0);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(
    page.viewportSize()!.width,
  );
  await page.screenshot({
    path: testInfo.outputPath("positions-regression-tooltip.png"),
  });
  await button.press("Escape");
  await expect(tooltip).toHaveCount(0);
});

test("positions load without requesting correlations or the benchmark", async ({
  page,
}) => {
  await mockApi(page);
  const requests: {
    include_correlation: boolean;
    include_benchmark: boolean;
    years: number;
  }[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/portfolio/analytics")
      requests.push(request.postDataJSON());
  });
  await page.addInitScript(() => {
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold" }),
    );
    localStorage.setItem(
      "investor-quantities",
      JSON.stringify({ "yf-test": 2 }),
    );
  });
  await page.goto("/markets/portfolio");
  await expect(page.locator(".portfolio-total")).toContainText(/160,00\s*€/);
  expect(requests.length).toBeGreaterThan(0);
  expect(
    requests.every(
      (request) => !request.include_correlation && !request.include_benchmark,
    ),
  ).toBe(true);
  await page.getByRole("tab", { name: "Corrélations", exact: true }).click();
  await expect.poll(() => requests.at(-1)?.include_correlation).toBe(true);
  expect(requests.at(-1)?.include_benchmark).toBe(true);
  await expect(page.locator(".correlation-table")).toBeVisible();
  await page.getByRole("tab", { name: "Positions", exact: true }).click();
  await expect.poll(() => requests.at(-1)?.include_correlation).toBe(false);
  await expect(
    page.getByText("Actualisation des valeurs du portefeuille…"),
  ).toHaveCount(0);
});
