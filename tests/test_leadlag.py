import numpy as np
import pandas as pd
import pytest

from d1basis import data as D
from d1basis import leadlag as LL
from d1basis import run as RUN


def python_core(fn, *args):
    """fn(*args) with the compiled core switched off, i.e. on the Python reference path."""
    ext, LL._ext = LL._ext, None
    try:
        return fn(*args)
    finally:
        LL._ext = ext


def same_per_day(*args):
    """per_day(*args) on the compiled core and on the Python path: the same days, shapes and numbers (to 1e-12)."""
    c, p = LL.per_day(*args), python_core(LL.per_day, *args)
    assert c[3] == p[3]
    for u, v in zip(c[:3], p[:3]):
        assert u.shape == v.shape and np.max(np.abs(u - v), initial=0.0) <= 1e-12
    return c


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


@pytest.mark.skipif(not LL.HAVE_EXT, reason="compiled core not built")
def test_cpp_core_matches_python_on_random_asynchronous_series():
    rng = np.random.default_rng(11)
    grid = RUN.GRID_1M
    pairs = [LL.simulate_lagged(n=20000, lag=2.0, rho=0.8, seed=3)]     # long enough for numpy's blocked summation
    for _ in range(40):
        n, m = rng.integers(1, 600, 2)                                   # includes series with no increment
        tx, ty = np.sort(rng.uniform(0, 3600, n)), np.sort(rng.uniform(0, 3600, m))
        pairs.append((tx, np.cumsum(rng.standard_normal(n)) * 1e-3, ty, np.cumsum(rng.standard_normal(m)) * 1e-3))
    t = np.arange(50.0)                                                  # the two clocks share ticks
    pairs.append((t, np.cumsum(rng.standard_normal(50)), t[::2].copy(), np.cumsum(rng.standard_normal(25))))
    for tx, x, ty, y in pairs:
        a, b = LL.contrast(tx, x, ty, y, grid), python_core(LL.contrast, tx, x, ty, y, grid)
        assert len(a) == len(b) == len(grid) and np.max(np.abs(a["cov"].values - b["cov"].values)) <= 1e-12
        ids = rng.permutation(10)                                        # day ids out of time order
        same_per_day(tx, x, ty, y, ids[(tx // 400).astype(int) % 10], ids[(ty // 400).astype(int) % 10], grid)
        # rows of a day interleaved with other days', days seen by one series only, days under three rows
        same_per_day(tx, x, ty, y, rng.integers(0, 8, len(tx)), rng.integers(2, 10, len(ty)), grid)
    with pytest.raises(ValueError):                                      # the sweep needs sorted clocks
        LL.contrast(np.array([0.0, 2.0, 1.0]), np.zeros(3), t, np.zeros(50), grid)
    with pytest.raises(ValueError):
        LL.per_day(np.array([0.0, 2.0, 1.0]), np.zeros(3), t, np.zeros(50), np.zeros(3, int), np.zeros(50, int), grid)


@pytest.mark.skipif(not LL.HAVE_EXT, reason="compiled core not built")
def test_cpp_core_matches_python_on_checked_in_bars():
    """Every daily curve the pipeline computes for ES: future vs ETF and ETF vs index on the 1- and 2-minute bars, and
    SPY vs SPX over the FirstRate year, each on the pipeline's own grid."""
    cfg = D.pairs()["ES"]
    legs = []
    for iv, bar_s, grid in (("1m", 60, RUN.GRID_1M), ("2m", 120, RUN.GRID_2M)):
        etf = RUN.session(D.bar_closes(iv, [cfg["etf"]])[cfg["etf"]], cfg)
        idx = RUN.session(D.bar_closes(iv, [cfg["index"]])[cfg["index"]], cfg)
        fut = RUN.session(RUN.front_bars(cfg, iv), cfg)
        legs += [(fut, etf, bar_s, grid), (etf, idx, bar_s, grid)]
    w = D.bar_closes("1m", ["SPY", "SPX"], source="firstrate")
    w = w[D.session_mask(w.index, "America/New_York", "09:31", "16:00")]
    legs.append((w["SPY"].dropna(), w["SPX"].dropna(), 60, RUN.GRID_1M))
    for a, b, bar_s, grid in legs:
        ta, xa, da = LL.series_from_bars(a, bar_s)
        tb, xb, db = LL.series_from_bars(b, bar_s)
        assert same_per_day(ta, xa, tb, xb, da, db, grid)[0].shape[0] >= 15
