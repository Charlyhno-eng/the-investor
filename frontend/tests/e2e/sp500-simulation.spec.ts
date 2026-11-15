import { test, expect } from "@playwright/test";
import { mockApi, stock } from "./fixtures";

function result(seed: number) {
  const metrics = {
    total_return: 0.2,
    cagr: 0.04,
    max_drawdown: -0.3,
    volatility: 0.12,
    annual_turnover: 0.2,
    worst_quarter: -0.15,
    sharpe: 0.8,
    cost_eur: 120,
    positive_quarters: 10,
    winning_quarters: 8,
    market_exposure: 0.6,
  };
  return {
    status: "ready",
    simulation: { seed, source_start: "2013-09-16", source_end: "2026-11-13" },
    comparison: {
      status: "ready",
      start: "2026-11-13",
      end: "2031-11-13",
      benchmark_name: "S&P 500 · Buy & Hold",
      completed_quarters: 19,
      equity: Array.from({ length: 100 }, (_, i) => ({
        time: new Date(Date.UTC(2026, 10, 13 + i)).toISOString().slice(0, 10),
        benchmark: 100 + i / 10,
        strategy: 100 + i / 8,
      })),
      metrics: {
        benchmark: metrics,
        strategy: { ...metrics, sharpe: 1.1, max_drawdown: -0.15 },
      },
      final_portfolio: { initial_capital: 10000, total: 12000 },
    },
  };
}

