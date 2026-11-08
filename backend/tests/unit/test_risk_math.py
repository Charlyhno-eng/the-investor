import math
from datetime import date
from itertools import pairwise

import numpy as np
import pytest
from support import point

from investor.portfolio.volatility import (
    buckets,
    converted,
    coordinates,
    markowitz_frontier,
    risk_map,
)


def test_coordinates_known_mean_covariance_and_zero_risk():
    means = np.array([0.1, 0.2])
    covariance = np.array([[0.04, -0.04], [-0.04, 0.04]])
    a, mix = coordinates([[1, 0], [0.5, 0.5]], means, covariance)
    assert a == pytest.approx({"return": 10, "volatility": 20, "sharpe": 0.5})
    assert mix["return"] == pytest.approx(15)
    assert mix["volatility"] == 0
    assert mix["sharpe"] is None


def test_markowitz_matches_analytic_minimum_and_target_return_qp():
    means = np.array([0.08, 0.12, 0.20])
    covariance = np.diag([0.04, 0.09, 0.16])
    upper, lower = markowitz_frontier(means, covariance)
    inverse = np.linalg.inv(covariance)
    minimum_weights = inverse @ np.ones(3) / np.sum(inverse)
    minimum = coordinates(minimum_weights, means, covariance)[0]
    assert upper[0] == pytest.approx(minimum)
    assert lower[0] == pytest.approx(minimum)
    assert upper[-1]["return"] == pytest.approx(20)
    assert lower[-1]["return"] == pytest.approx(8)
    # Closed-form equality-constrained solution applies whenever its weights are positive.
    constraints = np.vstack([np.ones(3), means])
    for p in upper + lower:
        target = np.array([1, p["return"] / 100])
        w = (
            inverse
            @ constraints.T
            @ np.linalg.solve(constraints @ inverse @ constraints.T, target)
        )
        if np.min(w) >= 0:
            assert p["volatility"] == pytest.approx(
                coordinates(w, means, covariance)[0]["volatility"], abs=1e-5
            )
    assert all(
        a["return"] < b["return"] and a["volatility"] <= b["volatility"] + 1e-6
        for a, b in pairwise(upper)
    )


@pytest.mark.parametrize(
    "means,covariance",
    [
        (np.array([0.1, 0.2]), np.array([[0.04, 0], [0, 0.09]])),
        (np.array([-0.2, -0.1]), np.array([[0.04, 0.04], [0.04, 0.04]])),
        (np.array([0.1, 0.1]), np.array([[0.04, 0.04], [0.04, 0.04]])),
        (np.array([0.0, 0.0]), np.zeros((2, 2))),
    ],
)
def test_two_asset_frontier_degenerate_and_negative_returns(means, covariance):
    upper, lower = markowitz_frontier(means, covariance)
    assert all(
        math.isfinite(p["volatility"]) and math.isfinite(p["return"])
        for p in upper + lower
    )
    for p in upper + lower:
        if np.ptp(means) > 0:
            w = (p["return"] / 100 - means[1]) / (means[0] - means[1])
            assert -0.000001 <= w <= 1.000001
            assert p["volatility"] == pytest.approx(
                coordinates([w, 1 - w], means, covariance)[0]["volatility"], abs=1e-6
            )
        else:
            assert len(upper) == 1
            assert lower == []


def test_monthly_completed_months_and_selected_period():
    today = date.today()
    months = []
    for i in range(60):
        index = today.year * 12 + today.month - 60 + i
        months.append(f"{index // 12}-{index % 12 + 1:02d}-01")
    history = {
        d: 100 * math.exp(i * 0.002 + 0.01 * math.sin(i)) for i, d in enumerate(months)
    }
    assets = [{"id": "m", "name": "Monthly", "frequency": "monthly"}]
    full = risk_map(assets, [history], history, 3)
    zoom = risk_map(assets, [history], history, 1)
    assert full["frequency"] == "monthly"
    assert full["annualization"] == 12
    assert full["end"][:7] < today.isoformat()[:7]
    assert zoom["observations"] >= 12
    assert zoom["observations"] < full["observations"]
    assert point(zoom, "m")["return"] != point(full, "m")["return"]
    assert buckets({"2025-01-03": 2, "2025-01-20": 3}, True) == {"2025-01-31": 3}


def test_fx_uses_no_future_and_expires_after_seven_days():
    assert converted(
        {"2025-01-02": 100, "2025-01-10": 100}, None, {"2025-01-01": 2, "2025-01-11": 4}
    ) == {"2025-01-02": 50}
    assert converted({"2025-01-01": 100}, None, {"2025-01-02": 2}) == {}
