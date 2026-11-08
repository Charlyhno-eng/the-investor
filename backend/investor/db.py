import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DATA_DIR = Path(
    os.environ.get("INVESTOR_DATA_DIR", Path(__file__).resolve().parents[2] / "data")
)


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA_DIR / "investor.sqlite3", timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS reference_observations (
      symbol TEXT NOT NULL, date TEXT NOT NULL, value REAL NOT NULL,
      PRIMARY KEY(symbol,date));
    CREATE TABLE IF NOT EXISTS reference_imports (
      symbol TEXT PRIMARY KEY, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS assets (
      id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
      metric TEXT NOT NULL, unit TEXT NOT NULL, frequency TEXT NOT NULL,
      source TEXT NOT NULL, source_url TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS price_observations (
      asset_id TEXT REFERENCES assets(id), date TEXT NOT NULL, value REAL NOT NULL,
      PRIMARY KEY(asset_id,date));
    CREATE TABLE IF NOT EXISTS observations (
      asset_id TEXT REFERENCES assets(id), date TEXT NOT NULL, value REAL NOT NULL,
      PRIMARY KEY(asset_id, date));
    CREATE TABLE IF NOT EXISTS imports (
      source TEXT PRIMARY KEY, completed_at TEXT NOT NULL, observations INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS import_jobs (
      id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, category TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'queued', asset_id TEXT, error TEXT,
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
      updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
    CREATE UNIQUE INDEX IF NOT EXISTS pending_symbol ON import_jobs(symbol)
      WHERE status IN ('queued','running');
    CREATE TABLE IF NOT EXISTS analysis_runs (
      id TEXT PRIMARY KEY, result TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
    CREATE TABLE IF NOT EXISTS dividends (
      asset_id TEXT REFERENCES assets(id), date TEXT NOT NULL, amount REAL NOT NULL,
      PRIMARY KEY(asset_id,date));
    CREATE TABLE IF NOT EXISTS dividend_imports (
      asset_id TEXT PRIMARY KEY REFERENCES assets(id), first_date TEXT NOT NULL,
      last_date TEXT NOT NULL, updated_at TEXT NOT NULL);
    """)
    columns = {row["name"] for row in db.execute("PRAGMA table_info(assets)")}
    for column, kind in [
        ("country_code", "TEXT"),
        ("benchmark_years", "INTEGER"),
        ("country", "TEXT"),
        ("is_dividend", "INTEGER NOT NULL DEFAULT 0"),
        ("sector", "TEXT"),
    ]:
        if column not in columns:
            db.execute(f"ALTER TABLE assets ADD COLUMN {column} {kind}")
    dividend_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(dividends)")
    }
    if "yield_percent" not in dividend_columns:
        db.execute("ALTER TABLE dividends ADD COLUMN yield_percent REAL")
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def save(
    assets,
    observations,
    source,
    *,
    country_code=None,
    benchmark_years=None,
    dividends=None,
    dividend_coverage=None,
):
    if not assets or not observations:
        raise ValueError(f"{source}: import vide, données locales conservées")
    with connect() as db:
        db.executemany(
            "INSERT INTO assets (id,name,category,metric,unit,frequency,source,source_url) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, category=excluded.category, metric=excluded.metric, unit=excluded.unit, frequency=excluded.frequency, source=excluded.source, source_url=excluded.source_url",
            assets,
        )
        if country_code is not None:
            db.executemany(
                "UPDATE assets SET country_code=?, benchmark_years=? WHERE id=?",
                [(country_code, benchmark_years, asset[0]) for asset in assets],
            )
        db.executemany(
            "INSERT INTO observations VALUES (?,?,?) ON CONFLICT(asset_id,date) DO UPDATE SET value=excluded.value",
            observations,
        )
        if dividends is not None and dividend_coverage is not None:
            asset_id, first, last = dividend_coverage
            # Replace only the successfully fetched window, including removed/corrected events.
            db.execute(
                "DELETE FROM dividends WHERE asset_id=? AND date>=? AND date<=?",
                (asset_id, first, last),
            )
            db.executemany(
                "INSERT INTO dividends (asset_id,date,amount,yield_percent) VALUES (?,?,?,?)",
                [
                    tuple(event) if len(event) == 4 else (*event, None)
                    for event in dividends
                ],
            )
            db.execute(
                "INSERT OR REPLACE INTO dividend_imports VALUES (?,?,?,strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
                (asset_id, first, last),
            )
        db.execute(
            "INSERT INTO imports VALUES (?,strftime('%Y-%m-%dT%H:%M:%SZ','now'),?) ON CONFLICT(source) DO UPDATE SET completed_at=excluded.completed_at, observations=excluded.observations",
            (source, len(observations)),
        )
