"""The pipeline: python -m d1basis run [--fast] [--skip-intraday] [--source ES]  -> results/run.json, data/derived/*.parquet"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from . import basket as B
from . import calendar as C
from . import data as D
from . import fairvalue as FV
from . import leadlag as LL
from . import panel as P
from . import strategy as S
from . import transfer as T

GRID_1M = np.arange(-900, 901, 30.0)       # seconds; 1-minute bars
GRID_2M = np.arange(-1800, 1801, 60.0)
EPPS = (60, 120, 300, 600, 1800, 3600)


def _j(x):
    """json-safe."""
    if isinstance(x, dict):
        return {str(k): _j(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_j(v) for v in x]
    if isinstance(x, pd.DataFrame):
        return _j(x.to_dict(orient="records"))
    if isinstance(x, pd.Series):
        return _j(x.tolist())
    if isinstance(x, (pd.Timestamp, dt.date, dt.datetime)):
        return str(x)[:19]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if (isinstance(x, float) or isinstance(x, np.floating)) and not np.isfinite(x) else float(x)
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.ndarray):
        return _j(x.tolist())
    return x


# ----------------------------------------------------------------------------- intraday helpers
def front_bars(cfg: dict, interval: str) -> pd.Series:
    """The front contract's close series at `interval`, stitched from the listed contracts by the eight-day roll, with
    the continuous series filling days no listed contract covers.  UTC index."""
    syms = [s for s in cfg["contracts"]] + ([cfg["continuous"]] if cfg["continuous"] else [])
    w = D.bar_closes(interval, syms)
    if w.empty:
        return pd.Series(dtype=float)
    days = w.index.tz_convert(ZoneInfo(cfg["index_tz"])).normalize().tz_localize(None)
    out = pd.Series(np.nan, index=w.index)
    for d in days.unique():
        m = days == d
        s = C.contract_symbol(cfg["future_root"], C.front_expiry(d, 8))
        if s in w.columns and w.loc[m, s].notna().sum() > 10:
            out[m] = w.loc[m, s]
        elif cfg["continuous"] in w.columns:
            out[m] = w.loc[m, cfg["continuous"]]
    return out.dropna()


def session(close: pd.Series, cfg: dict) -> pd.Series:
    if close.empty:
        return close
    m = D.session_mask(close.index, cfg["index_tz"], cfg["session"][0], cfg["session"][1])
    return close[m]


def leadlag_block(a: pd.Series, b: pd.Series, bar_s: int, grid: np.ndarray, n_boot: int, tz: str) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """a leads b when theta* > 0.  Returns the summary, the pooled contrast curve and the per-day table."""
    if a.empty or b.empty:
        return {"n_days": 0}, pd.DataFrame(), pd.DataFrame()
    ta, xa, da = LL.series_from_bars(a, bar_s)
    tb, xb, db = LL.series_from_bars(b, bar_s)
    covs, sxs, sys_, days = LL.per_day(ta, xa, tb, xb, da, db, grid)
    if len(covs) == 0:
        return {"n_days": 0}, pd.DataFrame(), pd.DataFrame()
    out, pooled = LL.bootstrap(covs, sxs, sys_, grid, n_boot)
    rows = []
    for k, d in enumerate(days):
        c = covs[k]
        s = LL.summarise(pd.DataFrame({"theta": grid, "cov": c, "rho": c / np.sqrt(sxs[k] * sys_[k])}))
        s["day"] = str(pd.Timestamp(int(d) * 86400, unit="s").date())
        rows.append(s)
    return out, pooled, pd.DataFrame(rows)


def intraday_pair(pair: str, cfg: dict, panel: pd.DataFrame, prof, n_boot: int) -> dict:
    """The 1-minute triangle: lead-lag future/fund/index/basket, the Epps curve, the minute richness and its half-life,
    the basket's tracking; then the 2-minute lead-lag by week."""
    out = {}
    tz = cfg["index_tz"]
    etf = session(D.bar_closes("1m", [cfg["etf"]]).get(cfg["etf"], pd.Series(dtype=float)), cfg)
    idx = session(D.bar_closes("1m", [cfg["index"]]).get(cfg["index"], pd.Series(dtype=float)), cfg)
    fut = session(front_bars(cfg, "1m"), cfg) if cfg["future_root"] else pd.Series(dtype=float)
    legs = {"future": fut, "etf": etf, "index": idx}
    if cfg.get("basket_top"):
        h = D.holdings(cfg["etf"]).head(cfg["basket_top"])
        names = [str(t).replace(".", "-") for t in h.ticker]
        cons = D.bar_closes("1m", names)
        if not cons.empty:
            cons = cons[D.session_mask(cons.index, tz, cfg["session"][0], cfg["session"][1])]
            level, cov = B.basket_levels(cfg["etf"], cons, cfg["basket_top"])
            if not level.empty:
                legs["basket"] = np.exp(level)
                e_level = np.log(etf.reindex(level.index).ffill())
                out["basket"] = {**{k: v for k, v in cov.items() if k != "names"}, **B.tracking(level, e_level)}
                out["basket"]["names"] = cov.get("names", [])
    pairs_ = [("future", "etf"), ("future", "index"), ("etf", "index"), ("future", "basket"), ("etf", "basket"), ("basket", "index")]
    ll, curves, by_day = {}, {}, {}
    for a, b in pairs_:
        if a in legs and b in legs and not legs[a].empty and not legs[b].empty:
            s, pooled, days = leadlag_block(legs[a], legs[b], 60, GRID_1M, n_boot, tz)
            ll[f"{a}_vs_{b}"] = s
            if not pooled.empty:
                curves[f"{a}_vs_{b}"] = pooled
                by_day[f"{a}_vs_{b}"] = days
    out["leadlag_1m"] = ll
    out["curves_1m"] = {k: v.to_dict(orient="list") for k, v in curves.items()}
    out["by_day_1m"] = {k: v.to_dict(orient="records") for k, v in by_day.items()}
    if "future" in legs and not fut.empty and not etf.empty:
        ta, xa, da = LL.series_from_bars(fut, 60)
        tb, xb, db = LL.series_from_bars(etf, 60)
        out["epps_future_etf"] = LL.epps(ta, xa, tb, xb, EPPS, da, db).to_dict(orient="records")
    if not etf.empty and not idx.empty:
        ta, xa, da = LL.series_from_bars(etf, 60)
        tb, xb, db = LL.series_from_bars(idx, 60)
        out["epps_etf_index"] = LL.epps(ta, xa, tb, xb, EPPS, da, db).to_dict(orient="records")
    # minute richness against the index and against the fund
    if not fut.empty and panel is not None and not panel.empty:
        rows, segs_i, segs_e = [], [], []
        days = fut.index.tz_convert(ZoneInfo(tz)).normalize().tz_localize(None)
        kap = FV.kappa_series(cfg["index"], cfg["etf"])
        prem = FV.etf_premium(cfg["index"], cfg["etf"], cfg["etf_fee_bp"], prof)
        for d in days.unique():
            if d not in panel.index or pd.isna(panel.at[d, "F_fair"]):
                continue
            r, Dv, tau = panel.at[d, "r"], panel.at[d, "D"], panel.at[d, "tau"]
            f = fut[days == d]
            i = idx.reindex(f.index)
            e = etf.reindex(f.index)
            pv = Dv / (1 + r * tau)
            rho_i = 1e4 * (f - (i - pv) * (1 + r * tau)) / i
            A = float(prem.at[d, "A_model"]) if d in prem.index else 0.0
            k = float(prem.at[d, "kappa"]) if d in prem.index else float(kap.get(d, kap.iloc[-1]))
            i_e = k * (e - A)
            rho_e = 1e4 * (f - (i_e - pv) * (1 + r * tau)) / i_e
            df = pd.DataFrame({"ts": f.index, "date": d, "F": f.values, "I": i.values, "E": e.values, "rho_index_bp": rho_i.values, "rho_etf_bp": rho_e.values})
            rows.append(df)
            ri, re_ = rho_i.dropna().values, rho_e.dropna().values
            if len(ri) > 30:
                segs_i.append(ri - ri.mean())
            if len(re_) > 30:
                segs_e.append(re_ - re_.mean())
        if rows:
            mr = pd.concat(rows)
            D.write_parquet(mr, f"minute_richness_{pair}")
            out["minute_richness"] = {"n_days": int(mr.date.nunique()), "n_bars": int(len(mr)),
                                      "sd_vs_index_bp": float(mr.rho_index_bp.std()), "sd_vs_etf_bp": float(mr.rho_etf_bp.std()),
                                      "within_day_sd_vs_index_bp": float(np.concatenate(segs_i).std()) if segs_i else np.nan,
                                      "within_day_sd_vs_etf_bp": float(np.concatenate(segs_e).std()) if segs_e else np.nan,
                                      "half_life_vs_index_min": FV.half_life_segments(segs_i, n_boot), "half_life_vs_etf_min": FV.half_life_segments(segs_e, n_boot)}
    # 2-minute bars by week
    etf2 = session(D.bar_closes("2m", [cfg["etf"]]).get(cfg["etf"], pd.Series(dtype=float)), cfg)
    idx2 = session(D.bar_closes("2m", [cfg["index"]]).get(cfg["index"], pd.Series(dtype=float)), cfg)
    fut2 = session(front_bars(cfg, "2m"), cfg) if cfg["future_root"] else pd.Series(dtype=float)
    ll2 = {}
    for name, (a, b) in {"future_vs_etf": (fut2, etf2), "etf_vs_index": (etf2, idx2), "future_vs_index": (fut2, idx2)}.items():
        if a.empty or b.empty:
            continue
        s, pooled, days = leadlag_block(a, b, 120, GRID_2M, n_boot, tz)
        if days.empty:
            continue
        days["week"] = pd.to_datetime(days.day).dt.to_period("W").astype(str)
        wk = days.groupby("week").agg(theta_star=("theta_star", "median"), llr=("llr", "median"), rho_star=("rho_star", "median"), n=("day", "size")).reset_index()
        ll2[name] = {"summary": s, "by_week": wk.to_dict(orient="records")}
    out["leadlag_2m"] = ll2
    return out


