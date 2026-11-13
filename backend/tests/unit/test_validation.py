"""Independent cash/share ledger and causality checks for walk-forward validation."""

from datetime import date, timedelta

import numpy as np
import pytest
from fastapi import HTTPException

from investor.portfolio import validation as engine
from investor.portfolio.validation import ValidationRequest, rebalance, validation_data


def sample():
    start = date(2018, 1, 2)
    days = [
        (start + timedelta(days=i)).isoformat()
        for i in range(6 * 366)
        if (start + timedelta(days=i)).weekday() < 5
    ]
    t = np.arange(len(days))
    prices = [
        100 * np.exp(0.0004 * t + 0.05 * np.sin(t / 15) ** 3),
        100 * np.exp(0.0001 * t + 0.03 * np.cos(t / 11) ** 3),
    ]
    histories = [dict(zip(days, p, strict=True)) for p in prices]
    benchmark = dict(
        zip(days, 100 * np.exp(0.0002 * t + 0.04 * np.sin(t / 20)), strict=True)
    )
    assets = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    return assets, histories, benchmark


def run(data, **kwargs):
    return validation_data(*data, ValidationRequest(asset_ids=["a", "b"], **kwargs))


def test_future_prices_cannot_change_past_decisions_or_equity(monkeypatch):
    data = sample()
    calls = []
    real = engine.optimize_weights

    def spy(returns, current, mode, **kwargs):
        calls.append((returns.copy(), current.copy()))
        return real(returns, current, mode, **kwargs)

    monkeypatch.setattr(engine, "optimize_weights", spy)
    original = run(data)
    baseline_calls = calls.copy()
    calls.clear()
    # Include a change at the EXECUTION close: target must remain unchanged.
    boundary = original["folds"][3]["execution"]
    changed = [
        {d: v * (2 if d >= boundary else 1) for d, v in h.items()} for h in data[1]
    ]
    updated = run((data[0], changed, data[2]))
    assert original["status"] == updated["status"] == "ready"
    for before, after in zip(baseline_calls[:4], calls[:4], strict=True):
        np.testing.assert_allclose(before[0], after[0])
        np.testing.assert_allclose(before[1], after[1])
    assert [f["weights"] for f in original["folds"][:4]] == [
        f["weights"] for f in updated["folds"][:4]
    ]
    assert [p for p in original["equity"] if p["time"] < boundary] == [
        p for p in updated["equity"] if p["time"] < boundary
    ]
    for fold in original["folds"]:
        assert fold["train_end"] == fold["signal"] < fold["execution"]
        assert fold["observations"] >= 500
        assert (
            1090
            <= (
                date.fromisoformat(fold["signal"])
                - date.fromisoformat(fold["train_start"])
            ).days
            <= 1097
        )


def test_independent_share_ledger_reproduces_all_curves_and_quarters(monkeypatch):
    data = sample()
    target = np.array([0.7, 0.3])
    monkeypatch.setattr(engine, "optimize_weights", lambda *args, **kwargs: target)
    fee = 0.01
    result = run(data, fee_rate=fee)
    events = {f["execution"]: f for f in result["folds"]}
    # Independently solve orders using share quantities and an accounting identity.
    shares = {
        key: np.zeros(1 if key == "benchmark" else 2) for key in result["metrics"]
    }
    cash = dict.fromkeys(shares, 100.0)
    accumulated_cost = dict.fromkeys(shares, 0.0)
    quarter_starts = {}
    prior = None
    for p in result["equity"]:
        day = p["time"]
        for key in shares:
            price = (
                np.array([data[2][day]])
                if key == "benchmark"
                else np.array([h[day] for h in data[1]])
            )
            wealth = float(shares[key] @ price + cash[key])
            if day in events:
                if prior:
                    assert prior["returns"][key] == pytest.approx(
                        wealth / quarter_starts[key] - 1
                    )
                quarter_starts[key] = wealth
                if not prior or key in ("strategy", "equal"):
                    weights = (
                        target
                        if key == "strategy"
                        else np.array([1.0])
                        if key == "benchmark"
                        else np.array([0.5, 0.5])
                    )
                    # Fixed point in fees, independent of engine bisection.
                    cost = 0.0
                    for _ in range(100):
                        orders = (wealth - cost) * weights / price - shares[key]
                        cost = float(fee * np.abs(orders * price).sum())
                    shares[key] = (wealth - cost) * weights / price
                    cash[key] = 0.0
                    accumulated_cost[key] += cost
            assert p[key] == pytest.approx(shares[key] @ price + cash[key])
        if day in events:
            prior = events[day]
    for key in shares:
        assert result["metrics"][key]["cost_base_100"] == pytest.approx(
            accumulated_cost[key]
        )
        assert result["metrics"][key]["total_return"] == pytest.approx(
            result["equity"][-1][key] / 100 - 1
        )
    assert result["metrics"]["buy_hold"]["annual_turnover"] == 0
    assert result["metrics"]["benchmark"]["annual_turnover"] == 0
    assert result["equity"][0]["strategy"] == 100
    assert result["completed_quarters"] == len(result["folds"]) - 1
    assert not result["folds"][-1]["complete"]
    # A short test has no complete quarter: rates and worst quarter are undefined.
    last = result["folds"][0]["execution"]
    end = (date.fromisoformat(last) + timedelta(days=20)).isoformat()
    truncated = (
        data[0],
        [{d: v for d, v in h.items() if d <= end} for h in data[1]],
        {d: v for d, v in data[2].items() if d <= end},
    )
    short = run(truncated)
    assert short["completed_quarters"] == 0
    assert short["metrics"]["strategy"]["worst_quarter"] is None