test("random simulation belongs only to built-in S&P strategy, compares two curves and regenerates", async ({
  page,
}, info) => {
  await mockApi(page);
  await page.addInitScript(() =>
    localStorage.setItem(
      "investor-strategies",
      JSON.stringify([
        {
          id: "personal",
          name: "Stratégie 1",
          quantities: {},
          lockedAssetIds: [],
        },
      ]),
    ),
  );
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/portfolio/sp500-simulation", async (route) => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({ json: result(100 + requests.length) });
  });
  await page.goto("/markets/strategy");
  await expect(
    page.getByRole("tab", { name: "Simulation aléatoire" }),
  ).toHaveCount(0);
  await page.locator(".strategy-list .strategy-built-in").click();
  await expect(
    page.getByRole("tab", { name: "Validation historique", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page
    .getByRole("spinbutton", { name: "Capital initial (€)", exact: true })
    .fill("15000");
  await page
    .getByRole("tab", { name: "Simulation aléatoire", exact: true })
    .click();
  const panel = page.getByRole("region", {
    name: "Simulation aléatoire S&P 500",
  });
  expect(requests).toHaveLength(0);
  await panel
    .getByRole("button", { name: "Générer un nouveau parcours" })
    .click();
  await expect(
    panel.getByRole("table", { name: "Résultats de la simulation aléatoire" }),
  ).toBeVisible();
  expect(requests[0]).toEqual({
    years: 5,
    initial_capital: 10000,
    fee_rate: 0.0012,
    whole_shares: true,
  });
  const table = panel.getByRole("table", {
    name: "Résultats de la simulation aléatoire",
  });
  for (const label of [
    "CAGR net",
    "Drawdown maximal",
    "Volatilité annualisée",
    "Sharpe · taux de référence 0 %",
    "Frais payés (€)",
  ]) {
    await expect(table.getByRole("rowheader", { name: label })).toBeVisible();
  }
  await expect(table.getByRole("columnheader")).toHaveText([
    "Indicateur",
    "S&P 500 · Buy & Hold",
    "S&P 500 · Régression",
  ]);
  await expect(
    panel
      .getByRole("group", { name: "Légende de la simulation" })
      .locator("span"),
  ).toHaveText(["S&P 500 · Buy & Hold", "S&P 500 · Régression"]);
  await expect(panel).not.toContainText("Équipondération");
  for (const text of [
    "Des baisses de 30",
    "Tirage 101",
    "Capital final ·",
    "Comparaison à S&P 500",
  ]) {
    await expect(panel).not.toContainText(text);
  }
  await panel
    .getByRole("combobox", { name: "Durée simulée" })
    .selectOption("3");
  await panel
    .getByRole("spinbutton", { name: "Capital initial (€)" })
    .fill("20000");
  await panel.getByRole("checkbox", { name: "Titres entiers" }).uncheck();
  await panel
    .getByRole("button", { name: "Générer un nouveau parcours" })
    .click();
  await expect(
    panel.getByRole("table", { name: "Résultats de la simulation aléatoire" }),
  ).toBeVisible();
  expect(requests[1]).toEqual({
    years: 3,
    initial_capital: 20000,
    fee_rate: 0.0012,
    whole_shares: false,
  });
  await page.screenshot({
    path: info.outputPath("sp500-random.png"),
    fullPage: true,
  });
  await page
    .getByRole("tab", { name: "Validation historique", exact: true })
    .click();
  await expect(
    page.getByRole("spinbutton", { name: "Capital initial (€)", exact: true }),
  ).toHaveValue("15000");
  await page
    .getByRole("tab", { name: "Simulation aléatoire", exact: true })
    .click();
  await expect(
    panel.getByRole("table", { name: "Résultats de la simulation aléatoire" }),
  ).toBeVisible();
  await page
    .locator(".strategy-list button")
    .filter({ hasText: "Stratégie 1" })
    .click();
  await expect(
    page.getByRole("tab", { name: "Simulation aléatoire" }),
  ).toHaveCount(0);
});

test("random simulation handles missing history and server errors then retries", async ({
  page,
}) => {
  await mockApi(page);
  let calls = 0;
  await page.route("**/api/portfolio/sp500-simulation", async (route) => {
    calls++;
    if (calls === 1)
      await route.fulfill({
        json: {
          status: "insufficient",
          message: "Importez au moins cinq ans de cours PSP5.",
        },
      });
    else if (calls === 2)
      await route.fulfill({
        status: 503,
        json: { detail: "Calcul temporairement indisponible." },
      });
    else await route.fulfill({ json: result(999) });
  });
  await page.goto("/markets/strategy");
  await page.locator(".strategy-list .strategy-built-in").click();
  await page.getByRole("tab", { name: "Simulation aléatoire" }).click();
  const panel = page.getByRole("region", {
    name: "Simulation aléatoire S&P 500",
  });
  const generate = panel.getByRole("button", {
    name: "Générer un nouveau parcours",
  });
  await generate.click();
  await expect(panel.getByRole("status")).toContainText(
    "Importez au moins cinq ans",
  );
  await generate.click();
  await expect(panel.getByRole("alert")).toContainText(
    "Calcul temporairement indisponible",
  );
  await generate.click();
  await expect(
    panel.getByRole("table", { name: "Résultats de la simulation aléatoire" }),
  ).toBeVisible();
  await expect(panel.getByRole("alert")).toHaveCount(0);
});

test("batch updates live, stops and compares win rates without plotting every path", async ({
  page,
}, info) => {
  await mockApi(page);
  await page.clock.install();
  let catalogueCalls = 0;
  await page.route("**/api/assets", async (route) => {
    catalogueCalls++;
    await route.fulfill({
      json: [
        {
          ...stock,
          id: "yf-psp5.pa",
          data_revision: catalogueCalls,
          last_value: stock.last_value + catalogueCalls,
        },
      ],
    });
  });
  await page.addInitScript(() => {
    const original = window.fetch;
    window.fetch = async (input, init) => {
      if (!String(input).endsWith("/portfolio/sp500-simulation/batch"))
        return original(input, init);
      const payload = JSON.parse(String(init?.body));
      const encoder = new TextEncoder();
      let completed = 0;
      const stream = new ReadableStream({
        async pull(controller) {
          if (init?.signal?.aborted) {
            controller.close();
            return;
          }
          if (completed > 0)
            await new Promise((resolve) => setTimeout(resolve, 400));
          completed++;
          const row = {
            valid: completed,
            benchmark_wins: 0,
            strategy_wins: completed,
            ties: 0,
            benchmark_mean: 0.1,
            strategy_mean: 0.2,
            lower_is_better: false,
          };
          controller.enqueue(
            encoder.encode(
              JSON.stringify({
                status: completed === payload.count ? "complete" : "running",
                completed,
                total: payload.count,
                seed: 123,
                metrics: {
                  cagr: row,
                  max_drawdown: {
                    ...row,
                    benchmark_mean: -0.3,
                    strategy_mean: -0.1,
                  },
                  volatility: {
                    ...row,
                    benchmark_wins: completed,
                    strategy_wins: 0,
                    lower_is_better: true,
                  },
                },
              }) + "\n",
            ),
          );
          if (completed === payload.count) controller.close();
        },
      });
      return new Response(stream);
    };
  });
  await page.goto("/markets/strategy");
  await page.locator(".strategy-list .strategy-built-in").click();
  await page.getByRole("tab", { name: "Simulation aléatoire" }).click();
  const panel = page.getByRole("region", {
    name: "Simulation aléatoire S&P 500",
  });
  await expect(
    panel.getByRole("spinbutton", { name: "Frais par achat/vente (%)" }),
  ).toHaveValue("0.12");
  await panel
    .getByRole("combobox", { name: "Mode de génération" })
    .selectOption("batch");
  await expect(
    panel.getByRole("spinbutton", { name: "Nombre de parcours" }),
  ).toHaveValue("1000");
  await panel.getByRole("button", { name: "Lancer les simulations" }).click();
  const table = panel.getByRole("table", {
    name: "Comparaison des simulations multiples",
  });
  await expect(table).toBeVisible();
  await expect(panel.getByRole("status")).toContainText(
    "/ 1000 parcours calculés",
  );
  // A background price refresh must preserve the active stream and its table.
  const callsBeforeRefresh = catalogueCalls;
  await page.clock.fastForward(15_000);
  await expect.poll(() => catalogueCalls).toBeGreaterThan(callsBeforeRefresh);
  await expect(table).toBeVisible();
  await expect(
    panel.getByRole("button", { name: "Simulation en cours…" }),
  ).toBeDisabled();
  await panel.getByRole("button", { name: "Arrêter", exact: true }).click();
  await expect(table).toBeVisible();
  await expect(
    panel.getByRole("button", { name: "Lancer les simulations" }),
  ).toBeEnabled();
  await expect(panel.getByRole("img", { name: /deux courbes/ })).toHaveCount(0);
  await panel.getByRole("spinbutton", { name: "Nombre de parcours" }).fill("3");
  await expect(table).toHaveCount(0);
  await panel.getByRole("button", { name: "Lancer les simulations" }).click();
  await expect(panel.getByRole("status")).toContainText(
    "3 / 3 parcours calculés · Terminé",
  );
  // Completed results also remain available after later catalogue updates.
  const callsBeforeCompletionRefresh = catalogueCalls;
  await page.clock.fastForward(15_000);
  await expect
    .poll(() => catalogueCalls)
    .toBeGreaterThan(callsBeforeCompletionRefresh);
  await expect(panel.getByRole("status")).toContainText(
    "3 / 3 parcours calculés · Terminé",
  );
  const cagr = table.getByRole("row", { name: /^CAGR net/ });
  await expect(cagr.locator("td").nth(2)).toHaveText(/0\s*%/);
  await expect(cagr.locator("td").nth(3)).toHaveText(/100\s*%/);
  await expect(cagr.locator("td").nth(3)).toHaveAttribute("data-best", "true");
  await expect(table.getByRole("columnheader")).toHaveText([
    "Indicateur",
    "Buy & Hold · moyenne",
    "Régression · moyenne",
    "Buy & Hold gagne",
    "Régression gagne",
    "Égalités",
  ]);
  await page.screenshot({
    path: info.outputPath("sp500-batch.png"),
    fullPage: true,
  });
});
