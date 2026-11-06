"""One sovereign benchmark per country; ten-year maturity is source metadata."""

COUNTRIES = {
    "US": "États-Unis",
    "CA": "Canada",
    "MX": "Mexique",
    "CL": "Chili",
    "FR": "France",
    "DE": "Allemagne",
    "GB": "Royaume-Uni",
    "IT": "Italie",
    "ES": "Espagne",
    "NL": "Pays-Bas",
    "BE": "Belgique",
    "AT": "Autriche",
    "PT": "Portugal",
    "IE": "Irlande",
    "GR": "Grèce",
    "FI": "Finlande",
    "DK": "Danemark",
    "SE": "Suède",
    "NO": "Norvège",
    "CH": "Suisse",
    "PL": "Pologne",
    "CZ": "Tchéquie",
    "HU": "Hongrie",
    "SK": "Slovaquie",
    "SI": "Slovénie",
    "IS": "Islande",
    "LT": "Lituanie",
    "LV": "Lettonie",
    "JP": "Japon",
    "KR": "Corée du Sud",
    "AU": "Australie",
    "NZ": "Nouvelle-Zélande",
    "IN": "Inde",
    "ZA": "Afrique du Sud",
}


def series_for(country_code):
    overrides = {"IN": "INDIRLTLT01STM", "LT": "LTUIRLTLT01STM", "LV": "LVAIRLTLT01STM"}
    return overrides.get(country_code, f"IRLTLT01{country_code}M156N")
