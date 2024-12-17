"""Paths, configuration and loaders.  Every table is a parquet or csv under data/; DuckDB views sit on top of them.

data/reference/   daily.parquet (date, symbol, open..volume), dividends.parquet (symbol, ex_date, amount),
                  rates.parquet (date, EFFR, SOFR, ESTR, tbill_1m..tbill_6m), holdings/<ETF>.csv, contracts.csv,
                  firstrate_1m.parquet (one year of 1-minute bars: SPY QQQ DIA SPX NDX RUT DJI, 2022-10 .. 2023-09)
data/intraday/    bars_1m.parquet, bars_2m.parquet, bars_1h.parquet (ts UTC, symbol, open..volume), appended by tools/download.py
data/derived/     what the run writes (basis series, lead-lag tables, strategy trades)
"""
from __future__ import annotations

import json
import os
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("D1_DATA", os.path.join(ROOT, "data"))
REF = os.path.join(DATA, "reference")
INTRA = os.path.join(DATA, "intraday")
DERIVED = os.path.join(DATA, "derived")
RESULTS = os.path.join(ROOT, "results")

MONTH_CODES = {"H": 3, "M": 6, "U": 9, "Z": 12}


def pairs() -> dict:
    with open(os.path.join(ROOT, "configs", "pairs.json")) as f:
        cfg = json.load(f)
    return {k: v for k, v in cfg.items() if not k.startswith("_")}


def contract_expiry(symbol: str) -> pd.Timestamp:
    """'ESZ26.CME' -> the third Friday of December 2026 (the last trading day of an equity-index future)."""
    from .calendar import third_friday

    code = symbol.split(".")[0]
    yy = int(code[-2:])
    m = MONTH_CODES[code[-3]]
    return third_friday(2000 + yy, m)


def contract_root(symbol: str) -> str:
    return symbol.split(".")[0][:-3]


# ----------------------------------------------------------------------------- reference tables
def daily(symbols=None) -> pd.DataFrame:
    """Daily bars, long format; symbols filter optional.  Dates are naive calendar dates."""
    df = pd.read_parquet(os.path.join(REF, "daily.parquet"))
    if symbols is not None:
        df = df[df.symbol.isin(list(symbols))]
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


def closes(symbols) -> pd.DataFrame:
    """Wide table of daily closes (date index)."""
    d = daily(symbols)
    return d.pivot(index="date", columns="symbol", values="close").sort_index()


def dividends(symbol: str) -> pd.DataFrame:
    df = pd.read_parquet(os.path.join(REF, "dividends.parquet"))
    return df[df.symbol == symbol].sort_values("ex_date").reset_index(drop=True)


def rates() -> pd.DataFrame:
    """Daily overnight and bill rates in percent, date index, forward-filled over weekends/holidays."""
    r = pd.read_parquet(os.path.join(REF, "rates.parquet")).set_index("date").sort_index()
    idx = pd.date_range(r.index.min(), max(r.index.max(), pd.Timestamp.today().normalize()), freq="D")
    return r.reindex(idx).ffill()


def holdings(etf: str) -> pd.DataFrame:
    p = os.path.join(REF, "holdings", f"{etf}.csv")
    if not os.path.exists(p):
        return pd.DataFrame(columns=["ticker", "name", "weight", "shares"])
    h = pd.read_csv(p)
    h["weight"] = h["weight"].astype(float)
    return h.sort_values("weight", ascending=False).reset_index(drop=True)


def contracts() -> pd.DataFrame:
    p = os.path.join(REF, "contracts.csv")
    if not os.path.exists(p):
        return pd.DataFrame(columns=["symbol", "root", "expiry", "first_date", "last_date", "n"])
    c = pd.read_csv(p, parse_dates=["expiry", "first_date", "last_date"])
    return c


# ----------------------------------------------------------------------------- intraday
def bars(interval: str = "1m", symbols=None, source: str = "yahoo") -> pd.DataFrame:
    """Intraday bars, long format, ts tz-aware UTC.  source 'yahoo' (data/intraday) or 'firstrate' (the one-year sample)."""
    if source == "firstrate":
        p = os.path.join(REF, "firstrate_1m.parquet")
    else:
        p = os.path.join(INTRA, f"bars_{interval}.parquet")
    if not os.path.exists(p):
        return pd.DataFrame(columns=["ts", "symbol", "open", "high", "low", "close", "volume"])
    df = pd.read_parquet(p)
    if symbols is not None:
        df = df[df.symbol.isin(list(symbols))]
    df = df.sort_values(["symbol", "ts"]).reset_index(drop=True)
    if df.ts.dt.tz is None:
        df["ts"] = df.ts.dt.tz_localize("UTC")
    return df


