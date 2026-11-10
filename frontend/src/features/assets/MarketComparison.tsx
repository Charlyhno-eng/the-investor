import { useEffect, useState } from "react";
import { HistoryChart } from "../../components/HistoryChart";
import { api } from "../../lib/api";
import { date, percent } from "../../lib/format";
import type { ComparisonEquity, Asset } from "../../lib/types";

type Comparison = {
  status: "ready";
  equity: ComparisonEquity;
  asset_return: number;
  index_return: number;
  start: string;
  end: string;
  converted: boolean;
  dividends_reinvested: boolean;
  price_proxy: boolean;
  reinvest: boolean;
};
const labels = {
  strategy: "Actif",
  benchmark: "S&P 500 · dividendes réinvestis",
  accessible: "Performance de l’actif et du S&P 500, base 100 en dollars",
};
export function MarketComparison({
  asset,
  start,
  end,
  reinvest,
}: {
  asset: Asset;
  start?: string;
  end: string;
  reinvest: boolean;
}) {
  const [result, setResult] = useState<Comparison | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    setResult(null);
    setError("");
    async function load() {
      try {
        const query = new URLSearchParams({ end, reinvest: String(reinvest) });
        if (start) query.set("start", start);
        const response = await api<Comparison | { status: "pending" }>(
          `/assets/${encodeURIComponent(asset.id)}/comparison?${query}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        if (response.status === "pending") {
          if (++attempts >= 60)
            throw new Error(
              "L’import de la référence prend plus de temps que prévu. Réessayez dans un instant.",
            );
          timer = setTimeout(load, 2000);
        } else setResult(response);
      } catch (e) {
        if (!controller.signal.aborted) setError((e as Error).message);
      }
    }
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [
    asset.data_revision,
    asset.id,
    asset.last_value,
    start,
    end,
    revision,
    reinvest,
  ]);
  return (
    <section className="market-comparison" aria-label="Comparaison au S&P 500">
      {error ? (
        <div className="chart-placeholder error" role="alert">
          {error}
          <button
            className="secondary-button"
            onClick={() => setRevision((v) => v + 1)}
          >
            Réessayer
          </button>
        </div>
      ) : !result ? (
        <div className="chart-placeholder" role="status">
          <span className="spinner" />
          Chargement de la comparaison au S&P 500…
        </div>
      ) : (
        <>
          <div className="market-comparison-summary">
            <span>
              <i className="strategy-dot" />
              {asset.name}
              <strong>{percent(result.asset_return, true)}</strong>
            </span>
            <span>
              <i className="market-dot" />
              S&P 500 · {reinvest ? "dividendes réinvestis" : "hors dividendes"}
              <strong>{percent(result.index_return, true)}</strong>
            </span>
          </div>
          <HistoryChart
            comparison={result.equity}
            comparisonLabels={{
              ...labels,
              benchmark: `S&P 500 · ${reinvest ? "dividendes réinvestis" : "hors dividendes"}`,
            }}
          />
          <p className="comparison-caption">
            Base 100 en USD · du {date(result.start)} au {date(result.end)} ·
            dates communes observées, sans interpolation · hors frais et
            fiscalité.{" "}
            {result.dividends_reinvested &&
              "Action : dividendes réinvestis via les clôtures ajustées, sans double comptage. "}
            {result.converted &&
              "Prix de l’actif convertis en USD au taux de chaque date. "}
            {result.price_proxy &&
              "Matière première : variation du prix ou de l’indice, sans roulement de contrats futures. "}
            {!reinvest && "Comparaison des prix hors dividendes. "}
            Le S&P 500 est représenté par{" "}
            {reinvest
              ? "son indice de rendement total (^SP500TR)"
              : "son indice de prix (^GSPC)"}
            .
          </p>
        </>
      )}
    </section>
  );
}
