import type { Point } from "../../lib/types";
import { predict, type ForecastPoint } from "./model";

export type HoldingSeries = {
  id: string;
  name: string;
  crypto: boolean;
  value: number;
  price_date: string;
  points: Point[];
};
const PATHS = 4096;
const DAY = 86400000;

/** PSD Gram correlation of dated standardized innovations. Missing observations
 * contribute zero, never fabricated prices. Shrinkage keeps short overlaps stable. */
export function dependence(vectors: Map<string, number>[]) {
  const norms = vectors.map((v) =>
    Math.sqrt([...v.values()].reduce((s, x) => s + x * x, 0)),
  );
  const matrix = vectors.map((a, i) =>
    vectors.map((b, j) => {
      if (i === j) return 1;
      const dot = [...a].reduce((s, [d, x]) => s + x * (b.get(d) ?? 0), 0);
      return norms[i] && norms[j] ? (0.95 * dot) / norms[i] / norms[j] : 0;
    }),
  );
  const factor = matrix.map(() => Array(vectors.length).fill(0) as number[]);
  for (let i = 0; i < vectors.length; i++)
    for (let j = 0; j <= i; j++) {
      let sum = matrix[i][j];
      for (let k = 0; k < j; k++) sum -= factor[i][k] * factor[j][k];
      factor[i][j] =
        i === j ? Math.sqrt(Math.max(sum, 1e-12)) : sum / factor[j][j];
    }
  return { matrix, factor };
}
function normal(day: number, pair: number, component: number) {
  let seed =
    (20261111 ^
      Math.imul(day, 73856093) ^
      Math.imul(pair + 1, 19349663) ^
      Math.imul(component + 1, 83492791)) >>>
    0;
  // Avalanche mixing avoids related component seeds in the Gaussian copula.
  seed ^= seed >>> 16;
  seed = Math.imul(seed, 0x7feb352d);
  seed ^= seed >>> 15;
  seed = Math.imul(seed, 0x846ca68b);
  seed ^= seed >>> 16;
  function uniform() {
    seed ^= seed << 13;
    seed ^= seed >>> 17;
    seed ^= seed << 5;
    return ((seed >>> 0) + 0.5) / 4294967296;
  }
  return (
    Math.sqrt(-2 * Math.log(uniform())) * Math.cos(2 * Math.PI * uniform())
  );
}
export function predictPortfolio(series: HoldingSeries[]) {
  if (!series.length) throw new Error("Aucune position à projeter.");
  const fitted = series.map((s) =>
    s.points.length >= 61 ? predict(s.points, s.crypto) : null,
  );
  const vectors = fitted.map((m) => {
    const vector = new Map<string, number>();
    if (!m) return vector;
    const scale = m.regression.degenerate ? 1 : m.regression.sigma;
    const residuals = m.regression.rows.map(
      (p) => (Math.log(p.value) - Math.log(p.trend)) / scale,
    );
    let variance = m.garch.variance;
    for (let i = 1; i < residuals.length; i++) {
      const e = residuals[i] - m.phi * residuals[i - 1];
      vector.set(
        m.history[i].time,
        variance > 1e-20 ? e / Math.sqrt(variance) : 0,
      );
      variance =
        m.garch.omega + m.garch.alpha * e * e + m.garch.beta * variance;
    }
    return vector;
  });
  const { factor, matrix } = dependence(vectors);
  const origin = series
    .map((s) => s.points.at(-1)!.time)
    .sort()
    .at(-1)!;
  const horizon = new Date(origin + "T00:00:00Z");
  const day = horizon.getUTCDate();
  horizon.setUTCDate(1);
  horizon.setUTCMonth(horizon.getUTCMonth() + 6);
  horizon.setUTCDate(
    Math.min(
      day,
      new Date(
        Date.UTC(horizon.getUTCFullYear(), horizon.getUTCMonth() + 1, 0),
      ).getUTCDate(),
    ),
  );
  const dates = [origin];
  for (let t = Date.parse(origin) + DAY; t <= +horizon; t += DAY)
    dates.push(new Date(t).toISOString().slice(0, 10));
  const totals = dates.map(() => new Float64Array(PATHS));
  series.forEach((s, index) => {
    const samples = new Map<string, Float64Array>();
    const last = s.points.at(-1)!;
    function shock(time: string, pair: number) {
      const day = Math.floor(Date.parse(time) / DAY);
      return factor[index].reduce(
        (sum, w, k) => sum + w * normal(day, pair, k),
        0,
      );
    }
    if (fitted[index]) {
      predict(s.points, s.crypto, {
        normal: shock,
        observe: (time, prices) => {
          samples.set(time, prices);
        },
      });
    } else {
      // Insufficient data for regression/GARCH: driftless log random walk.
      // A single quote supplies no empirical volatility; report that limitation.
      const returns = s.points
        .slice(1)
        .map(
          (p, i) =>
            Math.log(p.value / s.points[i].value) /
            Math.sqrt(
              Math.max(
                1,
                (Date.parse(p.time) - Date.parse(s.points[i].time)) / DAY,
              ),
            ),
        );
      const variance =
        returns.length > 1
          ? returns.reduce((v, r) => v + r * r, 0) / returns.length
          : 0;
      const states = new Float64Array(PATHS).fill(last.value);
      for (let t = Date.parse(last.time) + DAY; t <= +horizon; t += DAY) {
        const time = new Date(t).toISOString().slice(0, 10);
        if (!s.crypto && [0, 6].includes(new Date(t).getUTCDay())) continue;
        for (let i = 0; i < PATHS / 2; i++) {
          const z =
            Math.sqrt(variance * (s.crypto ? 1 : 365.25 / 252)) *
            shock(time, i);
          states[2 * i] *= Math.exp(z);
          states[2 * i + 1] *= Math.exp(-z);
        }
        samples.set(time, Float64Array.from(states));
      }
    }
    let previous = new Float64Array(PATHS).fill(last.value);
    const entries = [...samples].sort(([a], [b]) => a.localeCompare(b));
    let cursor = 0;
    dates.forEach((time, d) => {
      while (cursor < entries.length && entries[cursor][0] <= time)
        previous = entries[cursor++][1];
      for (let p = 0; p < PATHS; p++)
        totals[d][p] +=
          d === 0 ? s.value : (s.value * previous[p]) / last.value;
    });
  });
  const forecast: ForecastPoint[] = dates.map((time, i) => {
    const sorted = totals[i].sort();
    const q = (p: number) => {
      const x = p * (PATHS - 1),
        j = Math.floor(x);
      return (
        sorted[j] + (x - j) * (sorted[Math.min(j + 1, PATHS - 1)] - sorted[j])
      );
    };
    const row = {
      time,
      p05: q(0.05),
      p25: q(0.25),
      p50: q(0.5),
      p75: q(0.75),
      p95: q(0.95),
    };
    if (
      Object.values(row).some(
        (v) => typeof v === "number" && (!Number.isFinite(v) || v <= 0),
      )
    )
      throw new Error("Projection hors limites numériques.");
    return row;
  });
  // Historical chart only: overlap never controls any individual model fit.
  const histories = series.map(
    (s, i) =>
      new Map((fitted[i]?.history ?? s.points).map((p) => [p.time, p.value])),
  );
  const common = [...histories[0].keys()]
    .filter((d) => histories.every((h) => h.has(d)))
    .sort();
  const history = common
    .filter((d) => d < origin)
    .map((time) => ({
      time,
      value: series.reduce(
        (v, s, i) =>
          v + (s.value * histories[i].get(time)!) / s.points.at(-1)!.value,
        0,
      ),
    }));
  history.push({
    time: origin,
    value: series.reduce((v, s) => v + s.value, 0),
  });
  return {
    forecast,
    history,
    correlations: matrix,
    short: series.filter((_, i) => !fitted[i]).map((s) => s.name),
  };
}
