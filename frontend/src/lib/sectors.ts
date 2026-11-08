const sectors: Record<string, [string, string]> = {
  Technology: ["Technologie", "#3399ff"],
  "Consumer Cyclical": ["Consommation cyclique", "#ff44cc"],
  "Consumer Defensive": ["Consommation de base", "#b8e62e"],
  Financial: ["Finance", "#ffe033"],
  "Financial Services": ["Finance", "#ffe033"],
  Healthcare: ["Santé", "#ff5252"],
  Industrials: ["Industrie", "#ff922b"],
  Energy: ["Énergie", "#18d6b0"],
  Utilities: ["Services collectifs", "#a78bfa"],
  "Basic Materials": ["Matériaux", "#a87946"],
  "Communication Services": ["Communication", "#46e7ff"],
  "Real Estate": ["Immobilier", "#f0f1fa"],
};
export function sectorInfo(sector?: string | null) {
  const [name, color] = sector
    ? (sectors[sector] ?? [sector, "#94a3b8"])
    : ["Secteur non renseigné", "#8490a2"];
  return { name, color };
}
export function currencyCountry(id: string) {
  const code = id.slice(3, 6).toUpperCase();
  return (
    (
      {
        EUR: "Zone euro",
        GBP: "Royaume-Uni",
        JPY: "Japon",
        CNY: "Chine",
        CHF: "Suisse",
        AUD: "Australie",
        CAD: "Canada",
        HKD: "Hong Kong",
        SGD: "Singapour",
        INR: "Inde",
        KRW: "Corée du Sud",
        NZD: "Nouvelle-Zélande",
        SEK: "Suède",
        MXN: "Mexique",
        TWD: "Taïwan",
        ZAR: "Afrique du Sud",
        BRL: "Brésil",
        NOK: "Norvège",
        DKK: "Danemark",
        PLN: "Pologne",
        USD: "États-Unis",
      } as Record<string, string>
    )[code] ?? code
  );
}
