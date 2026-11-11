import type { Point } from "../../lib/types";
import { fitRegression } from "../reversion/regression";
import { fitGarch } from "./garch";

const DAY = 86_400_000;
const YEAR = 365.25;
const PATHS = 4096;
export type ForecastPoint = {
  time: string;
  p05: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
};

/** Up to three years of log regression + AR(1) deviations + GARCH(1,1).
 * Parameters are fitted only up to the final observation. Probabilities are
 * conditional on this fitted model, not empirically calibrated coverage.
 */
export function predict(
  points: Point[],
  crypto: boolean,
  simulation?: {
    normal: (time: string, pair: number) => number;
    observe: (time: string, prices: Float64Array) => void;
  },
) {
  if (points.length < 61)
    throw new Error(
      "Au moins 61 cours quotidiens sont nécessaires pour estimer la régression et GARCH.",
    );
  if (
    points.some(
      (p, i) =>
        !Number.isFinite(p.value) ||
        p.value <= 0 ||
        !/^\d{4}-\d{2}-\d{2}$/.test(p.time) ||
        !Number.isFinite(Date.parse(p.time)) ||
        (i > 0 && p.time <= points[i - 1].time),
    )
  )
    throw new Error(
      "Le modèle exige des cours positifs, finis et des dates strictement croissantes.",
    );
  const last = points.at(-1)!;
  const origin = Date.parse(last.time);
  const cutoff = new Date(origin);
  cutoff.setUTCFullYear(cutoff.getUTCFullYear() - 3);
  const partialHistory =
    Date.parse(points[0].time) > cutoff.getTime() + (crypto ? 10 : 20) * DAY;
  const history = points.filter((p) => Date.parse(p.time) >= cutoff.getTime());
  if (history.length < 61)
    throw new Error(
      "Au moins 61 cours quotidiens sont nécessaires sur la période disponible.",
    );
  if (
    history.some(
      (p, i) =>
        i > 0 &&
        Date.parse(p.time) - Date.parse(history[i - 1].time) >
          (crypto ? 10 : 20) * DAY,
    )
  )
    throw new Error(
      `Historique trop discontinu : un écart entre deux cours dépasse ${crypto ? 10 : 20} jours.`,
    );
  const regression = fitRegression(history, "log", 2);
  // Work in the exact residual standard deviation used by the Regression tab.
  const scale = regression.degenerate ? 1 : regression.sigma;
  const residuals = regression.rows.map(
    (p) => (Math.log(p.value) - Math.log(p.trend)) / scale,
  );
  let numerator = 0,
    denominator = 0;
  for (let i = 1; i < residuals.length; i++) {
    numerator += residuals[i] * residuals[i - 1];
    denominator += residuals[i - 1] ** 2;
  }
  const phi = regression.degenerate
    ? 1
    : Math.max(0, Math.min(1, numerator / denominator));
  const innovations = residuals.slice(1).map((u, i) => u - phi * residuals[i]);
  const garch = fitGarch(innovations);
  // Seeded antithetic Gaussian paths: stable output and a symmetric log-price distribution.
  let seed = 20261111;
  function normal() {
    function uniform() {
      seed = (Math.imul(1664525, seed) + 1013904223) >>> 0;
      return (seed + 0.5) / 4294967296;
    }
    return (
      Math.sqrt(-2 * Math.log(uniform())) * Math.cos(2 * Math.PI * uniform())
    );
  }
  const end = new Date(origin),
    day = end.getUTCDate();
  end.setUTCDate(1);
  end.setUTCMonth(end.getUTCMonth() + 6);
  end.setUTCDate(
    Math.min(
      day,
      new Date(
        Date.UTC(end.getUTCFullYear(), end.getUTCMonth() + 1, 0),
      ).getUTCDate(),
    ),
  );
  // Stocks project on weekdays; holidays are not modelled. A weekend horizon ends on Friday.
  if (!crypto)
    while ([0, 6].includes(end.getUTCDay()))
      end.setUTCDate(end.getUTCDate() - 1);
  const lastResidual = residuals.at(-1)!;
  const states = new Float64Array(PATHS).fill(lastResidual);
  const variances = new Float64Array(PATHS / 2).fill(garch.nextVariance);
  const forecast: ForecastPoint[] = [
    {
      time: last.time,
      p05: last.value,
      p25: last.value,
      p50: last.value,
      p75: last.value,
      p95: last.value,
    },
  ];
  const lastTrend = Math.log(regression.rows.at(-1)!.trend);
  let step = 0;
  for (let time = origin + DAY; time <= end.getTime(); time += DAY) {
    const date = new Date(time);
    if (!crypto && [0, 6].includes(date.getUTCDay())) continue;
    step++;
    const trend = lastTrend + (regression.slope * (time - origin)) / DAY / YEAR;
    for (let i = 0; i < PATHS / 2; i++) {
      const shock =
        Math.sqrt(variances[i]) *
        (simulation?.normal(date.toISOString().slice(0, 10), i) ?? normal());
      states[2 * i] = phi * states[2 * i] + shock;
      states[2 * i + 1] = phi * states[2 * i + 1] - shock;
      variances[i] =
        garch.omega + garch.alpha * shock * shock + garch.beta * variances[i];
    }
    const sorted = Float64Array.from(states).sort();
    const quantile = (p: number) => {
      const index = p * (PATHS - 1),
        i = Math.floor(index);
      return Math.exp(
        trend +
          scale *
            (sorted[i] +
              (index - i) * (sorted[Math.min(i + 1, PATHS - 1)] - sorted[i])),
      );
    };
    const row = {
      time: date.toISOString().slice(0, 10),
      p05: quantile(0.05),
      p25: quantile(0.25),
      p50: Math.exp(trend + scale * phi ** step * lastResidual),
      p75: quantile(0.75),
      p95: quantile(0.95),
    };
    if (
      [row.p05, row.p25, row.p50, row.p75, row.p95].some(
        (v) => !Number.isFinite(v) || v <= 0,
      )
    )
      throw new Error(
        "Projection hors limites numériques pour cet historique.",
      );
    simulation?.observe(
      row.time,
      Float64Array.from(states, (u) => Math.exp(trend + scale * u)),
    );
    forecast.push(row);
  }
  return {
    history,
    forecast,
    regression,
    garch,
    phi,
    paths: PATHS,
    observations: history.length,
    partialHistory,
    volatility:
      Math.sqrt(garch.nextVariance) * scale * Math.sqrt(crypto ? YEAR : 252),
    currentZ: regression.rows.at(-1)!.z,
  };
}
