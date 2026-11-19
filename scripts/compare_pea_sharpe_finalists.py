"""Score already frozen policies on the confirmation audit's exact markets."""

import json
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import audit_pea_sharpe_hybrid as audit
import numpy as np
import study_pea_direct_sharpe as direct
import study_pea_sharpe_macro as macro
import study_pea_sharpe_models as core
import study_pea_timing as base

OUT = Path("data/backtests/pea-sharpe-finalists.json")


def main():
    models = json.loads(core.OUT.read_text())
    external = json.loads(macro.OUT.read_text())
    fit = json.loads(direct.OUT.read_text())
    ridge = tuple(models["frozen"][models["winner"]])
    cross = tuple(external["frozen"][external["winner"]])
    idx = fit["winner"]
    s, step, band = fit["frozen"][idx]
    s = tuple(s)
    weights = {s: [np.array(v) for v in fit["coefficients"][idx]]}
    report = dict(
        columns=["passive", "current", "previous", "ridge", "macro", "direct"], lots={}
    )
    with (
        sqlite3.connect(
            f"file:{base.DATA_DIR}/investor.sqlite3?mode=ro", uri=True
        ) as src,
        sqlite3.connect(":memory:") as conn,
        tempfile.TemporaryDirectory() as tmp,
    ):
        src.backup(conn)
        d, p = base.read_data(conn, "yf-psp5.pa")
        x = macro.factors(d, conn)
        lib = str(Path(tmp) / "allocation.so")
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
        for label, y, n, seed in audit.LOTS[:2]:
            results = []
            for cal, pp, xx in macro.paths(d, p, x, y, n, seed):
                a = core.run(lib, cal, pp, [*core.REF, ridge], d[-1])
                b = macro.score(lib, cal, pp, xx, [cross], d[-1])
                c = direct.evaluate(lib, cal, pp, weights, [(s, step, band)], d[-1])
                results.append(np.vstack([a, b, c]))
            rows = np.array(results)
            report["lots"][label] = core.summary(rows)
            reference = json.loads(audit.OUT.read_text())
            if label in reference["audit"]:
                np.testing.assert_allclose(
                    rows.mean(axis=0)[:3],
                    np.array(reference["audit"][label]["mean"])[:3],
                    atol=1e-9,
                )
            OUT.write_text(json.dumps(report, allow_nan=False))
            print(label, flush=True)


if __name__ == "__main__":
    main()
