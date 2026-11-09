export const MOMENTUM_HORIZONS = [36, 12, 6] as const;
export type MomentumStock = {
  id: string;
  name: string;
  scores: (number | null)[] | null;
  reason?: string | null;
  partial?: boolean;
};
export function effectiveWeights(
  scores: (number | null)[] | null,
  weights: number[],
): number[] {
  if (!scores || scores.length !== 3 || weights.length !== 3) return [0, 0, 0];
  const available = weights.map((weight, i) =>
    scores[i] !== null &&
    Number.isFinite(scores[i]) &&
    Number.isFinite(weight) &&
    weight > 0
      ? weight
      : 0,
  );
  const total = available.reduce((sum, weight) => sum + weight, 0);
  return available.map((weight) => (total > 0 ? weight / total : 0));
}
export function weightedScore(
  scores: (number | null)[] | null,
  weights: number[],
): number | null {
  const effective = effectiveWeights(scores, weights);
  if (!scores || !effective.some((weight) => weight > 0)) return null;
  return scores.reduce<number>(
    (sum, score, i) => sum + (effective[i] > 0 ? score! * effective[i] : 0),
    0,
  );
}
export function partialHistory(scores: (number | null)[] | null): boolean {
  return (
    !!scores &&
    scores.some((score) => score === null) &&
    scores.some((score) => score !== null)
  );
}
