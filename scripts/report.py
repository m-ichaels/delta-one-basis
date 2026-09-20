#!/usr/bin/env python3
"""report.pdf from results/run.json and results/figures.   python scripts/report.py"""
import json
import os

import numpy as np
import pandas as pd
from fpdf import FPDF

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "results", "figures")
R = json.load(open(os.path.join(ROOT, "results", "run.json")))
P = R["pairs"]


def clean(s):
    return str(s).encode("latin-1", "replace").decode("latin-1")


def f(x, d=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    return "> 500" if x > 500 and d == 0 else f"{x:.{d}f}"


class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 6, "delta-one-basis: ETF, index future and cash basket - fair value, lead-lag, and what transfers to a new product", align="R")
        self.ln(8)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 8, f"{self.page_no()}", align="C")

    def heading(self, t, size=13):
        self.set_font("Helvetica", "B", size)
        self.multi_cell(0, 7, clean(t))
        self.ln(1)

    def para(self, t):
        self.set_font("Helvetica", "", 9.5)
        self.multi_cell(0, 4.8, clean(t))
        self.ln(2)

    def fig(self, name, caption, w=185):
        p = os.path.join(FIG, name)
        if os.path.exists(p):
            if self.get_y() > 190:
                self.add_page()
            self.image(p, w=w)
            self.set_font("Helvetica", "I", 8.5)
            self.multi_cell(0, 4.2, clean(caption))
            self.ln(3)

    def tab(self, df, cols, widths, fmt="{:.2f}", size=7.5):
        self.set_font("Helvetica", "B", size)
        for c, w in zip(cols, widths):
            self.cell(w, 5, clean(c)[:26], border="B")
        self.ln()
        self.set_font("Helvetica", "", size)
        for _, r in df.iterrows():
            for c, w in zip(cols, widths):
                v = r[c]
                self.cell(w, 4.6, clean(fmt.format(v) if isinstance(v, (float, np.floating)) else v)[:40])
            self.ln()
        self.ln(3)


