import datetime as dt

import pandas as pd

from d1basis import calendar as C
from d1basis import data as D


def test_third_friday_and_holiday_pull():
    assert C.third_friday(2026, 9) == pd.Timestamp("2026-09-18")
    assert C.third_friday(2026, 12) == pd.Timestamp("2026-12-18")
    # 19 June 2026 is a Friday and Juneteenth: the contract's last day is Thursday the 18th (as ESM26 traded)
    assert C.third_friday(2026, 6) == pd.Timestamp("2026-06-18")
    assert C.third_friday(2025, 3) == pd.Timestamp("2025-03-21")


def test_holidays():
    h = C.nyse_holidays(2026)
    assert dt.date(2026, 6, 19) in h and dt.date(2026, 7, 3) in h and dt.date(2026, 11, 26) in h
    assert dt.date(2026, 4, 3) in h  # Good Friday
    assert C.is_trading_day("2026-09-18") and not C.is_trading_day("2026-09-19")
    assert dt.date(2021, 6, 18) not in C.nyse_holidays(2021)  # Juneteenth observed from 2022


def test_front_and_roll():
    assert C.front_expiry("2026-09-18", 0) == pd.Timestamp("2026-09-18")
    assert C.front_expiry("2026-09-21", 0) == pd.Timestamp("2026-12-18")
    # eight trading days before 18 Sep: the panel has rolled by 9 Sep
    assert C.front_expiry("2026-09-09", 8) == pd.Timestamp("2026-12-18")
    assert C.front_expiry("2026-09-01", 8) == pd.Timestamp("2026-09-18")
    assert C.next_expiry("2026-09-18") == pd.Timestamp("2026-12-18")
    assert C.quarter_bounds("2026-10-01") == (pd.Timestamp("2026-09-18"), pd.Timestamp("2026-12-18"))
    assert C.quarter_bounds("2026-09-18") == (pd.Timestamp("2026-09-18"), pd.Timestamp("2026-12-18"))


def test_contract_symbols():
    assert C.contract_symbol("ES", pd.Timestamp("2026-12-18")) == "ESZ26.CME"
    assert D.contract_expiry("ESZ26.CME") == pd.Timestamp("2026-12-18")
    assert D.contract_expiry("RTYH27.CME") == pd.Timestamp("2027-03-19")
    assert D.contract_root("RTYH27.CME") == "RTY"
    assert len(C.roll_window(pd.Timestamp("2026-09-18"), 8)) == 8
    assert C.roll_window(pd.Timestamp("2026-09-18"), 8)[-1] == pd.Timestamp("2026-09-18")
