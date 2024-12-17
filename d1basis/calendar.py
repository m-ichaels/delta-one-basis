"""Exchange calendar: NYSE holidays by rule, the quarterly equity-index futures cycle (third Friday of Mar/Jun/Sep/Dec,
pulled to Thursday when the Friday is a holiday), front and second contract on a date, the roll window."""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

import numpy as np
import pandas as pd

QUARTER_MONTHS = (3, 6, 9, 12)
MONTH_CODE = {3: "H", 6: "M", 9: "U", 12: "Z"}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    off = (weekday - d.weekday()) % 7
    return d + dt.timedelta(days=off + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    d = dt.date(year + (month == 12), (month % 12) + 1, 1) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def easter(year: int) -> dt.date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)


def _observed(d: dt.date) -> dt.date:
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


@lru_cache(maxsize=None)
def nyse_holidays(year: int) -> frozenset:
    h = {
        _observed(dt.date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),           # MLK
        _nth_weekday(year, 2, 0, 3),           # Presidents
        easter(year) - dt.timedelta(days=2),   # Good Friday
        _last_weekday(year, 5, 0),             # Memorial
        _observed(dt.date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),           # Labor
        _nth_weekday(year, 11, 3, 4),          # Thanksgiving
        _observed(dt.date(year, 12, 25)),
    }
    if year >= 2022:
        h.add(_observed(dt.date(year, 6, 19)))
    if dt.date(year, 1, 1).weekday() == 5:     # Jan 1 on a Saturday is not observed on Dec 31
        h.discard(dt.date(year - 1, 12, 31))
    # one-off closures
    for d in ((2012, 10, 29), (2012, 10, 30), (2018, 12, 5), (2025, 1, 9)):
        if d[0] == year:
            h.add(dt.date(*d))
    return frozenset(h)


def is_trading_day(d) -> bool:
    d = pd.Timestamp(d).date()
    return d.weekday() < 5 and d not in nyse_holidays(d.year)


def trading_days(start, end) -> pd.DatetimeIndex:
    days = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D")
    return pd.DatetimeIndex([d for d in days if is_trading_day(d)])


@lru_cache(maxsize=None)
def third_friday(year: int, month: int) -> pd.Timestamp:
    """Last trading day of the equity-index contract: third Friday, or the Thursday before when that Friday is closed
    (Good Friday in April never coincides; the rule matters for e.g. 19 June)."""
    d = _nth_weekday(year, month, 4, 3)
    while d in nyse_holidays(d.year):
        d -= dt.timedelta(days=1)
    return pd.Timestamp(d)


def expiries(start, end) -> pd.DatetimeIndex:
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    out = []
    for y in range(s.year - 1, e.year + 2):
        for m in QUARTER_MONTHS:
            x = third_friday(y, m)
            if s <= x <= e:
                out.append(x)
    return pd.DatetimeIndex(out)


@lru_cache(maxsize=100000)
def front_expiry(date, roll_days: int = 0) -> pd.Timestamp:
    """The expiry of the front contract on `date`.  With roll_days = k the front is deemed to have rolled k trading
    days before expiry (the conventional 8 for the equity-index quarterlies; 0 = the contract still trading)."""
    d = pd.Timestamp(date).normalize()
    for y in (d.year, d.year + 1):
        for m in QUARTER_MONTHS:
            x = third_friday(y, m)
            cutoff = x if roll_days == 0 else trading_days(x - pd.Timedelta(days=roll_days * 2 + 5), x)[-roll_days - 1]
            if d < cutoff or (roll_days == 0 and d == cutoff):
                return x
    raise ValueError(date)


def next_expiry(after) -> pd.Timestamp:
    x = front_expiry(after)
    return expiries(x + pd.Timedelta(days=1), x + pd.Timedelta(days=120))[0]


def contract_symbol(root: str, expiry: pd.Timestamp, suffix: str = ".CME") -> str:
    return f"{root}{MONTH_CODE[expiry.month]}{expiry.year % 100:02d}{suffix}"


def quarter_bounds(date) -> tuple[pd.Timestamp, pd.Timestamp]:
    """(previous expiry, next expiry] - the dividend quarter of the index funds, whose ex-dates are the expiry Fridays."""
    d = pd.Timestamp(date).normalize()
    nxt = front_expiry(d)
    if nxt == d:
        nxt = next_expiry(d)
    prev = expiries(nxt - pd.Timedelta(days=120), nxt - pd.Timedelta(days=1))[-1]
    return prev, nxt


def year_fraction(t0, t1, basis: str = "act/360") -> float:
    days = (pd.Timestamp(t1).normalize() - pd.Timestamp(t0).normalize()).days
    return days / (360.0 if basis == "act/360" else 365.0)


def days_to(t0, t1) -> int:
    return int((pd.Timestamp(t1).normalize() - pd.Timestamp(t0).normalize()).days)


def roll_window(expiry: pd.Timestamp, days: int = 8) -> pd.DatetimeIndex:
    """The `days` trading days ending at expiry - the window in which the open interest moves to the next contract."""
    td = trading_days(expiry - pd.Timedelta(days=days * 2 + 5), expiry)
    return td[-days:]
