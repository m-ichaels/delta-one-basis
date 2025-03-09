"""Lead-lag between two price series observed at their own times.

Hayashi-Yoshida (2005) covariance of two asynchronous increment series with a time shift theta applied to the second,
    HY(theta) = sum_i sum_j dX_i dY_j 1[ (t_{i-1}, t_i] overlaps (s_{j-1} - theta, s_j - theta] ],
the Hoffmann-Rosenbaum-Vetter (2013) lead-lag estimator theta* = argmax_theta |HY(theta)| over a grid, the normalised
contrast rho(theta) = HY(theta) / sqrt(sum dX^2 sum dY^2), and the Huth-Abergel (2014) lead-lag ratio
    LLR = sum_{theta>0} rho(theta)^2 / sum_{theta<0} rho(theta)^2 .
theta > 0 means X leads Y by theta (Y's increment at s is matched with X's increment around s - theta).

Series are (times in seconds, log prices) with one observation per change; bars pass their bar-end times and closes.
The overlap sum is computed with two searchsorted calls and a cumulative sum, O((n + m) log m) per theta.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def hy_cov(tx: np.ndarray, x: np.ndarray, ty: np.ndarray, y: np.ndarray, theta: float = 0.0) -> float:
    """HY(theta) for observation times tx, ty (seconds, increasing) and log prices x, y."""
    if len(tx) < 2 or len(ty) < 2:
        return 0.0
    dx = np.diff(x)
    dy = np.diff(y)
    a, b = tx[:-1], tx[1:]                 # X intervals (a_i, b_i]
    s0, s1 = ty[:-1] - theta, ty[1:] - theta  # shifted Y intervals (s0_j, s1_j]
    C = np.concatenate([[0.0], np.cumsum(dy)])
    j_lo = np.searchsorted(s1, a, side="right")   # first j with s1_j > a_i
    j_hi = np.searchsorted(s0, b, side="left")    # number of j with s0_j < b_i  -> last index + 1
    j_hi = np.maximum(j_hi, j_lo)
    return float(np.sum(dx * (C[j_hi] - C[j_lo])))


def contrast(tx, x, ty, y, grid: np.ndarray) -> pd.DataFrame:
    """rho(theta) over the grid, plus the raw HY covariances."""
    sx = float(np.sum(np.diff(x) ** 2))
    sy = float(np.sum(np.diff(y) ** 2))
    norm = np.sqrt(sx * sy) if sx > 0 and sy > 0 else np.nan
    cov = np.array([hy_cov(tx, x, ty, y, th) for th in grid])
    return pd.DataFrame({"theta": grid, "cov": cov, "rho": cov / norm})


def summarise(df: pd.DataFrame) -> dict:
    """theta* (argmax |rho|), rho at theta*, rho at 0, LLR, and the horizon beyond which |rho| has decayed to half of
    its peak on the leading side."""
    r = df.rho.values
    th = df.theta.values
    k = int(np.nanargmax(np.abs(r)))
    pos = r[th > 0] ** 2
    neg = r[th < 0] ** 2
    llr = float(pos.sum() / neg.sum()) if neg.sum() > 0 else np.inf
    peak = abs(r[k])
    side = th > 0 if th[k] > 0 else th < 0
    tail = df[side & (np.abs(df.rho) < 0.5 * peak)]
    if th[k] > 0:
        half = float(tail.theta.min()) if len(tail) else np.nan
    else:
        half = float(tail.theta.max()) if len(tail) else np.nan
    return {"theta_star": float(th[k]), "rho_star": float(r[k]), "rho_0": float(r[np.argmin(np.abs(th))]), "llr": llr, "half_horizon": half, "rho_max_abs": float(peak)}


def per_day(tx, x, ty, y, day_x: np.ndarray, day_y: np.ndarray, grid: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, list]:
    """HY covariance per day over the grid (rows = days) with the per-day sums of squares, for the day bootstrap."""
    days = sorted(set(day_x) & set(day_y))
    covs, sxs, sys_ = [], [], []
    for d in days:
        mx, my = day_x == d, day_y == d
        if mx.sum() < 3 or my.sum() < 3:
            continue
        covs.append([hy_cov(tx[mx], x[mx], ty[my], y[my], th) for th in grid])
        sxs.append(np.sum(np.diff(x[mx]) ** 2))
        sys_.append(np.sum(np.diff(y[my]) ** 2))
    return np.array(covs), np.array(sxs), np.array(sys_), days


def bootstrap(covs: np.ndarray, sxs: np.ndarray, sys_: np.ndarray, grid: np.ndarray, n_boot: int = 300, seed: int = 0) -> dict:
    """Resample days with replacement; theta*, LLR and rho* intervals.  Also the pooled point estimate."""
    n = len(covs)
    if n == 0:
        return {"n_days": 0}
    pooled = pd.DataFrame({"theta": grid, "cov": covs.sum(0), "rho": covs.sum(0) / np.sqrt(sxs.sum() * sys_.sum())})
    out = summarise(pooled)
    out["n_days"] = int(n)
    rng = np.random.default_rng(seed)
    ths, llrs, rhos = [], [], []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        c = covs[idx].sum(0)
        s = summarise(pd.DataFrame({"theta": grid, "cov": c, "rho": c / np.sqrt(sxs[idx].sum() * sys_[idx].sum())}))
        ths.append(s["theta_star"])
        llrs.append(s["llr"])
        rhos.append(s["rho_star"])
    ths, llrs = np.array(ths), np.array(llrs)
    llrs = llrs[np.isfinite(llrs)]
    out.update({"theta_lo": float(np.percentile(ths, 2.5)), "theta_hi": float(np.percentile(ths, 97.5)),
                "llr_lo": float(np.percentile(llrs, 2.5)) if len(llrs) else np.nan, "llr_hi": float(np.percentile(llrs, 97.5)) if len(llrs) else np.nan,
                "p_x_leads": float(np.mean(ths > 0)), "rho_star_lo": float(np.percentile(rhos, 2.5)), "rho_star_hi": float(np.percentile(rhos, 97.5))})
    return out, pooled


def sample_previous_tick(t: np.ndarray, x: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Previous-tick sampling of a series on a synchronous grid (NaN before the first observation)."""
    idx = np.searchsorted(t, grid, side="right") - 1
    out = np.where(idx >= 0, x[np.clip(idx, 0, len(x) - 1)], np.nan)
    return out


