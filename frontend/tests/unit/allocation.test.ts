import { expect, test } from "vitest";
import {
  allocationColors,
  colorSeparation,
  donutArc,
} from "../../src/features/portfolio/allocationColors";

test("generated palette has no RGB duplicates for 500 and 10000 assets", () => {
  for (const count of [500, 10000]) {
    const items = Array.from({ length: count }, (_, i) => ({
      id: `stock-${i}`,
    }));
    const colors = allocationColors(items);
    expect(new Set(colors.values()).size).toBe(count);
    expect([...colors.values()].every((c) => /^#[0-9a-f]{6}$/.test(c))).toBe(
      true,
    );
    expect(allocationColors([...items].reverse())).toEqual(colors);
  }
});
test("duplicate sector colors are resolved and colors survive a weight reorder", () => {
  const items = [
    { id: "a", color: "#8490a2" },
    { id: "b", color: "#8490a2" },
    { id: "c" },
  ];
  const colors = allocationColors(items);
  expect(new Set(colors.values()).size).toBe(3);
  expect(allocationColors([...items, { id: "other" }]).get("a")).toBe(
    colors.get("a"),
  );
});
test("tiny and full-circle slices remain finite SVG arcs", () => {
  for (const weight of [1, 0.5, 1 / 500, 1e-8]) {
    const path = donutArc(0, weight, 144, 104);
    expect(path).toMatch(/^M/);
    expect(path).not.toMatch(/NaN|Infinity/);
    expect(path.match(/ A/g)).toHaveLength(2);
  }
});

test("nine positions are perceptually separated rather than clustering in similar greens", () => {
  const colors = [
    ...allocationColors(
      Array.from({ length: 9 }, (_, i) => ({ id: `asset-${i}` })),
    ).values(),
  ];
  for (let i = 0; i < colors.length; i++)
    for (let j = i + 1; j < colors.length; j++)
      expect(colorSeparation(colors[i], colors[j])).toBeGreaterThan(0.12);
});

test("similar preferred greens are replaced by separated colors", () => {
  const colors = [
    ...allocationColors([
      { id: "a", color: "#55bb77" },
      { id: "b", color: "#56bc78" },
      { id: "c", color: "#57bd79" },
    ]).values(),
  ];
  for (let i = 0; i < colors.length; i++)
    for (let j = i + 1; j < colors.length; j++)
      expect(colorSeparation(colors[i], colors[j])).toBeGreaterThan(0.12);
});
