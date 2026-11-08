import type { Point } from "../../lib/types";

/** Single-asset timing adaptation of MAD; signals use completed observations only. */
export function simulateMad(
  points: Point[],
  start: string,
  end: string,
  fee: number,
) {
  if (!start || !end || start >= end)
    throw new Error("Le début doit précéder la fin de la période.");
  if (!Number.isFinite(fee) || fee < 0 || fee >= 1)
    throw new Error("Les frais doivent être compris entre 0 et 100 % exclus.");
  if (
    points.some(
      (p, i) =>
        !Number.isFinite(p.value) ||
        p.value <= 0 ||
        (i > 0 && p.time <= points[i - 1].time),
    )
  )
    throw new Error(
      "L’historique doit contenir des prix positifs, datés et ordonnés.",
    );
  const first = points.findIndex((p) => p.time >= start);
  if (first < 200)
    throw new Error(
      "Il faut 200 observations avant le début de la simulation. Choisissez une date plus récente.",
    );
  const selected = points.filter((p) => p.time >= start && p.time <= end);
  if (selected.length < 2)
    throw new Error(
      "Au moins deux observations sont nécessaires sur la période.",
    );

  let shortSum = 0;
  let longSum = 0;
  const averages = points.map((p, i) => {
    shortSum += p.value;
    longSum += p.value;
    if (i >= 21) shortSum -= points[i - 21].value;
    if (i >= 200) longSum -= points[i - 200].value;
    return {
      time: p.time,
      short: i >= 20 ? shortSum / 21 : null,
      long: i >= 199 ? longSum / 200 : null,
    };
  });
  let cash = 100;
  let units = 0;
  let purchases = 0;
  let sales = 0;
  let investedDays = 0;
  const day = (time: string) => Date.parse(`${time}T00:00:00Z`);
  const benchmarkUnits = 100 / (selected[0].value * (1 + fee));
  const equity = selected.map((p, offset) => {
    if (offset > 0 && units > 0)
      investedDays += day(p.time) - day(selected[offset - 1].time);
    const signal = averages[first + offset - 1];
    const target = signal.short! > signal.long!;
    if (target && units === 0) {
      units = cash / (p.value * (1 + fee));
      cash = 0;
      purchases++;
    } else if (!target && units > 0) {
      cash = units * p.value * (1 - fee);
      units = 0;
      sales++;
    }
    return {
      time: p.time,
      strategy: cash + units * p.value,
      benchmark: benchmarkUnits * p.value,
    };
  });
  const last = equity.at(-1)!;
  const current = averages[first + selected.length - 1];
  return {
    points: selected,
    short: averages
      .slice(first, first + selected.length)
      .map((p) => ({ time: p.time, value: p.short! })),
    long: averages
      .slice(first, first + selected.length)
      .map((p) => ({ time: p.time, value: p.long! })),
    equity,
    strategyReturn: last.strategy / 100 - 1,
    benchmarkReturn: last.benchmark / 100 - 1,
    assetReturn: selected.at(-1)!.value / selected[0].value - 1,
    purchases,
    sales,
    invested: units > 0,
    exposure: investedDays / (day(last.time) - day(selected[0].time)),
    distance: current.short! / current.long! - 1,
  };
}
