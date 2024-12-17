"""Fair value of the delta-one triangle: the financing curve, the dividend forecast and its within-quarter accrual
profile (measured from the ETF's own price against the index), the fair futures price, richness in bp, the implied
financing rate and its spread to the measured rate, the ETF premium to the index, and the mean-reversion half-life.

Notation.  I index level, E fund price, F futures price, tau = years to the contract's last trading day (act/360),
r(t, tau) the financing rate, D(t, T) the index dividend points going ex in (t, T].
    F* = (I - PV D)(1 + r tau)                       fair futures price
    rho = 1e4 (F - F*) / I                           richness, bp of index
    r_impl = ((F + D) / I - 1) / tau                 implied financing (simple, act/360)
    s = 1e4 (r_impl - r)                             implied financing spread, bp per year
    E* = I / kappa_q + A(t) - fee(t)                 fair fund price inside dividend quarter q; kappa_q = I/E at the
                                                     previous ex-date, A the dividends per share accrued since it
    e = 1e4 (E - E*) / E                             fund premium, bp
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from functools import lru_cache

from . import calendar as C
from . import data as D

TENORS = {"tbill_1m": 30, "tbill_2m": 61, "tbill_3m": 91, "tbill_6m": 182, "tsy_1y": 365}


# ----------------------------------------------------------------------------- financing
def financing_curve(currency: str = "USD") -> pd.DataFrame:
    """Daily table (date index) of the rates the fair value can use, in percent."""
    r = D.rates()
    if currency == "EUR":
        out = pd.DataFrame({"ESTR": r.get("ESTR")}, index=r.index)
        out["bill"] = out["ESTR"]
        return out
    return r


def rate_at(r: pd.DataFrame, date, days: int, which: str = "bill") -> float:
    """Simple annual rate (decimal) for `days` ahead from the curve row on `date`.  which: 'bill' (Treasury par curve
    interpolated in tenor), 'EFFR', 'SOFR', 'ESTR' (flat overnight rate)."""
    d = pd.Timestamp(date).normalize()
    if d not in r.index:
        d = r.index[r.index.searchsorted(d) - 1] if d > r.index[0] else r.index[0]
    row = r.loc[d]
    if which != "bill":
        v = row.get(which, np.nan)
        return float(v) / 100.0 if pd.notna(v) else np.nan
    if "tbill_1m" not in r.columns:
        v = row.get("bill", row.get("ESTR", np.nan))
        return float(v) / 100.0 if pd.notna(v) else np.nan
    xs, ys = [], []
    for c, n in TENORS.items():
        v = row.get(c, np.nan)
        if pd.notna(v):
            xs.append(n)
            ys.append(float(v))
    if not xs:
        return np.nan
    return float(np.interp(max(days, 1), xs, ys)) / 100.0


def rate_series(r: pd.DataFrame, dates: pd.DatetimeIndex, days: np.ndarray, which: str = "bill") -> np.ndarray:
    """Vectorised rate_at over a date index (rows re-indexed with forward fill)."""
    rows = r.reindex(pd.DatetimeIndex(dates).normalize(), method="ffill")
    if which != "bill":
        return rows[which].values.astype(float) / 100.0 if which in rows else np.full(len(rows), np.nan)
    if "tbill_1m" not in r.columns:
        col = "bill" if "bill" in rows else "ESTR"
        return rows[col].values.astype(float) / 100.0
    cols = [c for c in TENORS if c in rows.columns]
    xs = np.array([TENORS[c] for c in cols], float)
    M = rows[cols].values.astype(float)
    out = np.full(len(rows), np.nan)
    for i in range(len(rows)):
        ok = ~np.isnan(M[i])
        if ok.any():
            out[i] = np.interp(max(int(days[i]), 1), xs[ok], M[i][ok]) / 100.0
    return out


# ----------------------------------------------------------------------------- dividends
def quarterly_distributions(etf: str) -> pd.DataFrame:
    """One row per dividend quarter: ex_date, amount (per fund share), the expiry that closes the quarter."""
    dv = D.dividends(etf)
    if dv.empty:
        return pd.DataFrame(columns=["ex_date", "amount", "quarter_end"])
    dv = dv.copy()
    dv["quarter_end"] = [C.quarter_bounds(x - pd.Timedelta(days=1))[1] for x in dv.ex_date]
    q = dv.groupby("quarter_end").agg(ex_date=("ex_date", "last"), amount=("amount", "sum")).reset_index()
    return q[["ex_date", "amount", "quarter_end"]]


_FQ_CACHE: dict = {}


def forecast_quarter(q: pd.DataFrame, asof, quarter_end) -> float:
    """Point-in-time forecast of the fund's distribution for the quarter ending at `quarter_end`: the same quarter a
    year earlier grown by the trailing four-quarter growth, using only distributions that went ex before `asof`."""
    n_known = int(np.searchsorted(q.ex_date.values, np.datetime64(pd.Timestamp(asof)), side="left"))
    key = (id(q), n_known, pd.Timestamp(quarter_end))
    if key in _FQ_CACHE:
        return _FQ_CACHE[key]
    v = _forecast_quarter(q.iloc[:n_known], quarter_end)
    _FQ_CACHE[key] = v
    return v


def _forecast_quarter(known: pd.DataFrame, quarter_end) -> float:
    """Half the seasonal forecast (same quarter a year earlier times the trailing four-quarter growth, clipped to
    [0.5, 2]) and half the median of the last four distributions.  The seasonal half carries the funds whose
    distributions follow the calendar (SPY, the Euro Stoxx fund); the median half protects against the lumpy ones
    (IWM, QQQ).  forecast_errors() reports what each rule would have done."""
    if len(known) < 4:
        return float(known.amount.iloc[-1]) if len(known) else np.nan
    a = known.set_index("quarter_end").amount
    same = a[a.index <= pd.Timestamp(quarter_end) - pd.Timedelta(days=360)]
    base = float(same.iloc[-1]) if len(same) else float(a.iloc[-4])
    g = a.iloc[-4:].sum() / a.iloc[-8:-4].sum() if len(a) >= 8 else 1.0
    seasonal = base * float(np.clip(g, 0.5, 2.0))
    return 0.5 * seasonal + 0.5 * float(np.median(a.iloc[-4:]))


def forecast_errors(etf: str, lead_days: int = 80) -> dict:
    """Mean absolute error, relative to the realised distribution, of the point-in-time forecast made `lead_days`
    before each ex-date, for the rule in use and its two halves."""
    q = quarterly_distributions(etf)
    rows = {"blend": [], "seasonal": [], "median4": []}
    for k in range(8, len(q)):
        asof = q.ex_date.iloc[k] - pd.Timedelta(days=lead_days)
        known = q[q.ex_date < asof]
        if len(known) < 8:
            continue
        a = float(q.amount.iloc[k])
        if a <= 0:
            continue
        kk = known.set_index("quarter_end").amount
        same = kk[kk.index <= q.quarter_end.iloc[k] - pd.Timedelta(days=360)]
        base = float(same.iloc[-1]) if len(same) else float(kk.iloc[-4])
        seasonal = base * float(np.clip(kk.iloc[-4:].sum() / kk.iloc[-8:-4].sum(), 0.5, 2.0))
        med = float(np.median(kk.iloc[-4:]))
        rows["seasonal"].append(abs(seasonal - a) / a)
        rows["median4"].append(abs(med - a) / a)
        rows["blend"].append(abs(0.5 * (seasonal + med) - a) / a)
    out = {k: float(np.mean(v)) if v else np.nan for k, v in rows.items()}
    out["n"] = len(rows["blend"])
    return out


def accrual_profile(index_sym: str, etf: str, fee_bp: float, n_bins: int = 20) -> pd.DataFrame:
    """Within-quarter dividend accrual measured from the fund: A(t) = E_t - I_t / kappa_q + fee accrual, as a share of
    the quarter's distribution, by fraction of the quarter elapsed; median and quartiles across quarters.
    The fund holds constituents' dividends as cash from their ex-dates to its own, so its price against the index
    traces when the index pays."""
    px = D.closes([index_sym, etf]).dropna()
    q = quarterly_distributions(etf)
    rows = []
    for k in range(1, len(q)):
        t0, t1, amt = q.ex_date.iloc[k - 1], q.ex_date.iloc[k], q.amount.iloc[k]
        w = px[(px.index >= t0) & (px.index < t1)]
        if len(w) < 30 or amt <= 0:
            continue
        kappa = w[index_sym].iloc[0] / w[etf].iloc[0]
        span = (t1 - t0).days
        frac = np.array([(d - t0).days / span for d in w.index])
        fee = w[etf].values * fee_bp / 1e4 * frac * span / 365.0
        A = (w[etf].values - w[index_sym].values / kappa + fee) / amt
        for f, a in zip(frac, A):
            rows.append({"quarter_end": q.quarter_end.iloc[k], "frac": f, "share": a})
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame({"frac": np.linspace(0, 1, n_bins + 1), "share": np.linspace(0, 1, n_bins + 1), "lo": np.nan, "hi": np.nan, "n": 0})
    df["bin"] = np.minimum((df.frac * n_bins).astype(int), n_bins - 1)
    g = df.groupby("bin").share
    prof = pd.DataFrame({"frac": (np.arange(n_bins) + 0.5) / n_bins, "share": g.median(), "lo": g.quantile(0.25), "hi": g.quantile(0.75), "n": g.size()}).reset_index(drop=True)
    prof["share"] = np.clip(prof.share.cummax(), 0, 1)
    return prof


def profile_fn(prof: pd.DataFrame | None):
    """Cumulative share of the quarter's dividends gone ex by fraction f of the quarter; None -> uniform accrual."""
    if prof is None or prof.empty or prof["n"].sum() == 0:
        return lambda f: np.clip(f, 0, 1)
    xs = np.concatenate([[0.0], prof.frac.values, [1.0]])
    ys = np.concatenate([[0.0], prof.share.values, [1.0]])
    return lambda f: np.interp(np.clip(f, 0, 1), xs, ys)


