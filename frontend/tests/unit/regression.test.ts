import { test, expect } from "vitest";
import {
  compareRegressionStrategy,
  fitRegression,
} from "../../src/features/reversion/regression";

const series = (values: number[]) =>
  values.map((value, i) => ({
    time: new Date(Date.UTC(2020, 0, 1 + i)).toISOString().slice(0, 10),
    value,
  }));

const bandRows = (values: number[]) =>
  series(values).map((point) => ({
    ...point,
    lower: 90,
    upper: 110,
    z: (point.value - 100) / 10,
  }));

test("band strategy includes touches, holds between signals and reinvests sale proceeds", () => {
  const result = compareRegressionStrategy(
    bandRows([100, 90, 80, 100, 110, 120, 90, 95]),
  );
  expect(result.purchases).toBe(2);
  expect(result.sales).toBe(1);
  expect(result.invested).toBe(true);
  expect(result.equity.map((p) => p.strategy)).toEqual([
    100,
    100,
    (100 / 90) * 80,
    (100 / 90) * 100,
    (100 / 90) * 110,
    (100 / 90) * 110,
    (100 / 90) * 110,
    (((100 / 90) * 110) / 90) * 95,
  ]);
  expect(result.benchmark.capital).toBeCloseTo(95);
  expect(result.strategy.totalReturn).toBeCloseTo((110 / 90) * (95 / 90) - 1);
  expect(result.strategy.maxDrawdown).toBeCloseTo(80 / 90 - 1);
  expect(result.exposure).toBeCloseTo(4 / 7);
});

test("fees apply to executed notional and exposure measures calendar holding time", () => {
  const rows = bandRows([80, 120, 130]);
  rows[1].time = "2020-01-04";
  rows[2].time = "2020-01-05";
  const result = compareRegressionStrategy(rows, 0.001, 0.002);
  expect(result.strategy.capital).toBeCloseTo(
    (100 / (80 * 1.001)) * 120 * 0.998,
    10,
  );
  expect(result.benchmark.capital).toBeCloseTo((100 / (80 * 1.001)) * 130, 10);
  expect(result.exposure).toBe(0.75);
  const noEntry = compareRegressionStrategy(
    bandRows([100, 105, 110]),
    0.001,
    0.002,
  );
  expect(noEntry.exposure).toBe(0);
  expect(noEntry.strategy.capital).toBe(100);
  const lastEntry = compareRegressionStrategy(bandRows([100, 105, 80]));
  expect(lastEntry.invested).toBe(true);
  expect(lastEntry.exposure).toBe(0);
});

test("overshoots execute at observed prices and no entry stays in cash", () => {
  const result = compareRegressionStrategy(bandRows([80, 120, 130]));
  expect(result.strategy.capital).toBe(150);
  expect(result.sales).toBe(1);
  expect(result.invested).toBe(false);
  const noEntry = compareRegressionStrategy(bandRows([100, 110, 105]));
  expect(noEntry.strategy.capital).toBe(100);
  expect(noEntry.purchases).toBe(0);
  expect(noEntry.sales).toBe(0);
  expect(noEntry.benchmark.capital).toBe(105);
});

test("zero dispersion produces no trades, and threshold changes the comparison", () => {
  const flat = fitRegression(series(Array(40).fill(100)), "log", 0);
  expect(compareRegressionStrategy(flat.rows).purchases).toBe(0);
  const points = series(
    Array.from({ length: 80 }, (_, i) => 100 + 5 * Math.sin(i)),
  );
  expect(
    compareRegressionStrategy(fitRegression(points, "linear", 2).rows)
      .purchases,
  ).toBe(0);
  expect(
    compareRegressionStrategy(fitRegression(points, "linear", 0.5).rows).sales,
  ).toBeGreaterThan(0);
});

test("OLS recovers a known straight line and handles zero residual variance", () => {
  const fit = fitRegression(
    series(Array.from({ length: 60 }, (_, i) => 10 + 2 * i)),
    "linear",
    1,
  );
  expect(fit.slope).toBeCloseTo(2 * 365.25, 8);
  expect(fit.r2).toBeCloseTo(1, 10);
  expect(fit.rows[59].trend).toBeCloseTo(128, 10);
  expect(fit.degenerate).toBe(true);
  expect(fit.rows.every((p) => p.z === null && p.zone === "neutral")).toBe(
    true,
  );
});

test("log regression recovers compound growth and is invariant to price units", () => {
  const values = Array.from({ length: 80 }, (_, i) =>
    Math.exp(2 + 0.002 * i + 0.03 * Math.sin(i)),
  );
  const fit = fitRegression(series(values), "log", 1);
  const scaled = fitRegression(series(values.map((v) => v * 1000)), "log", 1);
  expect(fit.slope).toBeCloseTo(0.002 * 365.25, 2);
  expect(fit.rows.some((p) => p.zone === "entry")).toBe(true);
  expect(fit.rows.some((p) => p.zone === "exit")).toBe(true);
  for (let i = 0; i < values.length; i++) {
    expect(scaled.rows[i].z).toBeCloseTo(fit.rows[i].z!, 8);
    expect(scaled.rows[i].trend / 1000).toBeCloseTo(fit.rows[i].trend, 8);
  }
  const wider = fitRegression(series(values), "log", 2);
  expect(wider.rows.filter((p) => p.zone !== "neutral").length).toBeLessThan(
    fit.rows.filter((p) => p.zone !== "neutral").length,
  );
});

test("rejects insufficient and invalid prices; flat prices produce no spurious zones", () => {
  expect(() => fitRegression(series([1, 2]), "linear", 0)).toThrow(
    /30 observations/,
  );
  expect(() => fitRegression(series(Array(40).fill(0)), "log", 0)).toThrow(
    /positifs/,
  );
  const fit = fitRegression(series(Array(40).fill(100)), "log", 0);
  expect(fit.r2).toBeNull();
  expect(fit.rows.every((p) => p.zone === "neutral")).toBe(true);
});
