const oldId = "yf-ese.pa";
const newId = "yf-psp5.pa";

/** Migrate instrument references, never historical prices or synthetic returns.
 * Quantities retain their entered number of units; originals are backed up.
 */
export function migrateSp500Storage() {
  const marker = "investor-amundi-sp500-v1";
  try {
    if (localStorage.getItem(marker)) return;
    function map(value: unknown): unknown {
      if (value === oldId) return newId;
      if (Array.isArray(value)) return [...new Set(value.map(map))];
      if (value && typeof value === "object") {
        const result: Record<string, unknown> = {};
        for (const [key, child] of Object.entries(value)) {
          const target = key === oldId ? newId : key;
          const mapped = map(child);
          if (
            target in result &&
            typeof mapped === "number" &&
            typeof result[target] === "number"
          )
            result[target] = Math.min(1e15, mapped + result[target]);
          else if (!(target in result)) result[target] = mapped;
        }
        return result;
      }
      return value;
    }
    for (const key of [
      "investor-quantities",
      "investor-strategies",
      "investor-favorites",
      "investor-removed-assets",
    ]) {
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      const value = JSON.parse(raw) as unknown;
      const next =
        key === "investor-removed-assets" && Array.isArray(value)
          ? value.filter((id) => id !== oldId && id !== newId)
          : map(value);
      const encoded = JSON.stringify(next);
      if (encoded !== raw) {
        const backup = `${key}-before-amundi-sp500`;
        if (localStorage.getItem(backup) === null)
          localStorage.setItem(backup, raw);
        localStorage.setItem(key, encoded);
      }
    }
    localStorage.setItem(marker, "done");
  } catch {
    // Existing backups and preferences survive unavailable or invalid storage.
  }
}
