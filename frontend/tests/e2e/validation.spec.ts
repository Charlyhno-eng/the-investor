import { test, expect, type Page } from "@playwright/test";
import { mockApi, stock } from "./fixtures";

function model() {
  const metrics: Record<string, number | null> = {
    market_exposure: 0.45,
    total_return: 0.1,
    cagr: 0.1,
    max_drawdown: -0.08,
    volatility: 0.15,
    annual_turnover: 0.2,
    worst_quarter: -0.03,
    sharpe: 0.7,
    cost_eur: 80,
    positive_quarters: 2,
    winning_quarters: 1,
  };
  const keys = ["strategy", "equal", "buy_hold", "benchmark"];
  return {
    status: "ready",
    notices: [
      "ETF test : retour à la moyenne non appliqué ; achat puis quantité conservée dès sa disponibilité.",
      "Crypto récente : premières cotations le 2024-01-02, aucune position avant cette date.",
    ],
    start: "2024-01-02",
    end: "2024-11-01",
    requested_start: "2020-01-01",
    benchmark_name: "S&P 500 · dividendes réinvestis",
    completed_quarters: 3,
    assets: [
      { id: "yf-test", name: "Action test" },
      { id: "yf-btc-usd", name: "Bitcoin" },
    ],
    metrics: Object.fromEntries(keys.map((k) => [k, metrics])),
    equity: Array.from({ length: 200 }, (_, i) => ({
      time: new Date(Date.UTC(2024, 0, 2 + i)).toISOString().slice(0, 10),
      strategy: 100 + i * 0.07,
      equal: 100 + i * 0.05,
      buy_hold: 100 + i * 0.04,
      benchmark: 100 + i * 0.03,
    })),
    final_portfolio: {
      date: "2024-11-01",
      initial_capital: 10000,
      total: 11000,
      cash: 1000,
      positions: [
        {
          id: "yf-test",
          name: "Action test",
          quantity: 50,
          value: 10000,
          weight: 10000 / 11000,
        },
        { id: "yf-btc-usd", name: "Bitcoin", quantity: 0, value: 0, weight: 0 },
      ],
    },
    transactions: [
      {
        asset_id: "yf-test",
        name: "Action test",
        signal: "2024-01-02",
        execution: "2024-01-03",
        side: "buy",
        quantity: 50,
        price: 100,
        amount: 5000,
        fee: 25,
        cash_after: 4975,
        z: -1.6,
      },
      {
        asset_id: "yf-test",
        name: "Action test",
        signal: "2024-04-02",
        execution: "2024-04-03",
        side: "sell",
        quantity: 10,
        price: 110,
        amount: 1100,
        fee: 5.5,
        z: 1.7,
        profit_return: 0.089,
      },
      {
        asset_id: "yf-test",
        name: "Action test",
        signal: "2024-06-03",
        execution: "2024-06-04",
        side: "sell",
        quantity: 10,
        price: 90,
        amount: 900,
        fee: 4.5,
        z: null,
        profit_return: -0.109,
        reason: "funding",
      },
    ],
    folds: [
      {
        signal: "2024-01-02",
        execution: "2024-01-03",
        end: "2024-04-03",
        train_start: "2021-01-04",
        train_end: "2024-01-02",
        observations: 780,
        complete: true,
        weights: [0.6, 0.4],
        returns: Object.fromEntries(keys.map((k) => [k, 0.03])),
        costs: Object.fromEntries(keys.map((k) => [k, 0.5])),
        turnover: Object.fromEntries(keys.map((k) => [k, 0.99])),
      },
    ],
  };
}

async function setup(page: Page) {
  await mockApi(page);
  await page.addInitScript(() => {
    localStorage.setItem(
      "investor-favorites",
      JSON.stringify({ "yf-test": "gold", "yf-btc-usd": "gold" }),
    );
    localStorage.setItem(
      "investor-quantities",
      JSON.stringify({ "yf-test": 2, "yf-btc-usd": 1 }),
    );
    localStorage.setItem(
      "investor-strategies",
      JSON.stringify([
        {
          id: "s",
          name: "Test chronologique",
          quantities: { "yf-test": 3 },
          lockedAssetIds: [],
        },
      ]),
    );
  });
}

