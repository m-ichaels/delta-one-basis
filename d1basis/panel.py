"""The daily panel of one delta-one triangle: the front (and second) contract marked at the cash close, the index and
the fund, dividends, the fair value columns.  Yahoo's continuous series holds the expiring contract through its last
trading day and switches the next session; the panel rolls eight trading days before expiry, the conventional roll."""
from __future__ import annotations

from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import calendar as C
from . import data as D
from . import fairvalue as FV


def futures_marks(symbols: list[str], tz: str = "America/New_York", close_hour: int = 15) -> pd.DataFrame:
    """Wide date table of each symbol's price at the cash close: the hourly bar starting at 15:00 local (its close is
    the 16:00 print) where hourly bars exist, else the daily close (17:00 for CME, flagged in `mark`)."""
    daily = D.closes(symbols)
    out = daily.copy()
    mark = pd.DataFrame("daily", index=out.index, columns=out.columns)
    b = D.bars("1h", symbols)
    if not b.empty:
        loc = b.ts.dt.tz_convert(ZoneInfo(tz))
        b = b[(loc.dt.hour == close_hour)]
        b["date"] = loc[b.index].dt.normalize().dt.tz_localize(None)
        w = b.pivot_table(index="date", columns="symbol", values="close")
        for s in w.columns:
            common = out.index.intersection(w.index)
            common = common[w.loc[common, s].notna()]
            out.loc[common, s] = w.loc[common, s]
            mark.loc[common, s] = "16:00"
    return out, mark


def front_symbols(dates: pd.DatetimeIndex, root: str, roll_days: int = 8) -> tuple[list[str], list[pd.Timestamp]]:
    exp = [C.front_expiry(d, roll_days) for d in dates]
    return [C.contract_symbol(root, e) for e in exp], exp


def build(pair: str, cfg: dict, prof: pd.DataFrame | None = None, rate: str = "bill") -> pd.DataFrame:
    """Daily panel: date index; F (front at the cash close), contract, expiry, days, mark, F2/expiry2 (second contract
    where listed), I, E, div (fund distribution on its ex-date), r, D, F_fair, rho_bp, r_impl, spread_bp, and the same
    for the second contract with suffix 2."""
    idx_sym, etf = cfg["index"], cfg["etf"]
    px = D.closes([idx_sym, etf]).dropna()
    root = cfg["future_root"]
    syms = [s for s in cfg["contracts"] if s in D.daily().symbol.unique()]
    cont = cfg["continuous"]
    marks, mk = futures_marks(syms + ([cont] if cont else []))
    dates = px.index
    fsyms, fexp = front_symbols(dates, root)
    F = pd.Series(np.nan, index=dates)
    M = pd.Series("", index=dates)
    CS = pd.Series(fsyms, index=dates)
    for d, s, e in zip(dates, fsyms, fexp):
        if s in marks.columns and d in marks.index and pd.notna(marks.at[d, s]):
            F[d], M[d] = marks.at[d, s], mk.at[d, s]
        elif cont and d in marks.index and pd.notna(marks.at[d, cont]) and C.front_expiry(d, 0) == e:
            F[d], M[d] = marks.at[d, cont], mk.at[d, cont] + " (continuous)"
    panel = pd.DataFrame({"F": F, "contract": CS, "expiry": fexp, "mark": M, "I": px[idx_sym], "E": px[etf]})
    dv = D.dividends(etf).set_index("ex_date").amount
    panel["div"] = dv.reindex(panel.index).fillna(0.0)
    panel["days"] = [(e - d).days for d, e in zip(panel.index, panel.expiry)]
    ctx = FV.fv_context(idx_sym, etf, cfg["currency"])
    # fair value per contract
    fv_cols = ["tau", "r", "D", "F_fair", "rho_bp", "r_impl", "spread_bp"]
    for c in fv_cols:
        panel[c] = np.nan
    for s, e in sorted(set(zip(fsyms, fexp))):
        m = (panel.contract == s) & panel.F.notna()
        if not m.any():
            continue
        fv = FV.futures_fair_value(panel.loc[m, "F"], e, idx_sym, etf, cfg["etf_fee_bp"], cfg["currency"], prof, rate, index_px=px[idx_sym], ctx=ctx)
        for c in fv_cols:
            panel.loc[fv.index, c] = fv[c]
    # second contract where listed
    panel["F2"] = np.nan
    panel["expiry2"] = pd.NaT
    panel["spread2_bp"] = np.nan
    panel["r_impl2"] = np.nan
    for s, e in sorted(set(zip(fsyms, fexp))):
        e2 = C.expiries(e + pd.Timedelta(days=1), e + pd.Timedelta(days=120))[0]
        s2 = C.contract_symbol(root, e2)
        m = (panel.contract == s)
        if s2 not in marks.columns or not m.any():
            continue
        f2 = marks.loc[marks.index.intersection(panel.index[m]), s2].dropna()
        if f2.empty:
            continue
        fv2 = FV.futures_fair_value(f2, e2, idx_sym, etf, cfg["etf_fee_bp"], cfg["currency"], prof, rate, index_px=px[idx_sym], ctx=ctx)
        panel.loc[fv2.index, "F2"] = fv2.F
        panel.loc[fv2.index, "expiry2"] = e2
        panel.loc[fv2.index, "spread2_bp"] = fv2.spread_bp
        panel.loc[fv2.index, "r_impl2"] = fv2.r_impl
    # calendar-spread implied financing between front and second (bp/yr): ((F2 + D_12) / F1 - 1) / tau_12 - r
    m = panel.F2.notna() & panel.F.notna()
    if m.any():
        q, kap = ctx["q"], ctx["kap"]
        rows = []
        for d in panel.index[m]:
            e1, e2 = panel.at[d, "expiry"], panel.at[d, "expiry2"]
            D12 = FV.dividend_points(q, float(kap.get(d, kap.iloc[-1])), e1, e2, prof, cfg["etf_fee_bp"], float(panel.at[d, "E"]))
            tau12 = (e2 - e1).days / 360.0
            r12 = ((panel.at[d, "F2"] + D12) / panel.at[d, "F"] - 1) / tau12
            rows.append(1e4 * (r12 - panel.at[d, "r"]))
        panel.loc[m, "fwd_spread_bp"] = rows
    else:
        panel["fwd_spread_bp"] = np.nan
    panel.index.name = "date"
    return panel


def strategy_series(panel: pd.DataFrame, min_days: int = 15) -> pd.DataFrame:
    """The series the strategy trades: the front contract's implied-financing spread, with the last `min_days` before
    expiry masked (a few bp of price noise is hundreds of bp per year of financing when tau is two weeks); the panel
    itself rolls eight trading days out.  The result is sensitive to this choice and the run reports the sensitivity."""
    p = panel.copy()
    p.loc[p.days < min_days, ["spread_bp", "rho_bp"]] = np.nan
    return p
