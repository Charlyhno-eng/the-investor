import numpy as np

from investor.portfolio.research import shrunk_covariance
from investor.portfolio.reversion import reversion_orders
from investor.portfolio.validation import ValidationRequest


def test_oas_positive_and_permutation_equivariant():
    rng = np.random.default_rng(7)
    x = rng.normal(size=(600, 4))
    x[:, 1] = x[:, 0]
    cov = shrunk_covariance(x)
    assert np.linalg.eigvalsh(cov).min() > 0
    order = [2, 0, 3, 1]
    np.testing.assert_allclose(
        shrunk_covariance(x[:, order]), cov[np.ix_(order, order)]
    )


def test_entry_filter_preserves_exit():
    values, cash = reversion_orders(
        np.array([100.0, 0.0]), 100.0, [3.0, -3.0], 0, entry_allowed=[False, False]
    )
    np.testing.assert_allclose(values, [0, 0])
    assert cash == 200


def test_defaults_preserve_existing_rules():
    request = ValidationRequest(asset_ids=["a"])
    assert request.rebalance_tolerance == 0
    assert not request.regularize_covariance
    assert not request.reversion_quality_filter


def test_residual_diagnostics_ignore_future():
    from datetime import date, timedelta

    from investor.portfolio.research import residual_diagnostics

    dates = [date(2020, 1, 1) + timedelta(days=i) for i in range(1300)]
    rng = np.random.default_rng(8)
    prices = np.exp(rng.normal(0, 0.03, (1300, 2)) + np.arange(1300)[:, None] / 2000)
    before = residual_diagnostics(prices, dates, 1100)
    prices[1101:] *= 50
    after = residual_diagnostics(prices, dates, 1100)
    for key in before:
        np.testing.assert_array_equal(before[key], after[key])
