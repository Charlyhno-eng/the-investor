import { useRef, useState } from "react";
import type { Periods, Point } from "../../lib/types";
import { date } from "../../lib/format";

type Target = "train" | "test";
export function PeriodSelector({
  points,
  periods,
  onChange,
}: {
  points: Point[];
  periods: Periods;
  onChange: (value: Periods) => void;
}) {
  const [target, setTarget] = useState<Target>("train");
  const [anchor, setAnchor] = useState<number | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const index = (day: string) =>
    Math.max(
      0,
      points.findIndex((p) => p.time >= day),
    );
  const position = (day: string) =>
    (index(day) / Math.max(1, points.length - 1)) * 1000;
  const values = points.map((p) => p.value);
  const low = Math.min(...values),
    span = Math.max(...values) - low || 1;
  const stride = Math.max(1, Math.floor(points.length / 800));
  const path = points
    .filter((_, i) => i % stride === 0 || i === points.length - 1)
    .map((p) => {
      const i = index(p.time);
      return `${(i / Math.max(1, points.length - 1)) * 1000},${68 - ((p.value - low) / span) * 48}`;
    })
    .join(" ");
  function getIndex(event: React.PointerEvent<SVGSVGElement>) {
    const bounds = svg.current!.getBoundingClientRect();
    return Math.max(
      0,
      Math.min(
        points.length - 1,
        Math.round(
          ((event.clientX - bounds.left) / bounds.width) * (points.length - 1),
        ),
      ),
    );
  }
  function update(a: number, b: number) {
    if (a === b) return;
    onChange({
      ...periods,
      [`${target}_start`]: points[Math.min(a, b)].time,
      [`${target}_end`]: points[Math.max(a, b)].time,
    });
  }
  return (
    <div className="period-selection">
      <div className="selection-heading">
        <span className="field-label">Fenêtres d’analyse</span>
        <span className="fine-print">
          Choisissez une période, puis faites glisser sur la courbe.
        </span>
      </div>
      <div className="period-cards">
        {(["train", "test"] as const).map((key, i) => (
          <div
            key={key}
            className={`period-card ${key} ${target === key ? "selected" : ""}`}
          >
            <button
              className="period-card-title"
              type="button"
              onClick={() => setTarget(key)}
              aria-pressed={target === key}
            >
              <span className="step-number">0{i + 1}</span>
              <span>
                {key === "train" ? "Entraînement" : "Test hors échantillon"}
              </span>
              <span className="radio-dot" />
            </button>
            <div className="date-fields">
              <label>
                <span>Du</span>
                <input
                  aria-label={`Début ${key === "train" ? "entraînement" : "test"}`}
                  type="date"
                  min={points[0]?.time}
                  max={points.at(-1)?.time}
                  value={periods[`${key}_start`]}
                  onChange={(e) =>
                    onChange({ ...periods, [`${key}_start`]: e.target.value })
                  }
                />
              </label>
              <span className="date-arrow">→</span>
              <label>
                <span>Au</span>
                <input
                  aria-label={`Fin ${key === "train" ? "entraînement" : "test"}`}
                  type="date"
                  min={points[0]?.time}
                  max={points.at(-1)?.time}
                  value={periods[`${key}_end`]}
                  onChange={(e) =>
                    onChange({ ...periods, [`${key}_end`]: e.target.value })
                  }
                />
              </label>
            </div>
          </div>
        ))}
      </div>
      <div className={`timeline-selector ${target}`}>
        <svg
          ref={svg}
          viewBox="0 0 1000 86"
          preserveAspectRatio="none"
          role="img"
          aria-label="Sélection graphique des périodes ; les champs de dates permettent aussi la saisie au clavier"
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId);
            setAnchor(getIndex(e));
          }}
          onPointerMove={(e) => {
            if (anchor !== null) update(anchor, getIndex(e));
          }}
          onPointerUp={(e) => {
            if (anchor !== null) update(anchor, getIndex(e));
            setAnchor(null);
          }}
          onPointerCancel={() => setAnchor(null)}
        >
          {(["train", "test"] as const).map((key) => (
            <g key={key} className={key}>
              <rect
                x={position(periods[`${key}_start`])}
                y="0"
                width={Math.max(
                  0,
                  position(periods[`${key}_end`]) -
                    position(periods[`${key}_start`]),
                )}
                height="86"
              />
              <line
                x1={position(periods[`${key}_start`])}
                x2={position(periods[`${key}_start`])}
                y1="0"
                y2="86"
              />
              <line
                x1={position(periods[`${key}_end`])}
                x2={position(periods[`${key}_end`])}
                y1="0"
                y2="86"
              />
            </g>
          ))}
          <polyline
            points={path}
            fill="none"
            stroke="#8390a7"
            strokeWidth="1.3"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <div className="timeline-dates">
          <span>{date(points[0].time)}</span>
          <span>{date(points.at(-1)!.time)}</span>
        </div>
      </div>
    </div>
  );
}
