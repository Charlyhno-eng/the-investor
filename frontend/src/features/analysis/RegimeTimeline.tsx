import { date, percent } from "../../lib/format";
import type { Analysis } from "../../lib/types";

function intervals(points: { time: string; label: string; color: string }[]) {
  const output: {
    start: string;
    end: string;
    label: string;
    color: string;
    count: number;
  }[] = [];
  for (const point of points) {
    const last = output.at(-1);
    if (last?.label === point.label) {
      last.end = point.time;
      last.count++;
    } else {
      output.push({
        start: point.time,
        end: point.time,
        label: point.label,
        color: point.color,
        count: 1,
      });
    }
  }
  return output;
}

export function RegimeTimeline({ result }: { result: Analysis }) {
  if (!result.regimes.length || !result.positions.length) return null;
  const colors = new Map(
    result.states.map((state) => [
      state.name,
      state.mean_change < 0
        ? "#bf747d"
        : state.mean_change > 0
          ? "#75aca5"
          : "#768090",
    ]),
  );
  const rows = [
    {
      label: "Régime dominant",
      points: result.regimes.map((point) => ({
        time: point.time,
        label: point.state,
        color: colors.get(point.state) ?? "#768090",
      })),
    },
    {
      label: "Position après clôture",
      points: result.positions.map((point) => ({
        time: point.time,
        label: point.position ? "Investi" : "Liquidités",
        color: point.position ? "#edb786" : "#343e50",
      })),
    },
  ];
  return (
    <section
      className="regime-timeline"
      aria-label="Régimes détectés et positions"
    >
      <div className="regime-legend">
        {result.states.map((state) => (
          <span
            key={state.name}
            title={`Rendement moyen d’entraînement : ${percent(state.mean_change)}`}
          >
            <i style={{ background: colors.get(state.name) }} />
            {state.name}
          </span>
        ))}
        <span>
          <i style={{ background: "#edb786" }} />
          Investi
        </span>
        <span>
          <i style={{ background: "#343e50" }} />
          Liquidités
        </span>
      </div>
      {rows.map((row) => (
        <div className="regime-timeline-row" key={row.label}>
          <span>{row.label}</span>
          <div className="regime-strip" role="img" aria-label={row.label}>
            {intervals(row.points).map((interval) => (
              <span
                key={interval.start}
                style={{ flex: interval.count, background: interval.color }}
                title={`${date(interval.start)} — ${date(interval.end)} · ${interval.label} · ${interval.count} observations`}
              />
            ))}
          </div>
        </div>
      ))}
      <p className="fine-print">
        Le régime décrit le signal ; la position tient compte du délai
        d’exécution et des frais. La position après clôture s’applique au
        rendement suivant.
      </p>
    </section>
  );
}
