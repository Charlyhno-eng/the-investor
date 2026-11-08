import { date, number } from "../../lib/format";
export type Deviation = {
  id: string;
  z: number | null;
  start?: string;
  end?: string;
  reason?: string;
};
export function RegressionDeviation({ deviation }: { deviation?: Deviation }) {
  const z = deviation?.z;
  const hue = z == null ? 60 : 60 - Math.max(-1, Math.min(1, z / 1.5)) * 60;
  return (
    <span
      className="regression-deviation"
      data-z={z ?? undefined}
      title={
        deviation?.reason ??
        (deviation?.start && deviation.end
          ? `Régression du ${date(deviation.start)} au ${date(deviation.end)}`
          : "Chargement de la régression…")
      }
      style={
        z == null
          ? undefined
          : {
              color: `hsl(${hue} 65% 65%)`,
              background: `hsl(${hue} 60% 30% / 0.2)`,
            }
      }
    >
      {z == null ? "—" : `${z > 0 ? "+" : ""}${number(z, 2)} σ`}
    </span>
  );
}