@lru_cache(maxsize=20000)
def _quarter_bounds(d):
    return C.quarter_bounds(d)


def dividend_points(q: pd.DataFrame, kappa: float, asof, t_end, prof=None, fee_bp: float = 0.0, etf_price: float = np.nan) -> float:
    """Expected index dividend points going ex in (asof, t_end]: for every dividend quarter touched, the point-in-time
    forecast of the fund's distribution (grossed up by the fund's fee, which is paid out of the dividend income),
    times kappa, times the share of that quarter's accrual that falls inside the window."""
    p = profile_fn(prof)
    t, T = pd.Timestamp(asof).normalize(), pd.Timestamp(t_end).normalize()
    if T <= t:
        return 0.0
    total, cur = 0.0, t
    while cur < T:
        q0, q1 = _quarter_bounds(cur)
        amt = forecast_quarter(q, asof, q1)
        if np.isnan(amt):
            amt = 0.0
        if fee_bp and pd.notna(etf_price):
            amt += etf_price * fee_bp / 1e4 * (q1 - q0).days / 365.0
        f0 = (cur - q0).days / (q1 - q0).days
        f1 = min((T - q0).days / (q1 - q0).days, 1.0)
        total += amt * kappa * float(p(f1) - p(f0))
        cur = q1
    return total