def firstrate_pair(cfg: dict, n_boot: int) -> dict:
    """ETF against the cash index at one minute over the FirstRate year, by month."""
    m = {"SPY": "SPX", "QQQ": "NDX", "DIA": "DJI"}
    if cfg["etf"] not in m:
        return {}
    w = D.bar_closes("1m", [cfg["etf"], m[cfg["etf"]]], source="firstrate")
    if w.empty or cfg["etf"] not in w or m[cfg["etf"]] not in w:
        return {}
    w = w[D.session_mask(w.index, "America/New_York", "09:31", "16:00")]
    s, pooled, days = leadlag_block(w[cfg["etf"]].dropna(), w[m[cfg["etf"]]].dropna(), 60, GRID_1M, n_boot, "America/New_York")
    if days.empty:
        return {}
    days["month"] = pd.to_datetime(days.day).dt.to_period("M").astype(str)
    mo = days.groupby("month").agg(theta_star=("theta_star", "median"), llr=("llr", "median"), rho_star=("rho_star", "median"), n=("day", "size")).reset_index()
    return {"index_symbol": m[cfg["etf"]], "summary": s, "by_month": mo.to_dict(orient="records"), "curve": pooled.to_dict(orient="list"), "span": [str(days.day.min()), str(days.day.max())]}


