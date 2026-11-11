import { useEffect, useState } from "react";

export type MomentumCategory = "stock" | "crypto" | "etf";
const storageKey = (category: MomentumCategory) =>
  `investor-momentum-settings${category === "stock" ? "" : `-${category}`}`;
const event = "investor-momentum-settings-change";
type Settings = { weights: number[]; benchmark: string };
const defaults: Settings = { weights: [40, 35, 25], benchmark: "" };

function readSettings(category: MomentumCategory): Settings {
  try {
    const value = JSON.parse(
      localStorage.getItem(storageKey(category)) ?? "null",
    );
    if (
      value &&
      typeof value.benchmark === "string" &&
      Array.isArray(value.weights) &&
      value.weights.length === 3 &&
      value.weights.every(
        (v: unknown) =>
          typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 100,
      )
    )
      return value;
  } catch {
    /* Browser storage may be disabled. */
  }
  return defaults;
}

export function useMomentumSettings(category: MomentumCategory = "stock") {
  const [settings, setSettings] = useState(() => readSettings(category));
  useEffect(() => {
    const sync = () => setSettings(readSettings(category));
    window.addEventListener(event, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(event, sync);
      window.removeEventListener("storage", sync);
    };
  }, [category]);
  function update(next: Settings) {
    setSettings(next);
    try {
      localStorage.setItem(storageKey(category), JSON.stringify(next));
      window.dispatchEvent(new Event(event));
    } catch {
      /* Keep settings in memory when browser storage is disabled. */
    }
  }
  return { ...settings, update };
}
