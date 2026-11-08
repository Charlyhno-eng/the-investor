import { sectorInfo, currencyCountry } from "../../lib/sectors";
import { useEffect, useState } from "react";
import { VolatilityPanel } from "../volatility/VolatilityPanel";
import { HistoryChart } from "../../components/HistoryChart";
import { Icon } from "../../components/Icon";
import { api } from "../../lib/api";
import { categories, date, number, percent } from "../../lib/format";
import type { Asset, Point } from "../../lib/types";
import { Tooltip } from "../../components/Tooltip";
import { useDividends } from "./useDividends";
import { stockCountry } from "../../lib/countries";
import { MarketComparison } from "./MarketComparison";
import { ReversionPanel } from "../reversion/ReversionPanel";
import { favoriteLabel, type Favorite } from "../../lib/favorites";
export function AssetDetail({
  asset,
  favorite,
  onToggleFavorite,
  onRemove,
}: {
  asset: Asset;
  favorite?: Favorite;
  onToggleFavorite: () => void;
  onRemove: () => void;
}) {
  const [points, setPoints] = useState<Point[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const [range, setRange] = useState(5),
    [tab, setTab] = useState<"chart" | "reversion" | "volatility">("chart");
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    api<Point[]>(`/assets/${encodeURIComponent(asset.id)}/history`, {
      signal: controller.signal,
    })
      .then(setPoints)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [asset.id, asset.last_date, asset.points, asset.last_value]);
  const dividends = useDividends(asset);
  const [compareMarket, setCompareMarket] = useState(false);
  const [reinvest, setReinvest] = useState(false);
  const supportsRegression = ["stock", "crypto", "etf", "currency"].includes(
    asset.category,
  );
  const category = categories.find((c) => c.id === asset.category)!;
  const cutoff = new Date(`${asset.last_date}T00:00:00Z`);
  cutoff.setUTCFullYear(cutoff.getUTCFullYear() - range);
  const visible = range
    ? points.filter((p) => p.time >= cutoff.toISOString().slice(0, 10))
    : points;
  const start = visible[0]?.value;
  const difference =
    start == null
      ? null
      : asset.metric === "yield"
        ? asset.last_value - start
        : start > 0
          ? asset.last_value / start - 1
          : null;
  return (
    <div className="asset-detail">
      <div className="asset-heading">
        <div className="asset-title">
          <span className={`asset-emblem ${asset.category}`}>
            <Icon name={category.icon} size={24} />
          </span>
          <div>
            <h1>
              {asset.name}{" "}
              <button
                className={`favorite-button detail-favorite ${favorite ? `is-favorite ${favorite}` : ""}`}
                aria-label={favoriteLabel(favorite)}
                aria-pressed={!!favorite}
                onClick={onToggleFavorite}
              >
                <Icon name="star" size={20} />
              </button>
              <button
                className="favorite-button detail-remove"
                aria-label={`Retirer ${asset.name} de la liste`}
                title="Retirer cet actif de la liste"
                onClick={() => {
                  if (
                    window.confirm(
                      `Retirer « ${asset.name} » de la liste ? Son historique sera conservé.`,
                    )
                  )
                    onRemove();
                }}
              >
                <Icon name="minus" size={20} />
              </button>
            </h1>
            <span className="asset-subtitle">
              {asset.id.startsWith("yf-")
                ? asset.id.slice(3).toUpperCase()
                : (asset.country_code ?? asset.unit)}
              {asset.category === "stock" && (
                <>
                  <i />
                  {stockCountry(asset)}
                </>
              )}
              {asset.category === "currency" && (
                <>
                  <i />
                  {currencyCountry(asset.id)}
                </>
              )}
              <i />{" "}
              {asset.metric === "yield"
                ? `Référence souveraine ${asset.benchmark_years ?? 10} ans`
                : asset.frequency === "monthly"
                  ? "Prix & indices mensuels"
                  : "Clôture quotidienne ajustée"}
            </span>
          </div>
        </div>
        {asset.category === "stock" && asset.sector && (
          <span
            className="sector-badge"
            style={{
              color: sectorInfo(asset.sector).color,
              borderColor: sectorInfo(asset.sector).color,
              background: `${sectorInfo(asset.sector).color}18`,
            }}
          >
            {sectorInfo(asset.sector).name}
          </span>
        )}
      </div>
      <div className="detail-tabs" role="tablist" aria-label="Vue de l’actif">
        <button
          role="tab"
          aria-selected={tab === "chart"}
          onClick={() => setTab("chart")}
        >
          <Icon name="stock" size={16} />
          Vue du marché
        </button>
        {supportsRegression && (
          <button
            role="tab"
            aria-selected={tab === "reversion"}
            onClick={() => setTab("reversion")}
          >
            <Icon name="stock" size={16} />
            Régression
          </button>
        )}
        <button
          role="tab"
          aria-selected={tab === "volatility"}
          onClick={() => setTab("volatility")}
        >
          <Icon name="analysis" size={16} />
          Frontières d’efficience
        </button>
      </div>
      {tab === "volatility" && <VolatilityPanel key={asset.id} asset={asset} />}
      {supportsRegression &&
        tab === "reversion" &&
        (loading ? (
          <div className="chart-placeholder" role="status">
            Chargement de l’historique
          </div>
        ) : error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : points.length ? (
          <ReversionPanel key={asset.id} asset={asset} points={points} />
        ) : (
          <div className="chart-placeholder">Aucune observation.</div>
        ))}
      {tab === "chart" && (
        <section className="chart-panel">
          <div className="quote-row">
            <div>
              {asset.category === "bond" && (
                <div className="yield-caption">
                  Rendement actuel annualisé{" "}
                  <Tooltip label="Rendement et coupon">
                    Dernier taux souverain disponible, au{" "}
                    {date(asset.last_date)}. Cette série de référence ne fournit
                    pas le coupon d’une émission précise. Le coupon est
                    l’intérêt contractuel du titre ; le rendement dépend aussi
                    de son prix.
                  </Tooltip>
                </div>
              )}
              <div className="quote">
                <strong>
                  {number(asset.last_value, asset.last_value < 1 ? 4 : 2)}
                </strong>
                <span>{asset.unit}</span>
              </div>
              <div
                className={`quote-change ${difference == null ? "muted" : difference >= 0 ? "positive" : "negative"}`}
              >
                {difference == null
                  ? "—"
                  : asset.metric === "yield"
                    ? `${difference > 0 ? "+" : ""}${number(difference)} pp`
                    : percent(difference, true)}
                <span>
                  sur{" "}
                  {range
                    ? `${range} an${range > 1 ? "s" : ""}`
                    : "la période complète"}
                </span>
              </div>
            </div>
            {asset.category === "stock" && !compareMarket && (
              <div className="dividend-legend">
                <span className="dividend-dot">D</span>
                {dividends.error
                  ? "Dividendes indisponibles"
                  : !dividends.history
                    ? "Chargement…"
                    : !dividends.history.coverage
                      ? "Dividendes en attente"
                      : !dividends.history.events.length
                        ? "Aucun dividende enregistré"
                        : "Dividendes"}
                <Tooltip label="Repères de dividendes">
                  {dividends.error ||
                    "Survolez ou touchez un repère D : date de détachement et dividende brut en pourcentage de la clôture de la séance précédente, hors ajustement des dividendes. Pourcentage par versement, non annualisé. Les prix du graphique sont ajustés. Un pourcentage absent attend la prochaine actualisation."}
                </Tooltip>
              </div>
            )}
            <div className="range-buttons" aria-label="Période affichée">
              {[1, 5, 10, 0].map((y) => (
                <button
                  key={y}
                  onClick={() => setRange(y)}
                  aria-pressed={range === y}
                >
                  {y ? `${y}A` : "Tout"}
                </button>
              ))}
            </div>
          </div>
          <div className="market-chart-actions">
            {compareMarket && (
              <button
                className="secondary-button"
                aria-pressed={reinvest}
                onClick={() => setReinvest((v) => !v)}
              >
                Dividendes réinvestis
              </button>
            )}
            <button
              className="secondary-button"
              disabled={asset.metric === "yield"}
              title={
                asset.metric === "yield"
                  ? "Les taux obligataires ne sont pas une performance totale"
                  : undefined
              }
              aria-pressed={compareMarket}
              onClick={() => setCompareMarket((v) => !v)}
            >
              {compareMarket ? "Revenir au prix" : "Comparer au S&P 500"}
            </button>
          </div>
          {compareMarket && !loading && !error && points.length ? (
            <MarketComparison
              reinvest={reinvest}
              asset={asset}
              start={range ? cutoff.toISOString().slice(0, 10) : undefined}
              end={asset.last_date}
            />
          ) : loading ? (
            <div className="chart-placeholder" role="status">
              <span className="spinner" />
              Chargement de l’historique
            </div>
          ) : error ? (
            <div className="chart-placeholder error" role="alert">
              {error}
            </div>
          ) : points.length ? (
            <HistoryChart
              points={points}
              range={range}
              dividends={dividends.history?.events}
            />
          ) : (
            <div className="chart-placeholder">Aucune observation.</div>
          )}
        </section>
      )}
    </div>
  );
}
