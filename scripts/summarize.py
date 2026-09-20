#!/usr/bin/env python3
"""results/summary.md from results/run.json.   python scripts/summarize.py"""
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "results", "run.json")))
P = R["pairs"]
L = []


def f(x, d=1):
    return "—" if x is None or (isinstance(x, float) and x != x) else f"{x:.{d}f}"


def h(x):
    """half-lives: the noise-robust estimator caps phi, so very persistent series print as '> 500'."""
    if x is None or (isinstance(x, float) and x != x):
        return "—"
    return "> 500" if x > 500 else f"{x:.2f}"


L.append(f"# delta-one-basis — run summary ({R['run']['date']}, source pair {R['run']['source_pair']}, {R['run']['seconds']} s)\n")
d = R["run"]["data"]
L.append(f"Data: {d['daily_symbols']} daily symbols {d['daily_from']} .. {d['daily_to']}; 1-minute archive {d.get('bars_1m_symbols', 0)} symbols, {d.get('bars_1m_days', 0)} days ({d.get('bars_1m_from')} .. {d.get('bars_1m_to')}); FirstRate sample {d.get('firstrate_from')} .. {d.get('firstrate_to')}; Databento depth days: {d['databento_days']}.\n")

L.append("## Fair value and mean reversion (daily)\n")
L.append("| pair | days | richness mean / sd (bp) | spread median / sd (bp/yr) | last spread | fwd spread mean | HL rho OLS | HL rho noise-robust | HL spread noise-robust | 16:00 marks |")
L.append("|---|---|---|---|---|---|---|---|---|---|")
for k, p in P.items():
    fv = p.get("fair_value")
    if not fv:
        continue
    hr, hs = fv["half_life_rho"], fv["half_life_spread"]
    L.append(f"| {k} | {fv['n_days']} ({fv['from']}..{fv['to']}) | {f(fv['rho_mean_bp'])} / {f(fv['rho_sd_bp'])} | {f(fv['spread_median_bp'])} / {f(fv['spread_sd_bp'])} | {f(fv['spread_last_bp'])} | {f(fv['fwd_spread_mean_bp'])} ({fv['fwd_n']} d) | {h(hr['half_life'])} [{h(hr['hl_lo'])}, {h(hr['hl_hi'])}] | {h(hr['half_life_iv'])} [{h(hr['hl_iv_lo'])}, {h(hr['hl_iv_hi'])}] | {h(hs['half_life_iv'])} [{h(hs['hl_iv_lo'])}, {h(hs['hl_iv_hi'])}] | {100 * fv['share_1600_marks']:.0f} % |")
    fv2 = p.get("fair_value_1600")
    if fv2:
        hr, hs = fv2["half_life_rho"], fv2["half_life_spread"]
        L.append(f"| {k} 16:00 only | {fv2['n_days']} ({fv2['from']}..{fv2['to']}) | {f(fv2['rho_mean_bp'])} / {f(fv2['rho_sd_bp'])} | {f(fv2['spread_median_bp'])} / {f(fv2['spread_sd_bp'])} | {f(fv2['spread_last_bp'])} | {f(fv2['fwd_spread_mean_bp'])} | {h(hr['half_life'])} [{h(hr['hl_lo'])}, {h(hr['hl_hi'])}] | {h(hr['half_life_iv'])} [{h(hr['hl_iv_lo'])}, {h(hr['hl_iv_hi'])}] | {h(hs['half_life_iv'])} [{h(hs['hl_iv_lo'])}, {h(hs['hl_iv_hi'])}] | 100 % |")
L.append("")
L.append("## Fund premium to the index (daily)\n")
L.append("| pair | fund | days | premium mean (bp) | sd all / last 5y | sd with SPY profile | uniform | no accrual model | HL (days) | dividend forecast MAE |")
L.append("|---|---|---|---|---|---|---|---|---|---|")
for k, p in P.items():
    pb = p.get("etf_premium")
    if not pb:
        continue
    e = pb.get("dividend_forecast_mae", {})
    L.append(f"| {k} | {p['etf']} | {pb['n_days']} | {f(pb['prem_mean_bp'])} | {f(pb['prem_sd_bp'])} / {f(pb['prem_sd_5y_bp'])} | {f(pb['prem_sd_source_profile_bp'])} | {f(pb['prem_sd_uniform_bp'])} | {f(pb['prem_sd_no_accrual_bp'])} | {f(pb['half_life']['half_life'], 2)} [{f(pb['half_life']['hl_lo'], 2)}, {f(pb['half_life']['hl_hi'], 2)}] | {f(100 * e.get('blend', float('nan')), 0)} % (seasonal {f(100 * e.get('seasonal', float('nan')), 0)}, median {f(100 * e.get('median4', float('nan')), 0)}) |")
