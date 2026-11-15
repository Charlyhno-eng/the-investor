"""Independent accounting and time-direction checks for the regression search."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location(
    "sp500_study",
    Path(__file__).resolve().parents[3] / "scripts/study_sp500_regression.py",
)
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)


def sample():
    dates = np.arange("2014-01-01", "2022-01-01", dtype="datetime64[D]")
    days = [str(d) for d in dates if np.is_busday(d)]
    x = np.arange(len(days))
    raw = 100 * np.exp(x * 0.00025 + 0.09 * np.sin(x / 40) + 0.03 * np.cos(x / 7))
    return days, raw


def config(**kwargs):
    return dict(
        months=36,
        entry=1,
        exit=2,
        rule="level",
        filter="none",
        cadence=1,
        floor=0,
        entry_rule="below",
        **kwargs,
    )


def test_feature_prefix_invariance_and_production_ols():
    from datetime import date

    from investor.portfolio.reversion import regression_z

    days, prices = sample()
    f, _ = study.features(days, prices)
    cut = 1700
    shorter, _ = study.features(days[:cut], prices[:cut])
    for months in study.PROTOCOL["windows_months"]:
        np.testing.assert_allclose(
            f[months][0][:cut], shorter[months][0], equal_nan=True
        )
    expected = regression_z(
        prices[:, None], [date.fromisoformat(d) for d in days], cut - 1
    )[0]
    assert f[36][0][cut - 1] == pytest.approx(expected, abs=1e-11)


@pytest.mark.parametrize("whole", [False, True])
@pytest.mark.parametrize("start", ["2016-01-04", "2019-01-02", "2019-01-04"])
def test_sharpe_floor10_policy_matches_production_equity_and_fees(whole, start):
    from datetime import date

    from investor.portfolio.validation import ValidationRequest, validation_data

    days, prices = sample()
    f, ma = study.features(days, prices)
    history = dict(zip(days, prices, strict=True))
    period = [start, "2021-12-31"]
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    from study_sp500_three_years import BASE, simulate

    result = simulate(
        days,
        prices,
        prices,
        (f, {m: ma for m in [50, 100, 200]}, np.zeros(len(days))),
        [{**BASE, "warm": True, "floor": 0.10}],
        period,
        whole=whole,
        keep_curve=True,
        initial_capital=10000,
    )
    combined_curve = np.array(result["curve"])[:, 0]
    asset = dict(id="yf-psp5.pa", name="PSP5", category="etf", frequency="daily")
    production = validation_data(
        [asset],
        [history],
        history,
        ValidationRequest(
            asset_ids=["yf-psp5.pa"],
            mode="etf_switch",
            fee_rate=0.005,  # Fixed research protocol, independent of app defaults.
            whole_shares=whole,
            start_date=date.fromisoformat(period[0]),
            end_date=date.fromisoformat(period[1]),
        ),
        execution_histories=[history, history],
    )
    assert production["status"] == "ready"
    np.testing.assert_allclose(
        combined_curve,
        [p["strategy"] * 100 for p in production["equity"]],
        atol=1e-7,
    )
    assert result["metrics"][0]["fees"] == pytest.approx(
        production["metrics"]["strategy"]["cost_eur"], abs=1e-7
    )


def test_continuation_preserves_every_equity_point_and_cash():
    days, raw = sample()
    f, ma = study.features(days, raw)
    candidates = [
        config(),
        {**config(), "rule": "trail_1", "floor": 0.25, "cadence": 5},
    ]
    full = study.simulate(
        days, raw, f, ma, candidates, ["2019-01-02", "2021-12-31"], keep_curve=True
    )
    first = study.simulate(
        days, raw, f, ma, candidates, ["2019-01-02", "2020-12-31"], keep_curve=True
    )
    second = study.simulate(
        days,
        raw,
        f,
        ma,
        candidates,
        ["2021-01-01", "2021-12-31"],
        initial=first["terminal_state"],
        keep_curve=True,
    )
    joined = first["curve"] + second["curve"][1:]
    np.testing.assert_allclose(full["curve"], joined, atol=1e-9)
    assert full["terminal_state"] == second["terminal_state"]
    for i in range(len(candidates)):
        assert full["candidates"][i]["fees"] == pytest.approx(
            first["candidates"][i]["fees"] + second["candidates"][i]["fees"]
        )


def test_next_close_execution_and_integer_fee_ledger():
    days = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]
    raw = np.array([100.0, 110, 120, 130, 140])
    scores = np.array([0, 3, 0, 3, 0.0])
    f = {m: (scores, np.ones(5)) for m in study.PROTOCOL["windows_months"]}
    result = study.simulate(days, raw, f, raw, [config()], days[::4], keep_curve=True)
    cash = 10000.0
    units = 0
    expected = [cash]
    total_fee = 0
    for i in range(1, 5):
        buy = scores[i - 1] < 1
        target = int(np.floor((cash + units * raw[i]) / (raw[i] * 1.005))) if buy else 0
        fee = abs(target - units) * raw[i] * 0.005
        cash -= (target - units) * raw[i] + fee
        units = target
        total_fee += fee
        expected.append(cash + units * raw[i])
    np.testing.assert_allclose(np.array(result["curve"])[:, 0], expected)
    assert result["candidates"][0]["fees"] == pytest.approx(total_fee)


def test_fractional_sleeves_scale_with_actual_assigned_capital():
    days, prices = sample()
    f, ma = study.features(days, prices)
    kwargs = dict(whole=False, keep_curve=True)
    full = study.simulate(
        days, prices, f, ma, [config()], ["2019-01-02", "2021-12-31"], **kwargs
    )
    quarter = study.simulate(
        days,
        prices,
        f,
        ma,
        [config()],
        ["2019-01-02", "2021-12-31"],
        initial_capital=2500,
        **kwargs,
    )
    np.testing.assert_allclose(np.array(quarter["curve"]) * 4, full["curve"], atol=1e-8)
    assert quarter["candidates"][0]["cagr"] == pytest.approx(
        full["candidates"][0]["cagr"]
    )
    assert quarter["candidates"][0]["fees"] * 4 == pytest.approx(
        full["candidates"][0]["fees"]
    )


def test_mixed_drawdown_is_calculated_on_combined_daily_values():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    from study_sp500_compromise_blends import combine

    days = ["2020-01-01", "2020-01-02", "2020-01-03"]
    a = dict(curve=[[5000, 0], [4000, 0], [5000, 0]], candidates=[dict(fees=10)])
    b = dict(curve=[[5000, 0], [6000, 0], [5000, 0]], candidates=[dict(fees=20)])
    metrics = combine(a, b, days, [days[0], days[-1]])[0]
    assert metrics["max_drawdown"] == 0
    assert metrics["cagr"] == 0
    assert metrics["fees"] == 30
