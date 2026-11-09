import { expect, test } from "vitest";
import { recommendation } from "../../src/features/recommendations/model";

// Rounded inputs from the user's table: expectations describe the intended strategy.
const scenarios = [
  {
    name: "Gaztransport & Technigaz",
    m: 63.2,
    z: -0.75,
    held: true,
    action: "Renforcer",
  },
  { name: "Safran", m: 61.7, z: -2.77, held: true, action: "Renforcer" },
  { name: "Airbus", m: 51.9, z: -0.58, held: true, action: "Conserver" },
  {
    name: "Technip Energies",
    m: 41.6,
    z: -1.41,
    held: true,
    action: "Conserver",
  },
  {
    name: "Schneider Electric",
    m: 55.6,
    z: -2.23,
    held: false,
    action: "Acheter",
  },
  { name: "Thales", m: 52, z: -1.68, held: false, action: "Acheter" },
  { name: "ASML", m: 64.2, z: 0.49, held: false, action: "Attendre" },
  { name: "Air Liquide", m: 54.4, z: 0.87, held: false, action: "Attendre" },
  { name: "TotalEnergies", m: 58, z: 1.23, held: false, action: "Attendre" },
];

test("user's portfolio combines momentum and discount for entry decisions", () => {
  for (const s of scenarios) {
    const result = recommendation({ momentum: s.m, z: s.z, held: s.held });
    expect(result.action, s.name).toBe(s.action);
  }
  const schneider = recommendation({ momentum: 55.6, z: -2.23, held: false });
  expect(schneider.priority).toBeCloseTo(67.46, 2);
  expect(schneider.priority).toBeGreaterThan(55.6);
  expect(recommendation({ momentum: 55.6, z: 0, held: false }).action).toBe(
    "Attendre",
  );
});

test("held actions can be reinforced, kept, reduced or sold; watchlist is never sold", () => {
  for (const [m, z, action] of [
    [80, -0.5, "Renforcer"],
    [80, 2, "Conserver"],
    [50, 2, "Alléger"],
    [25, -1.5, "Vendre"],
  ] as const) {
    expect(recommendation({ momentum: m, z, held: true }).action).toBe(action);
    expect(["Vendre", "Alléger", "Conserver", "Renforcer"]).not.toContain(
      recommendation({ momentum: m, z, held: false }).action,
    );
  }
});
test("missing, degenerate, stale or invalid data cannot create an actionable recommendation", () => {
  for (const momentum of [null, NaN, Infinity, -1, 101])
    expect(recommendation({ momentum, z: -0.5, held: true }).action).toBe(
      "Indisponible",
    );
  for (const z of [null, NaN, Infinity])
    expect(recommendation({ momentum: 80, z, held: true }).action).toBe(
      "Indisponible",
    );
  expect(
    recommendation({
      momentum: 80,
      z: -0.5,
      held: true,
      unavailable: "Historique trop ancien",
    }).priority,
  ).toBeNull();
});
test("priority is bounded and increases with momentum and with signed discount", () => {
  for (let m = 0; m <= 100; m += 2) {
    let previous = Infinity;
    for (let z = -5; z <= 5; z += 0.1) {
      const result = recommendation({ momentum: m, z, held: false });
      expect(result.priority).toBeGreaterThanOrEqual(0);
      expect(result.priority!).toBeLessThanOrEqual(100);
      expect(result.priority!).toBeLessThanOrEqual(previous);
      expect(result.action === "Acheter").toBe(result.priority! >= 60);
      if (m < 100)
        expect(
          recommendation({ momentum: m + 1, z, held: false }).priority!,
        ).toBeGreaterThan(result.priority!);
      previous = result.priority!;
    }
  }
  const priority = (z: number) =>
    recommendation({ momentum: 80, z, held: false }).priority!;
  expect(priority(-3)).toBeGreaterThan(priority(-1.5));
  expect(priority(-1.5)).toBeGreaterThan(priority(-0.5));
  expect(priority(0)).toBe(71);
  expect(recommendation({ momentum: 0, z: -100, held: false }).priority).toBe(
    30,
  );
});

test("deep discounts favor entries but cannot alone compensate very weak momentum", () => {
  for (const z of [-2, -2.01, -3, -10, -100, -Number.MAX_VALUE]) {
    expect(recommendation({ momentum: 80, z, held: false }).action).toBe(
      "Acheter",
    );
    expect(recommendation({ momentum: 80, z, held: true }).action).toBe(
      "Renforcer",
    );
    expect(recommendation({ momentum: 55.6, z, held: false }).action).toBe(
      "Acheter",
    );
    expect(recommendation({ momentum: 25, z, held: false }).action).toBe(
      "Attendre",
    );
    expect(recommendation({ momentum: 25, z, held: true }).action).toBe(
      "Vendre",
    );
  }
});
