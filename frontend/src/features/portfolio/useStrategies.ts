import { useState } from "react";
import type { Quantities } from "./quantities";

type Strategy = {
  id: string;
  name: string;
  quantities: Quantities;
  lockedAssetIds: string[];
};
const storageKey = "investor-strategies";
function readStrategies(): Strategy[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(storageKey) ?? "[]");
    if (!Array.isArray(value)) return [];
    return value.flatMap((item) => {
      if (
        !item ||
        typeof item.id !== "string" ||
        typeof item.name !== "string" ||
        !item.quantities ||
        typeof item.quantities !== "object" ||
        Array.isArray(item.quantities)
      )
        return [];
      const quantities = Object.fromEntries(
        Object.entries(item.quantities).filter(
          (entry) =>
            typeof entry[1] === "number" &&
            Number.isFinite(entry[1]) &&
            entry[1] >= 0 &&
            entry[1] <= 1e15,
        ),
      ) as Quantities;
      return [
        {
          id: item.id,
          name: item.name,
          quantities,
          lockedAssetIds: Array.isArray(item.lockedAssetIds)
            ? item.lockedAssetIds.filter(
                (id: unknown): id is string =>
                  typeof id === "string" && id in quantities,
              )
            : [],
        },
      ];
    });
  } catch {
    return [];
  }
}
export function useStrategies() {
  const [strategies, setStrategies] = useState(readStrategies);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const selected = strategies.find((s) => s.id === selectedId) ?? strategies[0];
  function save(next: Strategy[]) {
    setStrategies(next);
    try {
      localStorage.setItem(storageKey, JSON.stringify(next));
      setError("");
    } catch {
      setError(
        "L’enregistrement local a échoué. Vos stratégies restent disponibles dans cette session.",
      );
    }
  }
  function update(strategy: Strategy) {
    save(strategies.map((s) => (s.id === strategy.id ? strategy : s)));
  }
  function create(name: string) {
    const strategy = {
      id: crypto.randomUUID(),
      name: name.trim(),
      quantities: {},
      lockedAssetIds: [],
    };
    if (!strategy.name) return;
    save([...strategies, strategy]);
    setSelectedId(strategy.id);
  }
  return {
    strategies,
    selected,
    select: setSelectedId,
    error,
    create,
    update,
    remove: (id: string) => save(strategies.filter((s) => s.id !== id)),
  };
}
export type StrategyStore = ReturnType<typeof useStrategies>;