es, nq, rty = P["ES"], P["NQ"], P["RTY"]
fv = {k: P[k]["fair_value_1600"] for k in ("ES", "NQ", "RTY")}
st = {k: P[k]["strategy_1600"]["transferred"] for k in ("ES", "NQ", "RTY")}
ll = {k: P[k]["leadlag_1m"] for k in P}
pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()
pdf.heading("Delta-one basis and lead-lag: ETF, index futures and the cash basket - fair value with measured financing and dividends, mean reversion, who leads whom, and what transfers from ES/SPY to a new product", 14)
pdf.para(f"Question.  A delta-one desk carries an index as a future, a fund and a basket and lives off the differences between them.  This project measures, on free data, where the basis sits against a fair value whose financing (the bill curve, EFFR/SOFR) and dividends (a point-in-time forecast with a within-quarter accrual profile read off the fund's own price) are measured rather than assumed; how fast a deviation closes at daily and minute horizons; the lead-lag between future, fund, basket and cash index by the Hayashi-Yoshida / Hoffmann-Rosenbaum-Vetter estimator on {R['run']['data'].get('bars_1m_days', 0)} days of 1-minute bars and one year of ETF-versus-index minutes; a basis strategy net of costs; and the new-products test, in which everything fitted on ES/SPY is applied unchanged to NQ/QQQ, RTY/IWM and a Euro Stoxx 50 pair.")
pdf.para(f"Answer.  (1) Half-way through a dividend quarter {100 * float(np.interp(0.5, [0] + es['accrual_profile']['frac'] + [1], [0] + es['accrual_profile']['share'] + [1])):.0f}% of SPY's dividends have gone ex; with that profile the SPY premium to fair has sd {es['etf_premium']['prem_sd_bp']:.1f} bp against {es['etf_premium']['prem_sd_no_accrual_bp']:.1f} with no accrual model; the dividend forecast misses by {100 * es['etf_premium']['dividend_forecast_mae']['blend']:.0f}% on SPY and {100 * rty['etf_premium']['dividend_forecast_mae']['blend']:.0f}% on IWM, so the model helps the first and hurts the second.  (2) With both legs marked at 16:00 ({fv['ES']['n_days']} days from {fv['ES']['from']}) the ES front implies financing of bills + {fv['ES']['spread_median_bp']:.0f} bp (NQ +{fv['NQ']['spread_median_bp']:.0f}, RTY +{fv['RTY']['spread_median_bp']:.0f}); the calendar spread implies bills + {fv['ES']['fwd_spread_mean_bp']:.0f}.  (3) Richness has an OLS half-life of {fv['ES']['half_life_rho']['half_life']:.1f} days on ES and a noise-robust persistent component of {f(fv['ES']['half_life_rho']['half_life_iv'], 0)} days; within the day the minute deviation halves in {es['minute_richness']['half_life_vs_index_min']['half_life']:.1f} min [{es['minute_richness']['half_life_vs_index_min']['hl_lo']:.1f}, {es['minute_richness']['half_life_vs_index_min']['hl_hi']:.1f}].  (4) At one-minute resolution future and fund are simultaneous (LLR {ll['ES']['future_vs_etf']['llr']:.2f} [{ll['ES']['future_vs_etf']['llr_lo']:.2f}, {ll['ES']['future_vs_etf']['llr_hi']:.2f}]); the fund leads the cash index by the grid's first step with LLR {ll['ES']['etf_vs_index']['llr']:.2f} on SPY/SPX, {ll['NQ']['etf_vs_index']['llr']:.2f} on QQQ/NDX and {ll['RTY']['etf_vs_index']['llr']:.2f} [{ll['RTY']['etf_vs_index']['llr_lo']:.2f}, {ll['RTY']['etf_vs_index']['llr_hi']:.2f}] on IWM/RUT: the index's stale-price lag grows with the number of small names.  (5) The z-score basis strategy with ES-fitted parameters nets {st['ES']['ann_net_bp']:.0f} bp/yr [{st['ES']['ann_lo']:.0f}, {st['ES']['ann_hi']:.0f}] on ES, {st['NQ']['ann_net_bp']:.0f} [{st['NQ']['ann_lo']:.0f}, {st['NQ']['ann_hi']:.0f}] on NQ, {st['RTY']['ann_net_bp']:.0f} [{st['RTY']['ann_lo']:.0f}, {st['RTY']['ann_hi']:.0f}] on RTY; the same rule on a series whose legs are marked an hour apart 'earns' {P['ES']['strategy']['transferred']['ann_net_bp']:.0f} bp/yr, an artefact shown beside the clean number.  (6) Transfer: " + " ".join(f"{r['pair']}: {r['verdict']}." for r in R['transfer']['rows'] if not r['is_source']))
pdf.fig("accrual_profile.png", "Figure 1.  Left: cumulative share of the quarter's dividends gone ex by fraction of the quarter, measured from each fund's price against its index.  Right: SPY against the index inside the last two quarters, measured and modelled.")
pdf.fig("basis_history.png", "Figure 2.  Left: median implied financing spread of the front contract over bills, by year, from the daily closes.  Right: the last year of the ES front spread with the 16:00 marks, and the calendar-spread-implied forward financing.")
pdf.fig("minute_basis.png", "Figure 3.  Left: ES richness to fair minute by minute on the last archived day, against the index and the fund-implied index.  Right: within-day half-life of the richness deviation by pair.")
pdf.fig("leadlag.png", "Figure 4.  The Hayashi-Yoshida contrast rho(theta) on 1-minute bars, per pair and leg pair.")
pdf.fig("leadlag_time.png", "Figure 5.  Left: the daily lead-lag ratio.  Middle: ETF vs cash index by month over the FirstRate year.  Right: the Epps curve.")
pdf.fig("strategy.png", "Figure 6.  Left: the z-score basis strategy on the 16:00-marked series, net of costs.  Middle: the marking artefact.  Right: cash-and-carry to the roll.")
pdf.fig("transfer.png", "Figure 7.  The transfer table: lead-lag ratio, richness dynamics and strategy return by pair, with ES's parameters applied to the others.")
pdf.add_page()
pdf.heading("Fair value and mean reversion, 16:00 marks", 12)
rows = []
for k in ("ES", "NQ", "RTY"):
    v = fv[k]
    rows.append({"pair": k, "days": v["n_days"], "rho mean": v["rho_mean_bp"], "rho sd": v["rho_sd_bp"], "spread median": v["spread_median_bp"], "spread sd": v["spread_sd_bp"], "fwd spread": v["fwd_spread_mean_bp"],
                 "HL OLS": v["half_life_rho"]["half_life"], "HL lo": v["half_life_rho"]["hl_lo"], "HL hi": v["half_life_rho"]["hl_hi"], "HL robust": min(v["half_life_rho"]["half_life_iv"], 999.0)})
