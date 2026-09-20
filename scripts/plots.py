#!/usr/bin/env python3
"""Figures from results/run.json and data/derived -> results/figures/*.png.   python scripts/plots.py"""
import json
import os
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from d1basis import data as D  # noqa: E402

FIG = os.path.join(ROOT, "results", "figures")
os.makedirs(FIG, exist_ok=True)
R = json.load(open(os.path.join(ROOT, "results", "run.json")))
PAIRS = R["pairs"]
plt.rcParams.update({"figure.dpi": 130, "font.size": 8.5, "axes.titlesize": 9, "axes.grid": True, "grid.alpha": 0.3, "legend.fontsize": 7.5})
COL = {"ES": "C0", "NQ": "C1", "RTY": "C2", "SX5E": "C3"}


def derived(name):
    p = os.path.join(D.DERIVED, name + ".parquet")
    return pd.read_parquet(p) if os.path.exists(p) else pd.DataFrame()


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, name))
    plt.close(fig)
    print(name)


# 1. accrual profiles
fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
for k, p in PAIRS.items():
    pr = pd.DataFrame(p["accrual_profile"])
    if pr["n"].sum() == 0:
        continue
    ax[0].plot(pr.frac, pr.share, color=COL[k], label=f"{p['etf']} / {p['label']}")
    if k == "ES":
        ax[0].fill_between(pr.frac, pr.lo, pr.hi, color=COL[k], alpha=0.15, label="SPY interquartile")
ax[0].plot([0, 1], [0, 1], "k--", lw=0.8, label="uniform")
ax[0].set_xlabel("fraction of the dividend quarter elapsed")
ax[0].set_ylabel("share of the quarter's dividends gone ex")
ax[0].set_title("When the index pays: accrual measured from the fund's price against the index")
ax[0].legend()
prem = derived("etf_premium_ES")
if not prem.empty:
    prem["date"] = pd.to_datetime(prem.date)
    w = prem[prem.date >= prem.date.max() - pd.Timedelta(days=200)]
    ax[1].plot(w.date, 1e4 * w.A_meas / w.E, color="C0", lw=0.9, label="measured: SPY - SPX / kappa")
    ax[1].plot(w.date, 1e4 * w.A_model / w.E, color="k", lw=0.9, ls="--", label="modelled accrual - fee")
    ax[1].set_ylabel("bp of the fund price")
    ax[1].set_title("SPY against the index inside the quarter: the dividend sawtooth")
    ax[1].legend()
    ax[1].tick_params(axis="x", rotation=30)
save(fig, "accrual_profile.png")

# 2. basis history: implied financing spread by year and the last year daily
fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
for k, p in PAIRS.items():
    fv = p.get("fair_value")
    if not fv:
        continue
    by = pd.DataFrame(fv["by_year"])
    ax[0].plot(by.year, by.spread_median, marker="o", ms=3, color=COL[k], label=f"{k} front: median implied financing - bills")
ax[0].axhline(0, color="k", lw=0.6)
ax[0].set_ylabel("bp per year")
ax[0].set_title("Implied financing spread of the front contract by year (days to expiry >= 20)")
ax[0].legend()
pn = derived("panel_ES")
if not pn.empty:
    pn["date"] = pd.to_datetime(pn.date)
    w = pn[(pn.date >= pn.date.max() - pd.Timedelta(days=370)) & (pn.days >= 20)]
    ax[1].plot(w.date, w.spread_bp, color="C0", lw=0.8, label="ES front, implied financing - bills")
    ax[1].plot(w.date, w.fwd_spread_bp, color="C3", lw=0.8, label="ES front -> second calendar spread, implied")
    m16 = w.mark.str.startswith("16:00")
    if m16.any():
        ax[1].scatter(w.date[m16], w.spread_bp[m16], s=4, color="C0", label="16:00 marks")
    ax[1].axhline(0, color="k", lw=0.6)
    ax[1].set_ylabel("bp per year")
    ax[1].set_title("The last year: front spread (17:00 close marks are noisy) and the forward spread")
    ax[1].legend()
    ax[1].tick_params(axis="x", rotation=30)
