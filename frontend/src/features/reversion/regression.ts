import type { Point } from "../../lib/types";

export type RegressionScale = "log" | "linear";
const minimumObservations = 30;

/** OLS against elapsed calendar years; residual error has n - 2 degrees of freedom. */
export function fitRegression(
  points: Point[],
  scale: RegressionScale,
  threshold: number,
) {
  if (points.length < minimumObservations)
    throw new Error(`Choisissez au moins ${minimumObservations} observations.`);
  if (points.some((p) => !Number.isFinite(p.value) || p.value <= 0))
    throw new Error(
      "La régression nécessite des prix strictement positifs et finis.",
    );
  const origin = Date.parse(points[0].time);
  const x = points.map(
    (p) => (Date.parse(p.time) - origin) / (365.25 * 86400000),
  );
  const y = points.map((p) => (scale === "log" ? Math.log(p.value) : p.value));
  const n = points.length;
  const meanX = x.reduce((a, b) => a + b, 0) / n;
  const meanY = y.reduce((a, b) => a + b, 0) / n;
  let xx = 0,
    xy = 0,
    yy = 0;
  for (let i = 0; i < n; i++) {
    xx += (x[i] - meanX) ** 2;
    xy += (x[i] - meanX) * (y[i] - meanY);
    yy += (y[i] - meanY) ** 2;
  }
  if (!(xx > 0))
    throw new Error("La période doit contenir plusieurs dates distinctes.");
  const slope = xy / xx;
  const predicted = x.map((t) => meanY + slope * (t - meanX));
  const residuals = y.map((v, i) => v - predicted[i]);
  const sse = residuals.reduce((a, b) => a + b * b, 0);
  const sigma = Math.sqrt(sse / (n - 2));
  const degenerate = sigma <= 1e-10 * Math.max(1, Math.abs(meanY));
  const restore = (v: number) => (scale === "log" ? Math.exp(v) : v);
  const rows = points.map((p, i) => {
    const z = degenerate ? null : residuals[i] / sigma;
    return {
      ...p,
      trend: restore(predicted[i]),
      lower: restore(predicted[i] - threshold * sigma),
      upper: restore(predicted[i] + threshold * sigma),
      z,
      zone:
        z !== null && z <= -threshold
          ? "entry"
          : z !== null && z >= threshold
            ? "exit"
            : "neutral",
    };
  });
  if (rows.some((p) => ![p.trend, p.lower, p.upper].every(Number.isFinite)))
    throw new Error(
      "L’échelle choisie produit des valeurs trop grandes. Réduisez la période.",
    );
  // A descriptive stability check, not a statistical stationarity test.
  const half = Math.floor(n / 2);
  function segmentSlope(start: number, end: number) {
    const count = end - start;
    let mx = 0,
      my = 0,
      numerator = 0,
      denominator = 0;
    for (let i = start; i < end; i++) {
      mx += x[i] / count;
      my += y[i] / count;
    }
    for (let i = start; i < end; i++) {
      numerator += (x[i] - mx) * (y[i] - my);
      denominator += (x[i] - mx) ** 2;
    }
    return denominator > 0 ? numerator / denominator : 0;
  }
  const firstSlope = segmentSlope(0, half),
    secondSlope = segmentSlope(half, n);
  return {
    rows,
    slope,
    sigma,
    degenerate,
    r2: yy > 1e-20 ? Math.max(0, Math.min(1, 1 - sse / yy)) : null,
    annualTrend:
      scale === "log"
        ? Math.expm1(slope)
        : predicted[0] > 0
          ? slope / predicted[0]
          : NaN,
    reversal: firstSlope * secondSlope < 0,
  };
}

/** Full-period fitted bands: descriptive simulation with hindsight, not out of sample. */
export function compareRegressionStrategy(
  rows: Pick<
    ReturnType<typeof fitRegression>["rows"][number],
    "time" | "value" | "lower" | "upper" | "z"
  >[],
  buyFee = 0,
  sellFee = 0,
) {
  if (
    ![buyFee, sellFee].every(
      (fee) => Number.isFinite(fee) && fee >= 0 && fee < 1,
    )
  )
    throw new Error("Les frais doivent être compris entre 0 et 100 % exclus.");
  let cash = 100;
  let units = 0;
  let purchases = 0;
  let sales = 0;
  let exposedTime = 0;
  const totalTime =
    rows.length > 1
      ? Date.parse(rows.at(-1)!.time) - Date.parse(rows[0].time)
      : 0;
  const equity = rows.map((row, i) => {
    if (row.z !== null) {
      if (units === 0 && row.value <= row.lower) {
        units = cash / (row.value * (1 + buyFee));
        cash = 0;
        purchases++;
      } else if (units > 0 && row.value >= row.upper) {
        cash = units * row.value * (1 - sellFee);
        units = 0;
        sales++;
      }
    }
    if (units > 0 && i + 1 < rows.length)
      exposedTime += Date.parse(rows[i + 1].time) - Date.parse(row.time);
    return {
      time: row.time,
      strategy: cash + units * row.value,
      benchmark: (100 * row.value) / (rows[0].value * (1 + buyFee)),
    };
  });
  const metrics = (key: "strategy" | "benchmark") => {
    let peak = 100;
    let maxDrawdown = 0;
    for (const point of equity) {
      peak = Math.max(peak, point[key]);
      maxDrawdown = Math.min(maxDrawdown, point[key] / peak - 1);
    }
    const capital = equity.at(-1)?.[key] ?? 100;
    return { capital, totalReturn: capital / 100 - 1, maxDrawdown };
  };
  return {
    equity,
    strategy: metrics("strategy"),
    benchmark: metrics("benchmark"),
    purchases,
    sales,
    invested: units > 0,
    exposure: totalTime > 0 ? exposedTime / totalTime : 0,
  };
}
