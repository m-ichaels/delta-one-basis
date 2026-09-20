#!/usr/bin/env python3
"""README.md from scripts/README.template.md and results/run.json, so every number in the README is the run's.
python scripts/readme.py [--check]   (--check renders without writing and fails on an unfilled placeholder)"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from d1basis import fairvalue as FV  # noqa: E402

R = json.load(open(os.path.join(ROOT, "results", "run.json")))
P = R["pairs"]
V = {}


def f(x, d=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:.{d}f}"


def h(x, d=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return "> 500" if x > 500 else f"{x:.{d}f}"


def g(*ks, default=None):
    cur = R
    for k in ks:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


# --- headline numbers
prof = pd.DataFrame(P["ES"]["accrual_profile"])
pf = FV.profile_fn(prof)
V["spy_share_mid"] = f(100 * float(pf(0.5)), 0)
V["spy_share_late"] = f(100 * float(pf(0.75)), 0)
V["n_quarters"] = str(len(FV.quarterly_distributions("SPY")) - 1)
pb = P["ES"]["etf_premium"]
V["spy_prem_sd"] = f(pb["prem_sd_bp"])
V["spy_prem_sd_5y"] = f(pb["prem_sd_5y_bp"])
V["spy_prem_sd_none"] = f(pb["prem_sd_no_accrual_bp"])
for k, name in (("ES", "spy"), ("NQ", "qqq"), ("RTY", "iwm"), ("SX5E", "sx5e")):
    V[f"{name}_div_mae"] = f(100 * P[k]["etf_premium"]["dividend_forecast_mae"]["blend"], 0)
fv16 = {k: P[k].get("fair_value_1600", P[k].get("fair_value")) for k in ("ES", "NQ", "RTY")}
V["clean_days"] = str(fv16["ES"]["n_days"])
V["clean_from"] = fv16["ES"]["from"]
V["clean_to"] = fv16["ES"]["to"]
for k in ("ES", "NQ", "RTY"):
    lk = k.lower()
    V[f"{lk}_spread_median"] = f(fv16[k]["spread_median_bp"], 0)
    V[f"{lk}_spread_sd"] = f(fv16[k]["spread_sd_bp"], 0)
    V[f"{lk}_hl_ols"] = f(fv16[k]["half_life_rho"]["half_life"])
    V[f"{lk}_hl_iv"] = h(fv16[k]["half_life_rho"]["half_life_iv"], 0)
    mr = P[k]["minute_richness"]
    V[f"{lk}_hl_min"] = f(mr["half_life_vs_index_min"]["half_life"])
    V[f"{lk}_hl_min_lo"] = f(mr["half_life_vs_index_min"]["hl_lo"])
    V[f"{lk}_hl_min_hi"] = f(mr["half_life_vs_index_min"]["hl_hi"])
    V[f"{lk}_hl_min_etf"] = f(mr["half_life_vs_etf_min"]["half_life"])
    ll = P[k]["leadlag_1m"]
    V[f"{lk}_llr_fe"] = f(ll["future_vs_etf"]["llr"], 2)
    V[f"{lk}_llr_fe_lo"] = f(ll["future_vs_etf"]["llr_lo"], 2)
    V[f"{lk}_llr_fe_hi"] = f(ll["future_vs_etf"]["llr_hi"], 2)
    V[f"{lk}_theta_ei"] = f(ll["etf_vs_index"]["theta_star"], 0)
    V[f"{lk}_llr_ei"] = f(ll["etf_vs_index"]["llr"], 2)
    V[f"{lk}_llr_ei_lo"] = f(ll["etf_vs_index"]["llr_lo"], 2)
    V[f"{lk}_llr_ei_hi"] = f(ll["etf_vs_index"]["llr_hi"], 2)
    st = P[k]["strategy_1600"]
    t = st["transferred"]
    V[f"{lk}_strat_net"] = f(t["ann_net_bp"], 0)
    V[f"{lk}_strat_lo"] = f(t["ann_lo"], 0)
    V[f"{lk}_strat_hi"] = f(t["ann_hi"], 0)
    V[f"{lk}_strat_sharpe"] = f(t["sharpe"])
    V[f"{lk}_cost"] = f(st["cost_one_way_bp"], 2)
    sens = [s["ann_net_bp"] for s in st["mask_sensitivity"]]
    V[f"{lk}_sens_min"] = f(min(sens), 0)
    V[f"{lk}_sens_max"] = f(max(sens), 0)
    V[f"{lk}_art_net"] = f(P[k]["strategy"]["transferred"]["ann_net_bp"], 0)
    V[f"{lk}_carry"] = f(st["carry"]["mean_net_ann_bp"], 0)
V["es_fwd_spread"] = f(fv16["ES"]["fwd_spread_mean_bp"], 0)
by = {b["year"]: b for b in P["ES"]["fair_value"]["by_year"]}
V["es_2008_spread"] = f(by.get(2008, {}).get("spread_median"), 0)
V["es_2025_spread"] = f(by.get(2025, {}).get("spread_median"), 0)
fr = P["ES"]["firstrate"]
V["fr_spy_llr"] = f(fr["summary"]["llr"], 2)
V["fr_spy_llr_lo"] = f(fr["summary"]["llr_lo"], 2)
V["fr_spy_llr_hi"] = f(fr["summary"]["llr_hi"], 2)
mo = pd.DataFrame(fr["by_month"])
V["fr_spy_llr_min"] = f(mo.llr.min(), 2)
V["fr_spy_llr_max"] = f(mo.llr.max(), 2)
ep = pd.DataFrame(P["RTY"]["epps_etf_index"]).set_index("interval_s").correlation
V["rty_epps_1m"] = f(ep[60], 2)
V["rty_epps_60m"] = f(ep[3600], 2)
V["rty_basket_cov"] = f(P["RTY"]["basket"]["weight_covered"], 1)
_tr = pd.read_parquet(os.path.join(ROOT, "data", "derived", "trades_RTY_1600.parquet"))
V["rty_top_share"] = f(100 * _tr.net_bp.max() / _tr.net_bp.sum(), 0) if len(_tr) and _tr.net_bp.sum() > 0 else "—"
V["run_date"] = R["run"]["date"]
V["databento_days"] = str(R["run"]["data"]["databento_days"])
dbs = R["run"]["data"].get("databento_sample", {})
V["dbs_date"] = dbs.get("date", "—")
V["dbs_rows"] = f"{dbs.get('mid_changes_session', 0):,}"
V["dbs_gap"] = f(dbs.get("median_gap_ms_rth"), 2)
V["dbs_secs"] = f(dbs.get("seconds_to_load"), 0)
V["bars_1m_from"] = R["run"]["data"].get("bars_1m_from", "—")
V["firstrate_from"] = R["run"]["data"].get("firstrate_from", "—")
V["firstrate_to"] = R["run"]["data"].get("firstrate_to", "—")
V["n_tests"] = str(sum(len(re.findall(r"^def test_", open(os.path.join(ROOT, "tests", fn), encoding="utf-8").read(), flags=re.M)) for fn in os.listdir(os.path.join(ROOT, "tests")) if fn.endswith(".py")))
tt = pd.DataFrame(R["transfer"]["rows"])
V["transfer_summary"] = " ".join(f"{r.pair}: {r.verdict}." for r in tt.itertuples() if not r.is_source)

# --- tables
rows = []
for k, p in P.items():
    b = p["etf_premium"]
    e = b["dividend_forecast_mae"]
    rows.append(f"| {p['etf']} ({p['label']}) | {b['n_days']} | {f(b['prem_sd_bp'])} / {f(b['prem_sd_5y_bp'])} | {f(b['prem_sd_source_profile_bp'])} | {f(b['prem_sd_uniform_bp'])} | {f(b['prem_sd_no_accrual_bp'])} | {f(b['half_life']['half_life'], 2)} [{f(b['half_life']['hl_lo'], 2)}, {f(b['half_life']['hl_hi'], 2)}] | {f(100 * e['blend'], 0)} / {f(100 * e['seasonal'], 0)} / {f(100 * e['median4'], 0)} % |")
V["premium_table"] = "\n".join(rows)

rows = []
for k in ("ES", "NQ", "RTY"):
    for key, name in (("fair_value_1600", "16:00 marks"), ("fair_value", "daily closes, 2005–")):
        fv = P[k].get(key)
        if not fv:
            continue
        hr = fv["half_life_rho"]
        rows.append(f"| {k} | {name} | {fv['n_days']} | {f(fv['rho_mean_bp'])} / {f(fv['rho_sd_bp'])} | {f(fv['spread_median_bp'], 0)} / {f(fv['spread_sd_bp'], 0)} | {f(fv['spread_last_bp'], 0)} | {f(fv['fwd_spread_mean_bp'], 0)} | {f(hr['half_life'], 2)} [{f(hr['hl_lo'], 2)}, {f(hr['hl_hi'], 2)}] | {h(hr['half_life_iv'], 1)} [{h(hr['hl_iv_lo'], 1)}, {h(hr['hl_iv_hi'], 1)}] |")
V["fairvalue_table"] = "\n".join(rows)

lines = []
for k in ("ES", "NQ", "RTY"):
    m = P[k]["minute_richness"]
    hi, he = m["half_life_vs_index_min"], m["half_life_vs_etf_min"]
    lines.append(f"- **{k}**: {m['n_days']} days, {m['n_bars']:,} minutes; richness sd {f(m['sd_vs_index_bp'], 1)} bp against the index and {f(m['sd_vs_etf_bp'], 1)} against the fund-implied index (within-day {f(m['within_day_sd_vs_index_bp'], 2)} / {f(m['within_day_sd_vs_etf_bp'], 2)} bp); within-day half-life {f(hi['half_life'], 2)} min [{f(hi['hl_lo'], 2)}, {f(hi['hl_hi'], 2)}] against the index, {f(he['half_life'], 2)} [{f(he['hl_lo'], 2)}, {f(he['hl_hi'], 2)}] against the fund.")
V["minute_lines"] = "\n".join(lines)

rows = []
for k, p in P.items():
    for key, s in p.get("leadlag_1m", {}).items():
        if s.get("n_days"):
            rows.append(f"| {k} | {key.replace('_', ' ')} | {s['n_days']} | {f(s['theta_star'], 0)} [{f(s['theta_lo'], 0)}, {f(s['theta_hi'], 0)}] | {f(s['rho_star'], 3)} | {f(s['rho_0'], 3)} | {f(s['llr'], 2)} [{f(s['llr_lo'], 2)}, {f(s['llr_hi'], 2)}] | {f(s['p_x_leads'], 2)} |")
    fr = p.get("firstrate")
    if fr:
        s = fr["summary"]
        rows.append(f"| {k} | {p['etf']} vs {fr['index_symbol']}, FirstRate year | {s['n_days']} | {f(s['theta_star'], 0)} [{f(s['theta_lo'], 0)}, {f(s['theta_hi'], 0)}] | {f(s['rho_star'], 3)} | {f(s['rho_0'], 3)} | {f(s['llr'], 2)} [{f(s['llr_lo'], 2)}, {f(s['llr_hi'], 2)}] | {f(s['p_x_leads'], 2)} |")
V["leadlag_table"] = "\n".join(rows)

lines = []
for k in ("ES", "NQ", "RTY"):
    b = P[k]["basket"]
    e1 = pd.DataFrame(P[k]["epps_future_etf"]).set_index("interval_s").correlation
    e2 = pd.DataFrame(P[k]["epps_etf_index"]).set_index("interval_s").correlation
    lines.append(f"- **{k}** basket: {b['n_names']} names, {f(b['weight_covered'], 1)} % of the fund, 1-minute return correlation with the fund {f(b['corr'], 3)}, tracking error {f(b['te_bp_per_bar'], 2)} bp per minute. Epps: future vs fund {f(e1[60], 3)} at 1 min → {f(e1[3600], 3)} at 60; fund vs index {f(e2[60], 3)} → {f(e2[3600], 3)}.")
V["basket_lines"] = "\n".join(lines)

rows = []
for k in ("ES", "NQ", "RTY"):
    for key, name in (("strategy_1600", "16:00 marks"), ("strategy", "17:00 closes (artefact)")):
        st = P[k].get(key, {})
        t = st.get("transferred")
        if not t:
            continue
        o = st["own"]
        rows.append(f"| {k} | {name} | z0 {t['z0']}, z1 {t['z1']}, w {t['window']} | {t['n_days']} | {t['n_trades']} | {f(t['mean_trade_net_bp'])} [{f(t['trade_lo'])}, {f(t['trade_hi'])}] | {f(t['hit_rate'], 2)} | {f(t['ann_net_bp'], 0)} [{f(t['ann_lo'], 0)}, {f(t['ann_hi'], 0)}] | {f(t['sharpe'], 2)} | {f(t['max_dd_bp'], 0)} | {f(st['transferred_costless']['ann_net_bp'], 0)} | {f(o['ann_net_bp'], 0)} (z0 {st['own_params']['z0']}, z1 {st['own_params']['z1']}, w {st['own_params']['window']}) |")
V["strategy_table"] = "\n".join(rows)
V["sens_lines"] = "; ".join(f"{k} " + ", ".join(f"{s['min_days']} d {f(s['ann_net_bp'], 0)}" for s in P[k]["strategy_1600"]["mask_sensitivity"]) for k in ("ES", "NQ", "RTY")) + "."

rows = []
for r in tt.itertuples():
    d = r._asdict()
    acc = f"{f(d.get('prem_sd_own'))} / {f(d.get('prem_sd_transferred'))} / {f(d.get('prem_sd_uniform'))} / {f(d.get('prem_sd_none'))}"
    hl = f"{f(d.get('hl_rho_own'), 2)} / {f(d.get('hl_rho_source'), 2)}" if pd.notna(d.get("hl_rho_own", np.nan)) else "—"
    mse = f"{f(d.get('mse_ratio_transferred'), 2)} / {f(d.get('mse_ratio_random_walk'), 2)}" if pd.notna(d.get("mse_ratio_transferred", np.nan)) else "—"
    stt = f"{f(d.get('strat_net_own'), 0)} / {f(d.get('strat_net_transferred'), 0)}" if pd.notna(d.get("strat_net_own", np.nan)) else "—"
    llr = f"{f(d.get('llr_own'), 2)} / {f(d.get('llr_source'), 2)}" if pd.notna(d.get("llr_own", np.nan)) else "—"
    rows.append(f"| {d['pair']} ({d['label']}) | {acc} | {hl} | {mse} | {stt} | {llr} | {d['verdict']} |")
V["transfer_table"] = "\n".join(rows)

tpl = open(os.path.join(ROOT, "scripts", "README.template.md"), encoding="utf-8").read()
out = re.sub(r"<<(\w+)>>", lambda m: V.get(m.group(1), f"<<{m.group(1)}>>"), tpl)
missing = re.findall(r"<<\w+>>", out)
if missing:
    print("unfilled:", sorted(set(missing)))
    sys.exit(1)
if "--check" in sys.argv:
    print(f"README renders: {len(out)} chars, {len(V)} values")
else:
    open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8", newline="\n").write(out)
    print("README.md")
