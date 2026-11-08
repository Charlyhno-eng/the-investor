export type Quantities = Record<string, number>;
export function readQuantities(): Quantities {
  try {
    const value = JSON.parse(
      localStorage.getItem("investor-quantities") ?? "{}",
    );
    if (value && typeof value === "object" && !Array.isArray(value))
      return Object.fromEntries(
        Object.entries(value).filter(
          (entry): entry is [string, number] =>
            typeof entry[1] === "number" &&
            Number.isFinite(entry[1]) &&
            entry[1] >= 0 &&
            entry[1] <= 1e15,
        ),
      );
  } catch {
    /* Session remains usable without storage. */
  }
  return {};
}
