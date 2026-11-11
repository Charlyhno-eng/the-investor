import { useEffect, useRef, useState } from "react";
import { date, number } from "../../lib/format";
import type { Point } from "../../lib/types";
import type { ForecastPoint } from "./model";

export function PredictionChart({
  history,
  forecast,
  unit,
}: {
  history: Point[];
  forecast: ForecastPoint[];
  unit: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1000);
  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(280, entry.contentRect.width)),
    );
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const height = width < 600 ? 320 : 420,
    left = 24,
    right = 100,
    top = 32,
    bottom = 44;
  const start = Date.parse(history[0].time),
    end = Date.parse(forecast.at(-1)!.time);
  const values = [
    ...history.map((p) => p.value),
    ...forecast.flatMap((p) => [p.p05, p.p95]),
  ];
  const min = values.reduce((a, b) => Math.min(a, b), Infinity),
    max = values.reduce((a, b) => Math.max(a, b), -Infinity);
  const padding = Math.max((max - min) * 0.1, max * 0.01);
  const low = min - padding,
    high = max + padding;
  const x = (time: string) =>
    left +
    ((Date.parse(time) - start) / (end - start)) * (width - left - right);
  const y = (value: number) =>
    top + ((high - value) / (high - low)) * (height - top - bottom);
  const path = (points: { time: string; value: number }[]) =>
    points
      .map((p, i) => `${i ? "L" : "M"}${x(p.time)},${y(p.value)}`)
      .join(" ");
  const band = (lower: "p05" | "p25", upper: "p75" | "p95") =>
    path([
      ...forecast.map((p) => ({ time: p.time, value: p[upper] })),
      ...[...forecast]
        .reverse()
        .map((p) => ({ time: p.time, value: p[lower] })),
    ]) + " Z";
  const rows = [
    ...history.map((p) => ({
      time: p.time,
      value: p.value,
      forecast: null as ForecastPoint | null,
    })),
    ...forecast
      .slice(1)
      .map((p) => ({ time: p.time, value: p.p50, forecast: p })),
  ];
  const active = hover === null ? null : rows[Math.min(hover, rows.length - 1)];
  return (
    <div className="prediction-chart" ref={container}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Historique du cours prolongé par la médiane et les intervalles probabilistes à 50 % et 90 %"
      >
        <title>Historique et projection probabiliste en {unit}</title>
        {Array.from({ length: 5 }, (_, i) => {
          const value = low + ((high - low) * i) / 4;
          return (
            <g key={i}>
              <line
                x1={left}
                x2={width - right}
                y1={y(value)}
                y2={y(value)}
                stroke="#ffffff0d"
              />
              <text x={width - right + 12} y={y(value) + 4}>
                {number(value, value < 1 ? 4 : 2)}
              </text>
            </g>
          );
        })}
        <path d={band("p05", "p95")} fill="#a78bfa25" />
        <path d={band("p25", "p75")} fill="#a78bfa45" />
        {(["p05", "p95"] as const).map((q) => (
          <path
            key={q}
            d={path(forecast.map((p) => ({ time: p.time, value: p[q] })))}
            fill="none"
            stroke="#a78bfa66"
            strokeWidth="1"
          />
        ))}
        <path
          d={path(history)}
          fill="none"
          stroke="#edb786"
          strokeWidth="2.5"
        />
        <path
          d={path(forecast.map((p) => ({ time: p.time, value: p.p50 })))}
          fill="none"
          stroke="#bda6ff"
          strokeWidth="2.5"
          strokeDasharray="7 4"
        />
        <line
          x1={x(forecast[0].time)}
          x2={x(forecast[0].time)}
          y1={top}
          y2={height - bottom}
          stroke="#939cab"
          strokeDasharray="4 5"
        />
        <text x={x(forecast[0].time) - 8} y={20} textAnchor="end">
          Dernier cours
        </text>
        {[
          history[0].time,
          ...(width >= 600 ? [forecast[0].time] : []),
          forecast.at(-1)!.time,
        ].map((time, i) => (
          <text
            key={i}
            x={x(time)}
            y={height - 12}
            textAnchor={i === 0 ? "start" : "end"}
          >
            {date(time)}
          </text>
        ))}
        {active && (
          <g>
            <line
              x1={x(active.time)}
              x2={x(active.time)}
              y1={top}
              y2={height - bottom}
              stroke="#939cab88"
            />
            <circle
              cx={x(active.time)}
              cy={y(active.value)}
              r="4"
              fill={active.forecast ? "#bda6ff" : "#edb786"}
            />
          </g>
        )}
        <rect
          x={left}
          y={top}
          width={width - left - right}
          height={height - top - bottom}
          fill="transparent"
          tabIndex={0}
          role="slider"
          aria-label="Explorer les cours et les projections avec les flèches"
          aria-valuemin={0}
          aria-valuemax={rows.length - 1}
          aria-valuenow={hover ?? history.length - 1}
          aria-valuetext={
            active
              ? `${date(active.time)} : ${number(active.value, 4)} ${unit}`
              : "Dernier cours"
          }
          onPointerMove={(event) => {
            const bounds =
              event.currentTarget.ownerSVGElement!.getBoundingClientRect();
            const position =
              ((event.clientX - bounds.left) / bounds.width) * width;
            let nearest = 0;
            for (let i = 1; i < rows.length; i++)
              if (
                Math.abs(x(rows[i].time) - position) <
                Math.abs(x(rows[nearest].time) - position)
              )
                nearest = i;
            setHover(nearest);
          }}
          onPointerLeave={() => setHover(null)}
          onKeyDown={(event) => {
            if (
              ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
            ) {
              event.preventDefault();
              setHover(
                event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? rows.length - 1
                    : Math.max(
                        0,
                        Math.min(
                          rows.length - 1,
                          (hover ?? history.length - 1) +
                            (event.key === "ArrowRight" ? 1 : -1),
                        ),
                      ),
              );
            }
          }}
        />
      </svg>
      <div className="prediction-readout" aria-live="polite">
        {active ? (
          <>
            <strong>{date(active.time)}</strong> ·{" "}
            {active.forecast ? "Médiane" : "Cours observé"} :{" "}
            {number(active.value, active.value < 1 ? 4 : 2)} {unit}
            {active.forecast && (
              <>
                {" "}
                · Zone 90 % : {number(active.forecast.p05, 4)} –{" "}
                {number(active.forecast.p95, 4)} {unit}
              </>
            )}
          </>
        ) : (
          "Survolez le graphique ou utilisez les flèches pour explorer les cours et les probabilités."
        )}
      </div>
    </div>
  );
}
