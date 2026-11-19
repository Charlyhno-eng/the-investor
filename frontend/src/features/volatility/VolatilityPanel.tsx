import { useEffect, useState } from "react";
import { api, post } from "../../lib/api";
import { date } from "../../lib/format";
import type { Asset } from "../../lib/types";
import { Tooltip } from "../../components/Tooltip";
import { RiskReturnChart } from "./RiskReturnChart";
import type { RiskResult } from "./types";

type Holding = { asset_id: string; quantity: number };
type Props =
  | {
      asset: Asset;
      holdings?: never;
      assets?: never;
      lockedAssetIds?: never;
      years?: never;
      onYearsChange?: never;
    }
  | {
      asset?: never;
      holdings: Holding[];
      assets: Asset[];
      lockedAssetIds?: string[];
      years: number;
      onYearsChange: (years: number) => void;
    };
export function VolatilityPanel({
  asset,
  assets,
  holdings,
  lockedAssetIds,
  years: portfolioYears,
  onYearsChange,
}: Props) {
  const [assetYears, setAssetYears] = useState(3);
  const years = portfolioYears ?? assetYears;
  const setYears = onYearsChange ?? setAssetYears;
  const [result, setResult] = useState<RiskResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const selected = JSON.stringify(holdings ?? []);
  const heldIds = new Set(holdings?.map((holding) => holding.asset_id));
  const locks = JSON.stringify(
    lockedAssetIds?.filter((id) => heldIds.has(id)) ?? [],
  );
  const dataRevision = JSON.stringify(
    (asset
      ? [asset]
      : (assets ?? []).filter((a) => heldIds.has(a.id) || a.id === "yf-psp5.pa")
    ).map((a) => [a.id, a.data_revision, a.last_date, a.last_value, a.points]),
  );
  const assetId = asset?.id;
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    setLoading(true);
    setError("");
    async function load() {
      try {
        const data = assetId
          ? await api<RiskResult>(
              `/assets/${encodeURIComponent(assetId)}/volatility?years=${years}`,
              { signal: controller.signal },
            )
          : await post<RiskResult>(
              "/portfolio/volatility",
              {
                holdings: JSON.parse(selected),
                years,
                locked_asset_ids: JSON.parse(locks),
              },
              controller.signal,
            );
        if (controller.signal.aborted) return;
        if (data.status === "pending") {
          if (++attempts > 90)
            throw new Error(
              "Les références de marché sont encore en cours d’import. Réessayez dans un instant.",
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
    timer = setTimeout(load, 180);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [dataRevision, assetId, selected, locks, years, revision]);
  const ready = result?.status === "ready";
  const portfolio = !!holdings;
  return (
    <section
      className={`vol-panel ${portfolio ? "portfolio-content vol-portfolio" : ""}`}
      aria-label={
        portfolio
          ? "Frontières d’efficience du portfolio"
          : "Frontières d’efficience de l’actif"
      }
    >
      <section className="vol-chart-card">
        <div className="vol-chart-heading">
          <div className="vol-chart-context">
            <h3>
              {portfolio
                ? "Frontière d’efficience"
                : `${asset?.name} face au marché`}
            </h3>
            <Tooltip label="Comprendre le graphique">
              {portfolio
                ? "L’étoile bleue représente le S&P 500 PEA PSP5 et l’étoile orange le portefeuille à ses poids actuels. Les points colorés représentent des allocations possibles des actifs détenus, avec les poids verrouillés conservés. La courbe peut évoluer avec la période, les historiques, les actifs détenus et les poids verrouillés."
                : "Un point représente l’actif et l’étoile bleue le S&P 500 PEA PSP5. La courbe combine les deux."}{" "}
              Les mesures utilisent les mêmes dates et sont calculées en euros.
              La courbe minimise la variance pour chaque rendement cible, sans
              vente à découvert. La branche efficiente est en trait plein et la
              branche inférieure est en pointillés.
            </Tooltip>
            {ready && (
              <span className="vol-chart-period">
                {loading ? (
                  <span role="status">Mise à jour du graphique…</span>
                ) : (
                  <>
                    {date(result.start)} — {date(result.end)} · EUR
                  </>
                )}
              </span>
            )}
          </div>
          <div className="range-buttons" aria-label="Période de comparaison">
            {[1, 3, 5, 10].map((y) => (
              <button
                key={y}
                aria-pressed={y === years}
                onClick={() => setYears(y)}
              >
                {y}A
              </button>
            ))}
          </div>
        </div>
        {loading && !ready && (
          <div className="chart-placeholder" role="status">
            <span className="spinner" />
            {portfolio
              ? "Calcul du risque et chargement de l’ETF S&P 500 PEA…"
              : "Calcul du rendement et chargement de l’ETF S&P 500 PEA…"}
          </div>
        )}
        {error && (
          <p className="error" role="alert">
            {error}{" "}
            <button
              className="secondary-button"
              onClick={() => setRevision((v) => v + 1)}
            >
              Réessayer
            </button>
          </p>
        )}
        {!loading && result?.status === "insufficient" && (
          <div className="portfolio-empty" role="status">
            {result.message}
          </div>
        )}

        {ready && <RiskReturnChart result={result} portfolio={portfolio} />}
      </section>
      {!!result?.excluded?.length && (
        <div className="vol-exclusions" role="note">
          <strong>Actifs hors graphique</strong>
          {result.excluded.map((p) => (
            <span key={p.id}>
              {p.name} · {p.reason}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
