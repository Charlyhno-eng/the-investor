"""Automatic refresh scheduling, retries and API lifecycle."""

from threading import Event

from fastapi.testclient import TestClient

from investor import db
from investor.api import app
from investor.imports import service
from investor.imports.refresh import schedule_refreshes


def stock():
    db.save(
        [
            (
                "yf-test",
                "Test",
                "stock",
                "price",
                "USD",
                "daily",
                "yahoo",
                "https://example.com",
            )
        ],
        [("yf-test", "2020-01-01", 100)],
        "yahoo:TEST",
    )


def expire():
    with db.connect() as c:
        c.execute("UPDATE imports SET completed_at='2000-01-01T00:00:00Z'")
        c.execute("UPDATE import_jobs SET updated_at='2000-01-01T00:00:00Z'")


def jobs():
    with db.connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM import_jobs")]


def test_refresh_deduplicates_backs_off_and_retries(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    stock()
    schedule_refreshes()
    assert not jobs()  # A successful recent check also covers closed markets.
    expire()
    schedule_refreshes()
    schedule_refreshes()
    assert len(jobs()) == 1

    def fail(*args):
        raise RuntimeError("offline")

    monkeypatch.setattr(service, "import_symbol", fail)
    assert service.process_one()
    schedule_refreshes()
    assert len(jobs()) == 1
    with db.connect() as c:
        assert c.execute("SELECT value FROM observations").fetchone()[0] == 100
    expire()
    schedule_refreshes()
    assert len(jobs()) == 2
    monkeypatch.setattr(service, "import_symbol", lambda *args: stock() or "yf-test")
    assert service.process_one()
    schedule_refreshes()
    assert len(jobs()) == 2


def test_api_refreshes_existing_data_without_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    stock()
    expire()
    imported = Event()

    def load(*args):
        stock()
        imported.set()
        return "yf-test"

    monkeypatch.setattr(service, "import_symbol", load)
    with TestClient(app) as client:
        assert imported.wait(3)
        after = client.get("/api/assets").json()[0]["data_revision"]
        assert "2000-01-01" not in after
        assert after
    assert jobs()[0]["status"] == "completed"


def test_scheduler_includes_commodities_bonds_and_references(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    from investor.imports.catalog import COMMODITY_FUTURES

    symbol, (asset_id, *_) = next(iter(COMMODITY_FUTURES.items()))
    with db.connect() as c:
        for identifier, category, source, code in [
            (asset_id, "commodity", "world-bank", None),
            ("IRLTLT01FRM156N", "bond", "oecd-fred", "FR"),
            ("yf-ada-usd", "crypto", "yahoo", None),
            ("yf-btc-usd", "crypto", "yahoo", None),
        ]:
            c.execute(
                "INSERT INTO assets(id,name,category,metric,unit,frequency,source,source_url,country_code) VALUES (?,?,?,'price','USD','daily',?,'',?)",
                (identifier, identifier, category, source, code),
            )
        c.execute(
            "INSERT INTO reference_imports VALUES ('BTC-USD','2000-01-01T00:00:00Z')"
        )
    schedule_refreshes()
    assert {(j["symbol"], j["category"]) for j in jobs()} == {
        (symbol, "commodity"),
        ("FR", "sovereign"),
        ("BTC-USD", "crypto"),
    }
    # BTC's reference job must still be scheduled after its asset job completes.
    with db.connect() as c:
        c.execute("UPDATE import_jobs SET status='completed'")
        c.execute(
            "INSERT INTO imports VALUES ('yahoo:BTC-USD',strftime('%Y-%m-%dT%H:%M:%SZ','now'),1)"
        )
    schedule_refreshes()
    assert ("BTC-USD", "reference") in {(j["symbol"], j["category"]) for j in jobs()}
