"""One sovereign benchmark per country; ten-year maturity is source metadata."""

COUNTRIES = {
    "US": "États-Unis",
    "CA": "Canada",
    "MX": "Mexique",
    "BR": "Brésil",
    "FR": "France",
    "DE": "Allemagne",
    "GB": "Royaume-Uni",
    "IT": "Italie",
    "ES": "Espagne",
    "GR": "Grèce",
    "CH": "Suisse",
    "PL": "Pologne",
    "HU": "Hongrie",
    "JP": "Japon",
    "KR": "Corée du Sud",
    "AU": "Australie",
    "NZ": "Nouvelle-Zélande",
    "IN": "Inde",
    "ZA": "Afrique du Sud",
    "NO": "Norvège",
}


def series_for(country_code):
    overrides = {"IN": "INDIRLTLT01STM", "LT": "LTUIRLTLT01STM", "LV": "LVAIRLTLT01STM"}
    return overrides.get(country_code, f"IRLTLT01{country_code}M156N")