# ----------------------------------------------------------------------------- daily
def fair_value_block(panel: pd.DataFrame, n_boot: int, min_days: int = 20) -> dict:
    p = panel[panel.F.notna() & (panel.days >= min_days)]
    by_year = p.groupby(p.index.year).agg(n=("F", "size"), rho_mean=("rho_bp", "mean"), rho_sd=("rho_bp", "std"), spread_median=("spread_bp", "median"),
                                          spread_mean=("spread_bp", "mean"), spread_sd=("spread_bp", "std"), r_mean=("r", "mean")).reset_index().rename(columns={"date": "year"})
    by_year["r_mean"] = 100 * by_year.r_mean
    fw = panel.fwd_spread_bp.dropna()
    return {"n_days": int(len(p)), "from": str(p.index.min().date()) if len(p) else None, "to": str(p.index.max().date()) if len(p) else None,
            "rho_mean_bp": float(p.rho_bp.mean()), "rho_sd_bp": float(p.rho_bp.std()), "spread_mean_bp": float(p.spread_bp.mean()), "spread_median_bp": float(p.spread_bp.median()), "spread_sd_bp": float(p.spread_bp.std()),
            "spread_last_bp": float(panel.spread_bp.dropna().iloc[-1]) if panel.spread_bp.notna().any() else np.nan, "rho_last_bp": float(panel.rho_bp.dropna().iloc[-1]) if panel.rho_bp.notna().any() else np.nan,
            "fwd_spread_mean_bp": float(fw.mean()) if len(fw) else np.nan, "fwd_spread_last_bp": float(fw.iloc[-1]) if len(fw) else np.nan, "fwd_n": int(len(fw)),
            "share_1600_marks": float((panel.mark.str.startswith("16:00")).mean()), "by_year": by_year.to_dict(orient="records"),
            "half_life_rho": FV.half_life(p.rho_bp, 20, n_boot), "half_life_spread": FV.half_life(p.spread_bp, 20, n_boot)}


