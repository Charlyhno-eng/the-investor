import { useEffect, useState } from "react";
import { post } from "../../lib/api";
import type { Asset } from "../../lib/types";
import { CorrelationPanel } from "../portfolio/CorrelationPanel";
import type { PortfolioResult } from "../portfolio/types";

export function EtfCorrelationPanel({
  asset,
  assets,
}: {
  asset: Asset;
  assets: Asset[];
}) {
  const [years, setYears] = useState(3);
  const [correlation, setCorrelation] =
    useState<PortfolioResult["correlation"]>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  // Preserve the list order, with the selected ETF first on both matrix axes.
  const universe = JSON.stringify(
    [
      asset,
      ...assets.filter((a) => a.category === "etf" && a.id !== asset.id),
    ].map((a) => [a.id, a.data_revision, a.last_date, a.last_value, a.points]),
  );

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    setLoading(true);
    setError("");
    setCorrelation(null);
    async function load() {
      try {
        const data = await post<PortfolioResult | { status: "pending" }>(
          "/portfolio/analytics",
          {
            holdings: (JSON.parse(universe) as [string, ...unknown[]][]).map(
              ([asset_id]) => ({ asset_id, quantity: 1 }),
            ),
            years,
            include_benchmark: false,
            include_correlation: true,
          },
          controller.signal,
        );
        if (controller.signal.aborted) return;
        if (data.status === "pending") {
          if (++attempts < 30) timer = setTimeout(load, 2000);
          else {
            setError(
              "Les données sont toujours en cours d’import. Réessayez dans un instant.",
            );
            setLoading(false);
          }
          return;
        }
        setCorrelation(data.correlation);
        setLoading(false);
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
  }, [universe, years, retry]);

  return (
    <section
      className="analysis-panel etf-correlation-panel"
      aria-label="Corrélations des ETF"
    >
      <p className="fine-print">
        Tous les ETF de la liste · {asset.name} en première ligne et première
        colonne.
      </p>
      {loading ? (
        <p role="status">Chargement des corrélations des ETF…</p>
      ) : error ? (
        <>
          <p className="error" role="alert">
            {error}
          </p>
          <button
            className="secondary-button"
            onClick={() => setRetry((n) => n + 1)}
          >
            Réessayer
          </button>
        </>
      ) : (
        <CorrelationPanel
          correlation={correlation}
          years={years}
          onYearsChange={setYears}
          caption="Corrélations des ETF de la liste, ETF sélectionné en premier"
        />
      )}
    </section>
  );
}
