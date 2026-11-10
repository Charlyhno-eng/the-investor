"""Market histories downloaded by background queue consumers."""

import argparse
import hashlib
import json
import logging
import math
from datetime import UTC, datetime
from itertools import pairwise

import yfinance as yf

from investor import db
from investor.imports.catalog import COMMODITY_FUTURES, CRYPTO, CURRENCIES, ETF

log = logging.getLogger(__name__)


def import_symbol(symbol: str, category: str) -> str:
    if category == "crypto" and symbol not in CRYPTO:
        raise ValueError("Cryptomonnaie absente du catalogue.")
    if category == "commodity" and symbol not in COMMODITY_FUTURES:
        raise ValueError("Matière première absente du catalogue journalier.")
    yf.set_tz_cache_location(str(db.DATA_DIR / "provider-cache"))
    ticker = yf.Ticker(symbol)
    frame = ticker.history(
        period="max", interval="1d", auto_adjust=False, actions=True, timeout=30
    )
    metadata = ticker.get_history_metadata()
    expected = {
        "crypto": "CRYPTOCURRENCY",
        "stock": "EQUITY",
        "etf": "ETF",
        "currency": "CURRENCY",
        "commodity": "FUTURE",
    }[category]
    if metadata.get("instrumentType") != expected:
        raise ValueError(
            f"Symbole introuvable ou catégorie incompatible : {symbol} ({metadata.get('instrumentType')})."
        )
    if frame.empty:
        raise ValueError("Aucun historique disponible pour ce symbole.")
    if category in ("stock", "etf") and "Adj Close" not in frame:
        raise ValueError("Clôtures ajustées absentes ; données précédentes conservées.")
    commodity = COMMODITY_FUTURES.get(symbol) if category == "commodity" else None
    asset_id = commodity[0] if commodity else "yf-" + symbol.lower()
    multiplier = commodity[3] if commodity else 1
    # Daily timestamps use the exchange's local calendar, not a UTC conversion.
    points = [
        (asset_id, stamp.date().isoformat(), float(value) * multiplier)
        for stamp, value in frame[
            "Adj Close" if "Adj Close" in frame else "Close"
        ].items()
        if math.isfinite(float(value)) and float(value) > 0
    ]
    if not points:
        raise ValueError("Historique vide après validation.")
    name = (
        CRYPTO.get(symbol)
        or ETF.get(symbol)
        or CURRENCIES.get(symbol)
        or metadata.get("longName")
        or metadata.get("shortName")
        or symbol
    )
    currency = metadata.get("currency", "USD")
    if commodity:
        expected_currency = (
            "USX" if symbol in {"KE=F", "ZC=F", "ZS=F", "KC=F"} else "USD"
        )
        if currency != expected_currency:
            raise ValueError(
                f"Devise du contrat inattendue : {symbol} ({currency}, attendu {expected_currency})."
            )
        name, currency = commodity[1], commodity[2]
        if len(points) < 22 or not any(
            0 < (datetime.fromisoformat(b[1]) - datetime.fromisoformat(a[1])).days < 7
            for a, b in pairwise(points)
        ):
            raise ValueError("Historique journalier insuffisant.")
    dividends = None
    coverage = None
    if category == "stock":
        if "Dividends" not in frame:
            raise ValueError(
                "Historique des dividendes absent de la réponse fournisseur."
            )
        dividends = []
        previous_close = frame["Close"].shift(1)
        for stamp, value in frame["Dividends"].items():
            amount = float(value)
            if not math.isfinite(amount) or amount < 0:
                raise ValueError("Dividende invalide ; données précédentes conservées.")
            if amount > 0:
                reference = float(previous_close.loc[stamp])
                yield_percent = (
                    100 * amount / reference
                    if math.isfinite(reference) and reference > 0
                    else None
                )
                dividends.append(
                    (asset_id, stamp.date().isoformat(), amount, yield_percent)
                )
        coverage = (
            asset_id,
            frame.index[0].date().isoformat(),
            frame.index[-1].date().isoformat(),
        )
    raw = db.DATA_DIR / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    payload = frame.to_csv().encode()
    digest = hashlib.sha256(payload).hexdigest()
    (raw / f"{digest}.csv").write_bytes(payload)
    (raw / f"{digest}.json").write_text(
        json.dumps(
            {
                "symbol": symbol,
                "source": "yahoo",
                "adjusted": False,
                "observation_column": "Adj Close" if "Adj Close" in frame else "Close",
                "downloaded_at": datetime.now(UTC).isoformat(),
                "metadata": metadata,
            },
            default=str,
        )
    )
    db.save(
        [
            (
                asset_id,
                name,
                category,
                "price",
                currency,
                "daily",
                "yahoo",
                f"https://finance.yahoo.com/quote/{symbol}/history/",
            )
        ],
        points,
        f"yahoo:{symbol}",
        dividends=dividends,
        dividend_coverage=coverage,
        replace_history=bool(commodity),
    )
    if category == "stock":
        update_country(ticker, asset_id)
    with db.connect() as connection:
        connection.executemany(
            "INSERT OR REPLACE INTO price_observations VALUES (?,?,?)",
            [
                (asset_id, stamp.date().isoformat(), float(value) * multiplier)
                for stamp, value in frame["Close"].items()
                if math.isfinite(float(value)) and value > 0
            ],
        )
    return asset_id