save(fig, "basis_history.png")

# 3. ETF premium
fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
for k, p in PAIRS.items():
    pr = derived(f"etf_premium_{k}")
    if pr.empty:
        continue
    pr["date"] = pd.to_datetime(pr.date)
    w = pr[pr.date >= pr.date.max() - pd.Timedelta(days=5 * 365)]
    ax[0].plot(w.date, w.prem_bp, lw=0.5, color=COL[k], alpha=0.8, label=f"{p['etf']} sd {w.prem_bp.std():.1f} bp")
ax[0].set_ylim(-60, 60)
ax[0].set_ylabel("bp")
ax[0].set_title("Fund premium to the modelled fair price, last five years")
ax[0].legend()
rows = []
for k, p in PAIRS.items():
    pb = p.get("etf_premium", {})
    if pb:
        rows.append({"pair": p["etf"], "own profile": pb["prem_sd_bp"], "SPY profile": pb["prem_sd_source_profile_bp"], "uniform": pb["prem_sd_uniform_bp"], "no accrual": pb["prem_sd_no_accrual_bp"]})
if rows:
    t = pd.DataFrame(rows).set_index("pair")
    t.plot.bar(ax=ax[1], width=0.8)
    ax[1].set_ylabel("sd of the premium, bp")
    ax[1].set_title("Accrual model transferred from SPY vs each fund's own vs none")
    ax[1].tick_params(axis="x", rotation=0)
save(fig, "etf_premium.png")

# 4. lead-lag contrast curves
keys = ["future_vs_etf", "future_vs_index", "etf_vs_index", "future_vs_basket", "etf_vs_basket"]
fig, axes = plt.subplots(1, len(PAIRS), figsize=(2.7 * len(PAIRS) + 1, 3.4), sharey=True)
for ax, (k, p) in zip(np.atleast_1d(axes), PAIRS.items()):
    curves = p.get("curves_1m", {})
    ll = p.get("leadlag_1m", {})
    for j, key in enumerate(keys):
        if key in curves:
            c = pd.DataFrame(curves[key])
            s = ll[key]
            ax.plot(c.theta / 60, c.rho, color=f"C{j}", lw=1, label=f"{key.replace('_', ' ')}: theta* {s['theta_star'] / 60:+.1f} min, LLR {s['llr']:.1f}")
    ax.axvline(0, color="k", lw=0.6)
    ax.set_xlim(-5, 5)
    ax.set_title(f"{p['label']}: HY contrast, 1-min bars, {ll.get('future_vs_etf', ll.get('etf_vs_index', {})).get('n_days', 0)} days")
    ax.set_xlabel("shift theta, minutes (> 0: first leg leads)")
    ax.legend(loc="upper left", fontsize=6.5)
np.atleast_1d(axes)[0].set_ylabel("rho(theta)")
save(fig, "leadlag.png")

# 5. lead-lag through time and the Epps curves
fig, ax = plt.subplots(1, 3, figsize=(12, 3.4))
for k, p in PAIRS.items():
    bd = p.get("by_day_1m", {})
    for key, ls in (("etf_vs_index", "-"), ("future_vs_etf", ":")):
        if key in bd:
            d = pd.DataFrame(bd[key])
            ax[0].plot(pd.to_datetime(d.day), d.llr, marker="o", ms=2.5, lw=0.8, ls=ls, color=COL[k], label=f"{k} {key.replace('_', ' ')}")
ax[0].axhline(1, color="k", lw=0.6)
ax[0].set_yscale("log")
ax[0].set_ylabel("lead-lag ratio (> 1: first leg leads)")
ax[0].set_title("Daily lead-lag ratio, 1-minute bars")
ax[0].legend()
ax[0].tick_params(axis="x", rotation=30)
for k, p in PAIRS.items():
    fr = p.get("firstrate", {})
    if fr:
        m = pd.DataFrame(fr["by_month"])
        ax[1].plot(m.month, m.llr, marker="o", ms=3, color=COL[k], label=f"{p['etf']} vs {fr['index_symbol']}: LLR by month")
