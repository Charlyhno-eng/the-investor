"""Causal filters, matured training labels, exact control and real budgets."""

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import study_sp500_deep_search as study  # noqa: E402


def sample(n=1800):
    dates = [date(2016, 1, 1) + timedelta(days=i) for i in range(n * 2)]
    days = [d.isoformat() for d in dates if d.weekday() < 5][:n]
    p = 100 * np.exp(np.cumsum(np.random.default_rng(1337).normal(0.0003, 0.013, n)))
    return days, p


def examples():
    seen, result = set(), []
    for c in study.grid():
        if c["family"] not in seen:
            seen.add(c["family"])
            result.append(c)
    return result


def test_every_tactical_parameterization_is_causal_and_bounded():
    _, p = sample(1000)
    cs = [c for c in study.grid() if c["family"] != "regression_joint"]
    full = study.weights(p, cs)
    prefix = study.weights(p[:777], cs)
    np.testing.assert_allclose(full[:, :777], prefix, rtol=0, atol=1e-12)
    assert np.all(np.isfinite(full))
    assert np.all(full >= 0) and np.all(full <= 1)
    changed = p.copy()
    changed[777:] *= 30
    altered = study.weights(changed, cs)
    np.testing.assert_allclose(full[:, :777], altered[:, :777], rtol=0, atol=1e-12)


@pytest.mark.parametrize("delay", [1, 2])
def test_executed_curves_do_not_change_with_future(delay):
    days, p = sample()
    cs = examples()
    full = study.evaluate(days, p, cs, [days[1400], days[-1]], delay=delay)
    prefix = study.evaluate(
        days[:1600], p[:1600], cs, [days[1400], days[1599]], delay=delay
    )
    # Metrics depend on horizon; compare an evaluation whose end excludes the
    # altered future while the supplied data still contain it.
    changed = p.copy()
    changed[1600:] *= 30
    same_end = study.evaluate(days, changed, cs, [days[1400], days[1599]], delay=delay)
    for a, b in zip(prefix, same_end, strict=True):
        for key in a:
            if a[key] is None:
                assert b[key] is None
            else:
                assert a[key] == pytest.approx(b[key], abs=1e-10)
    assert all(np.isfinite(m["cagr"]) for m in full)


@pytest.mark.parametrize("fee,delay", [(0.0012, 1), (0.0024, 1), (0.0012, 2)])
def test_v5_control_matches_existing_research_and_joint_same_rule(fee, delay):
    days, p = sample()
    c = dict(family="regression_joint", passive=0.35, regression=study.BASE)
    actual = study.evaluate(days, p, [c], [days[1400], days[-1]], fee=fee, delay=delay)
    reference = study.common.evaluate(
        days, p, [], [days[1400], days[-1]], fee=fee, delay=delay
    )
    for j in [0, 1]:
        for key in actual[j]:
            assert actual[j][key] == pytest.approx(reference[j][key], abs=1e-9)
    assert actual[2] == actual[1]


def test_disabling_research_trace_preserves_all_results():
    days, p = sample()
    engine = study.common.common.regression
    f = engine.previous.prepare(days, p)
    kw = dict(fee=0.0012, initial_capital=6500, keep_curve=True)
    verbose = engine.simulate(days, p, p, f, [study.BASE], [days[1400], days[-1]], **kw)
    compact = engine.simulate(
        days, p, p, f, [study.BASE], [days[1400], days[-1]], keep_trace=False, **kw
    )
    assert compact["trace"] is None
    assert verbose["trace"]
    assert compact["metrics"] == verbose["metrics"]
    assert compact["curve"] == verbose["curve"]


def test_channel_uses_prior_extrema_and_later_execution():
    days, p = sample(1000)
    p[:] = 100
    p[700] = 101
    p[701:] = 200
    c = dict(
        family="channel", entry=63, exit_window=21, floor=0.25, step=1, active=0.65
    )
    w = study.weights(p, [c])
    assert w[0, 700] == 1
    curve, fees = study.common.tactical(
        days, p, [c], [days[700], days[701]], target_weights=w
    )
    units = np.floor(3500 / (200 * 1.0012))
    cost = units * 200 * 0.0012
    assert fees[0] == pytest.approx(cost)
    np.testing.assert_allclose(curve[:, 0], [3500, 3500 - cost])


def test_online_experts_and_every_mixture_are_causal_and_bounded():
    import study_sp500_online_ensemble as online

    days, p = sample(1800)
    full = online.weights(p, online.grid(), days=days)
    prefix = online.weights(p[:1577], online.grid(), days=days[:1577])
    np.testing.assert_allclose(full[:, :1577], prefix, rtol=0, atol=1e-12)
    changed = p.copy()
    changed[1577:] *= 30
    altered = online.weights(changed, online.grid(), days=days)
    np.testing.assert_allclose(full[:, :1577], altered[:, :1577], rtol=0, atol=1e-12)
    assert np.all(np.isfinite(full))
    assert np.all(full >= 0.1) and np.all(full <= 1)


def test_online_expert_score_observes_next_close_execution_lag():
    import study_sp500_online_ensemble as online

    days, p = sample(1800)
    targets, log_returns = online.experts(days, p)
    i = 1600
    expected = targets[:, i - 2] * (p[i] / p[i - 1] - 1)
    expected -= 0.0012 * abs(targets[:, i - 1] - targets[:, i - 2])
    np.testing.assert_allclose(np.expm1(log_returns[:, i]), expected, atol=1e-15)


def test_online_mixture_executes_causally_with_independent_v4_budget(monkeypatch):
    import study_sp500_online_ensemble as online

    days, p = sample(1800)
    c = dict(online.grid()[2], active=0.65)
    monkeypatch.setattr(study, "weights", online.weights)
    expected = study.evaluate(days[:1700], p[:1700], [c], [days[1400], days[1699]])
    changed = p.copy()
    changed[1700:] *= 30
    actual = study.evaluate(days, changed, [c], [days[1400], days[1699]])
    for left, right in zip(expected, actual, strict=True):
        for key in left:
            assert left[key] == pytest.approx(right[key], abs=1e-10)
    assert actual[2]["cost_eur"] > 0
    assert actual[2]["total_return"] > -1
