import { useEffect, useState } from "react";
import { post } from "../../lib/api";
import type { Mode, PerformanceResponse as Result } from "./performanceTypes";

export function usePerformance({
  holdings,
  locks,
  years,
  history,
  feeRate,
  dataRevision,
}: {
  holdings: string;
  locks: string;
  years: number;
  history: string;
  feeRate: number;
  dataRevision: string;
}) {
  const [result, setResult] = useState<Result | null>(null);
  const [mode, setMode] = useState<Mode>("equal");
  const [optimize, setOptimize] = useState<Mode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    setLoading(true);
    setError("");
    async function load() {
      try {
        const data = await post<Result | { status: "pending" }>(
          optimize ? "/portfolio/optimize" : "/portfolio/performance",
          {
            holdings: JSON.parse(holdings),
            locked_asset_ids: JSON.parse(locks),
            years,
            history,
            mode: optimize ?? "equal",
            fee_rate: feeRate,
          },
          controller.signal,
        );
        if (controller.signal.aborted) return;
        if (data.status === "pending") {
          if (++attempts >= 90)
            throw new Error(
              "Les données prennent plus de temps que prévu. Réessayez dans un instant.",
            );
          timer = setTimeout(load, 2000);
        } else {
          setResult(data);
          setLoading(false);
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          setError((e as Error).message);
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [
    holdings,
    locks,
    years,
    history,
    feeRate,
    optimize,
    revision,
    dataRevision,
  ]);
  return {
    result,
    mode,
    setMode,
    optimize,
    setOptimize,
    loading,
    error,
    retry: () => setRevision((value) => value + 1),
  };
}