# ----------------------------------------------------------------------------- futures fair value
def kappa_series(index_sym: str, etf: str) -> pd.Series:
    """I/E measured at each fund ex-date close (the cum-dividend baseline of the following quarter), stepped forward."""
    px = D.closes([index_sym, etf]).dropna()
    q = quarterly_distributions(etf)
    k = {}
    for x in q.ex_date:
        w = px[px.index >= x]
        if len(w):
            k[w.index[0]] = w[index_sym].iloc[0] / w[etf].iloc[0]
    if not k:
        return pd.Series(px[index_sym] / px[etf], index=px.index)
    s = pd.Series(k).sort_index()
    return s.reindex(px.index, method="ffill").bfill()


def fv_context(index_sym: str, etf: str, currency: str = "USD") -> dict:
    """The tables futures_fair_value needs, computed once per pair."""
    px = D.closes([index_sym, etf])
    return {"I": px[index_sym], "E": px[etf], "q": quarterly_distributions(etf), "kap": kappa_series(index_sym, etf), "r": financing_curve(currency)}


def futures_fair_value(F: pd.Series, expiry, index_sym: str, etf: str, fee_bp: float, currency: str = "USD",
                       prof: pd.DataFrame | None = None, rate: str = "bill", index_px: pd.Series | None = None, ctx: dict | None = None) -> pd.DataFrame:
    """Per date: I, F, tau, r, D (expected dividend points to expiry), F*, richness rho (bp), r_impl, spread s (bp/yr).
    F is a date-indexed series of the contract's price marked at the cash close."""
    T = pd.Timestamp(expiry)
    ctx = ctx or fv_context(index_sym, etf, currency)
    I = ctx["I"] if index_px is None else index_px
    q, kap, E, r = ctx["q"], ctx["kap"], ctx["E"], ctx["r"]
    df = pd.DataFrame({"F": F}).join(I.rename("I"), how="inner").dropna()
    df = df[df.index < T]
    if df.empty:
        return df
    days = np.array([C.days_to(d, T) for d in df.index])
    df["days"] = days
    df["tau"] = days / 360.0
    df["r"] = rate_series(r, df.index, days, rate)
    df["D"] = [dividend_points(q, float(kap.get(d, kap.iloc[-1])), d, T, prof, fee_bp, float(E.get(d, np.nan))) for d in df.index]
    pv = df.D / (1 + df.r * df.tau)
    df["F_fair"] = (df.I - pv) * (1 + df.r * df.tau)
    df["rho_bp"] = 1e4 * (df.F - df.F_fair) / df.I
    df["r_impl"] = ((df.F + df.D) / df.I - 1) / df.tau
    df["spread_bp"] = 1e4 * (df.r_impl - df.r)
    df["contract_days"] = days
    return df


