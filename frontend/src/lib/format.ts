export const number = (value: number, digits = 2) =>
  (Math.abs(value) < 0.5 * 10 ** -digits ? 0 : value).toLocaleString("fr-FR", {
    maximumFractionDigits: digits,
  });
export const percent = (value: number | null | undefined, signed = false) =>
  value == null
    ? "—"
    : `${signed && value > 0 ? "+" : ""}${number(value * 100)} %`;
export const date = (value: string) =>
  new Date(`${value}T00:00:00Z`).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
export const categories = [
  {
    id: "commodity",
    name: "Matières premières",
    short: "Matières",
    icon: "commodity",
  },
  { id: "bond", name: "Obligations", short: "Obligations", icon: "bond" },
  { id: "stock", name: "Actions", short: "Actions", icon: "stock" },
  { id: "crypto", name: "Cryptomonnaies", short: "Crypto", icon: "crypto" },
] as const;
export const sources: Record<string, string> = {
  "world-bank": "Banque mondiale",
  "oecd-fred": "OCDE · FRED",
  yahoo: "Yahoo Finance",
};