test("chronological validation is explicit, auditable and invalidated when settings change", async ({
  page,
}, testInfo) => {
  await setup(page);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/portfolio/validation", (r) => {
    requests.push(r.request().postDataJSON());
    return r.fulfill({ json: model() });
  });
  await page.goto("/markets/portfolio");
  await expect(
    page
      .getByRole("tablist", { name: "Vues du Portfolio" })
      .getByRole("tab")
      .last(),
  ).toHaveText("Corrélation minimale");
  await expect(
    page.getByRole("tab", { name: "Volatilité minimale", exact: true }),
  ).toHaveCSS("border-left-width", "1px");
  await page
    .getByRole("tab", { name: "Volatilité minimale", exact: true })
    .click();
  const panel = page.getByRole("region", {
    name: "Validation historique",
    exact: true,
  });
  await expect(panel.getByText(/Biais de survivance/)).toHaveCount(0);
  await expect(panel.getByText(/^Univers :/)).toHaveCount(0);
  const tabs = page.getByRole("tablist", { name: "Vues du Portfolio" });
  await expect(tabs.getByRole("tab")).toHaveText([
    "Positions",
    "Comptes bancaires",
    "Prédiction",
    "Corrélations",
    "Frontières d’efficience",
    "Recommandation action",
    "Volatilité minimale",
    "Retour à la moyenne",
    "Corrélation minimale",
  ]);
  await expect(panel.getByLabel("Méthode à valider")).toHaveCount(0);
  await expect(panel.getByLabel("Référence de marché")).toHaveCount(0);
  await expect(panel.getByLabel("Bêta cible")).toHaveCount(0);
  await expect(
    panel.getByLabel("Titres entiers uniquement (actions et ETF)"),
  ).not.toBeChecked();
  expect(requests).toHaveLength(0);
  await panel.getByRole("button", { name: "Lancer la validation" }).click();
  await expect(
    panel.getByRole("table", { name: "Résultats hors échantillon" }),
  ).toBeVisible();
  await expect(panel.locator(".performance-caption")).toHaveCount(0);
  await expect(panel.getByText(/La validation commence après/)).toHaveCount(0);
  const labels = [
    "S&P 500 · dividendes réinvestis",
    "Achat-conservation",
    "Équipondération trimestrielle",
    "Méthode testée",
  ];
  await expect(
    panel.getByRole("group", { name: "Légende des courbes" }).locator("span"),
  ).toHaveText(labels);
  await expect(
    panel
      .getByRole("table", { name: "Résultats hors échantillon" })
      .locator("thead th"),
  ).toHaveText(["Indicateur", ...labels]);
  await expect(
    panel
      .getByRole("img", { name: /quatre courbes/ })
      .locator("canvas")
      .first(),
  ).toBeVisible();
  expect(requests[0]).toEqual({
    asset_ids: ["yf-test", "yf-btc-usd"],
    mode: "volatility",
    years: 5,
    fee_rate: 0.005,
    initial_capital: 10000,
    whole_shares: false,
    benchmark_asset_id: null,
  });
  await panel
    .getByText("Détail des décisions et des trimestres", { exact: true })
    .click();
  await expect(
    panel.getByRole("table", { name: "Fenêtres de validation" }),
  ).toContainText("780 variations");
  await expect(
    panel
      .getByRole("table", { name: "Fenêtres de validation" })
      .locator("thead th"),
  ).toHaveText([
    "Apprentissage",
    "Signal → exécution",
    "Fin de détention",
    ...labels,
    "Rotation de la méthode",
  ]);
  await expect(panel.getByText(/Allocation au/)).toContainText(
    "Action test 60 %",
  );
  await page
    .getByRole("tab", { name: "Retour à la moyenne", exact: true })
    .click();
  await expect(
    panel.getByText(/^Actions et cryptomonnaies\. Achat/),
  ).toHaveCount(0);
  await expect(
    panel.getByRole("table", { name: "Résultats hors échantillon" }),
  ).toHaveCount(0);
  await panel.getByLabel("Capital initial (€)").fill("20000");
  await panel.getByLabel("Titres entiers uniquement (actions et ETF)").check();
  await panel.getByLabel("Frais par achat et vente (%)").fill("0.8");
  await panel.getByRole("button", { name: "Lancer la validation" }).click();
  await expect.poll(() => requests.at(-1)?.fee_rate).toBe(0.008);
  expect(requests.at(-1)?.initial_capital).toBe(20000);
  expect(requests.at(-1)?.whole_shares).toBe(true);
  expect(requests.at(-1)?.mode).toBe("mean_reversion");
  await expect(
    panel.getByRole("table", { name: "Positions finales de la méthode" }),
  ).toContainText("Liquidités");
  await expect(
    panel
      .getByRole("table", { name: "Positions finales de la méthode" })
      .locator("tbody tr"),
  ).toHaveCount(3);
  await expect(
    panel.getByText(/ETF test : retour à la moyenne non appliqué/),
  ).toBeVisible();
  await expect(
    panel.getByText(/Crypto récente : premières cotations/),
  ).toBeVisible();
  const journal = panel.getByRole("table", {
    name: "Journal des achats et ventes",
  });
  await expect(journal.locator("thead")).toContainText("Écart-type");
  await expect(journal).toContainText("Achat");
  await expect(journal.locator("thead")).toContainText("Liquidités après");
  await expect(journal).toContainText("4 975 €");
  await expect(journal).toContainText("Financement d’un achat");
  await expect(
    journal.getByText("Vente (-10,9 %)", { exact: false }),
  ).toHaveClass("negative");
  await expect(journal.getByText("Vente (+8,9 %)")).toHaveClass("positive");
  await expect(journal).toContainText("-1,6");
  await page
    .getByRole("tab", { name: "Corrélation minimale", exact: true })
    .click();
  await panel.getByRole("button", { name: "Lancer la validation" }).click();
  await expect.poll(() => requests.at(-1)?.mode).toBe("correlation");
  await expect(
    panel.getByRole("table", { name: "Positions finales de la méthode" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() =>
      JSON.parse(localStorage.getItem("investor-quantities")!),
    ),
  ).toEqual({ "yf-test": 2, "yf-btc-usd": 1 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await panel.screenshot({ path: testInfo.outputPath("validation.png") });
  expect(errors).toEqual([]);
});

test("metric colors compare both references and correctly handle losses, costs, ties and missing values", async ({
  page,
}, testInfo) => {
  await setup(page);
  const data = model();
  data.metrics.benchmark = {
    ...data.metrics.benchmark,
    cagr: 0.1,
    max_drawdown: -0.25,
    volatility: 0.2,
    cost_eur: 50,
    sharpe: null,
  };
  data.metrics.buy_hold = {
    ...data.metrics.buy_hold,
    cagr: 0.15,
    max_drawdown: -0.1,
    volatility: 0.15,
    cost_eur: 50,
  };
  data.metrics.equal = {
    ...data.metrics.equal,
    cagr: 0.08,
    max_drawdown: -0.3,
    volatility: 0.25,
    cost_eur: 90,
  };
  data.metrics.strategy = {
    ...data.metrics.strategy,
    cagr: 0.12,
    max_drawdown: -0.08,
    volatility: 0.15,
    cost_eur: 70,
  };
  await page.route("**/api/portfolio/validation", (r) =>
    r.fulfill({ json: data }),
  );
  await page.goto("/markets/portfolio");
  await page
    .getByRole("tab", { name: "Volatilité minimale", exact: true })
    .click();
  const panel = page.getByRole("region", {
    name: "Validation historique",
    exact: true,
  });
  await panel.getByRole("button", { name: "Lancer la validation" }).click();
  const table = panel.getByRole("table", {
    name: "Résultats hors échantillon",
  });
  await expect(table.locator("tbody tr").last()).toContainText(
    "Exposition au marché",
  );
  await expect(
    table.locator("tbody tr").last().locator("[data-best]"),
  ).toHaveCount(0);
  await expect(
    table.locator("tbody tr").last().locator("td").nth(3).locator("i").first(),
  ).toHaveAttribute("data-comparison", "unavailable");
  await expect(
    table.locator("tbody tr").last().locator("td").nth(3),
  ).toContainText("45 %");
  await expect(table.getByText(/Bêta/)).toHaveCount(0);
  await expect(
    table
      .getByRole("row", { name: /^Frais payés/ })
      .locator("td")
      .nth(3),
  ).toContainText("70 €");
  const cells = (name: string) =>
    table.getByRole("row", { name: new RegExp(`^${name}`) }).locator("td");
  for (const [name, benchmark, buyHold] of [
    ["CAGR net", "better", "worse"],
    ["Drawdown maximal", "better", "better"],
    ["Volatilité annualisée", "better", "equal"],
    ["Frais payés", "worse", "worse"],
    ["Sharpe", "unavailable", "equal"],
  ]) {
    const markers = cells(name).nth(3).locator(".metric-signals i");
    await expect(markers).toHaveCount(2);
    for (const [i, state] of [benchmark, buyHold].entries()) {
      await expect(markers.nth(i)).toHaveAttribute("data-comparison", state);
      await expect(markers.nth(i)).toHaveCSS(
        "background-color",
        state === "better"
          ? "rgb(101, 199, 165)"
          : state === "worse"
            ? "rgb(237, 140, 133)"
            : "rgb(126, 135, 144)",
      );
    }
  }
  await expect(cells("CAGR net").nth(1)).toHaveAttribute("data-best", "true");
  await expect(cells("Drawdown maximal").nth(3)).toContainText("-8 %");
  await expect(cells("Drawdown maximal").nth(3)).toHaveAttribute(
    "data-best",
    "true",
  );
  await expect(cells("Volatilité annualisée").nth(1)).toHaveAttribute(
    "data-best",
    "true",
  );
  await expect(cells("Volatilité annualisée").nth(3)).toHaveAttribute(
    "data-best",
    "true",
  );
  await expect(cells("Frais payés").nth(0)).toHaveAttribute(
    "data-best",
    "true",
  );
  await expect(cells("Trimestres complets battant").nth(0)).toContainText("—");
  await expect(
    table.getByRole("row", { name: /^Rendement net/ }).locator("td[data-best]"),
  ).toHaveCount(0);
  const legend = panel.getByRole("group", { name: "Légende des courbes" });
  await expect(legend.locator("i").nth(0)).toHaveCSS(
    "background-color",
    "rgb(115, 157, 232)",
  );
  await expect(legend.locator("i").nth(3)).toHaveCSS(
    "background-color",
    "rgb(213, 170, 115)",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await panel.screenshot({
    path: testInfo.outputPath("validation-colors.png"),
  });
});

test("pending imports, errors and short histories can be retried", async ({
  page,
}) => {
  await setup(page);
  let attempt = 0;
  await page.route("**/api/portfolio/validation", (r) => {
    attempt++;
    if (attempt === 1) return r.fulfill({ json: { status: "pending" } });
    if (attempt === 2)
      return r.fulfill({
        json: {
          status: "insufficient",
          message: "Il faut trois ans d’apprentissage communs.",
        },
      });
    if (attempt === 3)
      return r.fulfill({
        status: 503,
        json: { detail: "Calcul indisponible" },
      });
    return r.fulfill({ json: model() });
  });
  await page.goto("/markets/portfolio");
  await page
    .getByRole("tab", { name: "Volatilité minimale", exact: true })
    .click();
  const panel = page.getByRole("region", {
    name: "Validation historique",
    exact: true,
  });
  const launch = panel.getByRole("button", { name: "Lancer la validation" });
  await launch.click();
  await expect(panel.getByRole("status")).toContainText("Calcul des fenêtres");
  await expect(panel.getByRole("status")).toContainText("trois ans");
  await launch.click();
  await expect(panel.getByRole("alert")).toContainText("Calcul indisponible");
  await launch.click();
  await expect(
    panel.getByRole("table", { name: "Résultats hors échantillon" }),
  ).toBeVisible();
});

test("the same tab validates an independent strategy universe", async ({
  page,
}) => {
  await setup(page);
  const requests: { asset_ids: string[] }[] = [];
  await page.route("**/api/portfolio/validation", (r) => {
    requests.push(r.request().postDataJSON());
    return r.fulfill({
      json: { status: "insufficient", message: "Historique trop court" },
    });
  });
  await page.goto("/markets/portfolio");
  await page.getByRole("button", { name: "Stratégie", exact: true }).click();
  await page
    .getByRole("tab", { name: "Volatilité minimale", exact: true })
    .click();
  await page.getByRole("button", { name: "Lancer la validation" }).click();
  await expect.poll(() => requests[0]?.asset_ids).toEqual(["yf-test"]);
});

test("reversion exposes only two thresholds with fixed defaults and preserves each strategy tab", async ({
  page,
}) => {
  await setup(page);
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/portfolio/validation", (route) => {
    requests.push(route.request().postDataJSON());
    const base = model();
    return route.fulfill({
      json: {
        ...base,
        transactions: base.transactions.map((transaction, index) =>
          index === 1 ? { ...transaction, reason: "trailing_z" } : transaction,
        ),
      },
    });
  });
  await page.goto("/markets/portfolio");
  await page
    .getByRole("tab", { name: "Retour à la moyenne", exact: true })
    .click();
  const panel = page.getByRole("region", {
    name: "Validation historique",
    exact: true,
  });
  await expect(panel.getByLabel("Seuil d’achat (−σ)")).toHaveValue("2");
  await expect(
    panel.getByLabel("Seuil de vente ou d’activation (+σ)"),
  ).toHaveValue("2");
  for (const label of [
    "Méthode à valider",
    "Réglage des écarts-types",
    "Règle de sortie",
    "Repli depuis le plus haut écart-type (σ)",
    "Écart-type minimal pour financer un achat (σ)",
    "Référence de marché",
  ]) {
    await expect(panel.getByLabel(label)).toHaveCount(0);
  }
  await panel.getByRole("button", { name: "Lancer la validation" }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0]).toMatchObject({
    mode: "mean_reversion",
    reversion_entry_z: 2,
    reversion_exit_z: 2,
    reversion_exit_mode: "trailing_z",
    reversion_trailing_gap: 1,
    reversion_funding_min_z: 0.3,
    benchmark_asset_id: null,
  });
  await expect(
    panel.getByText("Repli de l’écart-type", { exact: true }),
  ).toBeVisible();
  await panel.getByLabel("Seuil d’achat (−σ)").fill("1.8");
  await panel.getByLabel("Seuil de vente ou d’activation (+σ)").fill("1.6");
  await expect(
    panel.getByRole("table", { name: "Résultats hors échantillon" }),
  ).toHaveCount(0);
  await panel.getByRole("button", { name: "Lancer la validation" }).click();
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[1]).toMatchObject({
    reversion_entry_z: 1.8,
    reversion_exit_z: 1.6,
    reversion_exit_mode: "trailing_z",
    reversion_trailing_gap: 1,
    reversion_funding_min_z: 0.3,
  });
  await expect(
    panel.getByRole("table", { name: "Résultats hors échantillon" }),
  ).toBeVisible();
  await page
    .getByRole("tab", { name: "Volatilité minimale", exact: true })
    .click();
  await expect(
    panel.getByRole("table", { name: "Résultats hors échantillon" }),
  ).toHaveCount(0);
  await expect(panel.getByLabel("Seuil d’achat (−σ)")).toHaveCount(0);
  await panel.getByLabel("Capital initial (€)").fill("15000");
  await panel.getByRole("button", { name: "Lancer la validation" }).click();
  await expect.poll(() => requests.length).toBe(3);
  expect(requests[2]).toMatchObject({
    mode: "volatility",
    initial_capital: 15000,
    benchmark_asset_id: null,
  });
  expect(requests[2]).not.toHaveProperty("reversion_entry_z");
  await page
    .getByRole("tab", { name: "Retour à la moyenne", exact: true })
    .click();
  await expect(panel.getByLabel("Seuil d’achat (−σ)")).toHaveValue("1.8");
  await expect(panel.getByLabel("Capital initial (€)")).toHaveValue("10000");
  await expect(
    panel.getByRole("table", { name: "Résultats hors échantillon" }),
  ).toBeVisible();
  expect(requests).toHaveLength(3);
  await panel.getByLabel("Seuil d’achat (−σ)").fill("");
  await expect(
    panel.getByRole("button", { name: "Lancer la validation" }),
  ).toBeDisabled();
  await page
    .getByRole("tab", { name: "Corrélation minimale", exact: true })
    .click();
  await panel.getByRole("button", { name: "Lancer la validation" }).click();
  await expect.poll(() => requests.at(-1)?.mode).toBe("correlation");
});

