import { useEffect, useState } from "react";
import { api, post } from "../../lib/api";
import { date } from "../../lib/format";
import type { Asset } from "../../lib/types";
import { Tooltip } from "../../components/Tooltip";
import { RiskReturnChart } from "./RiskReturnChart";
import type { RiskResult } from "./types";

type Holding = { asset_id: string; quantity: number };
type Props =
  | { asset: Asset; holdings?: never; assets?: never; lockedAssetIds?: never }
  | {
      asset?: never;
      holdings: Holding[];
      assets: Asset[];
      lockedAssetIds?: string[];
    };
export function VolatilityPanel({
  asset,
  assets,
  holdings,
  lockedAssetIds,
}: Props) {
  const [years, setYears] = useState(3);
  const [result, setResult] = useState<RiskResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const selected = JSON.stringify(holdings ?? []);
  const locks = JSON.stringify(lockedAssetIds ?? []);
  const dataRevision = JSON.stringify(
    (asset ? [asset] : (assets ?? [])).map((a) => [
      a.data_revision,
      a.last_date,
      a.last_value,
      a.points,
    ]),
  );
  const assetId = asset?.id;
  const lastDate = asset?.last_date;
  const lastValue = asset?.last_value;
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    setLoading(true);
    setResult(null);
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
                locked_asset_ids: JSON.parse(locks).filter((id: string) =>
                  JSON.parse(selected).some(
                    (h: { asset_id: string }) => h.asset_id === id,
                  ),
                ),
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
  }, [
    dataRevision,
    assetId,
    lastDate,
    lastValue,
    selected,
    locks,
    years,
    revision,
  ]);
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
            {!portfolio && <h3>{asset?.name} face au marché</h3>}
            {ready && (
              <span className="fine-print">
                {date(result.start)} — {date(result.end)} · EUR
              </span>
            )}
            <Tooltip label="Comprendre le graphique">
              Un point par actif, et le S&P 500 en étoile bleue, sur les mêmes
              dates et en euros. La courbe minimise la variance pour chaque
              rendement cible, sans vente à découvert.
              {portfolio
                ? " Elle utilise uniquement les actifs du portefeuille ; le S&P 500 sert de comparatif."
                : " Sur cette fiche, elle combine l’actif et le S&P 500."}
              La branche efficiente est en trait plein ; la branche inférieure
              est en pointillés. Les rendements moyens historiques servent
              d’estimation des rendements attendus.
            </Tooltip>
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
        {loading && (
          <div className="chart-placeholder" role="status">
            <span className="spinner" />
            {portfolio
              ? "Calcul du risque et chargement du S&P 500…"
              : "Calcul du rendement et chargement du S&P 500…"}
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
        {result?.status === "insufficient" && (
          <div className="portfolio-empty" role="status">
            {result.message}
          </div>
        )}

        {ready && (
          <RiskReturnChart
            key={`${selected}-${years}-${result.end}`}
            result={result}
          />
        )}
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
