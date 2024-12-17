#!/usr/bin/env python3
"""Every download, incremental.   python tools/download.py [--only daily|intraday|rates|holdings|firstrate] [--since 2005-01-01]

Yahoo chart API      daily bars since 2005 and dividends for the futures (continuous and listed contracts), indices, ETFs;
                     intraday 1-minute bars in 7-day windows over the trailing 30 days (the only window Yahoo serves),
                     2-minute over 60 days, hourly over 730 days - appended to data/intraday/bars_*.parquet so the archive
                     grows beyond what Yahoo keeps; run it daily.
NY Fed               EFFR (2016-) and SOFR (2018-);  ECB  EUR short-term rate (2019-);  US Treasury  daily par curve (2005-)
SSGA / stockanalysis SPY full holdings (xlsx); top-25 holdings for QQQ, IWM (their sponsors' files are not served to scripts)
FirstRateData        the free one-year 1-minute sample: SPY QQQ DIA SPX NDX RUT DJI, 2022-10 .. 2023-09
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from d1basis import data as D  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}
LOG = open(os.path.join(D.DATA, "download.log"), "a")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LOG.write(f"{dt.datetime.now(dt.UTC).isoformat()} {s}\n")
    LOG.flush()


def get(url: str, retries: int = 4, timeout: int = 60, headers: dict | None = None) -> bytes:
    h = dict(UA)
    if headers:
        h.update(headers)
    for k in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            if code == 429 or "429" in str(e):
                time.sleep(20 * (k + 1))
            elif code in (404, 422) or k == retries - 1:
                raise
            else:
                time.sleep(2 * (k + 1))
    raise RuntimeError(url)


# ----------------------------------------------------------------------------- yahoo
def yahoo_chart(symbol: str, **params) -> dict | None:
    q = urllib.parse.urlencode(params)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{q}"
    try:
        d = json.loads(get(url))
    except Exception as e:  # noqa: BLE001
        log("yahoo fail", symbol, params, str(e)[:80])
        return None
    r = d.get("chart", {}).get("result")
    if not r or not r[0].get("timestamp"):
        return None
    return r[0]


def _frame(r: dict, symbol: str) -> pd.DataFrame:
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"ts": pd.to_datetime(r["timestamp"], unit="s", utc=True), "open": q.get("open"), "high": q.get("high"),
                       "low": q.get("low"), "close": q.get("close"), "volume": q.get("volume")})
    df["symbol"] = symbol
    df = df.dropna(subset=["close"])
    return df[["ts", "symbol", "open", "high", "low", "close", "volume"]]


def yahoo_daily(symbol: str, since: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    p1 = int(pd.Timestamp(since, tz="UTC").timestamp())
    p2 = int(time.time()) + 86400
    r = yahoo_chart(symbol, period1=p1, period2=p2, interval="1d", events="div")
    if r is None:
        return pd.DataFrame(), pd.DataFrame()
    tz = r["meta"].get("exchangeTimezoneName", "America/New_York")
    df = _frame(r, symbol)
    df["date"] = df.ts.dt.tz_convert(ZoneInfo(tz)).dt.normalize().dt.tz_localize(None)
    df = df.drop(columns="ts").drop_duplicates("date", keep="last")
    div = r.get("events", {}).get("dividends", {})
    dv = pd.DataFrame([{"symbol": symbol, "ex_date": pd.Timestamp(v["date"], unit="s", tz="UTC").tz_convert(ZoneInfo(tz)).normalize().tz_localize(None), "amount": float(v["amount"])} for v in div.values()])
    return df[["date", "symbol", "open", "high", "low", "close", "volume"]], dv


def yahoo_intraday(symbol: str, interval: str) -> pd.DataFrame:
    """1m: five 7-day windows back to the 30-day limit; 2m: range 60d; 1h: range 730d."""
    frames = []
    if interval == "1m":
        now = int(time.time())
        for k in range(5):
            p2 = now - k * 7 * 86400
            p1 = p2 - 7 * 86400
            r = yahoo_chart(symbol, period1=p1, period2=p2, interval="1m")
            if r is not None:
                frames.append(_frame(r, symbol))
            time.sleep(0.25)
    else:
        rng = {"2m": "60d", "5m": "60d", "1h": "730d"}[interval]
        r = yahoo_chart(symbol, range=rng, interval=interval)
        if r is not None:
            frames.append(_frame(r, symbol))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames).drop_duplicates(["ts"]).sort_values("ts")


def _append(path: str, new: pd.DataFrame, keys: list[str]):
    if new.empty:
        return
    if os.path.exists(path):
        old = pd.read_parquet(path)
        new = pd.concat([old, new])
    new = new.drop_duplicates(keys, keep="last").sort_values(keys).reset_index(drop=True)
    new.to_parquet(path, index=False, compression="zstd")


def universe() -> dict:
    cfg = D.pairs()
    fut, idx, etf = [], [], []
    for k, p in cfg.items():
        if p["continuous"]:
            fut.append(p["continuous"])
        fut += p["contracts"]
        idx.append(p["index"])
        etf.append(p["etf"])
    etf.append("FEZ")
    cons = []
    for k, p in cfg.items():
        if p.get("basket_top"):
            h = D.holdings(p["etf"])
            top = [str(t).replace(".", "-") for t in h.ticker.head(p["basket_top"]).tolist()]
            cons += [t for t in top if re.match(r"^[A-Z]{1,5}(-[A-Z])?$", t)]
    cons = sorted(set(cons) - set(etf))
    return {"futures": fut, "indices": idx, "etfs": etf, "constituents": cons}


def do_daily(since: str):
    u = universe()
    syms = u["futures"] + u["indices"] + u["etfs"] + u["constituents"]
    frames, divs, rows = [], [], []
    for s in syms:
        df, dv = yahoo_daily(s, since)
        if df.empty:
            log("daily: no data", s)
            continue
        frames.append(df)
        if not dv.empty:
            divs.append(dv)
        if s.endswith(".CME"):
            rows.append({"symbol": s, "root": D.contract_root(s), "expiry": D.contract_expiry(s), "first_date": df.date.min(), "last_date": df.date.max(), "n": len(df)})
        log("daily", s, len(df), df.date.min().date(), df.date.max().date())
        time.sleep(0.3)
    os.makedirs(D.REF, exist_ok=True)
    pd.concat(frames).to_parquet(os.path.join(D.REF, "daily.parquet"), index=False, compression="zstd")
    if divs:
        pd.concat(divs).sort_values(["symbol", "ex_date"]).to_parquet(os.path.join(D.REF, "dividends.parquet"), index=False)
    pd.DataFrame(rows).to_csv(os.path.join(D.REF, "contracts.csv"), index=False)


def do_intraday(intervals=("1m", "2m", "1h")):
    u = universe()
    syms = u["futures"] + u["indices"] + u["etfs"] + u["constituents"]
    os.makedirs(D.INTRA, exist_ok=True)
    for iv in intervals:
        frames = []
        for s in syms:
            df = yahoo_intraday(s, iv)
            if df.empty:
                log("intraday: no data", s, iv)
            else:
                frames.append(df)
                log("intraday", iv, s, len(df), df.ts.min(), df.ts.max())
            time.sleep(0.3)
        if frames:
            _append(os.path.join(D.INTRA, f"bars_{iv}.parquet"), pd.concat(frames), ["symbol", "ts"])


# ----------------------------------------------------------------------------- rates
def nyfed(kind: str, name: str) -> pd.DataFrame:
    out = []
    for y in range(2016, dt.date.today().year + 1):
        url = f"https://markets.newyorkfed.org/api/rates/{kind}/{name.lower()}/search.json?startDate={y}-01-01&endDate={y}-12-31"
        try:
            d = json.loads(get(url))
        except Exception as e:  # noqa: BLE001
            log("nyfed fail", name, y, str(e)[:60])
            continue
        out += [{"date": pd.Timestamp(r["effectiveDate"]), name: float(r["percentRate"])} for r in d.get("refRates", [])]
        time.sleep(0.2)
    return pd.DataFrame(out).drop_duplicates("date") if out else pd.DataFrame(columns=["date", name])


def ecb_estr() -> pd.DataFrame:
    url = "https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT?format=csvdata"
    try:
        df = pd.read_csv(io.BytesIO(get(url)))
    except Exception as e:  # noqa: BLE001
        log("ecb fail", str(e)[:60])
        return pd.DataFrame(columns=["date", "ESTR"])
    return pd.DataFrame({"date": pd.to_datetime(df["TIME_PERIOD"]), "ESTR": df["OBS_VALUE"].astype(float)})


def treasury_par(since_year: int) -> pd.DataFrame:
    frames = []
    for y in range(since_year, dt.date.today().year + 1):
        url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv"
        try:
            df = pd.read_csv(io.BytesIO(get(url)))
        except Exception as e:  # noqa: BLE001
            log("treasury fail", y, str(e)[:60])
            continue
        df.columns = [c.strip() for c in df.columns]
        df["date"] = pd.to_datetime(df["Date"])
        keep = {"1 Mo": "tbill_1m", "2 Mo": "tbill_2m", "3 Mo": "tbill_3m", "6 Mo": "tbill_6m", "1 Yr": "tsy_1y", "2 Yr": "tsy_2y"}
        cols = {k: v for k, v in keep.items() if k in df.columns}
        frames.append(df[["date"] + list(cols)].rename(columns=cols))
        time.sleep(0.3)
    return pd.concat(frames).sort_values("date") if frames else pd.DataFrame(columns=["date"])


def do_rates(since: str):
    r = treasury_par(int(since[:4]))
    for kind, name in (("unsecured", "EFFR"), ("secured", "SOFR")):
        x = nyfed(kind, name)
        r = r.merge(x, on="date", how="outer") if not x.empty else r
    e = ecb_estr()
    if not e.empty:
        r = r.merge(e, on="date", how="outer")
    r = r.sort_values("date").reset_index(drop=True)
    for c in r.columns:
        if c != "date":
            r[c] = pd.to_numeric(r[c], errors="coerce")
    r.to_parquet(os.path.join(D.REF, "rates.parquet"), index=False)
    log("rates", len(r), r.date.min().date(), r.date.max().date(), list(r.columns))


# ----------------------------------------------------------------------------- holdings
def ssga_spy() -> pd.DataFrame:
    url = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx"
    raw = get(url)
    import openpyxl

    ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True).active
    rows, hdr, asof = [], None, None
    for row in ws.iter_rows(values_only=True):
        if row and row[0] == "Holdings:":
            asof = str(row[1])
        if row and row[0] == "Name" and hdr is None:
            hdr = list(row)
            continue
        if hdr and row and row[0] and row[1]:
            rows.append(dict(zip(hdr, row)))
    df = pd.DataFrame(rows)
    out = pd.DataFrame({"ticker": df["Ticker"].astype(str).str.strip(), "name": df["Name"], "weight": pd.to_numeric(df["Weight"], errors="coerce"), "shares": pd.to_numeric(df["Shares Held"], errors="coerce")})
    out = out[out.ticker.str.match(r"^[A-Z.]+$")]
    out.attrs["asof"] = asof
    return out


def stockanalysis_top(etf: str) -> pd.DataFrame:
    h = get(f"https://stockanalysis.com/etf/{etf.lower()}/holdings/").decode("utf-8", "ignore")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", h, flags=re.S)
    out = []
    for r in rows[1:]:
        cells = [re.sub("<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.S)]
        if len(cells) >= 5 and cells[1] and cells[1] != "n/a":
            w = cells[3].replace("%", "").replace(",", "")
            sh = cells[4].replace(",", "")
            try:
                out.append({"ticker": cells[1].replace(".", "-"), "name": cells[2], "weight": float(w), "shares": float(sh) if sh else np.nan})
            except ValueError:
                continue
    df = pd.DataFrame(out)
    return df[~df.ticker.str.startswith("XTSLA")]  # the cash sweep line


def do_holdings():
    os.makedirs(os.path.join(D.REF, "holdings"), exist_ok=True)
    try:
        spy = ssga_spy()
        spy.to_csv(os.path.join(D.REF, "holdings", "SPY.csv"), index=False)
        log("holdings SPY (SSGA)", len(spy), spy.attrs.get("asof"))
    except Exception as e:  # noqa: BLE001
        log("SSGA fail", str(e)[:80])
    for etf in ("QQQ", "IWM"):
        try:
            h = stockanalysis_top(etf)
            h.to_csv(os.path.join(D.REF, "holdings", f"{etf}.csv"), index=False)
            log("holdings", etf, "(stockanalysis top)", len(h))
        except Exception as e:  # noqa: BLE001
            log("stockanalysis fail", etf, str(e)[:80])
        time.sleep(1)


# ----------------------------------------------------------------------------- firstrate sample
def do_firstrate():
    os.makedirs(os.path.join(D.DATA, "raw", "firstrate"), exist_ok=True)
    frames = []
    for s in ("SPY", "QQQ", "DIA", "SPX", "NDX", "RUT", "DJI"):
        p = os.path.join(D.DATA, "raw", "firstrate", f"{s}.zip")
        if not os.path.exists(p):
            try:
                raw = get(f"https://frd001.s3-us-east-2.amazonaws.com/{s}_1min_sample_firstratedata.zip")
            except Exception as e:  # noqa: BLE001
                log("firstrate fail", s, str(e)[:60])
                continue
            open(p, "wb").write(raw)
        z = zipfile.ZipFile(p)
        raw_csv = z.read(z.namelist()[0])
        headed = raw_csv[:20].lower().startswith(b"timestamp")
        df = pd.read_csv(io.BytesIO(raw_csv), header=0 if headed else None)
        df.columns = [c.lower() for c in df.columns] if headed else ["timestamp", "open", "high", "low", "close", "volume"][: df.shape[1]]
        # FirstRate stamps bars in US Eastern at the bar start, as Yahoo does; stored as UTC
        ts = pd.to_datetime(df["timestamp"]).dt.tz_localize(ZoneInfo("America/New_York"), ambiguous="NaT", nonexistent="NaT")
        df["ts"] = ts.dt.tz_convert("UTC")
        df = df.dropna(subset=["ts"])
        df["symbol"] = s
        if "volume" not in df:
            df["volume"] = np.nan
        frames.append(df[["ts", "symbol", "open", "high", "low", "close", "volume"]])
        log("firstrate", s, len(df), df.ts.min(), df.ts.max())
    if frames:
        pd.concat(frames).sort_values(["symbol", "ts"]).to_parquet(os.path.join(D.REF, "firstrate_1m.parquet"), index=False, compression="zstd")


def main(argv):
    only = None
    since = "2005-01-01"
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    if "--since" in argv:
        since = argv[argv.index("--since") + 1]
    os.makedirs(D.REF, exist_ok=True)
    steps = {"holdings": do_holdings, "rates": lambda: do_rates(since), "daily": lambda: do_daily(since), "firstrate": do_firstrate, "intraday": do_intraday}
    for name, fn in steps.items():
        if only is None or only == name:
            log("==", name)
            fn()
    log("done")


if __name__ == "__main__":
    main(sys.argv[1:])
