import { useState } from "react";
import { money } from "../../lib/currency";
import { number, percent } from "../../lib/format";

type Slice = { id: string; name: string; value: number; weight: number };
const palette = [
  "#edb786",
  "#7bb8ea",
  "#9c91e7",
  "#70cbb1",
  "#e69ba8",
  "#e4ce7b",
  "#62bfcf",
  "#b5c591",
  "#c48cd4",
  "#e79870",
];
export function AllocationChart({
  positions,
  total,
}: {
  positions: Slice[];
  total: number;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [focused, setFocused] = useState<string | null>(null);
  const [selection, setSelection] = useState<string | null>(null);
  const active = focused ?? hovered ?? selection;
  const slices = [...positions]
    .filter((p) => p.weight > 0)
    .sort((a, b) => b.weight - a.weight);
  const selected = slices.find((p) => p.id === active);
  let offset = 0;
  return (
    <div className="allocation-chart">
      <div className="allocation-donut">
        <svg
          viewBox="0 0 360 360"
          role="group"
          aria-label="Répartition du Portfolio"
        >
          <circle
            cx="180"
            cy="180"
            r="136"
            fill="none"
            stroke="#ffffff08"
            strokeWidth="48"
          />
          {slices.map((p, i) => {
            const start = offset;
            offset += p.weight * 100;
            return (
              <circle
                key={p.id}
                cx="180"
                cy="180"
                r="136"
                fill="none"
                stroke={palette[i % palette.length]}
                strokeWidth={active === p.id ? 58 : 48}
                pathLength={100}
                strokeDasharray={`${p.weight * 100} ${100 - p.weight * 100}`}
                strokeDashoffset={-start}
                transform="rotate(-90 180 180)"
                className="allocation-slice"
                style={{ opacity: active && active !== p.id ? 0.35 : 1 }}
                tabIndex={0}
                role="button"
                aria-label={`${p.name} : ${percent(p.weight)}, ${money(p.value)}`}
                onPointerEnter={() => setHovered(p.id)}
                onPointerLeave={() => setHovered(null)}
                onFocus={() => setFocused(p.id)}
                onBlur={() => setFocused(null)}
                onClick={() => setSelection(p.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelection(p.id);
                  }
                }}
              >
                <title>
                  {p.name} · {percent(p.weight)} · {money(p.value)}
                </title>
              </circle>
            );
          })}
        </svg>
        <div className="donut-center" aria-live="polite">
          <span>{selected?.name ?? "Valeur totale"}</span>
          <strong>{number(selected?.value ?? total)}</strong>
          <small>
            {selected ? `${percent(selected.weight)} du portfolio · €` : "€"}
          </small>
        </div>
      </div>
      <div className="allocation-legend">
        <div className="allocation-legend-heading">
          <span>ACTIF</span>
          <span>POIDS / VALEUR</span>
        </div>
        {slices.map((p, i) => (
          <button
            key={p.id}
            className={`allocation-legend-item ${active === p.id ? "active" : ""}`}
            onPointerEnter={() => setHovered(p.id)}
            onPointerLeave={() => setHovered(null)}
            onFocus={() => setFocused(p.id)}
            onBlur={() => setFocused(null)}
            onClick={() => setSelection(p.id)}
          >
            <i style={{ background: palette[i % palette.length] }} />
            <span>{p.name}</span>
            <span>
              <strong>{percent(p.weight)}</strong>
              <small>{money(p.value)}</small>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

// Diverging blue / neutral / red, like the RdBu_r heatmaps used in notebooks.
export function correlationColor(value: number): string {
  const stops = [
    [33, 102, 172],
    [103, 169, 207],
    [209, 229, 240],
    [247, 247, 247],
    [253, 219, 199],
    [239, 138, 98],
    [178, 24, 43],
  ];
  const t = ((Math.max(-1, Math.min(1, value)) + 1) / 2) * (stops.length - 1);
  const left = Math.min(Math.floor(t), stops.length - 2);
  return `rgb(${stops[left].map((channel, i) => Math.round(channel + (stops[left + 1][i] - channel) * (t - left))).join(",")})`;
}
