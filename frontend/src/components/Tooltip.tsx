import { Icon } from "./Icon";
export function Tooltip({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <span className="tooltip">
      <button
        type="button"
        className="info-button"
        aria-label={`Définition : ${label}`}
      >
        <Icon name="info" size={13} />
      </button>
      <span role="tooltip" className="tooltip-content">
        <strong>{label}</strong>
        {children}
      </span>
    </span>
  );
}
