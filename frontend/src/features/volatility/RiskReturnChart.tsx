import { useEffect, useRef, useState } from "react";
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

export function RiskReturnChart({ result }: { result: RiskResult }) {
  const host = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [hovered, setHovered] = useState<number | null>(null);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(260, entry.contentRect.width)),
    );
    if (host.current) observer.observe(host.current);
    return () => observer.disconnect();
  }, []);
  const height = width < 500 ? 520 : 660;
  const left = 64,
    right = width - 22,
    top = 38,
    bottom = height - 62;
  const all = [...result.points, ...result.frontier, ...result.lower_frontier];
  const risks = all.map((p) => p.volatility),
    returns = all.map((p) => p.return);
  const riskLow = Math.min(...risks),
    riskHigh = Math.max(...risks);
  const returnLow = Math.min(...returns),
    returnHigh = Math.max(...returns);
  const riskPad = Math.max(1, (riskHigh - riskLow) * 0.17);
  const returnPad = Math.max(0.5, (returnHigh - returnLow) * 0.2);
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
  const markerColor = (index: number) =>
    result.points[index].kind === "benchmark"
      ? "#65b9ff"
      : palette[index % palette.length];
  const active = hovered === null ? null : result.points[hovered];
  return (
    <div ref={host} className="risk-map">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Frontière de Markowitz et actifs comparés au S&P 500"
        onMouseLeave={() => setHovered(null)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setHovered(null);
        }}
      >
        <title>Rendement et volatilité annualisés en euros</title>
        <desc>
          Un point par actif et un point pour le S&P 500. La courbe donne la
          variance minimale pour chaque rendement cible. Les valeurs des actifs
          figurent dans le tableau.
        </desc>
        {Array.from({ length: 6 }, (_, i) => {
          const xx = left + ((right - left) * i) / 5,
            yy = bottom - ((bottom - top) * i) / 5;
          return (
            <g key={i} className="risk-grid">
              <line x1={xx} x2={xx} y1={top} y2={bottom} />
              <line x1={left} x2={right} y1={yy} y2={yy} />
              <text x={xx} y={bottom + 23} textAnchor="middle">
                {number(xMin + ((xMax - xMin) * i) / 5, 1)} %
              </text>
              <text x={left - 10} y={yy + 4} textAnchor="end">
                {number(yMin + ((yMax - yMin) * i) / 5, 1)} %
              </text>
            </g>
          );
        })}
        {result.lower_frontier.length > 1 && (
          <path
            className="risk-lower-frontier"
            d={path(result.lower_frontier)}
            fill="none"
            stroke="#9eacff"
            strokeWidth="1.5"
            strokeDasharray="5 5"
            opacity=".5"
          />
        )}
        {result.frontier.length > 1 && (
          <path
            className="risk-frontier"
            d={path(result.frontier)}
            fill="none"
            stroke="#9eacff"
            strokeWidth="2.5"
            strokeLinejoin="round"
          />
        )}
        {result.points.map((p, i) => (
          <g
            key={p.id}
            className="risk-marker"
            data-kind={p.kind}
            tabIndex={0}
            role="button"
            aria-label={p.name}
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
            onFocus={() => setHovered(i)}
            onBlur={() => setHovered(null)}
            onClick={() => setHovered(i)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                setHovered(i);
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
            {p.kind === "benchmark" ? (
              <path
                className="risk-benchmark-star"
                transform={`translate(${x(p)},${y(p)})`}
                d="M0,-11 3,-3 11,-3 5,2 7,10 0,5 -7,10 -5,2 -11,-3 -3,-3Z"
                fill={markerColor(i)}
                stroke="#0d1016"
                strokeWidth="1.5"
              />
            ) : (
              <circle
                cx={x(p)}
                cy={y(p)}
                r={5.5}
                fill={markerColor(i)}
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
            top: Math.max(0, y(active) - 85),
          }}
        >
          <strong>{active.name}</strong>
          <span>Rendement : {pct(active.return)}</span>
          <span>Volatilité : {pct(active.volatility)}</span>
        </div>
      )}
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
                      <i style={{ background: markerColor(i) }} />
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
