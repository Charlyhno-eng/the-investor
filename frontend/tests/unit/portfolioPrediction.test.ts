import { describe, it, expect } from "vitest";
import {
  predictPortfolio,
  dependence,
  type HoldingSeries,
} from "../../src/features/prediction/portfolioModel";
import { predict } from "../../src/features/prediction/model";
function asset(id: string, n = 800, value = 100): HoldingSeries {
  return {
    id,
    name: id,
    crypto: true,
    value,
    price_date: "2026-11-11",
    points: Array.from({ length: n }, (_, i) => ({
      time: new Date(Date.UTC(2026, 10, 11 - n + 1 + i))
        .toISOString()
        .slice(0, 10),
      value: 100 * Math.exp(i * 0.0003 + 0.07 * Math.sin(i / 15)),
    })),
  };
}
describe("joint portfolio forecasts", () => {
  it("preserves individual marginal forecast and scales with quantities", () => {
    const a = asset("a");
    const one = predictPortfolio([a]);
    const own = predict(a.points, true);
    expect(one.forecast.at(-1)!.p50).toBeCloseTo(
      (100 * own.forecast.at(-1)!.p50) / a.points.at(-1)!.value,
      2,
    );
    const doubled = predictPortfolio([{ ...a, value: 200 }]);
    one.forecast.forEach((p, i) => {
      for (const k of ["p05", "p25", "p50", "p75", "p95"] as const)
        expect(doubled.forecast[i][k]).toBeCloseTo(2 * p[k], 8);
    });
  });
  it("does not truncate an older model when a young asset is added", () => {
    const a = asset("a");
    const original = predictPortfolio([a]);
    const young = asset("young", 20, 1e-8);
    const joint = predictPortfolio([a, young]);
    expect(joint.forecast.at(-1)!.p50).toBeCloseTo(
      original.forecast.at(-1)!.p50,
      5,
    );
    expect(joint.short).toEqual(["young"]);
  });
  it("includes the very first quote, starts at total and stays finite and ordered", () => {
    const result = predictPortfolio([asset("old"), asset("new", 1, 30)]);
    expect(result.forecast[0].p50).toBe(130);
    for (const p of result.forecast) {
      expect(p.p05).toBeGreaterThan(0);
      expect(p.p05).toBeLessThanOrEqual(p.p25);
      expect(p.p25).toBeLessThanOrEqual(p.p50);
      expect(p.p50).toBeLessThanOrEqual(p.p75);
      expect(p.p75).toBeLessThanOrEqual(p.p95);
      expect(Number.isFinite(p.p95)).toBe(true);
    }
  });
  it("estimates signed dependence and handles disjoint histories with a PSD factor", () => {
    const a = new Map([
        ["a", 1],
        ["b", -1],
      ]),
      b = new Map([
        ["a", -1],
        ["b", 1],
      ]),
      c = new Map([["c", 1]]);
    const { matrix, factor } = dependence([a, b, c]);
    expect(matrix[0][1]).toBeCloseTo(-0.95);
    expect(matrix[0][2]).toBe(0);
    matrix.forEach((row, i) =>
      row.forEach((x, j) =>
        expect(
          factor[i].reduce((s, v, k) => s + v * factor[j][k], 0),
        ).toBeCloseTo(x, 10),
      ),
    );
  });
  it("is reproducible and handles mixed market calendars", () => {
    const a = asset("stock");
    a.crypto = false;
    a.points = a.points.filter(
      (p) => ![0, 6].includes(new Date(p.time).getUTCDay()),
    );
    const series = [a, asset("crypto", 300)];
    expect(predictPortfolio(series).forecast).toEqual(
      predictPortfolio(series).forecast,
    );
  });
  it("lets dependence change portfolio dispersion instead of adding quantiles", () => {
    const a = asset("a", 200);
    const same = { ...a, id: "same" };
    const opposite = {
      ...a,
      id: "opposite",
      points: a.points.map((p) => ({ ...p, value: 10000 / p.value })),
    };
    const positive = predictPortfolio([a, same]);
    const negative = predictPortfolio([a, opposite]);
    const p = positive.forecast.at(-1)!,
      n = negative.forecast.at(-1)!;
    expect(positive.correlations[0][1]).toBeGreaterThan(0.9);
    expect(negative.correlations[0][1]).toBeLessThan(-0.9);
    expect(p.p95 - p.p05).toBeGreaterThan(n.p95 - n.p05);
  });
});