def test_rebalance_self_finances_round_trip_and_noop():
    values, cash, cost, turn = rebalance(
        np.array([0.0, 0.0]), 100, np.array([1.0, 0.0]), 0.01
    )
    assert values[0] == pytest.approx(100 / 1.01)
    assert values.sum() + cash + cost == pytest.approx(100)
    assert turn == pytest.approx(1 / 1.01)
    noop = rebalance(values, cash, np.array([1.0, 0.0]), 0.01)
    assert noop[2] == pytest.approx(0, abs=1e-12)
    sell = rebalance(values, cash, np.array([0.0, 0.0]), 0.01)
    assert sell[1] == pytest.approx(values.sum() * 0.99)
    assert sell[2] == pytest.approx(values.sum() * 0.01)


@pytest.mark.parametrize("mode", ["volatility", "correlation"])
def test_existing_optimizers_run_only_on_training(mode):
    data = sample()
    result = run(data, mode=mode, years=1, fee_rate=0)
    assert result["status"] == "ready", result
    for fold in result["folds"]:
        assert sum(fold["weights"]) == pytest.approx(1)
        assert min(fold["weights"]) >= 0


def test_failure_never_silently_skips_bad_quarter(monkeypatch):
    def fail(*args, **kwargs):
        raise HTTPException(422, "Cible inaccessible")

    monkeypatch.setattr(engine, "optimize_weights", fail)
    result = run(sample())
    assert result["status"] == "insufficient"
    assert "Cible inaccessible" in result["message"]
    assert "equity" not in result


def test_missing_short_and_discontinuous_histories():
    assets, histories, benchmark = sample()
    missing = run((assets, [histories[0], {}], benchmark))
    assert missing["status"] == "ready"
    assert any("B : aucun cours" in n for n in missing["notices"])
    short = [{d: v for d, v in h.items() if d < "2020-01-01"} for h in histories]
    assert run((assets, short, benchmark))["status"] == "insufficient"
    gap = [
        {d: v for d, v in h.items() if not "2021-04-01" <= d <= "2021-05-01"}
        for h in histories
    ]
    assert run((assets, gap, benchmark))["status"] == "insufficient"
    # A gap older than the first learning window must not block a recent test.
    old_gap = [
        {d: v for d, v in h.items() if not "2018-04-01" <= d <= "2018-05-01"}
        for h in histories
    ]
    assert run((assets, old_gap, benchmark), years=1)["status"] == "ready"


