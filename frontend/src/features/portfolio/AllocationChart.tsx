import { useMemo, useState, type CSSProperties } from "react";
import { money } from "../../lib/currency";
import { number, percent } from "../../lib/format";
import { allocationColors, donutArc } from "./allocationColors";

type Slice = {
  id: string;
  name: string;
  value: number;
  weight: number;
  color?: string;
};
export function AllocationChart({
  positions,
  total,
  label = "ACTIF",
}: {
  positions: Slice[];
  total: number;
  label?: string;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [focused, setFocused] = useState<string | null>(null);
  const [selection, setSelection] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const active = focused ?? hovered ?? selection;
  const colors = useMemo(() => allocationColors(positions), [positions]);
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
            r="160"
            fill="none"
            stroke="#ffffff0b"
            strokeWidth="1"
            strokeDasharray="1 6"
          />
          <circle
            cx="180"
            cy="180"
            r="123"
            fill="none"
            stroke="#ffffff04"
            strokeWidth="42"
          />
          <circle
            cx="180"
            cy="180"
            r="96"
            fill="none"
            stroke="#ffffff0c"
            strokeWidth="1"
          />
          {slices.map((p) => {
            const start = offset;
            offset += p.weight;
            return (
              <path
                key={p.id}
                d={donutArc(start, p.weight, active === p.id ? 150 : 144, 104)}
                fill={colors.get(p.id)}
                stroke="#0d1119"
                strokeWidth={slices.length > 80 ? 0 : 0.6}
                className="allocation-slice"
                data-color={colors.get(p.id)}
                style={{ opacity: active && active !== p.id ? 0.28 : 1 }}
                tabIndex={0}
                role="button"
                aria-pressed={selection === p.id}
                aria-label={`${p.name} : ${percent(p.weight)}, ${money(p.value)}`}
                onPointerEnter={() => setHovered(p.id)}
                onPointerLeave={() => setHovered(null)}
                onFocus={() => setFocused(p.id)}
                onBlur={() => setFocused(null)}
                onClick={() => setSelection(selection === p.id ? null : p.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelection(selection === p.id ? null : p.id);
                  }
                  if (e.key === "Escape") {
                    setSelection(null);
                    setFocused(null);
                    setHovered(null);
                  }
                }}
              >
                <title>
                  {p.name} · {percent(p.weight)} · {money(p.value)}
                </title>
              </path>
            );
          })}
        </svg>
        <div className="donut-center" aria-live="polite">
          <span>{selected?.name ?? "Valeur du portefeuille"}</span>
          <strong>{number(selected?.value ?? total)}</strong>
          <small>
            {selected ? `${percent(selected.weight)} du portfolio · €` : "€"}
          </small>
        </div>
        <div className="allocation-count">
          {slices.length} {label === "SECTEUR" ? "secteurs" : "actifs"}{" "}
          <span>· répartition en euros</span>
        </div>
      </div>
      <div className="allocation-legend">
        {slices.length > 12 && (
          <input
            className="allocation-search"
            aria-label="Rechercher dans la répartition"
            placeholder="Rechercher un actif…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        )}
        <div className="allocation-legend-heading">
          <span>{label}</span>
          <span>POIDS / VALEUR</span>
        </div>
        <div className="allocation-legend-list">
          {slices
            .filter((p) =>
              p.name.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
            )
            .map((p) => (
              <button
                key={p.id}
                className={`allocation-legend-item ${active === p.id ? "active" : ""}`}
                style={
                  {
                    "--slice-color": colors.get(p.id),
                    "--slice-weight": `${p.weight * 100}%`,
                  } as CSSProperties
                }
                onPointerEnter={() => setHovered(p.id)}
                onPointerLeave={() => setHovered(null)}
                onFocus={() => setFocused(p.id)}
                onBlur={() => setFocused(null)}
                onClick={() => setSelection(selection === p.id ? null : p.id)}
                aria-pressed={selection === p.id}
              >
                <i style={{ background: colors.get(p.id) }} />
                <span>{p.name}</span>
                <span>
                  <strong>{percent(p.weight)}</strong>
                  <small>{money(p.value)}</small>
                </span>
              </button>
            ))}
          {slices.length > 0 &&
            !slices.some((p) =>
              p.name.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
            ) && <p className="fine-print">Aucun actif trouvé.</p>}
        </div>
      </div>
    </div>
  );
}
