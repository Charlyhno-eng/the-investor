"""Deterministic price fixture shared by synthetic-scenario tests."""

from datetime import date, timedelta

import numpy as np


def historical_rows():
    day = date(2013, 1, 2)
    dates = []
    while day <= date(2024, 1, 2):
        if day.weekday() < 5:
            dates.append(day.isoformat())
        day += timedelta(days=1)
    i = np.arange(len(dates))
    prices = 100 * np.exp(0.0003 * i + 0.09 * np.sin(i / 77))
    return [(d, float(p), float(p)) for d, p in zip(dates, prices, strict=True)]