@pytest.mark.parametrize(
    "mode,settings",
    [
        ("volatility", {}),
        ("correlation", {}),
        ("mean_reversion", {}),
        ("mean_reversion", {"reversion_entry_z": 1.2, "reversion_exit_z": 0.7}),
        ("mean_reversion", {"reversion_exit_mode": "trailing_z"}),
    ],
)
def test_journal_reconciles_every_daily_value_final_positions_and_beta(mode, settings):
    data = sample()
    capital, fee = 12345, 0.008
    result = run(data, mode=mode, initial_capital=capital, fee_rate=fee, **settings)
    assert result["status"] == "ready"
    trades = result["transactions"]
    assert trades
    cash, shares = capital, dict.fromkeys(("a", "b"), 0.0)
    basis = dict.fromkeys(("a", "b"), 0.0)
    index = {a["id"]: j for j, a in enumerate(data[0])}
    exposed_days = 0.0
    prior_day = None
    for point in result["equity"]:
        day = date.fromisoformat(point["time"])
        if (
            prior_day is not None
            and prior_day.isoformat() >= result["folds"][0]["execution"]
        ):
            invested = sum(
                q * data[1][index[a]][prior_day.isoformat()] for a, q in shares.items()
            )
            exposed_days += (day - prior_day).days * invested / (invested + cash)
        prior_day = day
        for trade in (t for t in trades if t["execution"] == point["time"]):
            assert trade["signal"] < trade["execution"]
            assert trade["fee"] == pytest.approx(trade["amount"] * fee)
            assert trade["quantity"] * trade["price"] == pytest.approx(trade["amount"])
            direction = 1 if trade["side"] == "buy" else -1
            aid = trade["asset_id"]
            if direction == 1:
                basis[aid] += trade["amount"] + trade["fee"]
                assert trade["profit_return"] is None
            else:
                sold_basis = basis[aid] * trade["quantity"] / shares[aid]
                assert trade["profit_return"] == pytest.approx(
                    (trade["amount"] - trade["fee"]) / sold_basis - 1
                )
                basis[aid] -= sold_basis
            shares[trade["asset_id"]] += direction * trade["quantity"]
            assert trade["cash_before"] == pytest.approx(cash, abs=1e-7)
            cash -= direction * trade["amount"] + trade["fee"]
            assert trade["cash_after"] == pytest.approx(cash, abs=1e-7)
            assert cash >= -1e-7
            assert shares[trade["asset_id"]] >= -1e-7
            if mode == "mean_reversion":
                if direction == 1:
                    assert trade["z"] <= -settings.get("reversion_entry_z", 1.4)
                    assert trade["amount"] + trade["fee"] <= (
                        0.25 * trade["portfolio_before"] + 1e-7
                    )
                elif trade["reason"] == "threshold":
                    assert trade["z"] >= settings.get("reversion_exit_z", 1.4)
                elif trade["reason"] == "trailing_z":
                    assert settings.get("reversion_exit_mode") == "trailing_z"
                else:
                    assert trade["reason"] == "funding"
                    assert trade["z"] >= 0
        wealth = cash + sum(
            q * data[1][index[a]][point["time"]] for a, q in shares.items()
        )
        assert wealth == pytest.approx(point["strategy"] * capital / 100)
    assert result["metrics"]["strategy"]["cost_eur"] == pytest.approx(
        sum(t["fee"] for t in trades)
    )
    assert result["metrics"]["strategy"]["market_exposure"] == pytest.approx(
        exposed_days
        / (
            date.fromisoformat(result["end"])
            - date.fromisoformat(result["folds"][0]["execution"])
        ).days
    )
    for metrics in result["metrics"].values():
        assert 0 <= metrics["market_exposure"] <= 1
        assert metrics["cost_eur"] == pytest.approx(
            metrics["cost_base_100"] * capital / 100
        )
    final = result["final_portfolio"]
    assert final["cash"] == pytest.approx(cash, abs=1e-7)
    assert final["total"] == pytest.approx(
        cash + sum(p["value"] for p in final["positions"])
    )
    for p in final["positions"]:
        assert p["quantity"] == pytest.approx(shares[p["id"]])
    curves = np.array(
        [[p[k] for k in ("strategy", "benchmark")] for p in result["equity"]]
    )
    changes = curves[1:] / curves[:-1] - 1
    beta = np.cov(changes.T, ddof=1)[0, 1] / np.var(changes[:, 1], ddof=1)
    assert result["metrics"]["strategy"]["beta"] == pytest.approx(beta)
    if mode == "mean_reversion":
        # Daily decisions include trades away from quarterly allocation dates.
        assert any(
            t["execution"] not in {f["execution"] for f in result["folds"]}
            for t in trades
        )
        assert {t["side"] for t in trades} == {"buy", "sell"}


@pytest.mark.parametrize("mode", ["volatility", "correlation", "mean_reversion"])
def test_reversion_past_only_regression_and_next_session_execution(mode):
    from investor.portfolio.reversion import regression_z

    data = sample()
    baseline = run(data, mode=mode)
    boundary = baseline["transactions"][5]["execution"]
    changed = [
        {d: v * (3 if d >= boundary else 1) for d, v in h.items()} for h in data[1]
    ]
    updated = run((data[0], changed, data[2]), mode=mode)
    assert [p for p in baseline["equity"] if p["time"] < boundary] == [
        p for p in updated["equity"] if p["time"] < boundary
    ]
    assert [
        (t["asset_id"], t["side"], t["z"])
        for t in baseline["transactions"]
        if t["execution"] == boundary
    ] == [
        (t["asset_id"], t["side"], t["z"])
        for t in updated["transactions"]
        if t["execution"] == boundary
    ]
    days = sorted(data[1][0])
    dates = [date.fromisoformat(d) for d in days]
    prices = np.array([[h[d] for h in data[1]] for d in days])
    for t in baseline["transactions"][:10]:
        i = days.index(t["signal"])
        assert t["execution"] == days[i + 1]
        j = 0 if t["asset_id"] == "a" else 1
        # Independent polynomial fit on the actual calendar lookback.
        lower = engine.months_before(dates[i], 36)
        chosen = [k for k in range(i + 1) if dates[k] >= lower]
        x = np.array([(dates[k] - dates[chosen[0]]).days for k in chosen])
        y = np.log(prices[chosen, j])
        residuals = y - np.polyval(np.polyfit(x, y, 1), x)
        expected = residuals[-1] / np.sqrt((residuals**2).sum() / (len(y) - 2))
        assert t["z"] == pytest.approx(expected)
    # Perfect exponential trends have no usable residual dispersion.
    trend = np.exp(np.array([(d - dates[0]).days for d in dates]) * 0.001)[:, None]
    assert regression_z(trend, dates, 1000) == [None]
    # Native signal history, supplied separately, controls entry regardless of FX.
    flat = [{d: 100.0 for d in days} for _ in data[0]]
    result = validation_data(
        *data,
        ValidationRequest(asset_ids=["a", "b"], mode="mean_reversion"),
        signal_histories=flat,
    )
    assert result["transactions"] == []
    assert result["final_portfolio"]["cash"] == 10000


