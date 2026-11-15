"""Sharpe selection ignores all former return/drawdown gates."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import study_sp500_sharpe as study  # noqa: E402


def test_selector_uses_only_sharpe_and_requires_defined_ratios():
    summary = dict(
        count=200,
        means=[
            {},
            {},
            dict(sharpe=1.2, cagr=0.25, max_drawdown=-0.01),
            dict(sharpe=1.4, cagr=0.02, max_drawdown=-0.50),
            dict(sharpe=9.0, cagr=0.50, max_drawdown=0),
        ],
        valid_counts=[{}, {}, dict(sharpe=200), dict(sharpe=200), dict(sharpe=199)],
    )
    assert study.winner(summary) == 1
    summary["means"][2]["sharpe"] = 1.4
    assert study.winner(summary) == 0  # Deterministic first-index tie.


def test_all_volatility_rules_are_causal_bounded_and_finite():
    p = 100 * np.exp(np.cumsum(np.random.default_rng(871).normal(0.0003, 0.012, 900)))
    cs = study.grid()
    assert len(cs) == 162
    full = study.weights(p, cs)
    prefix = study.weights(p[:701], cs)
    changed = p.copy()
    changed[701:] *= 15
    altered = study.weights(changed, cs)
    np.testing.assert_allclose(full[:, :701], prefix, rtol=0, atol=1e-12)
    np.testing.assert_allclose(full[:, :701], altered[:, :701], rtol=0, atol=1e-12)
    assert np.all(np.isfinite(full))
    assert np.all(full <= 1)
    for row, c in zip(full, cs, strict=True):
        assert np.all(row >= c["floor"])


def test_cash_dilution_does_not_create_frictionless_zero_rate_sharpe():
    r = np.random.default_rng(511).normal(0.0004, 0.01, 1000)
    curve = 10000 * np.r_[1, np.cumprod(1 + r)]
    scaled_curve = 10000 * np.r_[1, np.cumprod(1 + 0.2 * r)]
    metrics = study.engine.common.common.metrics(
        np.column_stack([curve, scaled_curve]), 4
    )
    np.testing.assert_allclose(metrics["sharpe"][0], metrics["sharpe"][1], atol=1e-12)
