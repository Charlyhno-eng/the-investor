"""Read archived Yahoo OHLC, adjusted consistently with the observed close."""

import csv
import json
import math
from functools import lru_cache

from investor import db


@lru_cache(maxsize=4)
def _catalog(signature):
    found = {}
    for filename, _, _ in signature:
        try:
            with open(filename) as handle:
                meta = json.load(handle)
            if meta.get("source") != "yahoo" or not meta.get("symbol"):
                continue
            aid = "yf-" + meta["symbol"].lower()
            stamp = meta.get("downloaded_at", "")
            if aid not in found or stamp > found[aid][0]:
                found[aid] = (
                    stamp,
                    filename.replace(".json", ".csv"),
                    meta.get("observation_column", "Close"),
                )
        except (OSError, ValueError, AttributeError):
            continue
    return found


@lru_cache(maxsize=16)
def _read_bars(filename, mtime, size, observation_column):
    bars = {}
    with open(filename, newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                close = float(row["Close"])
                observed = float(row[observation_column])
                factor = observed / close
                values = [float(row[key]) * factor for key in ("Open", "High", "Low")]
                if not all(math.isfinite(v) and v > 0 for v in [observed, *values]):
                    continue
                opening, high, low = values
                if low > min(opening, observed) or high < max(opening, observed):
                    continue
                bars[row["Date"][:10]] = {
                    "open": opening,
                    "high": high,
                    "low": low,
                    "bar_close": observed,
                }
            except (KeyError, ValueError, ZeroDivisionError):
                continue
    return bars


def enrich_rows(asset_id, rows):
    """No network or writes. Reject stale archive bars if their close differs."""
    signature = tuple(
        sorted(
            (str(p), p.stat().st_mtime_ns, p.stat().st_size)
            for p in (db.DATA_DIR / "raw").glob("*.json")
        )
    )
    record = _catalog(signature).get(asset_id)
    if not record:
        return [dict(row) for row in rows]
    _, filename, column = record
    try:
        from pathlib import Path

        stat = Path(filename).stat()
        bars = _read_bars(filename, stat.st_mtime_ns, stat.st_size, column)
    except OSError:
        bars = {}
    result = []
    for row in rows:
        item = dict(row)
        bar = bars.get(item["date"])
        if bar and math.isclose(
            bar["bar_close"], item["value"], rel_tol=1e-8, abs_tol=1e-10
        ):
            item.update(bar)
        result.append(item)
    return result