test("catalogue polling preserves validation settings, requests and results", async ({
  page,
}) => {
  await setup(page);
  await page.clock.install();
  let catalogueRevision = 0;
  let catalogueCalls = 0;
  await page.route("**/api/assets", (r) => {
    catalogueCalls++;
    return r.fulfill({
      json: [
        { ...stock, data_revision: String(catalogueRevision) },
        {
          ...stock,
          id: "yf-btc-usd",
          name: "Bitcoin",
          category: "crypto",
          data_revision: String(catalogueRevision),
        },
      ],
    });
  });
  let validationCalls = 0;
  let release: (() => void) | undefined;
  await page.route("**/api/portfolio/validation", async (r) => {
    validationCalls++;
    await new Promise<void>((resolve) => {
      release = resolve;
    });
    return r.fulfill({
      json: { ...model(), parameters: { whole_shares: true } },
    });
  });
  await page.goto("/markets/portfolio");
  await page
    .getByRole("tab", { name: "Volatilité minimale", exact: true })
    .click();
  const panel = page.getByRole("region", {
    name: "Validation historique",
    exact: true,
  });
  await page
    .getByRole("tab", { name: "Corrélation minimale", exact: true })
    .click();
  await panel.getByLabel("Capital initial (€)").fill("12500");
  await panel.getByLabel("Titres entiers uniquement (actions et ETF)").check();
  await panel.getByRole("button", { name: "Lancer la validation" }).click();
  await expect.poll(() => validationCalls).toBe(1);
  let navigations = 0;
  page.on("framenavigated", (f) => {
    if (f === page.mainFrame()) navigations++;
  });
  catalogueRevision++;
  const before = catalogueCalls;
  await page.clock.fastForward(15001);
  await expect.poll(() => catalogueCalls).toBeGreaterThan(before);
  await expect(panel.getByLabel("Capital initial (€)")).toHaveValue("12500");
  await expect(
    page.getByRole("tab", { name: "Corrélation minimale", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    panel.getByLabel("Titres entiers uniquement (actions et ETF)"),
  ).toBeChecked();
  release!();
  await expect(
    panel.getByRole("table", { name: "Résultats hors échantillon" }),
  ).toBeVisible();
  await expect(
    panel.getByText(/Des données ont été actualisées depuis ce calcul/),
  ).toBeVisible();
  await expect(
    panel
      .getByRole("table", { name: "Positions finales de la méthode" })
      .locator("thead"),
  ).toContainText("Quantité");
  catalogueRevision++;
  await page.clock.fastForward(15001);
  await expect.poll(() => catalogueCalls).toBeGreaterThan(before + 1);
  await expect(
    panel.getByRole("table", { name: "Résultats hors échantillon" }),
  ).toBeVisible();
  expect(validationCalls).toBe(1);
  expect(navigations).toBe(0);
});
