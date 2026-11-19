import { useId, useLayoutEffect, useRef, useState } from "react";
import { number } from "../../lib/format";
import type { MapPoint, RiskResult } from "./types";

const palette = [
  "#efb180",
  "#77cbb3",
  "#bc9bf3",
  "#f38994",
  "#e2d078",
  "#92a7c6",
];
const pct = (value: number) => `${number(value, 2)} %`;

const benchmarkColor = "#65b9ff";
const portfolioColor = "#ffbd76";
const sharpeColors = ["#5b257e", "#365d96", "#21918c", "#66cc57", "#fde725"];
const sharpeGradient = `linear-gradient(90deg, ${sharpeColors.join(", ")})`;

function sharpeColor(fraction: number) {
  const index = fraction * (sharpeColors.length - 1);
  const stop = Math.min(Math.floor(index), sharpeColors.length - 2);
  const mix = (index - stop) * 100;
  return `color-mix(in srgb, ${sharpeColors[stop]} ${100 - mix}%, ${sharpeColors[stop + 1]})`;
}
const undefinedSharpeColor = "#98a4b8";

export function RiskReturnChart({
  result,
  portfolio,
}: {
  result: RiskResult;
  portfolio: boolean;
}) {
  const gradientId = useId();
  const host = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [hovered, setHovered] = useState<{
    group: "marker" | "allocation";
    index: number;
  } | null>(null);
  useLayoutEffect(() => {
    const element = host.current;
    if (!element) return;
    setWidth(element.clientWidth);
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.round(entry.contentRect.width)),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const markers = portfolio
    ? [
        ...(result.portfolio_point ? [result.portfolio_point] : []),
        ...result.points.filter((p) => p.kind === "benchmark"),
      ]
    : result.points;
  const cloud = result.cloud ?? [];
  const sharpes = cloud.flatMap((p) => (p.sharpe === null ? [] : [p.sharpe]));
  const sharpeMin = Math.min(...sharpes);
  const sharpeMax = Math.max(...sharpes);
  const showScale = sharpes.length > 0 && sharpeMax > sharpeMin;
  const compact = width < 620;
  const height = compact ? 430 : 550;
  const left = compact ? 62 : 78,
    right = Math.max(left + 1, width - (!compact && showScale ? 84 : 30)),
    top = 24,
    bottom = height - 58;
  const all = [
    ...markers,
    ...cloud,
    ...result.frontier,
    ...result.lower_frontier,
  ];
  const risks = all.map((p) => p.volatility),
    returns = all.map((p) => p.return);
  const riskLow = Math.min(...risks),
    riskHigh = Math.max(...risks);
  const returnLow = Math.min(...returns),
    returnHigh = Math.max(...returns);
  const riskPad = Math.max(1, (riskHigh - riskLow) * 0.075);
  const returnPad = Math.max(0.5, (returnHigh - returnLow) * 0.1);
  const xMin = Math.max(0, riskLow - riskPad),
    xMax = riskHigh + riskPad;
  const yMin = returnLow - returnPad,
    yMax = returnHigh + returnPad;
  const x = (p: MapPoint) =>
    left + ((p.volatility - xMin) / (xMax - xMin)) * (right - left);
  const y = (p: MapPoint) =>
    bottom - ((p.return - yMin) / (yMax - yMin)) * (bottom - top);
  const path = (points: MapPoint[]) =>
    points.map((p, i) => `${i ? "L" : "M"}${x(p)},${y(p)}`).join(" ");
  const markerColor = (kind: string, index: number) =>
    kind === "benchmark"
      ? benchmarkColor
      : kind === "portfolio"
        ? portfolioColor
        : palette[index % palette.length];
  const activeMarker =
    hovered?.group === "marker" ? markers[hovered.index] : null;
  const active =
    hovered?.group === "allocation" ? cloud[hovered.index] : activeMarker;
  return (
    <div ref={host} className="risk-map">
      <div className="risk-summary">
        {markers.map((p, i) => (
          <div className="risk-summary-item" key={p.id}>
            <strong>
              <span
                aria-hidden="true"
                style={{ color: markerColor(p.kind, i) }}
              >
                {p.kind === "asset" ? "●" : "★"}
              </span>{" "}
              {p.name}
            </strong>
            <span>
              {pct(p.return)} rendement · {pct(p.volatility)} volatilité
            </span>
          </div>
        ))}
      </div>
      <div className="risk-plot">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={
            portfolio
              ? "Frontière de Markowitz du portefeuille et référence S&P 500 PEA PSP5"
              : "Frontière de Markowitz et actifs comparés au S&P 500 PEA PSP5"
          }
          onMouseLeave={() => setHovered(null)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setHovered(null);
          }}
        >
          <title>Rendement et volatilité annualisés en euros</title>
          <desc>
            {portfolio
              ? "Les étoiles indiquent les coordonnées du portefeuille actuel et du S&P 500. Les points colorés représentent des allocations possibles."
              : "Un point par actif et une étoile pour l’ETF S&P 500 PEA PSP5."}{" "}
            La courbe donne la variance minimale pour chaque rendement cible.
          </desc>
          <rect
            className="risk-plot-frame"
            x={left}
            y={top}
            width={right - left}
            height={bottom - top}
            rx="6"
          />
          {Array.from({ length: 6 }, (_, i) => {
            const yy = bottom - ((bottom - top) * i) / 5;
            return (
              <g key={i} className="risk-grid">
                <line x1={left} x2={right} y1={yy} y2={yy} />
                <text x={left - 8} y={yy + 4} textAnchor="end">
                  {number(yMin + ((yMax - yMin) * i) / 5, 1)} %
                </text>
              </g>
            );
          })}
          {Array.from({ length: compact ? 4 : 6 }, (_, i) => {
            const fraction = i / (compact ? 3 : 5);
            const xx = left + (right - left) * fraction;
            return (
              <g key={i} className="risk-grid">
                <line x1={xx} x2={xx} y1={top} y2={bottom} />
                <text x={xx} y={bottom + 21} textAnchor="middle">
                  {number(xMin + (xMax - xMin) * fraction, 1)} %
                </text>
              </g>
            );
          })}
          {result.lower_frontier.length > 1 && (
            <path
              className="risk-lower-frontier"
              d={path(result.lower_frontier)}
              fill="none"
              stroke="#e6eaf7"
              strokeWidth="1.5"
              strokeDasharray="5 5"
              opacity=".58"
            />
          )}
          {result.frontier.length > 1 && (
            <path
              className="risk-frontier"
              d={path(result.frontier)}
              fill="none"
              stroke="#e6eaf7"
              strokeWidth="1.7"
              strokeLinejoin="round"
            />
          )}
          <g className="risk-allocation-cloud" aria-hidden="true">
            {cloud.map((p, i) => (
              <circle
                key={i}
                cx={x(p)}
                cy={y(p)}
                r={cloud.length > 500 ? (compact ? 2 : 2.8) : 2.4}
                fill={
                  p.sharpe === null
                    ? undefinedSharpeColor
                    : sharpeColor(
                        showScale
                          ? (p.sharpe - sharpeMin) / (sharpeMax - sharpeMin)
                          : 0.5,
                      )
                }
                onPointerEnter={() =>
                  setHovered({ group: "allocation", index: i })
                }
                onPointerLeave={() => setHovered(null)}
                onClick={() => setHovered({ group: "allocation", index: i })}
              />
            ))}
          </g>
          {!compact && showScale && (
            <g className="risk-colorbar">
              <defs>
                <linearGradient id={gradientId} x1="0" y1="100%" x2="0" y2="0">
                  {sharpeColors.map((color, i) => (
                    <stop
                      key={color}
                      offset={i / (sharpeColors.length - 1)}
                      stopColor={color}
                    />
                  ))}
                </linearGradient>
              </defs>
              <text x={right + 20} y={top - 8}>
                Sharpe
              </text>
              <rect
                x={right + 20}
                y={top}
                width="12"
                height={bottom - top}
                fill={`url(#${gradientId})`}
                rx="3"
              />
              {Array.from({ length: 5 }, (_, i) => (
                <text
                  key={i}
                  x={right + 38}
                  y={bottom - ((bottom - top) * i) / 4 + 4}
                >
                  {number(sharpeMin + ((sharpeMax - sharpeMin) * i) / 4, 2)}
                </text>
              ))}
            </g>
          )}
          {markers.map((p, i) => (
            <g
              key={p.id}
              className="risk-marker"
              data-kind={p.kind}
              tabIndex={0}
              role="button"
              aria-label={p.name}
              onMouseEnter={() => setHovered({ group: "marker", index: i })}
              onMouseLeave={() => setHovered(null)}
              onFocus={() => setHovered({ group: "marker", index: i })}
              onBlur={() => setHovered(null)}
              onClick={() => setHovered({ group: "marker", index: i })}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setHovered({ group: "marker", index: i });
                }
              }}
            >
              <rect
                x={x(p) - 14}
                y={y(p) - 14}
                width={28}
                height={28}
                fill="transparent"
              />
              {p.kind !== "asset" ? (
                <path
                  className={`risk-star risk-${p.kind}-star`}
                  transform={`translate(${x(p)},${y(p)}) scale(${p.kind === "portfolio" ? 1.35 : 1})`}
                  d="M0,-11 3,-3 11,-3 5,2 7,10 0,5 -7,10 -5,2 -11,-3 -3,-3Z"
                  fill={markerColor(p.kind, i)}
                  stroke="#0d1016"
                  strokeWidth="1.5"
                />
              ) : (
                <circle
                  cx={x(p)}
                  cy={y(p)}
                  r={5.5}
                  fill={markerColor(p.kind, i)}
                  stroke="#0d1016"
                  strokeWidth="2"
                />
              )}
            </g>
          ))}
          <text
            x={(left + right) / 2}
            y={height - 10}
            textAnchor="middle"
            className="risk-axis-title"
          >
            Volatilité annualisée (%)
          </text>
          <text
            transform={`translate(14,${(top + bottom) / 2}) rotate(-90)`}
            textAnchor="middle"
            className="risk-axis-title"
          >
            Rendement annualisé (%)
          </text>
        </svg>
        {active && (
          <div
            role="tooltip"
            className="risk-tooltip"
            style={{
              left: Math.max(0, Math.min(width - 210, x(active) + 14)),
              top: Math.max(0, y(active) - 115),
            }}
          >
            <strong>{activeMarker?.name ?? "Allocation possible"}</strong>
            <span>Rendement : {pct(active.return)}</span>
            <span>Volatilité : {pct(active.volatility)}</span>
            <span>
              Sharpe :{" "}
              {active.sharpe === null ? "indéfini" : number(active.sharpe, 2)}
            </span>
          </div>
        )}
      </div>
      <div className="risk-map-legend">
        {result.frontier.length > 1 && (
          <span>
            <i className="risk-legend-line" />
            Frontière efficiente
          </span>
        )}
        {result.lower_frontier.length > 1 && (
          <span>
            <i className="risk-legend-line dashed" />
            Branche inférieure
          </span>
        )}
        {cloud.length > 0 && (
          <span className="risk-sharpe-key">
            <span>{cloud.length} allocations · Sharpe</span>
            {compact && showScale && (
              <span className="risk-sharpe-mobile">
                <span>{number(sharpeMin, 2)}</span>
                <i style={{ background: sharpeGradient }} aria-hidden="true" />
                <span>{number(sharpeMax, 2)}</span>
              </span>
            )}
            {sharpes.length > 0 && !showScale && (
              <span>{number(sharpeMin, 2)}</span>
            )}
            {sharpes.length < cloud.length && (
              <span>
                <i style={{ background: undefinedSharpeColor }} />
                Indéfini
              </span>
            )}
          </span>
        )}
      </div>
      <details className="risk-table-details">
        <summary>Détail des actifs</summary>
        <div className="risk-table-wrap">
          <table className="risk-table">
            <thead>
              <tr>
                <th>Actif</th>
                <th>Rendement annualisé</th>
                <th>Volatilité annualisée</th>
              </tr>
            </thead>
            <tbody>
              {result.points.map((p, i) => (
                <tr key={p.id}>
                  <td>
                    <span className="risk-asset-name">
                      <i style={{ background: markerColor(p.kind, i) }} />
                      {p.name}
                    </span>
                  </td>
                  <td>{pct(p.return)}</td>
                  <td>{pct(p.volatility)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
