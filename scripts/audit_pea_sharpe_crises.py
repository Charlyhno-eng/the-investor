"""External historical stress only: never substitute a proxy in the application."""

import json
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import audit_pea_sharpe_hybrid as audit
import numpy as np
import study_pea_sharpe_hybrid as hybrid
import study_pea_timing as base

OUT = Path("data/backtests/pea-sharpe-proxy-crises.json")
PERIODS = {
    "price_usd": [
        ("1929-01-01", "1932-12-31"),
        ("1935-01-01", "1959-12-31"),
        ("1960-01-01", "1979-12-31"),
        ("1973-01-01", "1974-12-31"),
        ("1987-01-01", "1987-12-31"),
    ],
    "total_return_usd": [
        ("1994-01-01", "2013-12-31"),
        ("2000-01-01", "2002-12-31"),
        ("2007-01-01", "2009-12-31"),
    ],
    "spy_fx_eur": [("2007-01-01", "2009-12-31"), ("2010-01-01", "2013-12-31")],
}


def main():
    report = dict(rules=audit.RULES, metrics=hybrid.METRICS, results={})
    with (
        sqlite3.connect(
            f"file:{base.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
        ) as src,
        sqlite3.connect(":memory:") as conn,
        tempfile.TemporaryDirectory() as tmp,
    ):
        src.backup(conn)

        def reference(symbol):
            rows = conn.execute(
                "select date,value from reference_observations where symbol=? order by date",
                (symbol,),
            ).fetchall()
            return np.array([r[0] for r in rows]), np.array([r[1] for r in rows])

        sd, sp = base.read_data(conn, "yf-spy")
        fd, fx = reference("EURUSD=X")
        days, si, fi = np.intersect1d(sd, fd, return_indices=True)
        sources = {
            "price_usd": reference("^GSPC"),
            "total_return_usd": reference("^SP500TR"),
            "spy_fx_eur": (days, sp[si] / fx[fi]),
        }
        lib = str(Path(tmp) / "ledger.so")
        subprocess.run(
            [
                "cc",
                "-O3",
                "-shared",
                "-fPIC",
                str(Path(__file__).with_name("pea_sharpe_allocation.c")),
                "-lm",
                "-o",
                lib,
            ],
            check=True,
        )
        for key, periods in PERIODS.items():
            d, p = sources[key]
            report["results"][key] = {}
            for a, b in periods:
                lo = d.searchsorted(a)
                hi = d.searchsorted(b, side="right")
                assert lo < hi - 2 and d[-1] >= b and d[0] <= a
                # Unit price 30 at inception solely to approximate PSP5 rounding.
                rows = hybrid.evaluate(lib, d, p / p[lo] * 30, audit.RULES, a, b)
                report["results"][key][a] = dict(
                    first=d[lo],
                    last=d[hi - 1],
                    observations=int(hi - lo),
                    warmup=int(lo),
                    rows=rows.tolist(),
                )
        OUT.write_text(json.dumps(report, allow_nan=False))


if __name__ == "__main__":
    main()
