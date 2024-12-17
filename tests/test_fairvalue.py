import numpy as np
import pandas as pd

from d1basis import fairvalue as FV


def _q():
    return pd.DataFrame({"ex_date": pd.to_datetime(["2024-03-15", "2024-06-21", "2024-09-20", "2024-12-20", "2025-03-21", "2025-06-20", "2025-09-19", "2025-12-19"]),
                         "amount": [1.0, 1.1, 1.2, 1.3, 1.1, 1.21, 1.32, 1.43],
                         "quarter_end": pd.to_datetime(["2024-03-15", "2024-06-21", "2024-09-20", "2024-12-20", "2025-03-21", "2025-06-20", "2025-09-19", "2025-12-19"])})


def test_fair_value_known_answer():
    # I = 100, r = 5 %, tau = 0.5, D = 1:  F* = (I - D / (1 + r tau)) (1 + r tau) = I (1 + r tau) - D = 101.5
    I, r, tau, Dv = 100.0, 0.05, 0.5, 1.0
    pv = Dv / (1 + r * tau)
    F_fair = (I - pv) * (1 + r * tau)
    assert abs(F_fair - 101.5) < 1e-12
    # implied financing from the fair price is the input rate, spread zero
    r_impl = ((F_fair + Dv) / I - 1) / tau
    assert abs(r_impl - r) < 1e-12


def test_forecast_quarter_point_in_time():
    q = _q()
    # as of Jan 2026 the last four quarters sum 5.06, the four before 4.6: growth 1.1; same quarter a year earlier
    # (Mar 2025) 1.1 -> seasonal 1.21; median of the last four (1.1, 1.21, 1.32, 1.43) = 1.265; the blend is the mean
    f = FV.forecast_quarter(q, "2026-01-05", "2026-03-20")
    assert abs(f - 0.5 * (1.21 + 1.265)) < 1e-9
    # as of Feb 2025 only the first five are known: base is Mar 2024 (1.0), fewer than 8 known -> growth 1; median(1.0, 1.1, 1.2, 1.3) = 1.15
    assert abs(FV.forecast_quarter(q, "2025-02-01", "2025-03-21") - 0.5 * (1.0 + 1.15)) < 1e-9


def test_dividend_points_uniform_profile():
    q = _q()
    kappa = 10.0
    # inside the Sep-Dec 2025 quarter (19 Sep .. 19 Dec, 91 days), from 19 Oct (30 days in) to expiry: 61/91 of the quarter's forecast
    amt = FV.forecast_quarter(q, "2025-10-19", pd.Timestamp("2025-12-19"))
    d = FV.dividend_points(q, kappa, "2025-10-19", "2025-12-19", None)
    assert abs(d - amt * kappa * (61 / 91)) < 1e-9
    # a window that ends before it starts is empty
    assert FV.dividend_points(q, kappa, "2025-10-19", "2025-10-19", None) == 0.0


def test_profile_fn_monotone():
    prof = pd.DataFrame({"frac": [0.25, 0.75], "share": [0.2, 0.9], "lo": 0, "hi": 1, "n": [10, 10]})
    p = FV.profile_fn(prof)
    assert p(0.0) == 0.0 and abs(p(1.0) - 1.0) < 1e-12 and 0.2 < p(0.5) < 0.9
    u = FV.profile_fn(None)
    assert u(0.3) == 0.3


def test_ar1_half_life_and_noise_correction():
    rng = np.random.default_rng(1)
    phi, n = 0.9, 20000
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + rng.standard_normal()
    p, hl, _ = FV.ar1(x)
    assert abs(p - phi) < 0.02 and abs(hl - (-np.log(2) / np.log(phi))) < 1.0
    noisy = x + 3.0 * rng.standard_normal(n)      # heavy i.i.d. measurement noise
    p_ols, _, _ = FV.ar1(noisy)
    p_iv, _ = FV.ar1_iv(noisy)
    assert p_ols < 0.6                              # OLS reads the noise as fast reversion
    assert abs(p_iv - phi) < 0.05                   # the autocovariance ratio does not
    out = FV.half_life(noisy, block=50, n_boot=50)
    assert out["hl_iv_lo"] <= out["half_life_iv"] <= out["hl_iv_hi"]


def test_half_life_segments():
    rng = np.random.default_rng(2)
    segs = []
    for _ in range(30):
        x = np.zeros(300)
        for t in range(1, 300):
            x[t] = 0.8 * x[t - 1] + rng.standard_normal()
        segs.append(x)
    out = FV.half_life_segments(segs, n_boot=50)
    assert abs(out["phi"] - 0.8) < 0.03 and out["n_segments"] == 30
    assert out["hl_lo"] <= out["half_life"] <= out["hl_hi"]
