#!/usr/bin/env python3
"""notebooks/results.ipynb: the results walk-through, built from results/run.json so it never drifts from the run."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def md(s):
    return {"cell_type": "markdown", "metadata": {}, "source": s}


def code(s):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s}


cells = [
    md("# delta-one-basis: results\n\nEverything here reads `results/run.json` and `data/derived/*.parquet` written by `python -m d1basis run`; re-run the pipeline and re-execute to refresh."),
    code("import json, os, sys\nimport numpy as np, pandas as pd\nimport matplotlib.pyplot as plt\nfrom IPython.display import Image, display\nsys.path.insert(0, os.path.abspath('..'))\nfrom d1basis import data as D, fairvalue as FV, leadlag as LL, panel as P, strategy as S\nR = json.load(open('../results/run.json'))\npd.set_option('display.width', 200); pd.set_option('display.max_columns', 40)\nR['run']"),
    md("## 1. When the index pays: the accrual profile measured from the fund\n\nA(t) = E - I / kappa + fee, as a share of the quarter's distribution, by fraction of the quarter elapsed."),
    code("prof = pd.DataFrame(R['pairs']['ES']['accrual_profile']); display(prof.round(3).T)\ndisplay(Image('../results/figures/accrual_profile.png'))"),
    md("## 2. The futures basis: fair value, richness, implied financing\n\nThe daily panel of the front contract.  Note the `mark` column: rows marked `16:00` have the future at the cash close (hourly bars); `daily` rows carry the 17:00 CME close against the 16:00 cash close."),
    code("pn = pd.read_parquet('../data/derived/panel_ES.parquet').set_index('date')\ndisplay(pn[['F','contract','days','mark','I','E','r','D','F_fair','rho_bp','spread_bp','fwd_spread_bp']].tail(10).round(3))\nfor k, p in R['pairs'].items():\n    fv = p.get('fair_value')\n    if fv: print(k, {x: round(fv[x], 2) for x in ('rho_mean_bp','rho_sd_bp','spread_median_bp','spread_sd_bp','fwd_spread_mean_bp')}, 'HL spread noise-robust', round(fv['half_life_spread']['half_life_iv'], 2))\ndisplay(Image('../results/figures/basis_history.png'))"),
    md("## 3. The fund against the index\n\nPremium to the modelled fair price with each fund's own accrual profile, the SPY profile transferred, uniform accrual, and none."),
    code("rows = []\nfor k, p in R['pairs'].items():\n    pb = p.get('etf_premium', {})\n    if pb: rows.append({'pair': k, **{x: pb[x] for x in ('prem_mean_bp','prem_sd_bp','prem_sd_5y_bp','prem_sd_source_profile_bp','prem_sd_uniform_bp','prem_sd_no_accrual_bp')}, 'half_life': pb['half_life']['half_life']})\ndisplay(pd.DataFrame(rows).round(2))\ndisplay(Image('../results/figures/etf_premium.png'))"),
    md("## 4. Lead-lag: Hayashi-Yoshida contrast and the Hoffmann-Rosenbaum-Vetter estimator\n\ntheta* > 0 means the first leg leads.  The grid step is 30 s on 1-minute bars: the resolution is the bar."),
    code("rows = []\nfor k, p in R['pairs'].items():\n    for key, s in p.get('leadlag_1m', {}).items():\n        if s.get('n_days'): rows.append({'pair': k, 'legs': key, **{x: s[x] for x in ('n_days','theta_star','theta_lo','theta_hi','rho_star','rho_0','llr','llr_lo','llr_hi','p_x_leads')}})\ndisplay(pd.DataFrame(rows).round(3))\ndisplay(Image('../results/figures/leadlag.png')); display(Image('../results/figures/leadlag_time.png'))"),
    md("## 5. Minute richness and the basket"),
    code("for k, p in R['pairs'].items():\n    if p.get('minute_richness'): print(k, {x: (round(v, 2) if isinstance(v, float) else v) for x, v in p['minute_richness'].items() if not isinstance(v, dict)}, p['minute_richness']['half_life_vs_index_min'])\n    if p.get('basket'): print(k, 'basket', {x: v for x, v in p['basket'].items() if x != 'names'})\ndisplay(Image('../results/figures/minute_basis.png'))"),
    md("## 6. The basis strategy net of costs, and the carry to the roll"),
    code("rows = []\nfor k, p in R['pairs'].items():\n    for key in ('strategy_1600', 'strategy'):\n        t = p.get(key, {}).get('transferred')\n        if t: rows.append({'pair': k, 'series': key, **{x: t.get(x) for x in ('n_days','n_trades','mean_trade_net_bp','trade_lo','trade_hi','hit_rate','ann_net_bp','ann_lo','ann_hi','sharpe','max_dd_bp')}})\ndisplay(pd.DataFrame(rows).round(2))\ndisplay(Image('../results/figures/strategy.png'))"),
    md("## 7. The transfer table: fitted on ES / SPY, run unchanged elsewhere"),
    code("tt = pd.DataFrame(R['transfer']['rows']); display(tt.round(2).T)\ndisplay(Image('../results/figures/transfer.png'))"),
    md("## 8. SQL over the store"),
    code("con = D.store()\ncon.execute(\"SELECT contract, COUNT(*) n, ROUND(AVG(spread_bp),1) spread, ROUND(AVG(rho_bp),2) rho FROM panel_ES WHERE days >= 20 AND F IS NOT NULL GROUP BY contract ORDER BY MIN(date) DESC LIMIT 12\").df()"),
]
nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
os.makedirs(os.path.join(ROOT, "notebooks"), exist_ok=True)
json.dump(nb, open(os.path.join(ROOT, "notebooks", "results.ipynb"), "w"), indent=1)
print("notebooks/results.ipynb")
