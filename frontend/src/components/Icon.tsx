import type { CSSProperties } from "react";
const paths: Record<string, React.ReactNode> = {
  regression: (
    <>
      <path d="M3 20h18M4 20V4M6 17l14-12" />
      <circle cx="8" cy="13" r="1" />
      <circle cx="13" cy="11" r="1" />
      <circle cx="17" cy="6" r="1" />
    </>
  ),
  prediction: (
    <>
      <path d="M3 20h18M4 20V4m2 11 5-5 4 3" />
      <path d="m15 13 6-8m-5 0h5v5" strokeDasharray="2 3" />
    </>
  ),
  frontier: (
    <>
      <path d="M3 20h18M4 20V4M6 17c1-9 6-12 14-13" />
      <circle cx="12" cy="10" r="1" />
      <circle cx="16" cy="14" r="1" />
    </>
  ),
  shield: (
    <>
      <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  "mean-reversion": (
    <>
      <path d="M3 12h18" strokeDasharray="2 3" />
      <path d="M3 7c3 0 3 10 6 10s3-10 6-10 3 10 6 10" />
    </>
  ),
  diversification: (
    <>
      <path d="M4 12h5m6-6h5m-5 12h5M9 12l6-6M9 12l6 6" />
      <circle cx="3" cy="12" r="1" />
      <circle cx="21" cy="6" r="1" />
      <circle cx="21" cy="18" r="1" />
    </>
  ),
  correlation: (
    <>
      <circle cx="5" cy="6" r="2" />
      <circle cx="19" cy="6" r="2" />
      <circle cx="12" cy="19" r="2" />
      <path d="M7 6h10M6 8l5 9m7-9-5 9" />
    </>
  ),
  balance: (
    <>
      <path d="M12 3v17M7 21h10M4 7h16M6 7l-4 8h8Zm12 0-4 8h8Z" />
    </>
  ),
  simulation: (
    <>
      <path d="M9 3h6m-5 0v6L4 19a1.3 1.3 0 0 0 1 2h14a1.3 1.3 0 0 0 1-2L14 9V3M7 15h10" />
      <path d="m9 18 2-2 2 2 2-1" />
    </>
  ),
  allocation: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3v9h9M12 12l-6 7" />
    </>
  ),
  commodity: (
    <>
      <path d="m12 3 8 4.5v9L12 21l-8-4.5v-9Z" />
      <path d="m4 7.5 8 4.5 8-4.5M12 12v9M8 5.3l8 4.5" />
    </>
  ),
  bond: (
    <>
      <path d="m3 9 9-6 9 6M4 10h16M5 19h14M3 22h18M6 10v9m6-9v9m6-9v9" />
    </>
  ),
  stock: (
    <>
      <path d="M4 4v16h17M7 14l5-5 4 3 5-7M17 5h4v4" />
    </>
  ),
  crypto: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m13 5-5 8h5l-2 6 6-9h-5Z" />
    </>
  ),
  star: (
    <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9Z" />
  ),
  lock: (
    <>
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2" />
    </>
  ),
  unlock: (
    <>
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0m-4 8v2" />
    </>
  ),
  minus: <path d="M5 12h14" />,
  plus: <path d="M12 5v14M5 12h14" />,
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 4 4" />
    </>
  ),
  arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  "chevron-up": <path d="m6 15 6-6 6 6" />,
  "chevrons-up": <path d="m6 12 6-6 6 6m-12 6 6-6 6 6" />,
  "chevron-down": <path d="m6 9 6 6 6-6" />,
  "chevrons-down": <path d="m6 6 6 6 6-6m-12 6 6 6 6-6" />,
  equal: <path d="M5 9h14M5 15h14" />,
  settings: (
    <>
      <path d="M4 7h16M4 17h16" />
      <circle cx="9" cy="7" r="3" />
      <circle cx="15" cy="17" r="3" />
    </>
  ),
  analysis: (
    <>
      <path d="M4 20V10m5 10V4m6 16v-8m5 8V7" />
      <path d="M3 20h19" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6m0-10v1" />
    </>
  ),
  external: (
    <>
      <path d="M14 3h7v7m0-7L10 14M10 4H4v16h16v-6" />
    </>
  ),
  play: <path d="m8 5 11 7-11 7Z" />,
  check: <path d="m5 12 4 4L19 6" />,
  layers: (
    <>
      <path d="m12 3 10 5-10 5L2 8Z" />
      <path d="m2 12 10 5 10-5M2 16l10 5 10-5" />
    </>
  ),
};
export function Icon({
  name,
  size = 18,
  style,
}: {
  name: string;
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={style}
    >
      {paths[name] ?? paths.layers}
    </svg>
  );
}
