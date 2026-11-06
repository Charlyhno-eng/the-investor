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
  step?: number;
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
      onChange={(e) => setDraft(e.target.value)}
      onBlur={(e) => {
        const parsed = Number(draft);
        if (
          draft.trim() &&
          Number.isFinite(parsed) &&
          e.currentTarget.validity.valid
        ) {
          onChange(parsed);
          setDraft(String(parsed));
        } else setDraft(String(value));
        setFocused(false);
      }}
    />
  );
}
