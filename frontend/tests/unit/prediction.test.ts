import { describe, expect, it } from "vitest";
import { predict } from "../../src/features/prediction/model";
import { fitGarch } from "../../src/features/prediction/garch";
import { fitRegression } from "../../src/features/reversion/regression";
import type { Point } from "../../src/lib/types";

function history(length = 1200): Point[] {
  return Array.from({ length }, (_, i) => ({
    time: new Date(Date.UTC(2022, 0, 1 + i)).toISOString().slice(0, 10),
    value:
      100 *
      Math.exp(0.0003 * i + 0.08 * Math.sin(i / 15) + 0.01 * Math.sin(i * 2)),
  }));
}

describe("GARCH with regression deviations", () => {
  it("uses exactly three years, the shared log regression, and a six-month horizon", () => {
    const result = predict(history(), true);
    const fit = fitRegression(result.history, "log", 2);
    expect(result.history[0].time).toBe("2022-04-14");
    expect(result.forecast.at(-1)!.time).toBe("2025-10-14");
    expect(result.regression.slope).toBe(fit.slope);
    expect(result.regression.sigma).toBe(fit.sigma);
    expect(result.currentZ).toBe(fit.rows.at(-1)!.z);
    expect(result.phi).toBeGreaterThanOrEqual(0);
    expect(result.phi).toBeLessThanOrEqual(1);
    const first = result.forecast[0];
    for (const q of ["p05", "p25", "p50", "p75", "p95"] as const)
      expect(first[q]).toBe(history().at(-1)!.value);
    expect(first.time).toBe(history().at(-1)!.time);
  });

  it("uses all available prices for assets with less than three years of history", () => {
    for (const length of [61, 120, 800]) {
      const points = history(length);
      const result = predict(points, true);
      expect(result.history).toEqual(points);
      expect(result.observations).toBe(length);
      expect(result.partialHistory).toBe(true);
      expect(result.forecast[0].p50).toBe(points.at(-1)!.value);
      expect(result.forecast.at(-1)!.p95).toBeGreaterThan(
        result.forecast.at(-1)!.p05,
      );
    }
    expect(predict(history(), true).partialHistory).toBe(false);
  });

  it("computes the median from extrapolated regression and the AR residual", () => {
    const result = predict(history(), true);
    const last = result.regression.rows.at(-1)!;
    const terminal = result.forecast.at(-1)!;
    const t =
      (Date.parse(terminal.time) - Date.parse(last.time)) / 86400000 / 365.25;
    const steps = result.forecast.length - 1;
    const expected = Math.exp(
      Math.log(last.trend) +
        result.regression.slope * t +
        result.phi ** steps * (Math.log(last.value) - Math.log(last.trend)),
    );
    expect(terminal.p50).toBeCloseTo(expected, 10);
    for (const p of result.forecast) {
      expect(p.p05).toBeGreaterThan(0);
      expect(p.p05).toBeLessThanOrEqual(p.p25);
      expect(p.p25).toBeLessThanOrEqual(p.p50);
      expect(p.p50).toBeLessThanOrEqual(p.p75);
      expect(p.p75).toBeLessThanOrEqual(p.p95);
    }
  });

  it("is reproducible and invariant to the currency scale", () => {
    const a = predict(history(), true);
    expect(predict(history(), true).forecast).toEqual(a.forecast);
    const b = predict(
      history().map((p) => ({ ...p, value: p.value / 1000 })),
      true,
    );
    expect(b.currentZ).toBeCloseTo(a.currentZ!, 9);
    expect(b.forecast.at(-1)!.p95 * 1000).toBeCloseTo(
      a.forecast.at(-1)!.p95,
      7,
    );
  });

  it("does not use observations older than the calibration window", () => {
    const a = predict(history(), true);
    const points = history().map((p) =>
      p.time < a.history[0].time ? { ...p, value: 999999 } : p,
    );
    expect(predict(points, true).forecast).toEqual(a.forecast);
  });

  it("handles constant prices without fabricating uncertainty", () => {
    const result = predict(
      history().map((p) => ({ ...p, value: 42 })),
      true,
    );
    expect(result.currentZ).toBeNull();
    expect(result.volatility).toBe(0);
    for (const p of result.forecast) {
      expect(p.p05).toBeCloseTo(42, 10);
      expect(p.p95).toBeCloseTo(42, 10);
    }
  });

  it("projects crypto daily and stocks only on weekdays", () => {
    const crypto = predict(history(), true).forecast;
    const stock = predict(history(), false).forecast;
    expect(crypto.length).toBeGreaterThan(stock.length);
    expect(
      stock
        .slice(1)
        .every((p) => ![0, 6].includes(new Date(p.time).getUTCDay())),
    ).toBe(true);
    // A two-week exchange holiday must not disable forecasts for Asian stocks.
    const holiday = history().filter((_, i) => i < 500 || i > 512);
    expect(() => predict(holiday, false)).not.toThrow();
    expect(() => predict(holiday, true)).toThrow("discontinu");
    const endMonth = history().map((p, i) => ({
      ...p,
      time: new Date(Date.UTC(2025, 4, 31 - 1199 + i))
        .toISOString()
        .slice(0, 10),
    }));
    // 31 May + 6 months is clamped to 30 November, not 1 December.
    expect(predict(endMonth, true).forecast.at(-1)!.time).toBe("2025-11-30");
  });

  it("rejects short, nonpositive, unordered and discontinuous series", () => {
    expect(() => predict(history(60), true)).toThrow("61 cours");

    const invalid = history();
    invalid[100].value = 0;
    expect(() => predict(invalid, true)).toThrow("positifs");
    invalid[100].value = Infinity;
    expect(() => predict(invalid, true)).toThrow("positifs");
    const unordered = history();
    unordered[100].time = unordered[99].time;
    expect(() => predict(unordered, true)).toThrow("croissantes");
    expect(() =>
      predict(
        history().filter((_, i) => i < 500 || i > 520),
        true,
      ),
    ).toThrow("discontinu");
  });
});

