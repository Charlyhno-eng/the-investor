"""Fixed two-regime baseline: causal signal, literal switching, actual fees."""

import numpy as np
import pytest
from investor.analysis.basic import fit, simulate
from investor.analysis.model import forward_filter


def test_basic_hmm_has_exactly_two_states_and_recognizes_clear_heldout_drifts():
    rng = np.random.default_rng(81)
    returns = np.repeat([0.02, -0.02, 0.02, -0.02, 0.02, -0.02], 100)
    returns += rng.normal(0, 0.004, len(returns))
    model, mean, scale, _ = fit(returns[:400])
    assert model.n_components == 2
    assert model.means_.shape == (2, 1)
    bullish = int(np.argmax(model.means_[:, 0]))
    p = forward_filter(model, (returns[:, None] - mean) / scale)
    assert np.mean(p[420:500].argmax(axis=1) == bullish) > 0.95
    assert np.mean(p[520:600].argmax(axis=1) != bullish) > 0.95


def test_basic_switches_on_dominant_state_without_any_fee_veto():
    p = np.eye(2)[[1, 1, 0, 0, 1, 1, 1, 1]]
    changes = np.log1p([0.5, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
    free = simulate(changes, p, 1, 0)
    costed = simulate(changes, p, 1, 100)
    assert free[2:] == costed[2:]
    assert costed[3] == [1, 1, 0, 0, 1, 1, 0]
    assert costed[2] == [
        {"index": 0, "side": "buy"},
        {"index": 2, "side": "sell"},
        {"index": 4, "side": "buy"},
        {"index": 6, "side": "sell"},
    ]
    assert costed[0][0] == pytest.approx(-0.01)
    assert np.prod(1 + costed[0]) == pytest.approx(1.1**4 * 0.99**4)
    assert np.prod(1 + costed[1]) == pytest.approx(1.5 * 1.1**6 * 0.99**2)


def test_renumbering_states_does_not_change_positions_or_performance():
    p = np.array([[0.1, 0.9], [0.2, 0.8], [0.8, 0.2], [0.6, 0.4], [0.3, 0.7]])
    changes = np.array([0.01, -0.01, 0.05, -0.02])
    original = simulate(changes, p, 1, 50)
    renumbered = simulate(changes, p[:, ::-1], 0, 50)
    np.testing.assert_allclose(original[0], renumbered[0])
    assert original[2:] == renumbered[2:]
