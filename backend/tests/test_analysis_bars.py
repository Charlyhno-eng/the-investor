import json

from investor import db
from investor.analysis.bars import enrich_rows


def archive(tmp_path, text, **meta):
    raw = tmp_path / "raw"
    raw.mkdir(exist_ok=True)
    (raw / "quote.json").write_text(
        json.dumps(
            dict(
                source="yahoo",
                symbol="TEST",
                downloaded_at="2026-01-01",
                observation_column="Adj Close",
                **meta,
            )
        )
    )
    (raw / "quote.csv").write_text(text)


def test_archived_ohlc_uses_same_adjustment_as_observed_prices(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    archive(
        tmp_path, "Date,Open,High,Low,Close,Adj Close\n2020-01-01,100,110,90,100,50\n"
    )
    result = enrich_rows("yf-test", [{"date": "2020-01-01", "value": 50}])
    assert result == [
        {
            "date": "2020-01-01",
            "value": 50,
            "open": 50,
            "high": 55,
            "low": 45,
            "bar_close": 50,
        }
    ]


def test_archive_close_mismatch_rejects_stale_ohlc(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    archive(
        tmp_path, "Date,Open,High,Low,Close,Adj Close\n2020-01-01,100,110,90,100,50\n"
    )
    rows = [{"date": "2020-01-01", "value": 51}]
    assert enrich_rows("yf-test", rows) == rows


def test_csv_revision_invalidates_cached_bars_without_metadata_change(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    archive(
        tmp_path, "Date,Open,High,Low,Close,Adj Close\n2020-01-01,100,110,90,100,50\n"
    )
    rows = [{"date": "2020-01-01", "value": 50}]
    assert enrich_rows("yf-test", rows)[0]["low"] == 45
    (tmp_path / "raw/quote.csv").write_text(
        "Date,Open,High,Low,Close,Adj Close\n2020-01-01,100,110,80.1,100,50\n"
    )
    assert enrich_rows("yf-test", rows)[0]["low"] == 40.05


def test_invalid_or_missing_bars_use_explicit_close_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    archive(
        tmp_path,
        "Date,Open,High,Low,Close,Adj Close\n2020-01-01,100,80,90,100,50\n2020-01-02,nan,110,90,100,50\n",
    )
    rows = [{"date": "2020-01-01", "value": 50}, {"date": "2020-01-02", "value": 50}]
    assert enrich_rows("yf-test", rows) == rows
    assert enrich_rows("yf-missing", rows) == rows
