import numpy as np
import spmo_archived as spmo


def test_spmo_execution_distribution_and_unchanged_target():
    # Initial signal above the average. At the next close only 49 units fit.
    signal = np.array([8.0, 9.0, 10.0, 12.0, 13.0, 14.0])
    close = np.array([90.0, 90.0, 100.0, 200.0, 180.0, 190.0])
    adjusted = np.array([90.0, 90.0, 100.0, 200.0, 190.0, 190.0 * 190 / 180])
    prices = np.column_stack((signal, signal, adjusted, close))
    metrics = spmo.evaluate(prices, 2, np.array([2, 3]), [(2, 0.75)], 1)
    initial_cash = 10000 - 49 * 200 * 1.0012
    trough = initial_cash + 49 * (180 + 10)
    end = initial_cash + 49 * (190 + 10)
    np.testing.assert_allclose(metrics[0], [end / 10000 - 1, trough / 10000 - 1])
    np.testing.assert_allclose(metrics[0], metrics[-1])


def test_optimizer_requires_both_mean_improvements():
    data = np.array([[[0.2, -0.3], [0.12, -0.1], [0.1, -0.2], [0.2, -0.22]]])
    assert spmo.select(data) == 1
    assert spmo.summarize(data)[0]["joint"] == 0


if __name__ == "__main__":
    test_spmo_execution_distribution_and_unchanged_target()
    test_optimizer_requires_both_mean_improvements()