ax[1].axhline(1, color="k", lw=0.6)
ax[1].set_title("ETF vs cash index, one year of 1-minute bars (FirstRate sample)")
ax[1].set_ylabel("lead-lag ratio (> 1: ETF leads)")
ax[1].tick_params(axis="x", rotation=60)
ax[1].legend()
for k, p in PAIRS.items():
    for key, ls in (("epps_future_etf", "-"), ("epps_etf_index", "--")):
        if key in p:
            e = pd.DataFrame(p[key])
            ax[2].plot(e.interval_s / 60, e.correlation, marker="o", ms=3, ls=ls, color=COL[k], label=f"{k} {key[5:].replace('_', ' vs ')}")
ax[2].set_xscale("log")
ax[2].set_xlabel("sampling interval, minutes")
ax[2].set_ylabel("return correlation")
ax[2].set_title("The Epps curve")
ax[2].legend()
save(fig, "leadlag_time.png")

# 6. minute basis on one day
mr = derived("minute_richness_ES")
if not mr.empty:
    mr["ts"] = pd.to_datetime(mr.ts, utc=True)
    day = mr.date.iloc[-1] if "date" in mr else None
    w = mr[mr.date == mr.date.max()]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.3))
    t = w.ts.dt.tz_convert("America/New_York")
    ax[0].plot(t, w.rho_index_bp, lw=0.8, label="richness vs S&P 500 index")
    ax[0].plot(t, w.rho_etf_bp, lw=0.8, label="richness vs SPY-implied index")
    ax[0].set_ylabel("bp")
    ax[0].set_title(f"ES richness to fair value minute by minute, {str(w.date.iloc[0])[:10]}")
    ax[0].legend()
    ax[0].tick_params(axis="x", rotation=30)
    mrs = PAIRS["ES"].get("minute_richness", {})
    for k, p in PAIRS.items():
        m = p.get("minute_richness")
        if not m:
            continue
        hi = m["half_life_vs_index_min"]
        he = m["half_life_vs_etf_min"]
        ax[1].errorbar([f"{k}\nvs index"], [hi["half_life"]], yerr=[[hi["half_life"] - hi["hl_lo"]], [hi["hl_hi"] - hi["half_life"]]], fmt="o", color=COL[k], capsize=3)
        ax[1].errorbar([f"{k}\nvs fund"], [he["half_life"]], yerr=[[he["half_life"] - he["hl_lo"]], [he["hl_hi"] - he["half_life"]]], fmt="s", color=COL[k], capsize=3)
    ax[1].set_ylabel("half-life, minutes")
    ax[1].set_title("Within-day half-life of the richness deviation (AR(1), day bootstrap)")
    save(fig, "minute_basis.png")

# 7. strategy
fig, ax = plt.subplots(1, 3, figsize=(13, 3.5))
for k, p in PAIRS.items():
    for label, axis in (("1600", ax[0]), ("long", ax[1])):
        sdf = derived(f"strategy_{k}_{label}")
        if sdf.empty:
            continue
        sdf["date"] = pd.to_datetime(sdf.date)
        st = p.get("strategy_1600" if label == "1600" else "strategy", {}).get("transferred", {})
        axis.plot(sdf.date, sdf.net_bp.fillna(0).cumsum(), color=COL[k], lw=1, label=f"{k}: {st.get('ann_net_bp', float('nan')):.0f} bp/yr [{st.get('ann_lo', float('nan')):.0f}, {st.get('ann_hi', float('nan')):.0f}], Sharpe {st.get('sharpe', float('nan')):.1f}")
ax[0].set_ylabel("cumulative net P&L, bp of notional")
ax[0].set_title("Both legs marked at 16:00: the z-score basis strategy, net of costs")
ax[1].set_title("The artefact: future at the 17:00 close against the 16:00 cash close")
for a in ax[:2]:
    a.legend(fontsize=6.5)
    a.tick_params(axis="x", rotation=30)