def update_country(ticker, asset_id: str):
    """Company domicile from its profile; never infer it from the listing venue."""
    try:
        info = ticker.get_info()
        country = info.get("country")
        with db.connect() as connection:
            connection.execute(
                "UPDATE assets SET sector=? WHERE id=?", (info.get("sector"), asset_id)
            )
        if isinstance(country, str) and country.strip():
            with db.connect() as connection:
                connection.execute(
                    "UPDATE assets SET country=? WHERE id=?",
                    (country.strip(), asset_id),
                )
    except Exception:
        log.exception("Pays indisponible pour %s ; métadonnées conservées", asset_id)


def process_one() -> bool:
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        # Both the API consumer and bulk worker claim jobs atomically. Recover
        # abandoned downloads after a bounded lease rather than resetting live jobs.
        connection.execute(
            "UPDATE import_jobs SET status='queued' WHERE status='running' "
            "AND updated_at < strftime('%Y-%m-%dT%H:%M:%SZ','now','-15 minutes')"
        )
        job = connection.execute(
            "SELECT * FROM import_jobs WHERE status='queued' ORDER BY id LIMIT 1"
        ).fetchone()
        if job is None:
            return False
        connection.execute(
            "UPDATE import_jobs SET status='running', updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
            (job["id"],),
        )
    try:
        if job["category"] == "reference":
            from investor.assets.comparison import import_reference

            import_reference(job["symbol"])
            asset_id = None
        elif job["category"] == "sovereign":
            from investor.ingest import import_country

            asset_id = import_country(job["symbol"])
        else:
            asset_id = import_symbol(job["symbol"], job["category"])
        status, error = "completed", None
    except Exception:
        log.exception("Import échoué : %s", job["symbol"])
        status, asset_id = "failed", None
        error = f"Import impossible pour {job['symbol']}. Vérifiez le symbole ou réessayez si le fournisseur est indisponible."
    with db.connect() as connection:
        connection.execute(
            "UPDATE import_jobs SET status=?,asset_id=?,error=?,updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
            (status, asset_id, error, job["id"]),
        )
    return True


def seed_commodities():
    failures = []
    for symbol in COMMODITY_FUTURES:
        try:
            import_symbol(symbol, "commodity")
            log.info("Importé : %s", symbol)
        except Exception:
            log.exception("Échec : %s", symbol)
            failures.append(symbol)
    if failures:
        raise RuntimeError("Imports incomplets : " + ", ".join(failures))


def seed_crypto():
    failures = []
    for symbol in CRYPTO:
        try:
            import_symbol(symbol, "crypto")
            log.info("Importé : %s", symbol)
        except Exception:
            log.exception("Échec : %s", symbol)
            failures.append(symbol)
    if failures:
        raise RuntimeError("Imports incomplets : " + ", ".join(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.seed:
        seed_crypto()
