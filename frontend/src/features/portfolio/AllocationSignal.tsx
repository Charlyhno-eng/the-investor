import { Icon } from "../../components/Icon";

export function AllocationSignal({
  current,
  recommended,
}: {
  current: number;
  recommended: number | null;
}) {
  if (recommended == null) return null;
  const delta = recommended - current;
  // Ignore numerical solver noise, retaining changes below the display precision.
  const unchanged = Math.abs(delta) < 1e-8;
  const exit = !unchanged && recommended <= 1e-8;
  const strong = Math.abs(delta) >= 0.05 - 1e-8;
  const label = unchanged
    ? "Conserver la position"
    : exit
      ? "Sortir de la position"
      : delta > 0
        ? strong
          ? "Renforcer fortement la position"
          : "Renforcer la position"
        : strong
          ? "Alléger fortement la position"
          : "Alléger la position";
  const icon = unchanged
    ? "equal"
    : exit
      ? "close"
      : delta > 0
        ? strong
          ? "chevrons-up"
          : "chevron-up"
        : strong
          ? "chevrons-down"
          : "chevron-down";
  return (
    <span
      className={`allocation-signal ${unchanged ? "hold" : delta > 0 ? "increase" : "decrease"}`}
      role="img"
      aria-label={label}
      title={label}
    >
      <Icon name={icon} size={18} />
    </span>
  );
}
