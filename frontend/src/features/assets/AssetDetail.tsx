import { useEffect, useState } from "react";
import { HistoryChart } from "../../components/HistoryChart";
import { Icon } from "../../components/Icon";
import { api } from "../../lib/api";
import { categories, date, number, percent, sources } from "../../lib/format";
import type { Asset, Point } from "../../lib/types";
import { AnalysisPanel } from "../analysis/AnalysisPanel";
export function AssetDetail({ asset }: { asset: Asset }) {
  const [points, setPoints] = useState<Point[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const [range, setRange] = useState(5),
    [tab, setTab] = useState<"chart" | "analysis">("chart");
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
      <div className="asset-breadcrumb">
        <span>Marchés</span>
        <span>/</span>
        <span>{category.name}</span>
        <span>/</span>
        <span>{asset.name}</span>
      </div>
      <div className="asset-heading">
        <div className="asset-title">
          <span className={`asset-emblem ${asset.category}`}>
            <Icon name={category.icon} size={24} />
          </span>
          <div>
            <h1>{asset.name}</h1>
            <span className="asset-subtitle">
              {asset.id.startsWith("yf-")
                ? asset.id.slice(3).toUpperCase()
                : (asset.country_code ?? asset.unit)}
              <i />{" "}
              {asset.metric === "yield"
                ? `Référence souveraine ${asset.benchmark_years ?? 10} ans`
                : asset.frequency === "monthly"
                  ? "Prix & indices mensuels"
                  : "Clôture quotidienne ajustée"}
            </span>
          </div>
        </div>
        <span className="source-badge">
          <span className="status-dot" />
          Historique local
        </span>
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
        <button
          role="tab"
          aria-selected={tab === "analysis"}
          onClick={() => setTab("analysis")}
        >
          <Icon name="analysis" size={16} />
          Analyse quantitative<span className="new-tag">HMM</span>
        </button>
      </div>
      <section className="chart-panel">
        <div className="quote-row">
          <div>
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
        {loading ? (
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
            compact={tab === "analysis"}
          />
        ) : (
          <div className="chart-placeholder">Aucune observation.</div>
        )}
        <div className="chart-footer">
          <span>
            {date(asset.first_date)} <span className="muted">—</span>{" "}
            {date(asset.last_date)}
            <i />
            {number(asset.points, 0)} observations
          </span>
          <a href={asset.source_url} target="_blank" rel="noreferrer">
            {sources[asset.source] ?? asset.source}
            <Icon name="external" size={11} />
          </a>
        </div>
      </section>
      {tab === "analysis" && points.length > 2 && (
        <AnalysisPanel asset={asset} points={points} />
      )}
      {tab === "chart" && (
        <div className="asset-facts">
          <div>
            <span className="field-label">Fréquence</span>
            <strong>
              {asset.frequency === "monthly" ? "Mensuelle" : "Quotidienne"}
            </strong>
          </div>
          <div>
            <span className="field-label">Dernière observation</span>
            <strong>{date(asset.last_date)}</strong>
          </div>
          <div>
            <span className="field-label">Mesure</span>
            <strong>
              {asset.metric === "yield"
                ? "Rendement souverain"
                : asset.metric === "index"
                  ? "Indice"
                  : asset.source === "yahoo"
                    ? "Prix ajusté"
                    : "Prix de référence"}
            </strong>
          </div>
          <button
            className="analysis-shortcut"
            onClick={() => setTab("analysis")}
          >
            <span className="shortcut-icon">
              <Icon name="analysis" />
            </span>
            <span>
              Explorer les régimes<small>Modèle de Markov caché</small>
            </span>
            <Icon name="arrow" size={18} />
          </button>
        </div>
      )}
      <footer className="workspace-footer">
        <span>Données historiques · aucune cotation temps réel</span>
        <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
          Charts by TradingView
        </a>
      </footer>
    </div>
  );
}
