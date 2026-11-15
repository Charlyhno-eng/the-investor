"""Fixed-universe switch: thresholds, hysteresis, chronology and cash ledger."""

from datetime import date

import numpy as np
import pytest
from pydantic import ValidationError
from test_validation import sample

from investor.portfolio import validation as engine
from investor.portfolio.etf_switch import (
    defensive_target,
    initial_slow_state,
    slow_target,
)
from investor.portfolio.validation import ValidationRequest, validation_data


@pytest.mark.parametrize(
    "score,previous,risk_on,expected",
    [
        (-0.5, -0.6, False, True),
        (-0.6, -0.7, False, False),
        (-0.5, -0.5, False, False),
        (0, -0.4, False, False),
        (1.5, 1, True, True),
        (1.51, 1.5, True, False),
        (-2, -1, True, True),
        (None, -1, True, True),
        (None, -1, False, False),
        (0, None, False, False),
        (float("nan"), 0, True, True),
    ],
)
def test_rebound_and_exit_boundaries(score, previous, risk_on, expected):
    assert defensive_target(score, previous, risk_on) == expected


def test_switch_requires_exact_etfs():
    with pytest.raises(ValidationError, match="uniquement PSP5.PA"):
        ValidationRequest(asset_ids=["a", "b"], mode="etf_switch")
    with pytest.raises(ValidationError):
        ValidationRequest(asset_ids=["yf-psp5.pa", "yf-bx4.pa"], mode="cvar")


@pytest.mark.parametrize("whole", [False, True])
def test_switch_sequence_and_independent_cash_ledger(monkeypatch, whole):
    assets, histories, benchmark = sample()
    ids = ["yf-psp5.pa"]
    assets = [
        {**a, "id": identifier, "category": "etf"}
        for a, identifier in zip(assets[:1], ids, strict=True)
    ]
    histories = histories[:1]
    days = sorted(benchmark)
    first = days.index("2021-01-04")
    sp_sequence = np.full(len(days) - first, -0.25)
    sp_sequence[:5] = -1
    sp_sequence[5:10] = -0.5
    sp_sequence[10:15] = 1.5
    sp_sequence[15:19] = 1.51
    sp_sequence[19] = -0.75

    def score(prices, dates, signal, **kwargs):
        assert prices.shape[1] == 1
        if kwargs == {"months": 60, "min_observations": 501}:
            return [None]
        assert kwargs == {"months": 18, "min_observations": 251}
        return [float(sp_sequence[min(max(signal - first, 0), len(sp_sequence) - 1)])]

    monkeypatch.setattr(engine, "regression_z", score)
    options = {"execution_histories": [*histories, benchmark]} if whole else {}
    result = validation_data(
        assets,
        histories,
        benchmark,
        ValidationRequest(
            asset_ids=ids,
            mode="etf_switch",
            whole_shares=whole,
            start_date=date(2021, 1, 4),
        ),
        **options,
    )
    assert result["status"] == "ready"
    trades = result["transactions"]
    assert {t["sleeve"] for t in trades} == {"slow", "defensive"}
    slow = [t for t in trades if t["sleeve"] == "slow"]
    assert len(slow) == 1
    assert slow[0]["reason"] == "etf_slow_defensive_sp500"
    defensive = [t for t in trades if t["sleeve"] == "defensive"]
    assert [(t["asset_id"], t["side"]) for t in defensive] == [
        (ids[0], "buy"),
        (ids[0], "buy"),
        (ids[0], "sell"),
        (ids[0], "buy"),
    ]
    assert [t["z"] for t in defensive] == [-1, -0.5, 1.51, -0.25]
    assert [days.index(t["signal"]) - first for t in defensive] == [0, 5, 15, 20]
    assert (
        defensive[2]["quantity"] < defensive[0]["quantity"] + defensive[1]["quantity"]
    )
    assert defensive[2]["reason"] == "etf_defensive_sp500"
    cash, quantities = 10000.0, np.zeros(1)
    for point in result["equity"]:
        day = point["time"]
        for trade in (t for t in trades if t["execution"] == day):
            j = ids.index(trade["asset_id"])
            sign = 1 if trade["side"] == "buy" else -1
            quantities[j] += sign * trade["quantity"]
            cash -= sign * trade["amount"] + trade["fee"]
            assert days.index(day) == days.index(trade["signal"]) + 1
            assert trade["fee"] == pytest.approx(trade["amount"] * 0.0012)
            if whole:
                assert trade["quantity"] == int(trade["quantity"])
        assert cash >= -1e-7
        assert cash + sum(
            quantities[j] * histories[j][day] for j in range(1)
        ) == pytest.approx(point["strategy"] * 100)
    assert result["final_portfolio"]["cash"] == pytest.approx(cash, abs=1e-7)
    assert result["metrics"]["strategy"]["cost_eur"] == pytest.approx(
        sum(t["fee"] for t in trades)
    )


