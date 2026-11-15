"""Timing and incumbent equivalence for the new two-sleeve research engine."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
# Research modules are standalone scripts, outside the installed backend package.
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "next_sp500", SCRIPTS / "study_sp500_next_iteration.py"
)
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)


def synthetic():
    days = ["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-04", "2020-02-05"]
    prices = np.array([100.0, 100.0, 100.0, 110.0, 120.0])
    slow = np.array([-0.5, -0.2, 0.1, 0.2, 0.3])
    features = {
        m: (slow if m == 60 else np.full(5, 2.0), np.ones(5))
        for m in study.old.PROTOCOL["windows_months"]
    }
    return (
        days,
        prices,
        (features, {m: np.full(5, 100.0) for m in [50, 100, 200]}, np.zeros(5)),
    )


@pytest.mark.parametrize("recovery", ["rebound0", "rebound_0.0"])
def test_monthly_recovery_waits_for_next_close_and_preserves_prior_nav(recovery):
    days, prices, features = synthetic()
    config = {**study.BASE, "recovery": recovery}
    result = study.simulate(
        days,
        prices,
        prices,
        features,
        [study.BASE, config],
        [days[0], days[-1]],
        keep_curve=True,
    )
    curve = np.array(result["curve"])
    np.testing.assert_allclose(curve[:3, 0], curve[:3, 1])
    # Recovery signal is Monday; Tuesday's additional purchase pays a fee.
    assert curve[3, 1] < curve[3, 0]
    assert curve[4, 1] > curve[4, 0]
    assert result["metrics"][1]["fees"] > result["metrics"][0]["fees"]
    # A huge future close cannot change the earlier account path.
    changed = prices.copy()
    changed[-1] *= 10
    other = study.simulate(
        days,
        changed,
        changed,
        features,
        [study.BASE, config],
        [days[0], days[-1]],
        keep_curve=True,
    )
    np.testing.assert_allclose(np.array(other["curve"])[:-1], curve[:-1])


@pytest.mark.parametrize("whole", [True, False])
def test_baseline_matches_independent_existing_sleeve_engines(whole):
    days, prices, features = synthetic()
    slow_config = dict(
        months=60,
        entry=-2,
        exit=1.5,
        rule="level",
        filter="none",
        cadence=21,
        floor=0.25,
        entry_rule="below",
    )
    defensive = dict(
        months=18,
        entry=-0.5,
        exit=1.5,
        rule="level",
        filter="none",
        cadence=5,
        floor=0.25,
        entry_rule="rebound",
    )
    curves, fees = [], 0.0
    for config, capital, calendar in [
        (slow_config, 7500, True),
        (defensive, 2500, False),
    ]:
        r = study.old.simulate(
            days,
            prices,
            features[0],
            features[1][200],
            [config],
            [days[0], days[-1]],
            initial_capital=capital,
            whole=whole,
            calendar=calendar,
            keep_curve=True,
        )
        curves.append(np.array(r["curve"])[:, 0])
        fees += r["candidates"][0]["fees"]
    result = study.simulate(
        days,
        prices,
        prices,
        features,
        [study.BASE],
        [days[0], days[-1]],
        whole=whole,
        keep_curve=True,
    )
    np.testing.assert_allclose(
        np.array(result["curve"])[:, 0], curves[0] + curves[1], atol=1e-9
    )
    assert result["metrics"][0]["fees"] == pytest.approx(fees)