def test_reversion_new_thresholds_are_inclusive_and_close_only():
    from investor.portfolio.reversion import reversion_orders

    held, cash = reversion_orders(np.zeros(2), 10000.0, [-1.399, -1.4], 0.005)
    assert held[0] == 0
    assert held[1] == pytest.approx(2500 / 1.005)
    assert cash == pytest.approx(7500)
    unchanged, _ = reversion_orders(held, cash, [None, 1.399], 0.005)
    np.testing.assert_allclose(unchanged, held)
    sold, proceeds = reversion_orders(held, cash, [None, 1.4], 0.005)
    assert sold[1] == 0
    assert proceeds == pytest.approx(cash + held[1] * 0.995)
    jumped, _ = reversion_orders(held, cash, [None, 1.93], 0.005)
    assert jumped[1] == 0
    many, cash = reversion_orders(np.zeros(10), 10000.0, [-1.4] * 10, 0.005)
    np.testing.assert_allclose(many, np.full(10, 10000 / 10 / 1.005))
    assert cash == pytest.approx(0, abs=1e-8)


def test_configurable_entry_exit_and_funding_thresholds_are_inclusive():
    from investor.portfolio.reversion import reversion_orders

    values, cash = reversion_orders(
        np.zeros(2), 10000.0, [-1.999, -2.0], 0.005, entry_z=2.0, exit_z=0.7
    )
    assert values[0] == 0 and values[1] > 0
    held, _ = reversion_orders(values, cash, [None, 0.699], 0.005, exit_z=0.7)
    np.testing.assert_array_equal(held, values)
    sold, proceeds = reversion_orders(values, cash, [None, 0.7], 0.005, exit_z=0.7)
    assert sold[1] == 0
    assert proceeds == pytest.approx(cash + values[1] * 0.995)
    before = np.array([10000.0, 0.0])
    held, _ = reversion_orders(before, 0.0, [0.499, -2.0], 0.005, funding_min_z=0.5)
    np.testing.assert_array_equal(held, before)
    bought, _ = reversion_orders(before, 0.0, [0.5, -2.0], 0.005, funding_min_z=0.5)
    assert bought[1] > 0


def test_trailing_z_arms_then_waits_for_drawback_and_resets_closed_positions():
    from investor.portfolio.reversion import reversion_exits

    peaks = np.full(2, np.nan)
    values = np.array([100.0, 0.0])
    for score in (1.0, 1.4, 1.8, 2.0, None, 1.6):
        flags = reversion_exits(values, [score, 9.0], peaks, mode="trailing_z")
        assert not np.any(flags)
    assert peaks[0] == 2.0
    flags = reversion_exits(values, [1.5, None], peaks, mode="trailing_z")
    assert flags[0]
    reversion_exits(np.zeros(2), [None, None], peaks, mode="trailing_z")
    assert np.all(np.isnan(peaks))
    # A new position cannot inherit a previous round trip's armed peak.
    assert not np.any(reversion_exits(values, [1.0, None], peaks, mode="trailing_z"))


def test_explicit_study_dates_exclude_future_prices_and_keep_past_training():
    data = sample()
    settings = dict(
        mode="mean_reversion",
        reversion_exit_mode="trailing_z",
        start_date="2021-06-01",
        end_date="2022-12-30",
    )
    original = run(data, **settings)
    changed = [
        {d: v * (7 if d > "2022-12-30" else 1) for d, v in h.items()} for h in data[1]
    ]
    updated = run((data[0], changed, data[2]), **settings)
    assert original == updated
    assert original["start"] == "2021-06-01"
    assert original["end"] == "2022-12-30"
    assert original["folds"][0]["train_start"] <= "2018-06-08"
    assert all(t["execution"] <= "2022-12-30" for t in original["transactions"])


@pytest.mark.parametrize("whole", [False, True])
def test_reversion_first_three_entries_keep_cash_and_do_not_sell_negative_positions(
    whole,
):
    from investor.portfolio.reversion import reversion_orders

    values, cash = np.zeros(3), 10000.0
    prices = np.array([91.25, 243.4, 664.9])
    signals = [
        [-1.46, None, None],
        [-1.49, -1.55, None],
        [-1.48, -0.58, -1.47],
    ]
    for j, scores in enumerate(signals):
        before = values.copy()
        capital = values.sum() + cash
        values, cash = reversion_orders(
            values, cash, scores, 0.005, whole=[whole] * 3, unit_prices=prices
        )
        np.testing.assert_allclose(values[:j], before[:j])
        assert 0 < values[j] * 1.005 <= 0.25 * capital + 1e-8
        assert cash > 0
        if whole:
            assert values[j] / prices[j] == pytest.approx(round(values[j] / prices[j]))