pdf.tab(pd.DataFrame(rows), ["pair", "days", "rho mean", "rho sd", "spread median", "spread sd", "fwd spread", "HL OLS", "HL lo", "HL hi", "HL robust"], [14, 14, 18, 16, 22, 18, 18, 16, 14, 14, 18])
pdf.heading("Fund premium to the index", 12)
rows = []
for k, p in P.items():
    b = p["etf_premium"]
    rows.append({"fund": p["etf"], "days": b["n_days"], "sd all": b["prem_sd_bp"], "sd 5y": b["prem_sd_5y_bp"], "SPY profile": b["prem_sd_source_profile_bp"], "uniform": b["prem_sd_uniform_bp"], "no accrual": b["prem_sd_no_accrual_bp"], "HL days": b["half_life"]["half_life"], "div MAE %": 100 * b["dividend_forecast_mae"]["blend"]})
pdf.tab(pd.DataFrame(rows), ["fund", "days", "sd all", "sd 5y", "SPY profile", "uniform", "no accrual", "HL days", "div MAE %"], [22, 14, 16, 16, 20, 16, 18, 16, 18])
pdf.heading("Lead-lag, 1-minute bars (theta* > 0: first leg leads)", 12)
rows = []
for k, p in P.items():
    for key, s in p.get("leadlag_1m", {}).items():
        if s.get("n_days"):
            rows.append({"pair": k, "legs": key.replace("_", " "), "days": s["n_days"], "theta*": s["theta_star"], "lo": s["theta_lo"], "hi": s["theta_hi"], "rho*": s["rho_star"], "rho(0)": s["rho_0"], "LLR": s["llr"], "LLR lo": s["llr_lo"], "LLR hi": s["llr_hi"]})
    fr = p.get("firstrate")
    if fr:
        s = fr["summary"]
        rows.append({"pair": k, "legs": f"{p['etf']} vs {fr['index_symbol']} (1y)", "days": s["n_days"], "theta*": s["theta_star"], "lo": s["theta_lo"], "hi": s["theta_hi"], "rho*": s["rho_star"], "rho(0)": s["rho_0"], "LLR": s["llr"], "LLR lo": s["llr_lo"], "LLR hi": s["llr_hi"]})
pdf.tab(pd.DataFrame(rows), ["pair", "legs", "days", "theta*", "lo", "hi", "rho*", "rho(0)", "LLR", "LLR lo", "LLR hi"], [12, 40, 12, 14, 12, 12, 14, 14, 14, 14, 14])
pdf.heading("Strategy, net of costs", 12)
rows = []
for k in ("ES", "NQ", "RTY"):
    for key, name in (("strategy_1600", "16:00 marks"), ("strategy", "17:00 closes (artefact)")):
        t = P[k][key]["transferred"]
        rows.append({"pair": k, "series": name, "days": t["n_days"], "trades": t["n_trades"], "trade net": t["mean_trade_net_bp"], "hit": t["hit_rate"], "net bp/yr": t["ann_net_bp"], "lo": t["ann_lo"], "hi": t["ann_hi"], "Sharpe": t["sharpe"], "max DD": t["max_dd_bp"]})
pdf.tab(pd.DataFrame(rows), ["pair", "series", "days", "trades", "trade net", "hit", "net bp/yr", "lo", "hi", "Sharpe", "max DD"], [12, 36, 12, 14, 18, 12, 18, 14, 14, 14, 16])
pdf.heading("Validation and limits", 12)
pdf.para("Fair value reproduces F* = I(1 + r tau) - D on a hand case and the implied financing of the fair price is the input rate; the calendar reproduces the third Fridays including the Juneteenth pull-forward; AR(1) recovers a known phi and the autocovariance-ratio estimator recovers it under heavy measurement noise where OLS does not; the Hayashi-Yoshida sum equals the realised covariance on synchronous data and the HRV estimator recovers a known lag on Poisson-sampled Brownian motions; the strategy P&L reconciles to the basis move and the calendar-day carry with costs on entry, exit and roll; the Databento loader is tested on a synthetic file.  Limits: 1-minute bars are the finest free data, so the seconds-scale future-vs-fund lead is invisible and the ETF-vs-index theta* is the grid's first step; the 16:00-marked series is two and a half years long and the strategy's mask sensitivity is large; the baskets are the funds' largest names at fixed weights; the Euro Stoxx pair has no free future and a thinly traded fund; the dividend forecasts come from the funds' distributions and their errors are stated per fund.  No Databento depth was bought.")
pdf.output(os.path.join(ROOT, "report.pdf"))
print("report.pdf")
