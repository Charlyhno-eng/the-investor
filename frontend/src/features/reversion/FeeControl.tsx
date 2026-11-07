import { useEffect, useState } from "react";

export function FeeControl({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  const format = (n: number) => n.toFixed(2).replace(".", ",");
  const [draft, setDraft] = useState(format(value));
  useEffect(() => {
    setDraft(format(value));
  }, [value]);
  const step = (delta: number) =>
    onChange(
      Math.min(99.99, Math.max(0, Math.round((value + delta) * 100) / 100)),
    );
  return (
    <label className="regression-fee-control">
      <span>{label} (%)</span>
      <div>
        <input
          type="text"
          inputMode="decimal"
          role="spinbutton"
          aria-label={`${label} (%)`}
          aria-valuemin={0}
          aria-valuemax={99.99}
          aria-valuenow={value}
          value={draft}
          onChange={(e) => {
            const next = e.target.value;
            if (!/^\d{0,2}([.,]\d{0,2})?$/.test(next)) return;
            setDraft(next);
            const parsed = Number(next.replace(",", "."));
            if (
              next.trim() &&
              Number.isFinite(parsed) &&
              parsed >= 0 &&
              parsed <= 99.99
            )
              onChange(parsed);
          }}
          onBlur={() => setDraft(format(value))}
          onKeyDown={(e) => {
            if (e.key === "ArrowUp" || e.key === "ArrowDown") {
              e.preventDefault();
              step(e.key === "ArrowUp" ? 0.01 : -0.01);
            }
          }}
        />
        <button
          type="button"
          aria-label={`Diminuer ${label.toLowerCase()}`}
          disabled={value <= 0}
          onClick={() => step(-0.01)}
        >
          −
        </button>
        <button
          type="button"
          aria-label={`Augmenter ${label.toLowerCase()}`}
          disabled={value >= 99.99}
          onClick={() => step(0.01)}
        >
          +
        </button>
      </div>
    </label>
  );
}
