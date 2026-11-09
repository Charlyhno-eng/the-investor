import { Icon } from "./Icon";
import { useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
export function Tooltip({
  label,
  children,
  floating = false,
  question = false,
}: {
  label: string;
  children: React.ReactNode;
  floating?: boolean;
  question?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 8, top: 8 });
  const anchor = useRef<HTMLButtonElement>(null);
  const content = useRef<HTMLSpanElement>(null);
  const id = useId();
  useLayoutEffect(() => {
    if (!floating || !open) return;
    const place = () => {
      if (!anchor.current || !content.current) return;
      const rect = anchor.current.getBoundingClientRect();
      const tip = content.current.getBoundingClientRect();
      setPosition({
        left: Math.max(
          8,
          Math.min(rect.left - tip.width / 2, innerWidth - tip.width - 8),
        ),
        top: Math.max(
          8,
          rect.top > tip.height + 16
            ? rect.top - tip.height - 8
            : Math.min(rect.bottom + 8, innerHeight - tip.height - 8),
        ),
      });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [floating, open]);
  const tooltip = (
    <span
      ref={content}
      id={id}
      role="tooltip"
      className={`tooltip-content${floating ? " tooltip-floating" : ""}`}
      style={floating ? position : undefined}
    >
      <strong>{label}</strong>
      {children}
    </span>
  );
  return (
    <span
      className="tooltip"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="info-button"
        ref={anchor}
        aria-describedby={floating && open ? id : undefined}
        aria-label={`Définition : ${label}`}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
        }}
      >
        {question ? (
          <span className="question-mark" aria-hidden="true">
            ?
          </span>
        ) : (
          <Icon name="info" size={13} />
        )}
      </button>
      {floating ? open && createPortal(tooltip, document.body) : tooltip}
    </span>
  );
}
