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

ETF = {"SPY": "SPDR S&P 500 ETF"}
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
    )
)
COMMODITIES = {
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