def test_future_prices_do_not_change_prior_switch_decisions():
    assets, histories, benchmark = sample()
    ids = ["yf-psp5.pa"]
    assets = [
        {**a, "id": identifier, "category": "etf"}
        for a, identifier in zip(assets[:1], ids, strict=True)
    ]
    histories = histories[:1]
    request = ValidationRequest(asset_ids=ids, mode="etf_switch")
    original = validation_data(assets, histories, benchmark, request)
    boundary = "2022-07-01"
    changed = [
        {day: value * (3 if day >= boundary else 1) for day, value in h.items()}
        for h in histories
    ]
    updated = validation_data(assets, changed, benchmark, request)
    assert original["status"] == updated["status"] == "ready"
    prior = [t for t in original["transactions"] if t["execution"] < boundary]
    assert prior
    assert prior == [t for t in updated["transactions"] if t["execution"] < boundary]
    assert [p for p in original["equity"] if p["time"] < boundary] == [
        p for p in updated["equity"] if p["time"] < boundary
    ]


def test_defensive_uses_eighteen_months_without_requiring_three_years():
    assets, histories, benchmark = sample()
    history = {d: v for d, v in histories[0].items() if d < "2020-01-01"}
    result = validation_data(
        [{**assets[0], "id": "yf-psp5.pa", "category": "etf"}],
        [history],
        {d: v for d, v in benchmark.items() if d in history},
        ValidationRequest(
            asset_ids=["yf-psp5.pa"], mode="etf_switch", start_date=date(2019, 7, 2)
        ),
    )
    assert result["status"] == "ready"
    assert result["start"] == "2019-07-02"
    assert result["training_years"] == 1.5
    assert {t["reason"] for t in result["transactions"]} >= {
        "etf_defensive_sp500",
        "etf_slow_defensive_sp500",
    }
    assert not any(
        t["reason"] == "etf_slow_entry_sp500" for t in result["transactions"]
    )


def test_reference_is_ese_and_alternative_reference_is_rejected():
    request = ValidationRequest(asset_ids=["yf-psp5.pa"], mode="etf_switch")
    assert request.benchmark_asset_id == "yf-psp5.pa"
    with pytest.raises(ValidationError, match="référence"):
        ValidationRequest(
            asset_ids=["yf-psp5.pa"], mode="etf_switch", benchmark_asset_id="other"
        )


@pytest.mark.parametrize(
    "score,risk_on,expected",
    [
        (-2, False, False),
        (-2.01, False, True),
        (1.5, True, True),
        (1.51, True, False),
        (None, True, True),
        (float("nan"), False, False),
    ],
)
def test_slow_strict_thresholds(score, risk_on, expected):
    assert slow_target(score, None, risk_on) == expected