@pytest.mark.parametrize("lower_score", [-0.5, 0.5])
def test_reversion_finances_entries_without_cash_and_preserves_passive_holdings(
    lower_score,
):
    from investor.portfolio.reversion import reversion_orders

    previous = np.array([6000.0, 3000.0, 0.0, 5000.0])
    result, cash = reversion_orders(
        previous,
        0.0,
        [lower_score, 0.8, -1.4, -3.0],
        0.005,
        active=[True, True, True, False],
    )
    # Fund only the meaningful minimum, from just the highest-z holding.
    assert result[1] == pytest.approx(3000 - 1400 / 0.995)
    assert result[2] == pytest.approx(1400 / 1.005)
    assert result[0] == previous[0]
    assert result[3] == previous[3]
    assert cash >= 0
    assert result.sum() + cash + 0.005 * abs(result - previous).sum() == pytest.approx(
        previous.sum()
    )


@pytest.mark.parametrize("scores", [[-0.5, 0.8, -1.8], [None, 0.8, -1.8]])
def test_reversion_only_reduces_highest_z_holding_when_it_suffices(scores):
    from investor.portfolio.reversion import reversion_orders

    previous = np.array([6000.0, 4000.0, 0.0])
    result, cash = reversion_orders(previous, 0.0, scores, 0.005)
    assert result[0] == previous[0]
    assert result[2] == pytest.approx(1000 / 1.005)
    assert result[1] == pytest.approx(4000 - result[2] * 1.005 / 0.995)
    assert cash == pytest.approx(0, abs=1e-8)


def test_reversion_prefers_smaller_cash_only_entry_to_financing_sale():
    from investor.portfolio.reversion import reversion_orders

    previous = np.array([6000.0, 0.0])
    funded, cash = reversion_orders(previous, 1000.0, [0.8, -1.5], 0.005)
    assert funded[1] == pytest.approx(1000 / 1.005)
    assert funded[0] == previous[0]
    assert cash == pytest.approx(0, abs=1e-8)
    # Enough cash means no financing sale, regardless of the donor's z-score.
    funded, cash = reversion_orders(previous, 7000.0, [0.8, -1.5], 0.005)
    assert funded[0] == previous[0]
    assert funded[1] == pytest.approx(3250 / 1.005)
    assert cash == pytest.approx(7000 - 3250)


@pytest.mark.parametrize("score", [-1.6, -0.01, None])
def test_reversion_does_not_fund_from_depressed_or_unknown_holdings(score):
    from investor.portfolio.reversion import reversion_orders

    previous = np.array([10000.0, 0.0])
    result, cash = reversion_orders(previous, 0.0, [score, -1.8], 0.005)
    np.testing.assert_allclose(result, previous)
    assert cash == 0


def test_reversion_does_not_top_up_an_affordable_whole_order_by_selling():
    from investor.portfolio.reversion import reversion_orders

    result, cash = reversion_orders(
        np.array([6000.0, 0.0]),
        1000.0,
        [0.8, -1.5],
        0.005,
        whole=[True, True],
        unit_prices=np.array([100.0, 100.0]),
    )
    np.testing.assert_allclose(result, [6000, 900])
    assert cash == pytest.approx(1000 - 900 * 1.005)


@pytest.mark.parametrize("whole", [False, True])
def test_reversion_funds_meaningful_entry_instead_of_spending_last_80_euros(whole):
    from investor.portfolio.reversion import reversion_orders

    previous = np.array([9920.0, 0.0])
    result, cash = reversion_orders(
        previous,
        80.0,
        [0.6, -1.5],
        0.005,
        whole=[whole, whole],
        unit_prices=np.array([80.0, 80.0]),
    )
    # The 10% budget includes purchase fees. Whole lots round the minimum up.
    expected = 1040.0 if whole else 1000 / 1.005
    assert result[1] == pytest.approx(expected)
    assert result[0] < previous[0]
    assert result[1] * 1.005 >= 1000 - 1e-8
    assert result.sum() + cash + abs(result - previous).sum() * 0.005 == pytest.approx(
        10000
    )
    assert cash >= 0


@pytest.mark.parametrize("score", [-0.01, None])
def test_reversion_keeps_dust_cash_instead_of_opening_an_unfundable_small_position(
    score,
):
    from investor.portfolio.reversion import reversion_orders

    previous = np.array([9920.0, 0.0])
    result, cash = reversion_orders(previous, 80.0, [score, -1.8], 0.005)
    np.testing.assert_allclose(result, previous)
    assert cash == 80


def test_reversion_prioritizes_one_meaningful_entry_over_multiple_tiny_entries():
    from investor.portfolio.reversion import reversion_orders

    previous = np.array([8900.0, 0.0, 0.0])
    result, cash = reversion_orders(previous, 1100.0, [-0.5, -1.5, -2.0], 0.005)
    assert result[0] == previous[0]
    assert result[1] == 0
    assert result[2] == pytest.approx(1100 / 1.005)
    assert cash == pytest.approx(0, abs=1e-8)