L.append("")
L.append("## Lead-lag, 1-minute bars (theta* > 0: first leg leads; seconds)\n")
L.append("| pair | legs | days | theta* [95 %] | rho* | rho(0) | LLR [95 %] | P(first leads) |")
L.append("|---|---|---|---|---|---|---|---|")
for k, p in P.items():
    for key, s in p.get("leadlag_1m", {}).items():
        if s.get("n_days"):
            L.append(f"| {k} | {key.replace('_', ' ')} | {s['n_days']} | {f(s['theta_star'], 0)} [{f(s['theta_lo'], 0)}, {f(s['theta_hi'], 0)}] | {f(s['rho_star'], 3)} | {f(s['rho_0'], 3)} | {f(s['llr'], 2)} [{f(s['llr_lo'], 2)}, {f(s['llr_hi'], 2)}] | {f(s['p_x_leads'], 2)} |")
    fr = p.get("firstrate")
    if fr:
        s = fr["summary"]
        L.append(f"| {k} | {p['etf']} vs {fr['index_symbol']} (FirstRate {fr['span'][0]}..{fr['span'][1]}) | {s['n_days']} | {f(s['theta_star'], 0)} [{f(s['theta_lo'], 0)}, {f(s['theta_hi'], 0)}] | {f(s['rho_star'], 3)} | {f(s['rho_0'], 3)} | {f(s['llr'], 2)} [{f(s['llr_lo'], 2)}, {f(s['llr_hi'], 2)}] | {f(s['p_x_leads'], 2)} |")
L.append("")
L.append("## Minute richness and basket\n")
for k, p in P.items():
    m = p.get("minute_richness")
    if m:
        hi, he = m["half_life_vs_index_min"], m["half_life_vs_etf_min"]
        L.append(f"- {k}: {m['n_days']} days, {m['n_bars']} bars; richness sd vs index {f(m['sd_vs_index_bp'], 2)} bp (within-day {f(m['within_day_sd_vs_index_bp'], 2)}), vs fund {f(m['sd_vs_etf_bp'], 2)} (within-day {f(m['within_day_sd_vs_etf_bp'], 2)}); within-day half-life vs index {f(hi['half_life'], 2)} min [{f(hi['hl_lo'], 2)}, {f(hi['hl_hi'], 2)}], vs fund {f(he['half_life'], 2)} [{f(he['hl_lo'], 2)}, {f(he['hl_hi'], 2)}]")
    b = p.get("basket")
    if b:
        L.append(f"- {k} basket: {b['n_names']} names, {f(b['weight_covered'])} % of the fund; 1-minute return correlation with the fund {f(b['corr'], 3)}, tracking error {f(b['te_bp_per_bar'], 2)} bp per bar")
L.append("")
L.append("## Strategy (net of costs)\n")
L.append("| pair | series | params | days | trades | mean trade net (bp) [95 %] | hit | net bp/yr [95 %] | Sharpe | max DD (bp) | costless bp/yr | carry-to-roll: n, mean net bp/yr, hit |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
for k, p in P.items():
    for key, name in (("strategy_1600", "16:00 marks"), ("strategy", "17:00 close marks")):
        st = p.get(key, {})
        t = st.get("transferred")
        if not t:
            continue
        c = st.get("carry", {})
        L.append(f"| {k} | {name} | z0 {t['z0']}, z1 {t['z1']}, w {t['window']} | {t['n_days']} | {t['n_trades']} | {f(t.get('mean_trade_net_bp'))} [{f(t.get('trade_lo'))}, {f(t.get('trade_hi'))}] | {f(t.get('hit_rate'), 2)} | {f(t['ann_net_bp'], 0)} [{f(t['ann_lo'], 0)}, {f(t['ann_hi'], 0)}] | {f(t['sharpe'], 2)} | {f(t['max_dd_bp'], 0)} | {f(st['transferred_costless']['ann_net_bp'], 0)} | {c.get('n', '—')}, {f(c.get('mean_net_ann_bp'), 0)}, {f(c.get('hit_rate'), 2)} |")
L.append("")
L.append("Sensitivity of the transferred strategy to the near-expiry mask (net bp/yr on the 16:00 series):")
for k, p in P.items():
    sens = p.get("strategy_1600", {}).get("mask_sensitivity")
    if sens:
        L.append(f"- {k}: " + ", ".join(f"{s['min_days']} d: {f(s['ann_net_bp'], 0)} (Sharpe {f(s['sharpe'], 2)}, {s['n_trades']} trades)" for s in sens))
L.append("")
L.append("## Transfer table\n")
tt = pd.DataFrame(R["transfer"]["rows"])
cols = [c for c in ["pair", "prem_sd_own", "prem_sd_transferred", "prem_sd_uniform", "prem_sd_none", "hl_rho_own", "hl_rho_source", "hl_rho_own_iv", "mse_ratio_transferred", "mse_ratio_random_walk", "strat_net_own", "strat_net_transferred", "theta_own", "theta_source", "llr_own", "llr_source", "verdict"] if c in tt]
L.append(tt[cols].round(2).to_markdown(index=False) if hasattr(tt, "to_markdown") else tt[cols].round(2).to_string(index=False))
open(os.path.join(ROOT, "results", "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("results/summary.md")