def etf_premium(index_sym: str, etf: str, fee_bp: float, prof: pd.DataFrame | None = None) -> pd.DataFrame:
    """Daily fund premium to its modelled fair price (bp), with the modelled accrual and the measured one."""
    px = D.closes([index_sym, etf]).dropna()
    q = quarterly_distributions(etf)
    p = profile_fn(prof)
    rows = []
    for k in range(1, len(q)):
        t0, t1 = q.ex_date.iloc[k - 1], q.ex_date.iloc[k]
        w = px[(px.index >= t0) & (px.index < t1)]
        if w.empty:
            continue
        kappa = w[index_sym].iloc[0] / w[etf].iloc[0]
        span = (t1 - t0).days
        for d in w.index:
            f = (d - t0).days / span
            amt = forecast_quarter(q, d, q.quarter_end.iloc[k])
            fee = w.at[d, etf] * fee_bp / 1e4 * f * span / 365.0
            A_hat = (0.0 if np.isnan(amt) else amt) * float(p(f)) - fee
            E_fair = w.at[d, index_sym] / kappa + A_hat
            rows.append({"date": d, "I": w.at[d, index_sym], "E": w.at[d, etf], "kappa": kappa, "frac": f, "A_model": A_hat,
                         "A_meas": w.at[d, etf] - w.at[d, index_sym] / kappa, "E_fair": E_fair, "prem_bp": 1e4 * (w.at[d, etf] - E_fair) / w.at[d, etf]})
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


# ----------------------------------------------------------------------------- mean reversion
def ar1(x: np.ndarray) -> tuple[float, float, float]:
    """OLS x_{t+1} = c + phi x_t + e.  Returns phi, half-life in steps, residual sd."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 10:
        return np.nan, np.nan, np.nan
    a, b = x[:-1], x[1:]
    A = np.column_stack([np.ones_like(a), a])
    beta, *_ = np.linalg.lstsq(A, b, rcond=None)
    phi = float(beta[1])
    res = b - A @ beta
    hl = -np.log(2) / np.log(phi) if 0 < phi < 1 else np.inf if phi >= 1 else 0.0
    return phi, float(hl), float(res.std())


def ar1_iv(x: np.ndarray) -> tuple[float, float]:
    """AR(1) under i.i.d. measurement noise (an observed ARMA(1,1)): phi = gamma(2) / gamma(1), the ratio of the lag-2
    to the lag-1 autocovariance, which the noise does not touch.  Used on series whose legs are marked at different
    times (the 17:00 futures close against the 16:00 cash close), where OLS reads the noise as fast mean reversion."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 30:
        return np.nan, np.nan
    x = x - x.mean()
    g1 = np.mean(x[1:] * x[:-1])
    g2 = np.mean(x[2:] * x[:-2])
    if g1 <= 0 or g2 <= 0:
        return np.nan, np.nan
    phi = float(min(g2 / g1, 0.9999))
    return phi, float(-np.log(2) / np.log(phi))