def test_reversion_floor_adapts_to_a_large_universe_and_preserves_passive_budget():
    from investor.portfolio.reversion import reversion_orders

    previous = np.zeros(21)
    previous[-1] = 5000
    previous[0] = 4920
    result, cash = reversion_orders(
        previous,
        80.0,
        [0.6, -1.5, *([None] * 19)],
        0.005,
        active=[True] * 20 + [False],
        portfolio_value=10000.0,
    )
    assert result[1] == pytest.approx(500 / 1.005)
    assert result[-1] == 5000
    assert result[0] == pytest.approx(4920 - 420 / 0.995)
    assert cash == pytest.approx(0, abs=1e-8)


def test_reversion_does_not_sell_second_donor_to_afford_one_whole_share():
    from investor.portfolio.reversion import reversion_orders

    previous = np.array([900.0, 100.0, 0.0])
    result, cash = reversion_orders(
        previous,
        0.0,
        [0.5, 1.3, -1.8],
        0.005,
        whole=[True] * 3,
        unit_prices=np.array([100.0, 100.0, 200.0]),
    )
    np.testing.assert_allclose(result, previous)
    assert cash == 0


@pytest.mark.parametrize("whole", [False, True])
def test_reversion_four_entries_need_no_financing_even_when_nav_rises(whole):
    from investor.portfolio.reversion import reversion_orders

    values, cash = np.zeros(4), 10000.0
    for j in range(4):
        # Earlier purchases appreciate; new targets grow, but cash does not.
        values *= 1.1
        before = values.copy()
        capital = values.sum() + cash
        scores = [0.5 if k < j else -1.5 if k == j else None for k in range(4)]
        values, cash = reversion_orders(
            values,
            cash,
            scores,
            0.005,
            whole=[whole] * 4,
            unit_prices=np.full(4, 100.0),
        )
        np.testing.assert_allclose(values[:j], before[:j])
        assert 0 < values[j] * 1.005 <= 0.25 * capital + 1e-8
        assert cash >= 0


def test_reversion_whole_funding_uses_highest_z_and_only_needed_units():
    from investor.portfolio.reversion import reversion_orders

    previous = np.array([6000.0, 4000.0, 0.0])
    result, cash = reversion_orders(
        previous,
        0.0,
        [-0.5, 0.8, -1.8],
        0.005,
        whole=[True, True, True],
        unit_prices=np.array([100.0, 200.0, 300.0]),
    )
    # The meaningful minimum rounds up to 4 units; sell 7 highest-z units.
    np.testing.assert_allclose(result, [6000, 2600, 1200])
    assert cash == pytest.approx(1400 * 0.995 - 1200 * 1.005)


def test_reversion_whole_orders_can_fund_one_expensive_share_or_skip_impossible_entries():
    from investor.portfolio.reversion import reversion_orders

    # Funding may fully close a one-share position; both trades remain integral.
    before = np.array([3000.0, 0.0])
    prices = np.array([3000.0, 700.0])
    held, cash = reversion_orders(
        before, 0.0, [0.5, -1.4], 0.005, whole=[True, True], unit_prices=prices
    )
    np.testing.assert_allclose(held, [0.0, 700.0])
    assert cash == pytest.approx(3000 - 700 - 0.005 * 3700)
    # If the minimum order is unaffordable, do not sell anything to no purpose.
    untouched, cash = reversion_orders(
        before,
        0.0,
        [0.5, -1.4],
        0.005,
        whole=[True, True],
        unit_prices=np.array([3000.0, 1100.0]),
    )
    np.testing.assert_allclose(untouched, before)
    assert cash == 0
    # Simultaneous unaffordable signals prioritize the strongest deviation.
    held, cash = reversion_orders(
        np.array([600.0, 400.0, 0.0, 0.0]),
        0.0,
        [-0.5, 0.8, -1.6, -2.0],
        0.005,
        whole=[True] * 4,
        unit_prices=np.array([100.0, 100.0, 210.0, 210.0]),
    )
    np.testing.assert_allclose(held, [600.0, 100.0, 0.0, 210.0])
    assert cash == pytest.approx(300 * 0.995 - 210 * 1.005)


def test_exposure_measures_capital_and_excludes_initial_execution_wait(monkeypatch):
    # Selecting half the universe still invests the full portfolio.
    monkeypatch.setattr(
        engine, "optimize_weights", lambda *a, **k: np.array([1.0, 0.0])
    )
    result = run(sample())
    for metrics in result["metrics"].values():
        assert metrics["market_exposure"] == pytest.approx(1)
    assert result["final_portfolio"]["cash"] == pytest.approx(0, abs=1e-8)