def premium_block(cfg: dict, profiles: dict, source: str, pair: str, n_boot: int) -> tuple[dict, pd.DataFrame]:
    own = FV.etf_premium(cfg["index"], cfg["etf"], cfg["etf_fee_bp"], profiles[pair])
    if own.empty:
        return {}, own
    src = FV.etf_premium(cfg["index"], cfg["etf"], cfg["etf_fee_bp"], profiles[source])
    uni = FV.etf_premium(cfg["index"], cfg["etf"], cfg["etf_fee_bp"], None)
    none = 1e4 * (own.E - own.I / own.kappa) / own.E   # no accrual model at all
    recent = own[own.index >= own.index.max() - pd.Timedelta(days=5 * 365)]
    return {"n_days": int(len(own)), "from": str(own.index.min().date()), "to": str(own.index.max().date()),
            "prem_mean_bp": float(own.prem_bp.mean()), "prem_sd_bp": float(own.prem_bp.std()), "prem_sd_5y_bp": float(recent.prem_bp.std()),
            "prem_sd_source_profile_bp": float(src.prem_bp.std()), "prem_sd_uniform_bp": float(uni.prem_bp.std()), "prem_sd_no_accrual_bp": float(none.std()),
            "half_life": FV.half_life(own.prem_bp, 20, n_boot), "accrual_sd_meas_bp": float((1e4 * own.A_meas / own.E).std()),
            "dividend_forecast_mae": FV.forecast_errors(cfg["etf"])}, own


def strategy_block(pair: str, panel: pd.DataFrame, cfg: dict, source_params: dict | None, n_boot: int, label: str) -> dict:
    p = P.strategy_series(panel)
    p = p[p.F.notna()]
    if len(p) < 150:
        return {"n_days": int(len(p))}
    sens = []
    if source_params is not None:
        for md in (6, 10, 15, 20, 25):
            pm = P.strategy_series(panel, md)
            pm = pm[pm.F.notna()]
            m, _, _ = S.run(pm, cfg, source_params, True, 0)
            sens.append({"min_days": md, "ann_net_bp": m.get("ann_net_bp"), "sharpe": m.get("sharpe"), "n_trades": m.get("n_trades")})
    own_params, grid = S.fit(p, cfg)
    own, q_own, tr_own = S.run(p, cfg, own_params, True, n_boot)
    out = {"own_params": own_params, "own": own, "grid": grid.to_dict(orient="records")}
    if source_params is not None:
        tr, q_tr, tr_tr = S.run(p, cfg, source_params, True, n_boot)
        nocost, _, _ = S.run(p, cfg, source_params, False, n_boot)
        out["transferred"] = tr
        out["transferred_costless"] = nocost
        D.write_parquet(q_tr.reset_index()[["date", "contract", "F", "I", "E", "spread_bp", "z", "pos", "gross_bp", "cost_bp", "net_bp"]], f"strategy_{pair}_{label}")
        if len(tr_tr):
            D.write_parquet(tr_tr, f"trades_{pair}_{label}")
    carry = S.carry_to_expiry(p, cfg, 60, True)
    carry0 = S.carry_to_expiry(p, cfg, 60, False)
    if len(carry):
        out["carry"] = {"n": int(len(carry)), "mean_net_bp": float(carry.net_bp.mean()), "mean_net_ann_bp": float(carry.net_ann_bp.mean()), "mean_spread_entry_bp": float(carry.spread_entry_bp.mean()),
                        "hit_rate": float((carry.net_bp > 0).mean()), "mean_cost_bp": float(carry.cost_bp.mean()), "mean_gross_ann_bp": float(carry0.net_ann_bp.mean()), "rows": carry.to_dict(orient="records")}
    out["cost_one_way_bp"] = float(np.mean([S.cost_bp(r, cfg) for _, r in p.tail(250).iterrows()]))
    out["mask_sensitivity"] = sens
    return out


