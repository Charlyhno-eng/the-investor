import { useEffect, useState } from "react";

export function NumberInput({
  value,
  onChange,
  ...props
}: {
  value: number;
  onChange: (value: number) => void;
  min: number | string;
  max: number | string;
  step?: number | "any";
}) {
  const [draft, setDraft] = useState(String(value));
  const [focused, setFocused] = useState(false);
  useEffect(() => {
    if (!focused) setDraft(String(value));
  }, [value, focused]);
  return (
    <input
      {...props}
      type="number"
      value={draft}
      onFocus={() => setFocused(true)}
      onChange={(e) => {
        const next = e.target.value;
        setDraft(next);
        if (
          next.trim() &&
          e.target.validity.valid &&
          Number.isFinite(Number(next))
        )
          onChange(Number(next));
      }}
      onBlur={(e) => {
        const parsed = Number(draft);
        if (
          draft.trim() &&
          Number.isFinite(parsed) &&
          e.currentTarget.validity.valid
        ) {
          if (parsed !== value) onChange(parsed);
          setDraft(String(parsed));
        } else setDraft(String(value));
        setFocused(false);
      }}
    />
  );
}
