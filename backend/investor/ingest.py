"""Independent import worker. Network access lives here, never in the API."""

import argparse
import csv
import hashlib
import io
import json
import logging
import math
import re
import time
from datetime import UTC, datetime

import httpx
from openpyxl import load_workbook

from investor.countries import COUNTRIES, series_for
from investor.db import DATA_DIR, save
from investor.imports.catalog import ARCHIVED_COMMODITIES
from investor.imports.service import seed_commodities, seed_crypto

log = logging.getLogger("ingest")
WORLD_BANK = "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx"


def download(url: str, extension: str) -> bytes:
    for attempt in range(3):
        try:
            with httpx.Client(timeout=90, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                payload = response.content
            break
        except httpx.HTTPError:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    # Content-addressed raw archive: revisions remain reproducible.
    raw = DATA_DIR / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload).hexdigest()
    (raw / f"{digest}.{extension}").write_bytes(payload)
    (raw / f"{digest}.json").write_text(
        json.dumps({"url": url, "downloaded_at": datetime.now(UTC).isoformat()})
    )
    return payload


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def parse_world_bank(payload):
    workbook = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
    try:
        rows = list(workbook["Monthly Prices"].values)
        first = next(
            i for i, row in enumerate(rows) if re.fullmatch(r"\d{4}M\d{2}", str(row[0]))
        )
        # Workbook has a commodity name row followed by a unit row.
        names, units = rows[first - 2], rows[first - 1]
        assets, points = [], []
        for col in range(1, len(names)):
            if not names[col]:
                continue
            name = str(names[col]).strip()
            asset_id = "wb-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            if asset_id not in ARCHIVED_COMMODITIES:
                continue
            values = []
            for row in rows[first:]:
                match = re.fullmatch(r"(\d{4})M(\d{2})", str(row[0]))
                value = number(row[col]) if col < len(row) else None
                if match and value is not None:
                    values.append((asset_id, f"{match[1]}-{match[2]}-01", value))
            if values:
                assets.append(
                    (
                        asset_id,
                        name,
                        "commodity",
                        "index"
                        if "index" in name.lower() or "=100" in str(units[col])
                        else "price",
                        str(units[col] or ""),
                        "monthly",
                        "world-bank",
                        "https://www.worldbank.org/en/research/commodity-markets",
                    )
                )
                points.extend(values)
        return assets, points
    finally:
        workbook.close()


def world_bank():
    assets, points = parse_world_bank(download(WORLD_BANK, "xlsx"))
    # Explicit archival import must never overwrite migrated daily futures.
    from investor.db import connect

    with connect() as connection:
        migrated = {
            r["id"]
            for r in connection.execute(
                "SELECT id FROM assets WHERE category='commodity' AND frequency='daily'"
            )
        }
    assets = [a for a in assets if a[0] not in migrated]
    points = [p for p in points if p[0] not in migrated]
    if assets:
        save(assets, points, "world-bank")
    log.info("Banque mondiale : %d séries, %d observations", len(assets), len(points))


def parse_fred(payload, symbol):
    rows = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    if symbol not in (rows.fieldnames or []):
        raise ValueError(f"{symbol}: colonne absente")
    points = []
    for row in rows:
        value = number(row.get(symbol))
        if value is not None:
            day = row.get("observation_date") or row.get("DATE")
            if not day:
                raise ValueError(f"{symbol}: date absente")
            datetime.strptime(day, "%Y-%m-%d")
            points.append((symbol, day, value))
    return points


TESOURO_URL = "https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"


def parse_brazil(payload):
    rows = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), delimiter=";")
    candidates = {}
    for row in rows:
        if row["Tipo Titulo"] != "Tesouro Prefixado":
            continue
        day = datetime.strptime(row["Data Base"], "%d/%m/%Y").date()
        maturity = datetime.strptime(row["Data Vencimento"], "%d/%m/%Y").date()
        value = number(row["Taxa Compra Manha"].replace(",", "."))
        distance = abs((maturity - day).days / 365.25 - 10)
        if (
            value is not None
            and maturity > day
            and (day not in candidates or distance < candidates[day][0])
        ):
            candidates[day] = (distance, value)
    if not candidates:
        raise ValueError("Aucun taux nominal brésilien disponible.")
    return [
        ("br-tesouro-prefixado", day.isoformat(), value)
        for day, (_, value) in sorted(candidates.items())
    ]


def brazil():
    points = parse_brazil(download(TESOURO_URL, "csv"))
    save(
        [
            (
                "br-tesouro-prefixado",
                "Brésil · Tesouro Prefixado",
                "bond",
                "yield",
                "%",
                "daily",
                "tesouro-direto",
                TESOURO_URL,
            )
        ],
        points,
        "tesouro-direto",
        country_code="BR",
    )


def import_country(code):
    if code == "BR":
        brazil()
        return "br-tesouro-prefixado"
    symbol = series_for(code)
    payload = download(
        f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={symbol}&cosd=1900-01-01",
        "csv",
    )
    points = parse_fred(payload, symbol)
    save(
        [
            (
                symbol,
                COUNTRIES[code],
                "bond",
                "yield",
                "%",
                "monthly",
                "oecd-fred",
                f"https://fred.stlouisfed.org/series/{symbol}",
            )
        ],
        points,
        f"fred:{symbol}",
        country_code=code,
        benchmark_years=10,
    )
    log.info("%s (%s) : %d observations", COUNTRIES[code], symbol, len(points))
    return symbol


def fred():
    failures = []
    for code, country in COUNTRIES.items():
        try:
            import_country(code)
        except Exception:
            log.exception("Échec %s ; historique existant conservé", country)
            failures.append(country)
    if failures:
        raise RuntimeError(f"Imports incomplets : {', '.join(failures)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["all", "world-bank", "fred", "crypto", "commodities"],
        default="all",
    )
    parser.add_argument(
        "--interval", type=int, help="Répéter toutes les N secondes (minimum 3600)"
    )
    args = parser.parse_args()
    if args.interval is not None and args.interval < 3600:
        parser.error("--interval doit être >= 3600")
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    while True:
        failed = False
        for source, run in [
            ("commodities", seed_commodities),
            *([("world-bank", world_bank)] if args.source == "world-bank" else []),
            ("fred", fred),
            ("crypto", seed_crypto),
        ]:
            if args.source in ("all", source):
                try:
                    run()
                except Exception:
                    log.exception("Échec de la source %s", source)
                    failed = True
        if not args.interval:
            raise SystemExit(1 if failed else 0)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
