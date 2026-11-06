"""On-demand Yahoo histories. Only the independent worker calls this provider."""

import argparse
import hashlib
import json
import logging
import math
from datetime import UTC, datetime

import yfinance as yf

from investor import db
from investor.market_catalog import CRYPTO

log = logging.getLogger(__name__)


def import_symbol(symbol: str, category: str) -> str:
    yf.set_tz_cache_location(str(db.DATA_DIR / "provider-cache"))
    ticker = yf.Ticker(symbol)
    frame = ticker.history(
        period="max", interval="1d", auto_adjust=True, actions=False, timeout=30
    )
    metadata = ticker.get_history_metadata()
    expected = "CRYPTOCURRENCY" if category == "crypto" else "EQUITY"
    if metadata.get("instrumentType") != expected:
        raise ValueError(
            "Symbole introuvable ou catégorie incompatible (actions cotées uniquement)."
        )
    if frame.empty:
        raise ValueError("Aucun historique disponible pour ce symbole.")
    asset_id = "yf-" + symbol.lower()
    # Daily timestamps use the exchange's local calendar, not a UTC conversion.
    points = [
        (asset_id, stamp.date().isoformat(), float(value))
        for stamp, value in frame["Close"].items()
        if math.isfinite(float(value)) and float(value) > 0
    ]
    if not points:
        raise ValueError("Historique vide après validation.")
    name = (
        CRYPTO.get(symbol)
        or metadata.get("longName")
        or metadata.get("shortName")
        or symbol
    )
    currency = metadata.get("currency", "USD")
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
                "adjusted": True,
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
    )
    return asset_id


def process_one() -> bool:
    with db.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
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
