import { afterEach, expect, it, vi } from "vitest";
import { migrateSp500Storage } from "../../src/lib/sp500Migration";

afterEach(() => vi.unstubAllGlobals());
it("migrates instrument references once and backs up original quantities", () => {
  const saved = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => saved.get(key) ?? null,
    setItem: (key: string, value: string) => saved.set(key, value),
  });
  const original = JSON.stringify({
    "yf-ese.pa": 5,
    "yf-psp5.pa": 2,
    other: 4,
  });
  saved.set("investor-quantities", original);
  saved.set(
    "investor-strategies",
    JSON.stringify([
      {
        id: "s",
        quantities: { "yf-ese.pa": 3 },
        lockedAssetIds: ["yf-ese.pa"],
      },
    ]),
  );
  saved.set("investor-favorites", JSON.stringify({ "yf-ese.pa": "gold" }));
  saved.set(
    "investor-removed-assets",
    JSON.stringify(["yf-psp5.pa", "yf-ese.pa", "other"]),
  );
  migrateSp500Storage();
  expect(JSON.parse(saved.get("investor-quantities")!)).toEqual({
    "yf-psp5.pa": 7,
    other: 4,
  });
  expect(saved.get("investor-quantities-before-amundi-sp500")).toBe(original);
  expect(JSON.parse(saved.get("investor-strategies")!)).toEqual([
    {
      id: "s",
      quantities: { "yf-psp5.pa": 3 },
      lockedAssetIds: ["yf-psp5.pa"],
    },
  ]);
  expect(JSON.parse(saved.get("investor-favorites")!)).toEqual({
    "yf-psp5.pa": "gold",
  });
  expect(JSON.parse(saved.get("investor-removed-assets")!)).toEqual(["other"]);
  saved.set("investor-removed-assets", JSON.stringify(["yf-psp5.pa"]));
  migrateSp500Storage();
  expect(JSON.parse(saved.get("investor-removed-assets")!)).toEqual([
    "yf-psp5.pa",
  ]);
});