# ----------------------------------------------------------------------------- main
def run(fast: bool = False, skip_intraday: bool = False, source: str = "ES"):
    t0 = time.monotonic()
    n_boot = 100 if fast else 400
    cfgs = D.pairs()
    os.makedirs(D.DERIVED, exist_ok=True)
    os.makedirs(D.RESULTS, exist_ok=True)
    R = {"run": {"date": str(dt.date.today()), "fast": fast, "source_pair": source, "n_boot": n_boot}, "pairs": {}}
    dd = D.daily()
    R["run"]["data"] = {"daily_symbols": int(dd.symbol.nunique()), "daily_from": str(dd.date.min().date()), "daily_to": str(dd.date.max().date()), "databento_days": 0}
    dbs = os.path.join(D.REF, "databento_sample.json")
    if os.path.exists(dbs):
        with open(dbs) as f:
            R["run"]["data"]["databento_sample"] = json.load(f)   # the keyless one-session ESZ5 sample run through the loader
    b1 = D.bars("1m")
    if not b1.empty:
        R["run"]["data"].update({"bars_1m_symbols": int(b1.symbol.nunique()), "bars_1m_from": str(b1.ts.min())[:10], "bars_1m_to": str(b1.ts.max())[:10], "bars_1m_rows": int(len(b1)),
                                 "bars_1m_days": int(b1.ts.dt.tz_convert("America/New_York").dt.normalize().nunique())})
    fr = D.bars("1m", source="firstrate")
    if not fr.empty:
        R["run"]["data"].update({"firstrate_from": str(fr.ts.min())[:10], "firstrate_to": str(fr.ts.max())[:10], "firstrate_rows": int(len(fr))})
    del b1, fr
    # 1. accrual profiles
    profiles = {k: FV.accrual_profile(c["index"], c["etf"], c["etf_fee_bp"]) for k, c in cfgs.items()}
    for k, pr in profiles.items():
        D.write_parquet(pr, f"accrual_profile_{k}")
    print(f"profiles {time.monotonic() - t0:.0f}s", flush=True)
    # 2. panels, fair value, premium
    panels, prem_frames = {}, {}
    for k, c in cfgs.items():
        out = {"label": c["label"], "index": c["index"], "etf": c["etf"], "future_root": c["future_root"], "currency": c["currency"], "accrual_profile": profiles[k].to_dict(orient="list")}
        pb, own = premium_block(c, profiles, source, k, n_boot)
        out["etf_premium"] = pb
        if not own.empty:
            D.write_parquet(own.reset_index(), f"etf_premium_{k}")
        if c["future_root"]:
            pn = P.build(k, c, profiles[k])
            panels[k] = pn
            D.write_parquet(pn.reset_index(), f"panel_{k}")
            out["fair_value"] = fair_value_block(pn, n_boot)
            clean = pn[pn.mark.str.startswith("16:00")]
            if len(clean) >= 150:
                out["fair_value_1600"] = fair_value_block(clean, n_boot, 15)
        R["pairs"][k] = out
        print(f"{k} daily {time.monotonic() - t0:.0f}s", flush=True)
    # 3. strategy: fit on the source, transfer
    src_params = None
    if source in panels:
        clean = panels[source][panels[source].mark.str.startswith("16:00")]
        sb = strategy_block(source, clean if len(clean) >= 150 else panels[source], cfgs[source], None, n_boot, "fit")
        src_params = sb.get("own_params")
    for k, pn in panels.items():
        R["pairs"][k]["strategy"] = strategy_block(k, pn, cfgs[k], src_params, n_boot, "long")
        clean = pn[pn.mark.str.startswith("16:00")]
        if len(clean) >= 150:
            R["pairs"][k]["strategy_1600"] = strategy_block(k, clean, cfgs[k], src_params, n_boot, "1600")
        print(f"{k} strategy {time.monotonic() - t0:.0f}s", flush=True)
    R["run"]["strategy_params_source"] = src_params
    # 4. intraday
    if not skip_intraday:
        for k, c in cfgs.items():
            R["pairs"][k].update(intraday_pair(k, c, panels.get(k), profiles[k], n_boot))
            R["pairs"][k]["firstrate"] = firstrate_pair(c, n_boot)
            print(f"{k} intraday {time.monotonic() - t0:.0f}s", flush=True)
    # 5. transfer table
    rows = []
    srcp = R["pairs"].get(source, {})
    for k, c in cfgs.items():
        pr = R["pairs"][k]
        row = {"pair": k, "label": c["label"], "is_source": k == source}
        pb = pr.get("etf_premium", {})
        row.update({"prem_sd_own": pb.get("prem_sd_bp"), "prem_sd_transferred": pb.get("prem_sd_source_profile_bp"), "prem_sd_uniform": pb.get("prem_sd_uniform_bp"), "prem_sd_none": pb.get("prem_sd_no_accrual_bp")})
        fkey = "fair_value_1600" if "fair_value_1600" in pr and "fair_value_1600" in srcp else "fair_value"
        fv = pr.get(fkey, {})
        if fv and srcp.get(fkey):
            pn = panels[k]
            if fkey == "fair_value_1600":
                pn = pn[pn.mark.str.startswith("16:00")]
            p = pn[pn.F.notna() & (pn.days >= (15 if fkey == "fair_value_1600" else 20))].rho_bp
            h_own, h_src = fv["half_life_rho"], srcp[fkey]["half_life_rho"]
            row.update({"dynamics_series": fkey, "hl_rho_own": h_own["half_life"], "hl_rho_own_lo": h_own["hl_lo"], "hl_rho_own_hi": h_own["hl_hi"], "hl_rho_source": h_src["half_life"],
                        "hl_rho_own_iv": h_own["half_life_iv"], "hl_rho_source_iv": h_src["half_life_iv"],
                        "mse_ratio_transferred": FV.forecast_mse(p, h_src["phi"]) / FV.forecast_mse(p, h_own["phi"]),
                        "mse_ratio_random_walk": FV.forecast_mse(p, 1.0) / FV.forecast_mse(p, h_own["phi"])})
        skey = "strategy_1600" if "strategy_1600" in pr else "strategy"
        st = pr.get(skey, {})
        row["strategy_series"] = skey
        if st.get("own"):
            row.update({"strat_net_own": st["own"].get("ann_net_bp"), "strat_sharpe_own": st["own"].get("sharpe"),
                        "strat_net_transferred": st.get("transferred", {}).get("ann_net_bp"), "strat_sharpe_transferred": st.get("transferred", {}).get("sharpe"),
                        "strat_lo_transferred": st.get("transferred", {}).get("ann_lo"), "strat_hi_transferred": st.get("transferred", {}).get("ann_hi")})
        ll = pr.get("leadlag_1m", {})
        key = "etf_vs_index"   # the leg pair with a measurable lead at one-minute resolution
        sll = srcp.get("leadlag_1m", {}).get(key, {})
        if ll.get(key, {}).get("n_days"):
            row.update({"leadlag_key": key, "theta_own": ll[key]["theta_star"], "theta_own_lo": ll[key].get("theta_lo"), "theta_own_hi": ll[key].get("theta_hi"), "llr_own": ll[key]["llr"],
                        "llr_own_lo": ll[key].get("llr_lo"), "llr_own_hi": ll[key].get("llr_hi"),
                        "theta_source": sll.get("theta_star"), "theta_source_lo": sll.get("theta_lo"), "theta_source_hi": sll.get("theta_hi"), "llr_source": sll.get("llr"),
                        "llr_source_lo": sll.get("llr_lo"), "llr_source_hi": sll.get("llr_hi")})
            fe = ll.get("future_vs_etf", {})
            if fe.get("n_days"):
                row.update({"theta_future_etf": fe["theta_star"], "llr_future_etf": fe["llr"], "llr_future_etf_lo": fe.get("llr_lo"), "llr_future_etf_hi": fe.get("llr_hi")})
        rows.append(row)
    tt = T.table(rows)
    R["transfer"] = {"source": source, "params": src_params, "rows": tt.to_dict(orient="records")}
    D.write_parquet(tt, "transfer_table")
    R["run"]["seconds"] = round(time.monotonic() - t0)
    with open(os.path.join(D.RESULTS, "run.json"), "w") as f:
        json.dump(_j(R), f, indent=1)
    print(f"results/run.json in {R['run']['seconds']}s")
    return R
