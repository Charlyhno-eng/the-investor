import numpy as np
from investor.analysis.service import calculate
from research.hmm_benchmark import BASELINE, MODELS, RULES, evaluate, prepare


def test_benchmark_baseline_matches_application():
    from investor.analysis.schemas import AnalysisRequest

    rng = np.random.default_rng(21)
    values = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, 800)))
    dates = (
        np.arange("2020-01-01", "2022-03-11", dtype="datetime64[D]")
        .astype(str)
        .tolist()
    )
    assert len(dates) == len(values)
    data = {"values": values, "dates": dates}
    prepared = prepare(data, BASELINE[0], 499, 799)
    actual, _ = evaluate(prepared, BASELINE[1], 252)
    request = AnalysisRequest(
        train_start=dates[0],
        train_end=dates[499],
        test_start=dates[500],
        test_end=dates[-1],
        slippage_bps=5,
    )
    expected = calculate(
        {"category": "stock", "metric": "price", "frequency": "daily"},
        [{"date": d, "value": float(v)} for d, v in zip(dates, values)],
        request,
    )
    for key, value in expected["strategy_metrics"].items():
        if value is not None:
            np.testing.assert_allclose(actual[key], value, atol=1e-12)
    assert actual["orders"] == len(expected["trades"])

    # Alter all observations after a validation fold: its signals cannot change.
    prefix = prepare(data, "current", 399, 599)
    revised = {**data, "values": values.copy()}
    revised["values"][600:] *= 4
    repeated = prepare(revised, "current", 399, 599)
    np.testing.assert_array_equal(prefix["probabilities"], repeated["probabilities"])
    assert len(MODELS) * len(RULES) == 432
