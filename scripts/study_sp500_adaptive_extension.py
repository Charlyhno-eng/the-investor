"""Follow-up: calendar-stable signals, online expert mixtures, constant controls."""

from pathlib import Path

import numpy as np
import study_sp500_adaptive_risk as base

ORIGINAL_GRID = base.grid
ORIGINAL_FEATURES = base.features
ORIGINAL_SIMULATE = base.simulate


def grid():
    configs = ORIGINAL_GRID()
    for family, params in [("adaptive", [126, 252, 504]), ("constant", [0.6, 0.8])]:
        for p in params:
            for cadence in [5, 21]:
                for band in [0.05, 0.15]:
                    for target in [None, 0.1, 0.15]:
                        configs.append(
                            dict(
                                family=family,
                                param=p,
                                cadence=cadence,
                                band=band,
                                floor=0,
                                vol_target=target,
                            )
                        )
    return configs


def features(prices, configs):
    result = ORIGINAL_FEATURES(prices, configs)
    experts = [
        dict(family=f, param=p, cadence=5, band=0.15, floor=0, vol_target=None)
        for f, p in [
            ("ma", 100),
            ("ma", 150),
            ("ma", 200),
            ("ma", 250),
            ("ensemble_ma", 0),
            ("ensemble_ma", 1),
            ("ensemble_mom", 0),
            ("ensemble_mom", 1),
            ("hysteresis", 0.03),
        ]
    ]
    ew = ORIGINAL_FEATURES(prices, experts)
    r = np.r_[0, prices[1:] / prices[:-1] - 1]
    returns = np.zeros_like(ew)
    returns[:, 2:] = ew[:, :-2] * r[None, 2:]
    online = {}
    for window in [126, 252, 504]:
        weights = ew.mean(axis=0)
        for t in range(window, len(prices)):
            past = returns[:, t - window + 1 : t + 1]
            # Equal-weight top3 experts by trailing Sharpe; all returns are known
            # at signal close and use lagged expert exposures. Ties stable.
            vol = past.std(axis=1, ddof=1)
            score = np.divide(
                past.mean(axis=1), vol, out=np.zeros(len(experts)), where=vol > 1e-12
            )
            chosen = np.argsort(-score, kind="stable")[:3]
            weights[t] = ew[chosen, t].mean()
        online[window] = weights
    for i, c in enumerate(configs):
        if c["family"] == "adaptive":
            # Original unknown-family output is the optional volatility cap.
            result[i] *= online[c["param"]]
        elif c["family"] == "constant":
            result[i] *= c["param"]
    return result


def simulate(*args, **kwargs):
    return ORIGINAL_SIMULATE(*args, **kwargs, calendar=True)


if __name__ == "__main__":
    base.OUT = Path("data/backtests/sp500-adaptive-calendar.json")
    base.PLAN = {
        **base.PLAN,
        "extension": "Separate exploratory follow-up after first results. Same proxy-only selection and gates. Calendar Friday or first session of month; first allocation on evaluation start. Add9-expert trailing-Sharpe top3 equal-weight mixture with126/252/504 known return sessions and60/80% constant-exposure controls. No final ESE reselection. Expert rankings ignore turnover, but actual composite execution pays all commissions; limitation retained.",
    }
    base.grid = grid
    base.features = features
    base.simulate = simulate
    base.main()
