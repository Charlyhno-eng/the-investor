import { useEffect, useRef, useState } from "react";
import { number } from "../../lib/format";
import { correlationColor } from "./correlationColor";
import type { PortfolioResult } from "./types";

type Correlation = NonNullable<PortfolioResult["correlation"]>;
export function CorrelationHeatmap({
  correlation,
}: {
  correlation: Correlation;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [cell, setCell] = useState({ row: 0, column: 0 });
  const n = correlation.assets.length;
  const row = Math.min(cell.row, n - 1),
    column = Math.min(cell.column, n - 1);
  const value = correlation.matrix[row]?.[column] ?? null;
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const source = document.createElement("canvas");
    source.width = n;
    source.height = n;
    const context = source.getContext("2d")!;
    const pixels = context.createImageData(n, n);
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++) {
        const value = correlation.matrix[i]?.[j];
        const channels =
          value == null
            ? [23, 29, 41]
            : correlationColor(value).match(/\d+/g)!.map(Number);
        const at = (i * n + j) * 4;
        pixels.data.set([...channels, 255], at);
      }
    context.putImageData(pixels, 0, 0);
    const paint = () => {
      const dpr = devicePixelRatio || 1;
      element.width = Math.round(element.clientWidth * dpr);
      element.height = Math.round(element.clientHeight * dpr);
      const target = element.getContext("2d")!;
      target.imageSmoothingEnabled = false;
      target.drawImage(source, 0, 0, element.width, element.height);
    };
    const observer = new ResizeObserver(paint);
    observer.observe(element);
    paint();
    return () => observer.disconnect();
  }, [correlation, n]);
  return (
    <>
      <div className="correlation-viewport dense-correlation">
        <canvas
          ref={canvas}
          role="img"
          tabIndex={0}
          aria-label={`Matrice de corrélation de ${n} actifs. Utilisez les flèches ou les sélecteurs pour inspecter les cellules.`}
          onPointerMove={(e) => {
            const bounds = e.currentTarget.getBoundingClientRect();
            setCell({
              row: Math.max(
                0,
                Math.min(
                  n - 1,
                  Math.floor(((e.clientY - bounds.top) / bounds.height) * n),
                ),
              ),
              column: Math.max(
                0,
                Math.min(
                  n - 1,
                  Math.floor(((e.clientX - bounds.left) / bounds.width) * n),
                ),
              ),
            });
          }}
          onKeyDown={(e) => {
            const directions: Record<string, [number, number]> = {
              ArrowUp: [-1, 0],
              ArrowDown: [1, 0],
              ArrowLeft: [0, -1],
              ArrowRight: [0, 1],
            };
            const delta = directions[e.key];
            if (delta) {
              e.preventDefault();
              setCell({
                row: Math.max(0, Math.min(n - 1, row + delta[0])),
                column: Math.max(0, Math.min(n - 1, column + delta[1])),
              });
            }
          }}
        />
        <div
          className="correlation-crosshair"
          aria-hidden="true"
          style={{
            left: `${(column / n) * 100}%`,
            top: `${(row / n) * 100}%`,
            width: `${100 / n}%`,
            height: `${100 / n}%`,
          }}
        />
      </div>
      <div className="correlation-inspector">
        <label>
          Ligne
          <select
            aria-label="Actif en ligne"
            value={row}
            onChange={(e) => setCell({ row: Number(e.target.value), column })}
          >
            {correlation.assets.map((a, i) => (
              <option key={a.id} value={i}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Colonne
          <select
            aria-label="Actif en colonne"
            value={column}
            onChange={(e) => setCell({ row, column: Number(e.target.value) })}
          >
            {correlation.assets.map((a, i) => (
              <option key={a.id} value={i}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <div className="correlation-readout" role="status">
          <span>
            {correlation.assets[row].name} ↔ {correlation.assets[column].name}
          </span>
          <strong>r = {value === null ? "—" : number(value, 2)}</strong>
        </div>
      </div>
    </>
  );
}