for k, p in PAIRS.items():
    c = p.get("strategy_1600", {}).get("carry", {})
    if c and c.get("rows"):
        r = pd.DataFrame(c["rows"])
        ax[2].scatter(r.spread_entry_bp, r.net_ann_bp, s=18, color=COL[k], label=f"{k}: {c['n']} contracts, mean {c['mean_net_ann_bp']:.0f} bp/yr net")
ax[2].axhline(0, color="k", lw=0.6)
ax[2].axvline(0, color="k", lw=0.6)
ax[2].set_xlabel("implied financing spread at entry (60 days out), bp/yr")
ax[2].set_ylabel("realised net return to the roll, bp/yr")
ax[2].set_title("Cash-and-carry to the roll, 16:00 marks")
ax[2].legend(fontsize=6.5)
save(fig, "strategy.png")

# 8. transfer table
tt = pd.DataFrame(R["transfer"]["rows"])
fig, ax = plt.subplots(1, 3, figsize=(12, 3.4))
x = np.arange(len(tt))
if "llr_own" in tt:
    ax[0].errorbar(x, tt.llr_own, yerr=[tt.llr_own - tt.llr_own_lo, tt.llr_own_hi - tt.llr_own], fmt="o", capsize=3, label="own LLR, ETF vs index (95 %)")
    if "llr_future_etf" in tt:
        m = tt.llr_future_etf.notna()
        ax[0].errorbar(x[m] + 0.15, tt.llr_future_etf[m], yerr=[tt.llr_future_etf[m] - tt.llr_future_etf_lo[m], tt.llr_future_etf_hi[m] - tt.llr_future_etf[m]], fmt="s", color="C2", capsize=3, label="own LLR, future vs ETF")
    src = tt[tt.is_source].iloc[0] if tt.is_source.any() else None
    if src is not None and pd.notna(src.get("llr_source_lo")):
        ax[0].axhspan(src.llr_source_lo, src.llr_source_hi, color="C0", alpha=0.12, label="ES interval")
    ax[0].axhline(1, color="k", lw=0.6)
    ax[0].set_xticks(x)
    ax[0].set_xticklabels(tt.pair, fontsize=8)
    ax[0].set_yscale("log")
    ax[0].set_ylabel("lead-lag ratio (> 1: first leg leads)")
    ax[0].set_title("Lead-lag by pair, 1-minute bars")
    ax[0].legend(fontsize=7)
if "hl_rho_own" in tt:
    m = tt.hl_rho_own.notna()
    ax[1].bar(x[m] - 0.2, tt.mse_ratio_transferred[m], 0.4, label="ES phi / own phi")
    ax[1].bar(x[m] + 0.2, tt.mse_ratio_random_walk[m], 0.4, label="random walk / own phi")
    ax[1].axhline(1, color="k", lw=0.6)
    ax[1].set_xticks(x[m])
    ax[1].set_xticklabels(tt.pair[m])
    ax[1].set_ylabel("one-step forecast MSE ratio")
    ax[1].set_title("Richness dynamics (16:00 marks): ES coefficient applied elsewhere")
    ax[1].legend()
if "strat_net_own" in tt:
    m = tt.strat_net_own.notna()
    ax[2].bar(x[m] - 0.2, tt.strat_net_own[m], 0.4, label="own in-sample parameters")
    ax[2].bar(x[m] + 0.2, tt.strat_net_transferred[m], 0.4, label="ES parameters")
    ax[2].errorbar(x[m] + 0.2, tt.strat_net_transferred[m], yerr=[tt.strat_net_transferred[m] - tt.strat_lo_transferred[m], tt.strat_hi_transferred[m] - tt.strat_net_transferred[m]], fmt="none", color="k", capsize=3)
    ax[2].set_xticks(x[m])
    ax[2].set_xticklabels(tt.pair[m])
    ax[2].set_ylabel("net bp per year")
    ax[2].set_title("Strategy on the 16:00-marked series, net of costs")
    ax[2].legend()
save(fig, "transfer.png")