describe("variance-targeted Gaussian GARCH fit", () => {
  it("fits volatility clustering, improves on constant variance and filters the final shock", () => {
    let seed = 77;
    function uniform() {
      seed = (Math.imul(1664525, seed) + 1013904223) >>> 0;
      return (seed + 0.5) / 4294967296;
    }
    let variance = 1;
    const innovations = Array.from({ length: 6000 }, () => {
      const e =
        Math.sqrt(variance) *
        Math.sqrt(-2 * Math.log(uniform())) *
        Math.cos(2 * Math.PI * uniform());
      variance = 0.1 + 0.15 * e * e + 0.75 * variance;
      return e;
    });
    const result = fitGarch(innovations);
    expect(result.alpha).toBeCloseTo(0.15, 1);
    expect(result.beta).toBeCloseTo(0.75, 1);
    expect(result.alpha + result.beta).toBeLessThan(0.995);
    expect(result.loss).toBeLessThan(result.constantLoss - 50);
    expect(result.omega).toBeCloseTo(
      result.variance * (1 - result.alpha - result.beta),
      12,
    );
    let filtered = result.variance;
    for (const e of innovations)
      filtered = result.omega + result.alpha * e * e + result.beta * filtered;
    expect(result.nextVariance).toBeCloseTo(filtered, 12);
    expect(fitGarch([...innovations, 20]).nextVariance).toBeGreaterThan(
      result.nextVariance,
    );
  });
  it("supports zero variance and rejects invalid innovations", () => {
    expect(fitGarch(Array(100).fill(0)).nextVariance).toBe(0);
    expect(() => fitGarch(Array(10).fill(1))).toThrow("60 innovations");
    expect(() => fitGarch([...Array(100).fill(1), NaN])).toThrow("finies");
  });
});
