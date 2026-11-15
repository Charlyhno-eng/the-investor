"""Third diagnostic: preserve holdings and hysteresis across chronological splits."""

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

import numpy as np
from study_sp500_regression import PROTOCOL, features, grid, passes, score, simulate

from investor import db

OUT = Path("data/backtests/sp500-regression-continuation.json")
PLAN = {
    "reason": "Additional diagnostic after independent cash-start results. Preserve holdings, trailing state, cadence and cash across train/validation/test; starting cash can materially change a hysteresis strategy.",
    "selection": "Same original grid and gates; train all candidates, validate all candidates by continuation, select highest validation rank among candidates passing both. No final-test results used. If none pass, report diagnostic highest validation rank among train passers without adoption.",
    "train": PROTOCOL["train"],
    "validation": PROTOCOL["validation"],
    "test": PROTOCOL["reserved_test"],
    "gate": PROTOCOL["gate"],
    "stress": "Full train-to-test trajectory rerun with fees 1%, delay two sessions and 20bp added per side; selection remains frozen.",
    "limitations": "Third retrospective experiment; previous experiments have already examined the historical test. No independent prospective evidence. All expansions and failures documented.",
}


def subset(state, indices):
    n = len(state["state"])
    out = {}
    for k, v in state.items():
        out[k] = (
            [v[i] for i in [*indices, n]]
            if k in ("cash", "units")
            else [v[i] for i in indices]
            if isinstance(v, list)
            else v
        )
    return out


def main():
    OUT.write_text(json.dumps({"plan": PLAN}, indent=2) + "\n")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "snapshot.sqlite3"
        with (
            sqlite3.connect(
                f"file:{(db.DATA_DIR / 'investor.sqlite3').resolve()}?mode=ro", uri=True
            ) as src,
            sqlite3.connect(path) as dst,
        ):
            src.backup(dst)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        first = json.loads(
            Path("data/backtests/sp500-regression-study.json").read_text()
        )
        if sha != first["snapshot_sha256"]:
            raise ValueError("Dataset changed")
        with sqlite3.connect(path) as c:
            rows = c.execute(
                "SELECT o.date,o.value,p.value FROM observations o JOIN price_observations p ON o.asset_id=p.asset_id AND o.date=p.date WHERE o.asset_id='yf-ese.pa' ORDER BY o.date"
            ).fetchall()
        days = [r[0] for r in rows]
        adjusted, raw = np.array([[r[1], r[2]] for r in rows]).T
        f, ma = features(days, adjusted)
        configs = grid()
        train = simulate(days, raw, f, ma, configs, PROTOCOL["train"])
        val = simulate(
            days,
            raw,
            f,
            ma,
            configs,
            PROTOCOL["validation"],
            initial=train["terminal_state"],
        )
        tp = [
            i
            for i, m in enumerate(train["candidates"])
            if passes(m, train["benchmark"], True)
        ]
        both = [i for i in tp if passes(val["candidates"][i], val["benchmark"])]
        winner = max(
            both or tp, key=lambda i: score(val["candidates"][i], val["benchmark"])
        )
        ranked = sorted(
            both or tp, key=lambda i: -score(val["candidates"][i], val["benchmark"])
        )[:20]
        report = dict(
            plan=PLAN,
            snapshot_sha256=sha,
            candidate_count=len(configs),
            train_pass=len(tp),
            both_pass=len(both),
            selected=configs[winner],
            train_benchmark=train["benchmark"],
            validation_benchmark=val["benchmark"],
            selected_train=train["candidates"][winner],
            selected_validation=val["candidates"][winner],
            shortlist=[
                dict(
                    config=configs[i],
                    train=train["candidates"][i],
                    validation=val["candidates"][i],
                )
                for i in ranked
            ],
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            "Continuous selection frozen:",
            len(both),
            "qualified",
            configs[winner],
            flush=True,
        )
        test = simulate(
            days,
            raw,
            f,
            ma,
            [configs[winner]],
            PROTOCOL["reserved_test"],
            initial=subset(val["terminal_state"], [winner]),
            keep_curve=True,
        )
        report["test"] = test
        report["full"] = simulate(
            days,
            raw,
            f,
            ma,
            [configs[winner]],
            ["2018-09-17", days[-1]],
            keep_curve=True,
        )
        report["stresses"] = {}
        for name, kw in [
            ("double_fees", {"fee": 0.01}),
            ("extra_delay", {"delay": 2}),
            ("extra_cost_20bp", {"fee": 0.007}),
        ]:
            tr = simulate(days, raw, f, ma, [configs[winner]], PROTOCOL["train"], **kw)
            va = simulate(
                days,
                raw,
                f,
                ma,
                [configs[winner]],
                PROTOCOL["validation"],
                initial=tr["terminal_state"],
                **kw,
            )
            report["stresses"][name] = simulate(
                days,
                raw,
                f,
                ma,
                [configs[winner]],
                PROTOCOL["reserved_test"],
                initial=va["terminal_state"],
                **kw,
            )
        report["adopt"] = bool(
            both
            and passes(test["candidates"][0], test["benchmark"])
            and all(
                passes(v["candidates"][0], v["benchmark"])
                for v in report["stresses"].values()
            )
        )
        OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print("Complete. Adopt:", report["adopt"], flush=True)


if __name__ == "__main__":
    main()
