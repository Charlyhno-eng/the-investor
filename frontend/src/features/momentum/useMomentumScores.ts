import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { Asset } from "../../lib/types";
import { type MomentumStock } from "./score";
import {
  useMomentumSettings,
  type MomentumCategory,
} from "./useMomentumSettings";

type Result = {
  status: "ready" | "pending";
  universe?: MomentumStock[];
  as_of?: string;
};
function useCategoryScores(assets: Asset[], category: MomentumCategory) {
  const { benchmark, weights } = useMomentumSettings(category);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const revision = JSON.stringify(
    assets
      .filter((a) => a.category === category)
      .map((a) => [a.id, a.data_revision, a.last_date, a.last_value, a.points]),
  );
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    setResult(null);
    setError("");
    if (revision === "[]") return () => controller.abort();
    async function load() {
      try {
        const data = await api<Result>(
          `/momentum?category=${category}${benchmark ? `&benchmark=${encodeURIComponent(benchmark)}` : ""}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        setResult(data);
        if (data.status === "pending") {
          if (++attempts < 30) timer = setTimeout(load, 2000);
          else setError("Référence Momentum toujours en cours d’import.");
        }
      } catch (e) {
        if (!controller.signal.aborted) setError((e as Error).message);
      }
    }
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [revision, benchmark, category]);
  return {
    stocks: result?.universe ?? [],
    weights,
    error,
    pending: !error && result?.status !== "ready",
    asOf: result?.as_of,
  };
}

export function useMomentumScores(assets: Asset[]) {
  const stocks = useCategoryScores(assets, "stock");
  const crypto = useCategoryScores(assets, "crypto");
  return { ...stocks, crypto };
}
