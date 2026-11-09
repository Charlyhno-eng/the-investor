import { useEffect, useRef, useState } from "react";
import {
  AreaSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  type MouseEventParams,
  LineSeries,
  PriceScaleMode,
  type Time,
} from "lightweight-charts";
import { date, number } from "../lib/format";
import type { ComparisonEquity, DividendEvent, Point } from "../lib/types";

type Props = {
  accessibleLabel?: string;
  valueLabel?: string;
  points?: Point[];
  range?: number;
  comparison?: ComparisonEquity;
  comparisonLabels?: {
    strategy: string;
    benchmark: string;
    accessible: string;
  };
  compact?: boolean;
  dividends?: DividendEvent[];
  overlays?: { title: string; color: string; points: Point[] }[];
  pointColors?: string[];
  logarithmic?: boolean;
  lines?: {
    title: string;
    color: string;
    lineWidth?: 1 | 2 | 3 | 4;
    points: Point[];
  }[];
};
const emptyPoints: Point[] = [];
export function HistoryChart({
  accessibleLabel,
  valueLabel = "Base 100",
  points = emptyPoints,
  range = 0,
  comparison,
  comparisonLabels,
  compact = false,
  dividends,
  overlays,
  pointColors,
  logarithmic = false,
  lines,
}: Props) {
  const [lineHover, setLineHover] = useState<{
    time: string;
    x: number;
    y: number;
    values: { title: string; color: string; value: number }[];
  } | null>(null);
  const [trendHover, setTrendHover] = useState<{
    time: string;
    price: number;
    trend: number;
    gap: number;
    x: number;
    y: number;
  } | null>(null);
  const [hovered, setHovered] = useState<{
    event: DividendEvent;
    x: number;
    y: number;
  } | null>(null);
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
    setHovered(null);
    setTrendHover(null);
    setLineHover(null);
    const chart = createChart(container.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#0d1016" },
        textColor: "#768090",
        fontFamily: "Inter, sans-serif",
        fontSize: 11,
        attributionLogo: true,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "#ffffff06" },
      },
      rightPriceScale: {
        mode: logarithmic ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
        borderVisible: false,
        scaleMargins: { top: 0.18, bottom: 0.12 },
      },
      timeScale: { borderVisible: false, rightOffset: 3, timeVisible: false },
      crosshair: {
        vertLine: { color: "#657188", labelBackgroundColor: "#252d3b" },
        horzLine: { color: "#657188", labelBackgroundColor: "#252d3b" },
      },
    });
    if (lines) {
      const series = lines.map((line) => {
        const item = chart.addSeries(LineSeries, {
          color: line.color,
          lineWidth: line.lineWidth ?? 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        item.setData(line.points.map((p) => ({ ...p, time: p.time as Time })));
        return { item, line };
      });
      const show = (param: MouseEventParams<Time>) => {
        if (!param.time || !param.point || !container.current) {
          setLineHover(null);
          return;
        }
        const values = series.flatMap(({ item, line }) => {
          const data = param.seriesData.get(item);
          return data && "value" in data
            ? [{ title: line.title, color: line.color, value: data.value }]
            : [];
        });
        setLineHover(
          values.length
            ? {
                time: String(param.time),
                x: Math.max(
                  8,
                  Math.min(
                    param.point.x + 16,
                    container.current.clientWidth - 235,
                  ),
                ),
                y: Math.max(
                  8,
                  Math.min(
                    param.point.y + 16,
                    container.current.clientHeight - 140,
                  ),
                ),
                values,
              }
            : null,
        );
      };
      chart.subscribeCrosshairMove(show);
      chart.subscribeClick(show);
    } else if (comparison) {
      const benchmark = chart.addSeries(LineSeries, {
        color: "#65738e",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      benchmark.setData(
        comparison.map((p) => ({ time: p.time as Time, value: p.benchmark })),
      );
      const strategy = chart.addSeries(AreaSeries, {
        lineColor: "#edb786",
        topColor: "#edb78618",
        bottomColor: "#edb78600",
        lineWidth: 2,
        priceLineVisible: false,
      });
      strategy.setData(
        comparison.map((p) => ({ time: p.time as Time, value: p.strategy })),
      );
    } else {
      const series = chart.addSeries(overlays ? LineSeries : AreaSeries, {
        color: "#8390a7",
        lineColor: "#edb786",
        topColor: "#edb78620",
        bottomColor: "#edb78600",
        lineWidth: 2,
        priceLineVisible: true,
        priceLineColor: "#edb78644",
        priceLineStyle: 2,
        priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      });
      series.setData(
        points.map((p, i) => ({
          time: p.time as Time,
          value: p.value,
          ...(pointColors ? { color: pointColors[i] } : {}),
        })),
      );
      for (const overlay of overlays ?? []) {
        const line = chart.addSeries(LineSeries, {
          title: overlay.title,
          color: overlay.color,
          lineWidth: 2,
          lineStyle: overlay.title === "Tendance" ? 0 : 2,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        line.setData(
          overlay.points.map((p) => ({ ...p, time: p.time as Time })),
        );
      }
      if (overlays) {
        const trend = overlays.find((o) => o.title === "Tendance");
        const trends = new Map(trend?.points.map((p) => [p.time, p.value]));
        chart.subscribeCrosshairMove((param) => {
          const day = typeof param.time === "string" ? param.time : null;
          const data = param.seriesData.get(series);
          const value = data && "value" in data ? data.value : null;
          const reference = day ? trends.get(day) : undefined;
          setTrendHover(
            day &&
              param.point &&
              value != null &&
              reference != null &&
              reference > 0
              ? {
                  x: Math.max(
                    8,
                    Math.min(
                      param.point.x + 18,
                      (container.current?.clientWidth ?? 300) - 220,
                    ),
                  ),
                  y: Math.max(
                    8,
                    Math.min(
                      param.point.y + 18,
                      (container.current?.clientHeight ?? 300) - 112,
                    ),
                  ),
                  time: day,
                  price: value,
                  trend: reference,
                  gap: value / reference - 1,
                }
              : null,
          );
        });
      }
      const dates = new Set(points.map((point) => point.time));
      const events = new Map(
        (dividends ?? [])
          .filter((event) => dates.has(event.time))
          .map((event) => [event.time, event]),
      );
      createSeriesMarkers(
        series,
        [...events.values()].map((event) => ({
          time: event.time as Time,
          position: "belowBar",
          color: "#91c9c2",
          shape: "circle",
          text: "D",
          id: event.time,
          size: 0.7,
        })),
      );
      const showDividend = (param: MouseEventParams<Time>) => {
        const time =
          typeof param.hoveredObjectId === "string"
            ? param.hoveredObjectId
            : typeof param.time === "string"
              ? param.time
              : null;
        const event = time ? events.get(time) : null;
        if (!event || !param.point || !container.current) {
          setHovered(null);
          return;
        }
        setHovered({
          event,
          x: Math.max(
            8,
            Math.min(param.point.x + 14, container.current.clientWidth - 225),
          ),
          y: Math.max(
            8,
            Math.min(param.point.y - 85, container.current.clientHeight - 100),
          ),
        });
      };
      chart.subscribeCrosshairMove(showDividend);
      chart.subscribeClick(showDividend);
    }
    const data = lines?.[0]?.points ?? comparison ?? points;
    if (range && data.length > 1) {
      const last = data[data.length - 1].time;
      const from = new Date(`${last}T00:00:00Z`);
      from.setUTCFullYear(from.getUTCFullYear() - range);
      const first = data.find(
        (p) => p.time >= from.toISOString().slice(0, 10),
      )?.time;
      if (first && first !== last)
        chart
          .timeScale()
          .setVisibleRange({ from: first as Time, to: last as Time });
      else chart.timeScale().fitContent();
    } else chart.timeScale().fitContent();
    return () => chart.remove();
  }, [
    points,
    range,
    comparison,
    dividends,
    overlays,
    pointColors,
    logarithmic,
    lines,
  ]);
  return (
    <div className={`history-chart ${compact ? "compact" : ""}`}>
      <div
        ref={container}
        className="chart-canvas"
        role="img"
        aria-label={
          accessibleLabel ??
          (lines
            ? "Performance du portefeuille et du S&P 500, base 100 en euros"
            : overlays
              ? "Prix, tendance ajustée et zones de retour à la tendance"
              : comparison
                ? (comparisonLabels?.accessible ??
                  "Capital de la stratégie et du marché, base 100")
                : "Historique interactif : zoom et déplacement. Repères D : dividendes, détails au survol ou au toucher.")
        }
      />
      {lineHover && (
        <div
          className="chart-lines-tooltip"
          role="tooltip"
          style={{ left: lineHover.x, top: lineHover.y }}
        >
          <span>
            {date(lineHover.time)} · {valueLabel}
          </span>
          {lineHover.values.map((v) => (
            <span key={v.title} style={{ color: v.color }}>
              {v.title} <strong>{number(v.value, 2)}</strong>
            </span>
          ))}
        </div>
      )}
      {overlays && trendHover && (
        <div
          className="chart-trend-tooltip"
          role="status"
          aria-live="off"
          style={{ left: trendHover.x, top: trendHover.y }}
        >
          <span>{date(trendHover.time)}</span>
          <span>Prix : {number(trendHover.price, 4)}</span>
          <span>Tendance : {number(trendHover.trend, 4)}</span>
          <strong className={trendHover.gap < 0 ? "positive" : "negative"}>
            Écart : {trendHover.gap > 0 ? "+" : ""}
            {number(trendHover.gap * 100)} %
          </strong>
        </div>
      )}
      {hovered && (
        <div
          className="chart-dividend-tooltip"
          role="status"
          style={{ left: hovered.x, top: hovered.y }}
        >
          <span>DIVIDENDE · {date(hovered.event.time)}</span>
          <strong>
            {hovered.event.yield_percent == null
              ? "Pourcentage indisponible"
              : `${number(hovered.event.yield_percent, 3)} %`}
          </strong>
          <small>Du cours de la séance précédente · brut</small>
        </div>
      )}
    </div>
  );
}