def half_life(x: pd.Series | np.ndarray, block: int = 20, n_boot: int = 400, seed: int = 0) -> dict:
    """AR(1) half-life with a circular block-bootstrap interval (blocks of `block` steps).  Steps are whatever the
    series is sampled at (days, hours, minutes).  Also the noise-robust estimate (ar1_iv)."""
    x = np.asarray(pd.Series(x).dropna(), float)
    phi, hl, sd = ar1(x)
    phi_iv, hl_iv = ar1_iv(x)
    rng = np.random.default_rng(seed)
    n = len(x)
    hls, phis, hls_iv = [], [], []
    if n > 2 * block:
        nb = int(np.ceil(n / block))
        for _ in range(n_boot):
            starts = rng.integers(0, n, nb)
            idx = np.concatenate([(s + np.arange(block)) % n for s in starts])[:n]
            p, h, _ = ar1(x[idx])
            phis.append(p)
            hls.append(h)
            hls_iv.append(ar1_iv(x[idx])[1])
    hls = np.array(hls)
    hls_iv = np.array(hls_iv, float)
    return {"n": int(n), "phi": phi, "half_life": hl, "resid_sd": sd, "mean": float(np.mean(x)) if n else np.nan, "sd": float(np.std(x)) if n else np.nan,
            "hl_lo": float(np.nanpercentile(hls, 2.5)) if len(hls) else np.nan, "hl_hi": float(np.nanpercentile(hls, 97.5)) if len(hls) else np.nan,
            "phi_lo": float(np.nanpercentile(phis, 2.5)) if len(phis) else np.nan, "phi_hi": float(np.nanpercentile(phis, 97.5)) if len(phis) else np.nan,
            "phi_iv": phi_iv, "half_life_iv": hl_iv,
            "hl_iv_lo": float(np.nanpercentile(hls_iv, 2.5)) if np.isfinite(hls_iv).any() else np.nan, "hl_iv_hi": float(np.nanpercentile(hls_iv, 97.5)) if np.isfinite(hls_iv).any() else np.nan}


def forecast_mse(x: np.ndarray, phi: float) -> float:
    """One-step-ahead MSE of x_{t+1} = mean + phi (x_t - mean) with a given phi (the transfer test's yardstick)."""
    x = np.asarray(pd.Series(x).dropna(), float)
    m = x.mean()
    pred = m + phi * (x[:-1] - m)
    return float(np.mean((x[1:] - pred) ** 2))


def half_life_segments(segs: list, n_boot: int = 300, seed: int = 0) -> dict:
    """AR(1) half-life pooled over independent segments (e.g. the within-day deviations of each day), with a
    segment bootstrap.  Consecutive pairs are formed inside segments only."""
    segs = [np.asarray(s, float) for s in segs if len(s) > 5]
    if not segs:
        return {"n_segments": 0, "n": 0, "phi": np.nan, "half_life": np.nan, "hl_lo": np.nan, "hl_hi": np.nan}

    def fit(idx):
        a = np.concatenate([segs[i][:-1] for i in idx])
        b = np.concatenate([segs[i][1:] for i in idx])
        A = np.column_stack([np.ones_like(a), a])
        beta, *_ = np.linalg.lstsq(A, b, rcond=None)
        phi = float(beta[1])
        return phi, (-np.log(2) / np.log(phi) if 0 < phi < 1 else np.inf if phi >= 1 else 0.0)

    phi, hl = fit(range(len(segs)))
    rng = np.random.default_rng(seed)
    hls = [fit(rng.integers(0, len(segs), len(segs)))[1] for _ in range(n_boot)] if len(segs) > 1 else []
    return {"n_segments": len(segs), "n": int(sum(len(s) for s in segs)), "phi": phi, "half_life": float(hl),
            "hl_lo": float(np.nanpercentile(hls, 2.5)) if hls else np.nan, "hl_hi": float(np.nanpercentile(hls, 97.5)) if hls else np.nan}
