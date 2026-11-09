"""Small default watchlist; stocks are added explicitly by symbol."""

CRYPTO = {
    "XMR-USD": "Monero",
    "HYPE32196-USD": "Hyperliquid",
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "SOL-USD": "Solana",
    "BNB-USD": "BNB",
}

# Preserve archived histories while removing these assets from the library and refreshes.
REMOVED_CRYPTO = ("yf-ada-usd", "yf-xrp-usd")

ETF = {
    "SPY": "SPDR S&P 500 ETF",
    "CAC.PA": "Amundi CAC 40 UCITS ETF Dist",
    "LQQ.PA": "Amundi Nasdaq-100 Daily (2x) Leveraged UCITS ETF Acc",
    "EXA1.AS": "iShares EURO STOXX Banks 30-15 UCITS ETF (DE) EUR (Acc)",
    "SPMO": "Invesco S&P 500 Momentum ETF · US",
}
CURRENCIES = dict(
    zip(
        [
            "EURUSD=X",
            "GBPUSD=X",
            "JPYUSD=X",
            "CNYUSD=X",
            "CHFUSD=X",
            "AUDUSD=X",
            "CADUSD=X",
            "HKDUSD=X",
            "SGDUSD=X",
            "INRUSD=X",
            "KRWUSD=X",
            "NZDUSD=X",
            "SEKUSD=X",
            "MXNUSD=X",
            "TWDUSD=X",
            "ZARUSD=X",
            "BRLUSD=X",
            "NOKUSD=X",
            "DKKUSD=X",
            "PLNUSD=X",
        ],
        [
            "Euro",
            "Livre sterling",
            "Yen",
            "Yuan",
            "Franc suisse",
            "Dollar australien",
            "Dollar canadien",
            "Dollar de Hong Kong",
            "Dollar de Singapour",
            "Roupie indienne",
            "Won",
            "Dollar néo-zélandais",
            "Couronne suédoise",
            "Peso mexicain",
            "Dollar taïwanais",
            "Rand",
            "Réal brésilien",
            "Couronne norvégienne",
            "Couronne danoise",
            "Zloty",
        ],
        strict=True,
    )
)
ARCHIVED_COMMODITIES = {
    "wb-crude-oil-brent",
    "wb-natural-gas-us",
    "wb-coal-australian",
    "wb-gold",
    "wb-silver",
    "wb-platinum",
    "wb-aluminum",
    "wb-copper",
    "wb-iron-ore-cfr-spot",
    "wb-lead",
    "wb-nickel",
    "wb-tin",
    "wb-zinc",
    "wb-wheat-us-hrw",
    "wb-maize",
    "wb-rice-thai-5",
    "wb-soybeans",
    "wb-coffee-arabica",
    "wb-cocoa",
    "wb-cotton-a-index",
}

# Daily nearby futures; normalized to the previous physical quote's unit.
# Stable IDs retain browser watchlists and quantities. These are price proxies,
# not physical spot quotes or the total return of a rolling futures investment.
POUND_KG = 0.45359237
COMMODITY_FUTURES = {
    "BZ=F": ("wb-crude-oil-brent", "Brent · futures", "($/bbl)", 1),
    "NG=F": ("wb-natural-gas-us", "Gaz naturel US · futures", "($/mmbtu)", 1),
    "GC=F": ("wb-gold", "Or · futures", "($/troy oz)", 1),
    "SI=F": ("wb-silver", "Argent · futures", "($/troy oz)", 1),
    "PL=F": ("wb-platinum", "Platine · futures", "($/troy oz)", 1),
    "ALI=F": ("wb-aluminum", "Aluminium · futures", "($/mt)", 1),
    "HG=F": ("wb-copper", "Cuivre · futures", "($/mt)", 1000 / POUND_KG),
    "KE=F": ("wb-wheat-us-hrw", "Blé HRW US · futures", "($/mt)", 10 / (60 * POUND_KG)),
    "ZC=F": ("wb-maize", "Maïs · futures", "($/mt)", 10 / (56 * POUND_KG)),
    "ZS=F": ("wb-soybeans", "Soja · futures", "($/mt)", 10 / (60 * POUND_KG)),
    "KC=F": ("wb-coffee-arabica", "Café arabica · futures", "($/kg)", 0.01 / POUND_KG),
    "CC=F": ("wb-cocoa", "Cacao · futures", "($/kg)", 0.001),
}
COMMODITIES = {entry[0] for entry in COMMODITY_FUTURES.values()}
