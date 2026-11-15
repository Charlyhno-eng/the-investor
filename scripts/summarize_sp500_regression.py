"""Fixed-rule robustness diagnostics for the already frozen continuous candidate."""

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

import numpy as np
from study_sp500_regression import PROTOCOL, features, passes, simulate

from investor import db

PATH = Path("data/backtests/sp500-regression-continuation.json")


def bootstrap(curve, *, block, count=5000):
    """Paired circular block bootstrap. Conditional descriptive intervals only."""
    returns = np.array(curve)[1:] / np.array(curve)[:-1] - 1
    rng = np.random.default_rng(20261114 + block)
    length = len(returns)
    nblocks = int(np.ceil(length / block))
    starts = rng.integers(0, length, (count, nblocks))
    indices = ((starts[:, :, None] + np.arange(block)) % length).reshape(count, -1)[
        :, :length
    ]
    r = returns[indices]
    cagr = np.exp(np.log1p(r).mean(axis=1) * 252) - 1
    vol = r.std(axis=1, ddof=1) * np.sqrt(252)
    sharpe = r.mean(axis=1) * 252 / vol
    diff = cagr[:, 0] - cagr[:, -1]
    gain = sharpe[:, 0] - sharpe[:, -1]
    return dict(
        block=block,
        count=count,
        excess_cagr_95=np.quantile(diff, [0.025, 0.5, 0.975]).tolist(),
        sharpe_gain_95=np.quantile(gain, [0.025, 0.5, 0.975]).tolist(),
        warning="Conditional paired block-resampling intervals, not a probability of future success and no multiple-search correction.",
    )


def main():
    report = json.loads(PATH.read_text())
    selected = report["selected"]
    months = PROTOCOL["windows_months"]
    i = months.index(selected["months"])
    neighbors = [
        {**selected, "months": m, "entry": e, "exit": x}
        for m in months[max(0, i - 1) : i + 2]
        for e in PROTOCOL["entry_z"]
        if abs(e - selected["entry"]) <= 0.5
        for x in PROTOCOL["exit_z"]
        if abs(x - selected["exit"]) <= 0.5 and e < x
    ]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "snapshot.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        if hashlib.sha256(path.read_bytes()).hexdigest() != report["snapshot_sha256"]:
            raise ValueError("Dataset changed since selection")
        with sqlite3.connect(path) as c:
            rows = c.execute(
                "SELECT date,value FROM observations WHERE asset_id='yf-ese.pa' ORDER BY date"
            ).fetchall()
            raw = dict(
                c.execute(
                    "SELECT date,value FROM price_observations WHERE asset_id='yf-ese.pa'"
                )
            )
            proxy = c.execute(
                "SELECT date,value FROM reference_observations WHERE symbol='^SP500TR' ORDER BY date"
            ).fetchall()
    days = [r[0] for r in rows]
    p = np.array([r[1] for r in rows])
    f, ma = features(days, p)
    raw = np.array([raw[d] for d in days])
    train = simulate(days, raw, f, ma, neighbors, PROTOCOL["train"])
    val = simulate(
        days,
        raw,
        f,
        ma,
        neighbors,
        PROTOCOL["validation"],
        initial=train["terminal_state"],
    )
    test = simulate(
        days,
        raw,
        f,
        ma,
        neighbors,
        PROTOCOL["reserved_test"],
        initial=val["terminal_state"],
    )
    report["neighbors"] = [
        dict(config=c, metrics=m, pass_gate=passes(m, test["benchmark"]))
        for c, m in zip(neighbors, test["candidates"], strict=True)
    ]
    report["bootstrap"] = [
        bootstrap(report["test"]["curve"], block=b) for b in [21, 63]
    ]
    pdays = [r[0] for r in proxy]
    pp = np.array([r[1] for r in proxy])
    pf, pm = features(pdays, pp)
    report["proxy_stresses"] = {}
    for name, period in [
        ("dotcom", ["2000-01-03", "2003-12-31"]),
        ("financial_crisis", ["2007-01-03", "2009-12-31"]),
        ("long", ["1993-01-04", pdays[-1]]),
    ]:
        report["proxy_stresses"][name] = simulate(
            pdays, pp, pf, pm, [selected], period, whole=False
        )
    PATH.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        "Neighbors passing final gates:",
        sum(n["pass_gate"] for n in report["neighbors"]),
        "/",
        len(neighbors),
    )
    print("Bootstrap:", report["bootstrap"])


if __name__ == "__main__":
    main()