def test_monthly_sleeve_and_opposing_orders_keep_independent_budgets(monkeypatch):
    assets, histories, benchmark = sample()
    days = sorted(benchmark)
    first = days.index("2021-01-04")

    def score(prices, dates, signal, **kwargs):
        day = days[signal]
        if kwargs["months"] == 60:
            if day < "2021-01-04":
                return [None]
            # Low mid-month must not trigger an early buy. Initial non-monthly
            # signal must allocate only the defensive tenth, even at -3 sigma.
            return [-3 if day < "2021-03-01" else 2]
        offset = signal - first
        return [-1 if offset in (-1, 39) else 2 if 20 <= offset < 39 else 0]

    monkeypatch.setattr(engine, "regression_z", score)
    result = validation_data(
        [{**assets[0], "id": "yf-psp5.pa", "category": "etf"}],
        histories[:1],
        benchmark,
        ValidationRequest(
            asset_ids=["yf-psp5.pa"],
            mode="etf_switch",
            whole_shares=True,
            start_date=date(2021, 1, 4),
            end_date=date(2021, 3, 5),
        ),
        execution_histories=[histories[0], benchmark],
    )
    assert result["status"] == "ready"
    trades = result["transactions"]
    slow = [t for t in trades if t["sleeve"] == "slow"]
    assert [(t["signal"], t["side"]) for t in slow] == [
        ("2021-01-04", "buy"),
        ("2021-02-01", "buy"),
        ("2021-03-01", "sell"),
    ]
    assert slow[0]["amount"] <= 7500 * 0.10
    march = [t for t in trades if t["signal"] == "2021-03-01"]
    assert [t["side"] for t in march] == ["sell", "buy"]
    assert [t["sleeve"] for t in march] == ["slow", "defensive"]
    # Reconstruct each sleeve separately; neither can spend the other's cash.
    budgets = {"slow": [7500.0, 0], "defensive": [2500.0, 0]}
    for t in trades:
        cash, units = budgets[t["sleeve"]]
        sign = 1 if t["side"] == "buy" else -1
        budgets[t["sleeve"]] = [
            cash - sign * t["amount"] - t["fee"],
            units + sign * t["quantity"],
        ]
        assert budgets[t["sleeve"]][0] >= -1e-7
    final = result["final_portfolio"]
    for sleeve in final["sleeves"]:
        assert sleeve["cash"] == pytest.approx(budgets[sleeve["id"]][0])
        assert sleeve["quantity"] == pytest.approx(budgets[sleeve["id"]][1])
    assert sum(s["cash"] for s in final["sleeves"]) == pytest.approx(final["cash"])
    assert sum(s["value"] + s["cash"] for s in final["sleeves"]) == pytest.approx(
        final["total"]
    )
    assert result["metrics"]["strategy"]["cost_eur"] == pytest.approx(
        sum(t["fee"] for t in trades)
    )


def test_dividends_credit_each_sleeve_without_rebalancing(monkeypatch):
    assets, histories, benchmark = sample()
    monkeypatch.setattr(engine, "regression_z", lambda *args, **kwargs: [0.0])
    request = ValidationRequest(
        asset_ids=["yf-psp5.pa"],
        mode="etf_switch",
        whole_shares=True,
        start_date=date(2021, 1, 4),
        end_date=date(2021, 2, 5),
    )
    args = (
        [{**assets[0], "id": "yf-psp5.pa", "category": "etf"}],
        histories[:1],
        benchmark,
        request,
    )
    options = {"execution_histories": [histories[0], benchmark]}
    plain = validation_data(*args, **options)
    paid = validation_data(
        *args, **options, cash_distributions=[{"2021-01-13": 2.0}, {}]
    )
    assert plain["status"] == paid["status"] == "ready"
    assert len(paid["transactions"]) == 2  # Only initial sleeve allocations.
    for a, b in zip(
        plain["final_portfolio"]["sleeves"],
        paid["final_portfolio"]["sleeves"],
        strict=True,
    ):
        assert b["quantity"] == pytest.approx(a["quantity"])
        assert b["cash"] == pytest.approx(a["cash"] + 2 * a["quantity"])
    assert paid["final_portfolio"]["cash"] == pytest.approx(
        sum(s["cash"] for s in paid["final_portfolio"]["sleeves"])
    )
    assert paid["final_portfolio"]["total"] == pytest.approx(
        plain["final_portfolio"]["total"]
        + 2 * plain["final_portfolio"]["positions"][0]["quantity"]
    )


@pytest.mark.parametrize(
    "score,previous,risk_on,expected",
    [
        (0.0, -0.01, False, True),
        (0.1, -0.1, False, True),
        (0.0, 0.0, False, False),
        (0.2, 0.1, False, False),
        (-0.01, -0.2, False, False),
        (0.0, None, False, False),
        (0.0, float("nan"), False, False),
        (None, -0.1, False, False),
        (float("inf"), -0.1, False, False),
        (-2.01, None, False, True),
        (1.5, -0.1, True, True),
        (1.51, -0.1, True, False),
    ],
)
def test_slow_reentry_crossing_and_exit_precedence(score, previous, risk_on, expected):
    assert slow_target(score, previous, risk_on) == expected


