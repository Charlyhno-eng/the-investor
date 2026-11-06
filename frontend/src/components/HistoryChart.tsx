import { useEffect, useRef } from "react";
import {
  AreaSeries,
  ColorType,
  createChart,
  LineSeries,
  type Time,
} from "lightweight-charts";
import type { Analysis, Point } from "../lib/types";

type Props = {
  points?: Point[];
  range?: number;
  comparison?: Analysis["equity"];
  compact?: boolean;
};
export function HistoryChart({
  points = [],
  range = 0,
  comparison,
  compact = false,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
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
        borderVisible: false,
        scaleMargins: { top: 0.18, bottom: 0.12 },
      },
      timeScale: { borderVisible: false, rightOffset: 3, timeVisible: false },
      crosshair: {
        vertLine: { color: "#657188", labelBackgroundColor: "#252d3b" },
        horzLine: { color: "#657188", labelBackgroundColor: "#252d3b" },
      },
    });
    if (comparison) {
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
      const series = chart.addSeries(AreaSeries, {
        lineColor: "#edb786",
        topColor: "#edb78620",
        bottomColor: "#edb78600",
        lineWidth: 2,
        priceLineColor: "#edb78644",
        priceLineStyle: 2,
        priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      });
      series.setData(points.map((p) => ({ ...p, time: p.time as Time })));
    }
    const data = comparison ?? points;
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
  }, [points, range, comparison]);
  return (
    <div
      ref={container}
      className={`history-chart ${compact ? "compact" : ""}`}
      role="img"
      aria-label={
        comparison
          ? "Capital de la stratégie et du marché, base 100"
          : "Historique interactif : zoom et déplacement"
      }
    />
  );
}