def bar_closes(interval: str, symbols, source: str = "yahoo") -> pd.DataFrame:
    """Wide close table (UTC ts index) from the long bars."""
    b = bars(interval, symbols, source)
    if b.empty:
        return pd.DataFrame(columns=list(symbols))
    return b.pivot_table(index="ts", columns="symbol", values="close").sort_index()


def session_mask(ts: pd.DatetimeIndex, tz: str, start: str, end: str) -> np.ndarray:
    """True where a UTC timestamp falls inside the local cash session [start, end] (bar-end convention: the bar
    labelled 16:00 is excluded because it is the after-close bar; the bar labelled 09:30 is the first)."""
    loc = ts.tz_convert(ZoneInfo(tz))
    hm = loc.hour * 60 + loc.minute
    s = int(start[:2]) * 60 + int(start[3:])
    e = int(end[:2]) * 60 + int(end[3:])
    return (hm >= s) & (hm < e) & (loc.dayofweek < 5)


# ----------------------------------------------------------------------------- Databento
def load_mbp1(path: str, symbol: str | None = None) -> pd.DataFrame:
    """Databento MBP-1 (top of book) as a mid-quote series: csv (their csv export columns: ts_event, ts_recv, rtype,
    publisher_id, instrument_id, action, side, depth, price, size, flags, ts_in_delta, sequence, bid_px_00, ask_px_00,
    bid_sz_00, ask_sz_00, symbol) or a .dbn/.dbn.zst file when the databento-dbn package is installed.
    Returns ts (UTC), symbol, bid, ask, mid with one row per top-of-book change.  Prices are in units of the
    instrument (Databento's fixed-point 1e-9 integers are scaled when the csv carries them unscaled)."""
    if path.endswith(".csv") or path.endswith(".csv.zst") or path.endswith(".csv.gz"):
        df = pd.read_csv(path)
    else:
        try:
            import databento_dbn  # noqa: F401
            from databento import DBNStore
        except ImportError as e:
            raise ImportError("reading .dbn needs `pip install databento`; the csv export needs nothing") from e
        df = DBNStore.from_file(path).to_df().reset_index()
        df = df.rename(columns={"ts_event": "ts_event"})
    if symbol is not None and "symbol" in df:
        df = df[df.symbol == symbol]
    ts = pd.to_datetime(df["ts_event"], utc=True)
    bid = df["bid_px_00"].astype(float)
    ask = df["ask_px_00"].astype(float)
    if bid.abs().median() > 1e8:  # unscaled fixed-point
        bid, ask = bid / 1e9, ask / 1e9
    out = pd.DataFrame({"ts": pd.DatetimeIndex(ts.values, tz="UTC"), "symbol": df["symbol"].values if "symbol" in df else symbol, "bid": bid.values, "ask": ask.values})
    out = out[(out.bid > 0) & (out.ask > 0) & (out.ask >= out.bid)]
    out["mid"] = 0.5 * (out.bid + out.ask)
    out = out[out.mid.ne(out.mid.shift())]  # one row per mid change
    return out.reset_index(drop=True)


# ----------------------------------------------------------------------------- DuckDB
def store():
    """A DuckDB connection with a view on every reference, intraday and derived table."""
    import duckdb

    con = duckdb.connect()
    views = {
        "daily": os.path.join(REF, "daily.parquet"),
        "dividends": os.path.join(REF, "dividends.parquet"),
        "rates": os.path.join(REF, "rates.parquet"),
        "firstrate_1m": os.path.join(REF, "firstrate_1m.parquet"),
        "bars_1m": os.path.join(INTRA, "bars_1m.parquet"),
        "bars_2m": os.path.join(INTRA, "bars_2m.parquet"),
        "bars_1h": os.path.join(INTRA, "bars_1h.parquet"),
    }
    if os.path.isdir(DERIVED):
        for f in os.listdir(DERIVED):
            if f.endswith(".parquet"):
                views[f[:-8]] = os.path.join(DERIVED, f)
    def q(path):  # a path inside a SQL string literal (the workspace path has an apostrophe)
        return path.replace(os.sep, "/").replace("'", "''")

    for name, p in views.items():
        if os.path.exists(p):
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{q(p)}')")
    hd = os.path.join(REF, "holdings")
    if os.path.isdir(hd):
        for f in os.listdir(hd):
            if f.endswith(".csv"):
                con.execute(f"CREATE VIEW holdings_{f[:-4].replace('.', '_')} AS SELECT * FROM read_csv_auto('{q(os.path.join(hd, f))}')")
    return con


def write_parquet(df: pd.DataFrame, name: str, where: str = DERIVED):
    os.makedirs(where, exist_ok=True)
    p = os.path.join(where, name if name.endswith(".parquet") else name + ".parquet")
    df.to_parquet(p, index=False, compression="zstd")
    return p
