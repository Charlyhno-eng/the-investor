"""Causality, slower observations, hysteresis, and actual trading costs."""

import numpy as np
import pytest
from investor.analysis.persistent import (
    REPRESENTATIONS,
    observations,
    probabilities,
    simulate,
    targets,
)


@pytest.mark.parametrize("representation", REPRESENTATIONS)
def test_features_do_not_change_when_future_returns_are_added(representation):
    rng = np.random.default_rng(72)
    changes = rng.normal(0.001, 0.01, 1000)
    prefix, indices = observations(changes[:800], representation)
    full, full_indices = observations(changes, representation)
    np.testing.assert_equal(indices, full_indices[: len(indices)])
    np.testing.assert_allclose(prefix, full[: len(prefix)])
    if representation == "return21":
        assert indices[0] == 20
        assert np.all(np.diff(indices) == 21)
        assert prefix[0, 0] == pytest.approx(changes[:21].sum())


def test_hmm_filter_and_training_are_independent_of_future_test_prices():
    rng = np.random.default_rng(71)
    changes = rng.normal(0.0005, 0.015, 1000)
    prefix, negative, details = probabilities(changes[:850], 700, "trend21")
    changed = changes.copy()
    changed[850:] = -0.2
    full, full_negative, full_details = probabilities(changed, 700, "trend21")
    np.testing.assert_allclose(prefix, full[:850])
    assert negative == full_negative
    assert details == full_details


def test_hysteresis_holds_through_uncertain_regime_and_defensive_uses_sign():
    p = np.array([0.8, 0.49, 0.51, 0.49, 0.2, 0.6, 0.8])
    np.testing.assert_equal(targets(p, "hysteresis", 1, True), [1, 1, 1, 1, 0, 0, 1])
    np.testing.assert_equal(targets(p, "defensive", 1, False), np.ones(len(p)))
    np.testing.assert_equal(targets(p, "dominant", 3, True), [1, 1, 1, 0, 0, 0, 1])


def test_execution_cannot_capture_same_day_return_and_costs_match_orders():
    changes = np.log1p([0.5, 0.1, -0.2, 0.05, 0.1])
    decisions = np.array([1, 1, 0, 1, 1])
    free = simulate(changes, decisions, 0)
    paid = simulate(changes, decisions, 50)
    # First return cannot be earned; the -20% return precedes the sell execution.
    assert free["strategy"]["total_return"] == pytest.approx(1.1 * 0.8 * 1.1 - 1)
    assert paid["transactions"] == free["transactions"] == 4
    assert paid["exposure"] == free["exposure"]
    assert 1 + paid["strategy"]["total_return"] == pytest.approx(
        (1 + free["strategy"]["total_return"]) * 0.995**4
    )
    assert 1 + paid["benchmark"]["total_return"] == pytest.approx(
        (1 + free["benchmark"]["total_return"]) * 0.995**2
    )


def test_passive_delayed_entry_advantage_is_not_a_model_advantage(monkeypatch):
    import importlib
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    choose = importlib.import_module("evaluate_hmm_persistent_adaptive").choose
    changes = np.log1p([-0.1, 0.01, 0.02, 0.01])
    passive = dict(
        simulate(changes, np.ones(len(changes)), 50), policy="return1_defensive_c21"
    )
    # Simply avoiding the first -10% looks like a win against the old benchmark.
    assert passive["excess_return"] > 0.09
    # It provides zero advantage over passive entry on the same executable close.
    policy, advantage = choose([passive], changes[0])
    assert policy == "passive"
    assert advantage == pytest.approx(0)
    better = dict(
        passive, strategy={"total_return": passive["strategy"]["total_return"] + 0.03}
    )
    assert choose([better], changes[0])[0] == better["policy"]