@pytest.mark.parametrize(
    "mode,second_category",
    [
        ("volatility", "etf"),
        ("correlation", "crypto"),
        ("mean_reversion", "stock"),
        ("mean_reversion", "crypto"),
    ],
)
def test_whole_share_ledger_and_cash_dividends(mode, second_category):
    assets, histories, benchmark = sample()
    assets = [
        {**assets[0], "category": "stock"},
        {**assets[1], "category": second_category},
    ]
    raw = [{d: v * 3.217 for d, v in h.items()} for h in histories]
    capital, fee = 10000, 0.005
    payout_day = sorted(benchmark)[1200]
    payouts = [{payout_day: 2.0}, {payout_day: 3.0}, {}]
    result = validation_data(
        assets,
        histories,
        benchmark,
        ValidationRequest(
            asset_ids=["a", "b"],
            mode=mode,
            initial_capital=capital,
            fee_rate=fee,
            whole_shares=True,
        ),
        execution_histories=[*raw, {}],
        cash_distributions=payouts,
    )
    assert result["status"] == "ready"
    cash, quantities = capital, np.zeros(2)
    acquisition_cost, dividends = np.zeros(2), np.zeros(2)
    trades = result["transactions"]
    assert trades
    prior = result["start"]
    for point in result["equity"]:
        day = point["time"]
        for j, a in enumerate(assets):
            if a["category"] in ("stock", "etf") and prior < payout_day <= day:
                payout = quantities[j] * payouts[j][payout_day]
                cash += payout
                dividends[j] += payout
        for t in (t for t in trades if t["execution"] == day):
            j = 0 if t["asset_id"] == "a" else 1
            if assets[j]["category"] in ("stock", "etf"):
                assert isinstance(t["quantity"], int)
                assert t["quantity"] >= 1
                assert t["price"] == raw[j][day]
            sign = 1 if t["side"] == "buy" else -1
            if sign == 1:
                acquisition_cost[j] += t["amount"] + t["fee"]
            else:
                fraction = t["quantity"] / quantities[j]
                basis = acquisition_cost[j] * fraction
                income = dividends[j] * fraction
                assert t["profit_return"] == pytest.approx(
                    (t["amount"] - t["fee"] + income) / basis - 1
                )
                acquisition_cost[j] -= basis
                dividends[j] -= income
            quantities[j] += sign * t["quantity"]
            cash -= sign * t["amount"] + t["fee"]
            assert cash >= -1e-7
            assert min(quantities) >= -1e-7
        value = cash + sum(
            quantities[j]
            * (raw[j][day] if a["category"] in ("stock", "etf") else histories[j][day])
            for j, a in enumerate(assets)
        )
        assert value == pytest.approx(point["strategy"] * capital / 100)
        prior = day
    assert cash == pytest.approx(result["final_portfolio"]["cash"], abs=1e-7)
    if second_category == "crypto":
        assert any(
            t["asset_id"] == "b" and t["quantity"] != int(t["quantity"]) for t in trades
        )
    assert sum(t["fee"] for t in trades) == pytest.approx(
        result["metrics"]["strategy"]["cost_eur"]
    )


def test_whole_shares_missing_raw_prices_unaffordable_assets_and_local_etf():
    assets, histories, benchmark = sample()
    assets = [{**a, "category": "stock"} for a in assets]
    request = ValidationRequest(asset_ids=["a", "b"], whole_shares=True)
    missing = validation_data(assets, histories, benchmark, request)
    assert missing["status"] == "insufficient"
    expensive = [{d: 1000000.0 for d in h} for h in [*histories, benchmark]]
    result = validation_data(
        assets,
        histories,
        benchmark,
        request,
        execution_histories=expensive,
        benchmark_asset={"category": "etf", "name": "Reference"},
    )
    assert result["status"] == "ready"
    assert result["transactions"] == []
    assert len(result["final_portfolio"]["positions"]) == 2
    assert all(
        p["quantity"] == p["value"] == p["weight"] == 0
        for p in result["final_portfolio"]["positions"]
    )
    assert result["final_portfolio"]["cash"] == 10000
    for key in ("strategy", "equal", "buy_hold", "benchmark"):
        assert result["metrics"][key]["market_exposure"] == 0
        assert result["metrics"][key]["cost_eur"] == 0


@pytest.mark.parametrize("mode", ["volatility", "correlation"])
def test_optimization_invests_affordable_remainder_without_cash_overdraft(
    mode, monkeypatch
):
    assets, histories, benchmark = sample()
    assets = [{**a, "category": "stock"} for a in assets]
    raw = [
        {d: price for d in h}
        for h, price in zip(histories, [1100.0, 200.0], strict=True)
    ]
    monkeypatch.setattr(
        engine, "optimize_weights", lambda *args, **kwargs: np.array([0.5, 0.5])
    )
    result = validation_data(
        assets,
        histories,
        benchmark,
        ValidationRequest(asset_ids=["a", "b"], mode=mode, whole_shares=True),
        execution_histories=[*raw, {}],
    )
    final = result["final_portfolio"]
    assert 0 <= final["cash"] < 200 * 1.005
    assert all(p["quantity"] == int(p["quantity"]) for p in final["positions"])
    assert final["cash"] + sum(p["value"] for p in final["positions"]) + sum(
        t["fee"] for t in result["transactions"]
    ) == pytest.approx(10000)


