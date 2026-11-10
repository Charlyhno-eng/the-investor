import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { Asset, DividendHistory } from "../../lib/types";

export function useDividends(asset: Asset) {
  const [history, setHistory] = useState<DividendHistory | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (asset.category !== "stock") return;
    const controller = new AbortController();
    const load = () => {
      api<DividendHistory>(
        `/assets/${encodeURIComponent(asset.id)}/dividends`,
        { signal: controller.signal },
      )
        .then((data) => {
          setHistory((previous) =>
            JSON.stringify(previous) === JSON.stringify(data) ? previous : data,
          );
          setError("");
        })
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        });
    };
    load();
    const timer = setInterval(load, 15000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [asset.data_revision, asset.id, asset.last_date, asset.category]);
  return { history, error };
}