def epps(tx, x, ty, y, intervals_s=(60, 120, 300, 600, 1800, 3600), day_x=None, day_y=None) -> pd.DataFrame:
    """Correlation of synchronously sampled returns by sampling interval (the Epps curve), day by day."""
    rows = []
    days = sorted(set(day_x)) if day_x is not None else [None]
    for dt_ in intervals_s:
        num, den_x, den_y = 0.0, 0.0, 0.0
        for d in days:
            mx = day_x == d if d is not None else np.ones(len(tx), bool)
            my = day_y == d if d is not None else np.ones(len(ty), bool)
            if mx.sum() < 3 or my.sum() < 3:
                continue
            t0 = max(tx[mx][0], ty[my][0])
            t1 = min(tx[mx][-1], ty[my][-1])
            if t1 - t0 < 2 * dt_:
                continue
            g = np.arange(t0, t1 + 1e-9, dt_)
            rx = np.diff(sample_previous_tick(tx[mx], x[mx], g))
            ry = np.diff(sample_previous_tick(ty[my], y[my], g))
            ok = ~np.isnan(rx) & ~np.isnan(ry)
            num += np.sum(rx[ok] * ry[ok])
            den_x += np.sum(rx[ok] ** 2)
            den_y += np.sum(ry[ok] ** 2)
        rows.append({"interval_s": dt_, "correlation": num / np.sqrt(den_x * den_y) if den_x > 0 and den_y > 0 else np.nan})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- series builders
ORIGIN = pd.Timestamp("2020-01-01", tz="UTC")


def _seconds(idx: pd.DatetimeIndex) -> np.ndarray:
    """Seconds since 2020-01-01 as float64: a recent origin keeps nanosecond ticks distinct (float64 at 2e8 s resolves
    ~30 ns; at the Unix epoch it would be ~240 ns)."""
    return ((idx.tz_convert("UTC") - ORIGIN).to_numpy().astype("timedelta64[ns]").astype("int64") / 1e9).astype(float)


def _day_id(idx: pd.DatetimeIndex, tz: str = "America/New_York") -> np.ndarray:
    loc = idx.tz_convert(tz).normalize().tz_localize(None)
    return ((loc - pd.Timestamp("1970-01-01")).days).to_numpy().astype(int)


def series_from_bars(close: pd.Series, bar_seconds: int, tz: str = "America/New_York") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(t in seconds at bar end, log close, day id) from a UTC-indexed close series (bar labels at the bar start)."""
    s = close.dropna()
    return _seconds(s.index) + bar_seconds, np.log(s.values.astype(float)), _day_id(s.index, tz)


def series_from_ticks(ts: pd.Series, price: pd.Series, tz: str = "America/New_York") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ticks with the same timestamp are collapsed to the last one: HY needs strictly increasing times (a zero-length
    interval overlaps nothing and would drop its increment from the numerator only)."""
    s = pd.Series(np.asarray(price, float), index=pd.DatetimeIndex(pd.to_datetime(ts, utc=True)))
    s = s[~s.index.duplicated(keep="last")].sort_index()
    t = _seconds(s.index)
    keep = np.concatenate([np.diff(t) > 0, [True]])   # last of any run that still ties after the float conversion
    return t[keep], np.log(s.values[keep]), _day_id(s.index[keep], tz)


def run_pair(tx, x, dx, ty, y, dy, grid: np.ndarray, n_boot: int = 300, seed: int = 0) -> tuple[dict, pd.DataFrame]:
    covs, sxs, sys_, days = per_day(tx, x, ty, y, dx, dy, grid)
    if len(covs) == 0:
        return {"n_days": 0}, pd.DataFrame({"theta": grid, "rho": np.nan})
    out, pooled = bootstrap(covs, sxs, sys_, grid, n_boot, seed)
    return out, pooled


def simulate_lagged(n: int = 20000, lag: float = 2.0, rho: float = 0.8, dt_x: float = 0.7, dt_y: float = 1.1, seed: int = 0):
    """Two Brownian motions, Y = rho * X(t - lag) + noise, each observed on its own Poisson clock - the known-answer
    case of Hoffmann-Rosenbaum-Vetter."""
    rng = np.random.default_rng(seed)
    T = n
    fine = 0.05
    m = int(T / fine)
    w = rng.standard_normal(m) * np.sqrt(fine)
    z = rng.standard_normal(m) * np.sqrt(fine)
    X = np.cumsum(w)
    Y = rho * np.concatenate([np.zeros(int(lag / fine)), X[: m - int(lag / fine)]]) + np.sqrt(1 - rho**2) * np.cumsum(z)
    tgrid = np.arange(m) * fine
    tx = np.sort(rng.uniform(0, T, int(T / dt_x)))
    ty = np.sort(rng.uniform(0, T, int(T / dt_y)))
    x = np.interp(tx, tgrid, X)
    y = np.interp(ty, tgrid, Y)
    return tx, x, ty, y
