"""A financial acceptance check must fail independently of technical tests."""

import pytest
from investor.analysis.evaluation import majority_acceptance


def result(asset, strategy, benchmark):
    return {
        "asset_id": asset,
        "strategy": {"total_return": strategy},
        "benchmark": {"total_return": benchmark},
    }


def test_majority_is_strict_and_ties_do_not_count_as_wins():
    rows = [
        result("a", 0.2, 0.1),
        result("b", 0.2, 0.1),
        result("c", 0.1, 0.1),
        result("d", 0.1, 0.2),
    ]
    rejected = majority_acceptance(rows, ["a", "b", "c", "d"])
    assert not rejected["passed"]
    assert rejected["wins"] == 2 and rejected["ties"] == 1
    assert rejected["required_wins"] == 3
    rows[2] = result("c", 0.3, 0.1)
    assert majority_acceptance(rows, ["a", "b", "c", "d"])["passed"]


def test_missing_or_failed_assets_cannot_be_dropped_from_the_denominator():
    rows = [result("a", 0.2, 0.1), result("b", 0.2, 0.1)]
    receipt = majority_acceptance(rows, ["a", "b", "c"])
    assert not receipt["passed"] and receipt["missing_assets"] == ["c"]
    rows.append({"asset_id": "c", "error": "No fit"})
    receipt = majority_acceptance(rows, ["a", "b", "c"])
    assert not receipt["passed"] and len(receipt["errors"]) == 1


def test_duplicates_cannot_inflate_success_rate():
    receipt = majority_acceptance([result("a", 0.2, 0.1)] * 3, ["a", "b", "c"])
    assert not receipt["passed"] and receipt["duplicate_assets"] == ["a"]


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), None])
def test_invalid_returns_fail_acceptance(invalid):
    receipt = majority_acceptance([result("a", invalid, 0.1)], ["a"])
    assert not receipt["passed"] and receipt["errors"]


def test_reported_excess_cannot_override_actual_net_returns():
    row = result("a", 0.05, 0.6)
    row["excess_return"] = 100
    assert majority_acceptance([row], ["a"])["wins"] == 0


def test_empty_universe_is_rejected():
    assert not majority_acceptance([], [])["passed"]


def test_unreachable_entry_is_distinct_from_absence_of_an_observed_signal():
    import numpy as np
    from investor.analysis.diagnostics import switching_diagnostics

    args = (np.array([[0.5, 0.5], [0.4, 0.6]]), np.array([-0.001, 0.001]))
    blocked = switching_diagnostics(
        *args, np.array([0.002, 0.004]), 0.01, [0, 0], 0, 0.6
    )
    assert blocked["entry_reachable"] is False
    assert blocked["maximum_state_forecast"] == pytest.approx(0.004)
    assert blocked["entry_signal_observations"] == 0
    possible = switching_diagnostics(
        *args, np.array([-0.02, 0.02]), 0.01, [0, 0], 0, 0.6
    )
    assert possible["entry_reachable"] is True
    assert possible["entry_signal_observations"] == 0


def test_predictive_state_labels_only_use_completed_training_outcomes(monkeypatch):
    import importlib
    from pathlib import Path

    import numpy as np

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    research = importlib.import_module("research_hmm_predictive")
    rng = np.random.default_rng(172)
    returns = rng.normal(0, 0.01, 400)
    p = rng.dirichlet(np.ones(3), 400)
    original = research.rewards(returns, p, 250, 21)
    changed = returns.copy()
    changed[250:] += 1
    future_p = p.copy()
    future_p[250:] = [0, 0, 1]
    np.testing.assert_allclose(research.rewards(changed, future_p, 250, 21), original)
    changed = returns.copy()
    changed[249] += 0.5
    assert not np.allclose(research.rewards(changed, p, 250, 21), original)