def test_slow_recovery_is_monthly_and_uses_previous_session(monkeypatch):
    assets, histories, benchmark = sample()

    def score(prices, dates, signal, **kwargs):
        if kwargs["months"] == 18:
            return [2.0]
        # Mid-month recovery must not enter. February starts above zero without
        # a daily crossing, so the earlier recovery must not be carried forward.
        day = dates[signal].isoformat()
        if day < "2021-01-14" or day == "2021-02-26":
            return [-0.1]
        return [0.1]

    monkeypatch.setattr(engine, "regression_z", score)
    result = validation_data(
        [{**assets[0], "id": "yf-psp5.pa", "category": "etf"}],
        histories[:1],
        benchmark,
        ValidationRequest(
            asset_ids=["yf-psp5.pa"],
            mode="etf_switch",
            start_date=date(2021, 1, 4),
            end_date=date(2021, 3, 5),
        ),
    )
    slow = [t for t in result["transactions"] if t["sleeve"] == "slow"]
    assert [t["signal"] for t in slow] == ["2021-01-04", "2021-03-01"]
    assert slow[1]["execution"] == "2021-03-02"
    assert slow[1]["reason"] == "etf_slow_entry_sp500"
    assert slow[1]["z"] == 0.1


def test_initial_slow_state_replays_only_pre_start_monthly_signals():
    dates = [date(2020, 1, 31), date(2020, 2, 3), date(2020, 2, 4), date(2020, 3, 2)]
    scores = [-0.1, 0.1, 2.0, 2.0]
    calls = []

    def score_at(index):
        calls.append(index)
        return scores[index]

    assert initial_slow_state(dates, 3, score_at)
    # Daily February exit and March's first signal do not belong to the replay.
    assert calls == [1, 0]
    assert not initial_slow_state(dates, 4, score_at)
    assert not initial_slow_state(dates, 0, score_at)


@pytest.mark.parametrize("historical_exit", [False, True])
@pytest.mark.parametrize("whole", [False, True])
def test_warm_initial_allocation_has_no_prior_holdings_or_profits(
    monkeypatch, historical_exit, whole
):
    assets, histories, benchmark = sample()
    start = date(2021, 1, 6)  # Mid-month initialization, no new monthly decision.

    def score(prices, dates, signal, **kwargs):
        day = dates[signal]
        if kwargs["months"] == 18:
            # The first defensive decision still reads its prior daily score.
            assert day >= date(2021, 1, 5)
            return [2.0]
        if day < date(2020, 11, 1):
            return [None]
        if day < date(2020, 12, 1):
            return [-3.0]
        return [2.0 if historical_exit else None]

    monkeypatch.setattr(engine, "regression_z", score)
    result = validation_data(
        [{**assets[0], "id": "yf-psp5.pa", "category": "etf"}],
        histories[:1],
        benchmark,
        ValidationRequest(
            asset_ids=["yf-psp5.pa"],
            mode="etf_switch",
            whole_shares=whole,
            start_date=start,
            end_date=date(2021, 1, 15),
        ),
        execution_histories=[histories[0], benchmark] if whole else None,
    )
    assert result["status"] == "ready"
    assert result["equity"][0]["time"] == start.isoformat()
    assert result["equity"][0]["strategy"] == 100
    assert len(result["transactions"]) == 2
    slow = next(t for t in result["transactions"] if t["sleeve"] == "slow")
    assert slow["signal"] == start.isoformat()
    assert slow["execution"] == "2021-01-07"
    target = 0.10 if historical_exit else 1.0
    capital_spent = slow["amount"] + slow["fee"]
    assert capital_spent <= 7500 + 1e-7
    expected = 7500 * target / (1 + 0.0012 * target)
    assert slow["amount"] == pytest.approx(
        expected, abs=slow["price"] if whole else 1e-7
    )
    assert result["final_portfolio"]["sleeves"][0]["risk_on"] == (not historical_exit)
    assert result["metrics"]["strategy"]["cost_eur"] == pytest.approx(
        sum(t["fee"] for t in result["transactions"])
    )
