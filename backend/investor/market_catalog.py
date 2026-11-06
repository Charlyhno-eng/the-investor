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
