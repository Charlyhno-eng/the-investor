import { describe, expect, it } from "vitest";
import {
  effectiveWeights,
  partialHistory,
  weightedScore,
} from "../../src/features/momentum/score";

describe("momentum on available horizons", () => {
  it("preserves the configured weights for complete histories", () => {
    expect(weightedScore([90, 70, 20], [40, 35, 25])).toBeCloseTo(65.5);
    expect(partialHistory([90, 70, 20])).toBe(false);
  });
  it("redistributes the missing 36-month weight over 12 and 6 months", () => {
    const scores = [null, 70, 50];
    expect(effectiveWeights(scores, [40, 35, 25])).toEqual([
      0,
      35 / 60,
      25 / 60,
    ]);
    expect(weightedScore(scores, [40, 35, 25])).toBeCloseTo(61.6666667);
    expect(partialHistory(scores)).toBe(true);
    expect(weightedScore([null, null, 20], [40, 35, 25])).toBe(20);
  });
  it("does not invent a score when no available horizon has positive weight", () => {
    expect(weightedScore([null, 70, 50], [100, 0, 0])).toBeNull();
    expect(weightedScore([90, 70, 20], [0, 0, 0])).toBeNull();
    expect(weightedScore([null, null, null], [40, 35, 25])).toBeNull();
    expect(weightedScore(null, [40, 35, 25])).toBeNull();
    expect(weightedScore([NaN, 70, 50], [40, 35, 25])).toBeCloseTo(61.6666667);
  });
});
