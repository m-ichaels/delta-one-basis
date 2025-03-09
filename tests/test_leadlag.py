import numpy as np
import pandas as pd

from d1basis import leadlag as LL


def test_hy_synchronous_equals_realised_covariance():
    rng = np.random.default_rng(0)
    t = np.arange(500, dtype=float)
    x = np.cumsum(rng.standard_normal(500))
    y = np.cumsum(rng.standard_normal(500))
    assert abs(LL.hy_cov(t, x, t, y, 0.0) - np.sum(np.diff(x) * np.diff(y))) < 1e-9
    # a whole-step shift of a synchronous grid is the lagged cross-covariance
    assert abs(LL.hy_cov(t, x, t, y, 1.0) - np.sum(np.diff(x)[:-1] * np.diff(y)[1:])) < 1e-9


def test_hrv_recovers_known_lag_on_asynchronous_ticks():
    tx, x, ty, y = LL.simulate_lagged(n=20000, lag=2.0, rho=0.8, seed=3)
    grid = np.arange(-6, 6.01, 0.25)
    c = LL.contrast(tx, x, ty, y, grid)
    s = LL.summarise(c)
    assert abs(s["theta_star"] - 2.0) <= 0.5          # X leads Y by 2 units
    assert s["llr"] > 2.0 and s["rho_star"] > 0.3
    # the reverse ordering flips the sign
    c2 = LL.contrast(ty, y, tx, x, grid)
    assert abs(LL.summarise(c2)["theta_star"] + 2.0) <= 0.5


def test_day_bootstrap_interval_contains_estimate():
    tx, x, ty, y = LL.simulate_lagged(n=12000, lag=1.5, rho=0.7, seed=4)
    grid = np.arange(-5, 5.01, 0.25)
    dx = (tx // 1000).astype(int)
    dy = (ty // 1000).astype(int)
    covs, sxs, sys_, days = LL.per_day(tx, x, ty, y, dx, dy, grid)
    out, pooled = LL.bootstrap(covs, sxs, sys_, grid, n_boot=100)
    assert out["n_days"] == len(days) >= 10
    assert out["theta_lo"] <= out["theta_star"] <= out["theta_hi"]
    assert out["p_x_leads"] > 0.9


def test_epps_rises_with_interval():
    tx, x, ty, y = LL.simulate_lagged(n=30000, lag=2.0, rho=0.9, seed=5)
    e = LL.epps(tx, x, ty, y, intervals_s=(1, 4, 16, 64), day_x=np.zeros(len(tx), int), day_y=np.zeros(len(ty), int))
    assert e.correlation.iloc[-1] > e.correlation.iloc[0] + 0.2


def test_series_from_bars():
    idx = pd.date_range("2026-09-14 13:30", periods=5, freq="1min", tz="UTC")
    s = pd.Series([100.0, 101.0, np.nan, 102.0, 103.0], index=idx)
    t, lx, day = LL.series_from_bars(s, 60)
    assert len(t) == 4 and t[1] - t[0] == 60 and abs(lx[0] - np.log(100)) < 1e-12
    assert len(set(day)) == 1


def test_series_from_ticks_collapses_ties_and_self_contrast_is_one():
    ts = pd.to_datetime(["2026-09-14 13:30:00.000", "2026-09-14 13:30:00.000", "2026-09-14 13:30:00.250", "2026-09-14 13:30:01.000"], utc=True)
    t, lx, day = LL.series_from_ticks(pd.Series(ts), pd.Series([100.0, 100.5, 101.0, 101.5]))
    assert len(t) == 3 and abs(lx[0] - np.log(100.5)) < 1e-12
    c = LL.contrast(t, lx, t, lx, np.array([0.0]))
    assert abs(c.rho.iloc[0] - 1.0) < 1e-12
