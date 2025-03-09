"""python -m d1basis <run|panel|leadlag|strategy|transfer|sql> [options]

  run       [--fast] [--skip-intraday] [--source ES]   the whole pipeline -> results/run.json, data/derived/
  panel     [--pair ES] [--tail 15]                     the daily panel of one pair: front contract, fair value, richness, spread
  leadlag   [--pair ES] [--interval 1m] [--a future --b etf]   HY / HRV lead-lag of two legs on the archive
  strategy  [--pair ES] [--z0 1.5 --z1 0.25 --window 60] [--no-costs]   the basis strategy on one pair
  transfer                                              the transfer table from results/run.json
  sql       "SELECT ..."                                a query against the DuckDB views (daily, rates, bars_1m, panel_ES, ...)
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd


def _args(argv):
    out, i = {}, 0
    while i < len(argv):
        if argv[i].startswith("--"):
            k = argv[i][2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                out[k] = argv[i + 1]
                i += 2
            else:
                out[k] = True
                i += 1
        else:
            out.setdefault("_", []).append(argv[i])
            i += 1
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    cmd, a = argv[0], _args(argv[1:])
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    from . import data as D

    if cmd == "run":
        from .run import run
        run(fast=bool(a.get("fast")), skip_intraday=bool(a.get("skip-intraday")), source=a.get("source", "ES"))
        return 0
    if cmd == "panel":
        from . import fairvalue as FV, panel as P
        k = a.get("pair", "ES")
        cfg = D.pairs()[k]
        prof = FV.accrual_profile(cfg["index"], cfg["etf"], cfg["etf_fee_bp"])
        pn = P.build(k, cfg, prof)
        cols = ["F", "contract", "days", "mark", "I", "E", "r", "D", "F_fair", "rho_bp", "spread_bp", "F2", "spread2_bp", "fwd_spread_bp"]
        print(pn[cols].tail(int(a.get("tail", 15))).round(3).to_string())
        return 0
    if cmd == "leadlag":
        from . import run as RUN
        k = a.get("pair", "ES")
        cfg = D.pairs()[k]
        iv = a.get("interval", "1m")
        bar = {"1m": 60, "2m": 120}[iv]
        legs = {"etf": RUN.session(D.bar_closes(iv, [cfg["etf"]]).get(cfg["etf"], pd.Series(dtype=float)), cfg),
                "index": RUN.session(D.bar_closes(iv, [cfg["index"]]).get(cfg["index"], pd.Series(dtype=float)), cfg)}
        if cfg["future_root"]:
            legs["future"] = RUN.session(RUN.front_bars(cfg, iv), cfg)
        x, y = a.get("a", "future" if cfg["future_root"] else "etf"), a.get("b", "etf" if cfg["future_root"] else "index")
        s, pooled, days = RUN.leadlag_block(legs[x], legs[y], bar, RUN.GRID_1M if iv == "1m" else RUN.GRID_2M, 200, cfg["index_tz"])
        print(f"{k}: {x} vs {y} at {iv}: theta* = {s.get('theta_star')} s [{s.get('theta_lo')}, {s.get('theta_hi')}]  (>0: {x} leads)  LLR {s.get('llr'):.2f}  rho* {s.get('rho_star'):.3f}  days {s.get('n_days')}")
        print(pooled.round(4).to_string(index=False))
        return 0
    if cmd == "strategy":
        from . import fairvalue as FV, panel as P, strategy as S
        k = a.get("pair", "ES")
        cfg = D.pairs()[k]
        prof = FV.accrual_profile(cfg["index"], cfg["etf"], cfg["etf_fee_bp"])
        pn = P.strategy_series(P.build(k, cfg, prof))
        params = {"z0": float(a.get("z0", 1.5)), "z1": float(a.get("z1", 0.25)), "window": int(a.get("window", 60))}
        m, q, tr = S.run(pn[pn.F.notna()], cfg, params, not a.get("no-costs"), 300)
        print(json.dumps({kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in m.items()}, indent=1))
        print(tr.tail(10).round(2).to_string(index=False))
        return 0
    if cmd == "transfer":
        R = json.load(open(os.path.join(D.RESULTS, "run.json")))
        tt = pd.DataFrame(R["transfer"]["rows"])
        cols = [c for c in ("pair", "prem_sd_own", "prem_sd_transferred", "prem_sd_none", "hl_rho_own", "hl_rho_source", "mse_ratio_transferred", "strat_net_own", "strat_net_transferred", "llr_own", "llr_source", "verdict") if c in tt]
        print(tt[cols].round(2).to_string(index=False))
        return 0
    if cmd == "sql":
        con = D.store()
        print(con.execute(" ".join(a.get("_", []))).df().to_string())
        return 0
    print(__doc__)
    return 1
