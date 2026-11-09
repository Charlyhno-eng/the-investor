import { test, expect } from "@playwright/test";
import { mockApi, stock } from "./fixtures";

const scenarios = [
  {
    id: "schneider",
    name: "Schneider Electric",
    m: 55.6,
    z: -2.23,
    held: false,
    action: "Acheter",
  },
  {
    id: "strong",
    name: "Tendance solide",
    m: 80,
    z: -3,
    held: true,
    action: "Renforcer",
  },
  {
    id: "weak",
    name: "Tendance dégradée",
    m: 25,
    z: -1.5,
    held: true,
    action: "Vendre",
  },
  {
    id: "extended",
    name: "Rebond sans force",
    m: 50,
    z: 2,
    held: true,
    action: "Alléger",
  },
  {
    id: "trend",
    name: "Hausse étendue",
    m: 80,
    z: 2,
    held: true,
    action: "Conserver",
  },
  {
    id: "watch",
    name: "Entrée watchlist",
    m: 80,
    z: -3,
    held: false,
    action: "Acheter",
  },
  {
    id: "wait",
    name: "Watchlist faible",
    m: 25,
    z: -2,
    held: false,
    action: "Attendre",
  },
  {
    id: "missing",
    name: "Données insuffisantes",
    m: 80,
    z: null,
    held: false,
    action: "Indisponible",
  },
];
test("recommendations use only held and watchlist stocks, explain their scientific method without the removed heading controls", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await mockApi(page);
  await page.route("**/api/assets", (r) =>
    r.fulfill({
      json: [
        ...scenarios.map((s) => ({ ...stock, id: s.id, name: s.name })),
        { ...stock, id: "outside", name: "Hors sélection" },
        { ...stock, id: "crypto", name: "Crypto détenue", category: "crypto" },
      ],
    }),
  );
  await page.addInitScript(
    ({ scenarios }) => {
      localStorage.setItem(
        "investor-favorites",
        JSON.stringify(
          Object.fromEntries([
            ...scenarios.map((s) => [s.id, s.held ? "gold" : "silver"]),
            ["crypto", "gold"],
          ]),
        ),
      );
      localStorage.setItem(
        "investor-quantities",
        JSON.stringify(
          Object.fromEntries(
            scenarios.filter((s) => s.held).map((s) => [s.id, 1]),
          ),
        ),
      );
    },
    { scenarios },
  );
  let ids: string[] = [];
  await page.route("**/api/portfolio/regression", (r) => {
    ids = r.request().postDataJSON().asset_ids;
    return r.fulfill({
      json: {
        positions: scenarios
          .filter((s) => ids.includes(s.id))
          .map((s) => ({
            id: s.id,
            z: s.z,
            start: "2020-01-01",
            end: "2022-03-10",
          })),
      },
    });
  });
  await page.route("**/api/momentum*", (r) =>
    r.fulfill({
      json: {
        status: "ready",
        as_of: "2022-03-10",
        universe: scenarios.map((s) => ({
          id: s.id,
          name: s.name,
          scores: [s.m, s.m, s.m],
        })),
      },
    }),
  );
  await page.goto("/markets/portfolio");
  await page
    .getByRole("tab", { name: "Recommandation action", exact: true })
    .click();
  const panel = page.getByRole("region", {
    name: "Recommandation action",
    exact: true,
  });
  await expect(panel.locator("tbody tr")).toHaveCount(scenarios.length);
  expect(ids.sort()).toEqual(scenarios.map((s) => s.id).sort());
  for (const s of scenarios)
    await expect(
      panel
        .locator("tbody tr")
        .filter({ hasText: s.name })
        .locator(".recommendation-badge"),
    ).toHaveText(s.action);
  const badgeColors = await panel
    .locator(".recommendation-badge")
    .evaluateAll((items) => items.map((item) => getComputedStyle(item).color));
  expect(new Set(badgeColors).size).toBe(
    new Set(scenarios.map((s) => s.action)).size,
  );
  await expect(panel).not.toContainText("Hors sélection");
  await expect(panel).not.toContainText("Crypto détenue");
  await panel
    .getByText("Formule et critères de recommandation", { exact: true })
    .click();
  await expect(panel.locator("[role=math]")).toHaveCount(2);
  await expect(panel).toContainText("ne démontrent pas une rentabilité future");
  await expect(panel.getByLabel("Filtrer les recommandations")).toHaveCount(0);
  await expect(panel).not.toContainText("Analyse au");
  await expect(
    panel.locator("tbody tr").filter({ hasText: "Schneider Electric" }),
  ).toContainText("67,5 / 100");
  await expect(panel).toContainText("70 % de Momentum et 30 % de décote");
  await expect(panel).not.toContainText("attendre une stabilisation");
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("recommendations.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