@pytest.mark.parametrize("mode", ["volatility", "correlation", "mean_reversion"])
def test_staggered_listing_never_shortens_other_assets_or_uses_future_prices(mode):
    assets, histories, benchmark = sample()
    assets = [
        {**a, "category": "crypto" if j else "stock"} for j, a in enumerate(assets)
    ]
    histories[1] = {d: v for d, v in histories[1].items() if d >= "2020-01-02"}
    result = run((assets, histories, benchmark), mode=mode)
    assert result["status"] == "ready", result
    assert result["start"] == run(sample(), mode=mode)["start"]
    late = [t for t in result["transactions"] if t["asset_id"] == "b"]
    assert late, result["notices"]
    assert min(t["signal"] for t in late) >= "2023-01-02"
    assert all(t["execution"] > t["signal"] for t in late)
    assert not any("trois ans d’historique nécessaires" in n for n in result["notices"])
    # Independently reproduce every valuation, without any pre-listing price.
    cash, quantity = 10000.0, np.zeros(2)
    for point in result["equity"]:
        day = point["time"]
        for t in (t for t in result["transactions"] if t["execution"] == day):
            j = 0 if t["asset_id"] == "a" else 1
            sign = 1 if t["side"] == "buy" else -1
            quantity[j] += sign * t["quantity"]
            cash -= sign * t["amount"] + t["fee"]
        assert cash >= -1e-7
        assert cash + sum(
            quantity[j] * histories[j].get(day, 0) for j in range(2)
        ) == pytest.approx(point["strategy"] * 100)
    boundary = late[0]["execution"]
    changed = [dict(h) for h in histories]
    changed[1] = {d: v * (2 if d >= boundary else 1) for d, v in changed[1].items()}
    updated = run((assets, changed, benchmark), mode=mode)
    assert [p for p in result["equity"] if p["time"] < boundary] == [
        p for p in updated["equity"] if p["time"] < boundary
    ]


@pytest.mark.parametrize("whole", [False, True])
def test_reversion_crypto_and_fixed_etf_holdings_with_reserved_late_entry(whole):
    assets, histories, benchmark = sample()
    assets = [{**assets[0], "category": "crypto"}, {**assets[1], "category": "etf"}]
    # The passive ETF arrives after the simulation has started. Its budget must
    # not be spent by the active crypto before that listing.
    histories[1] = {d: v for d, v in histories[1].items() if d >= "2022-04-01"}
    raw = [dict(h) for h in histories]
    result = validation_data(
        assets,
        histories,
        benchmark,
        ValidationRequest(
            asset_ids=["a", "b"], mode="mean_reversion", whole_shares=whole
        ),
        execution_histories=[*raw, {}],
    )
    assert result["status"] == "ready", result
    assert any("B" in n and "quantité conservée" in n for n in result["notices"])
    passive = [t for t in result["transactions"] if t["asset_id"] == "b"]
    assert len(passive) == 1
    assert passive[0]["side"] == "buy"
    assert passive[0]["signal"] == "2022-04-01"
    assert passive[0]["execution"] > passive[0]["signal"]
    assert passive[0]["amount"] + passive[0]["fee"] <= 5000 + 1e-7
    final = next(p for p in result["final_portfolio"]["positions"] if p["id"] == "b")
    assert final["quantity"] == pytest.approx(passive[0]["quantity"])
    crypto = [t for t in result["transactions"] if t["asset_id"] == "a"]
    assert {t["side"] for t in crypto} == {"buy", "sell"}
    assert any(t["quantity"] != int(t["quantity"]) for t in crypto)
    cash, quantities = 10000.0, np.zeros(2)
    for point in result["equity"]:
        day = point["time"]
        for t in (t for t in result["transactions"] if t["execution"] == day):
            j = 0 if t["asset_id"] == "a" else 1
            sign = 1 if t["side"] == "buy" else -1
            quantities[j] += sign * t["quantity"]
            cash -= sign * t["amount"] + t["fee"]
        assert cash >= -1e-7
        if day < passive[0]["execution"]:
            assert cash >= 5000 - 1e-7
        assert cash + sum(
            quantities[j] * histories[j].get(day, 0) for j in range(2)
        ) == pytest.approx(point["strategy"] * 100)


def test_recent_crypto_without_training_stays_in_cash_while_others_run():
    assets, histories, benchmark = sample()
    assets = [{**a, "category": "crypto"} for a in assets]
    histories[1] = {d: v for d, v in histories[1].items() if d >= "2022-01-01"}
    result = run((assets, histories, benchmark), mode="mean_reversion")
    assert result["status"] == "ready"
    assert result["transactions"]
    assert all(t["asset_id"] == "a" for t in result["transactions"])
    assert (
        next(p for p in result["final_portfolio"]["positions"] if p["id"] == "b")[
            "quantity"
        ]
        == 0
    )
