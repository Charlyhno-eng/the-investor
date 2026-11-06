import type { Asset } from "./types";
const names: Record<string, string> = {
  "United States": "États-Unis",
  Netherlands: "Pays-Bas",
  "United Kingdom": "Royaume-Uni",
  Germany: "Allemagne",
  Switzerland: "Suisse",
  Spain: "Espagne",
  Italy: "Italie",
  Belgium: "Belgique",
  Japan: "Japon",
  China: "Chine",
  "South Korea": "Corée du Sud",
  Taiwan: "Taïwan",
  Sweden: "Suède",
  Denmark: "Danemark",
  Australia: "Australie",
  Ireland: "Irlande",
};
export function stockCountry(asset: Asset): string {
  return asset.country
    ? (names[asset.country] ?? asset.country)
    : "Pays non renseigné";
}
