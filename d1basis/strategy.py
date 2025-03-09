"""The basis strategy: trade the front contract's implied-financing spread against the fund, net of measured costs.

Position +1 = long basis (long future, short fund; the cash from the short earns the rebate r - borrow);
         -1 = short basis (short future, long fund funded at r + funding spread).
Daily P&L in bp of notional:  pos x [ dF / I - (dE + div) / E ] x 1e4  +  pos x carry,
carry(+1) = (r - borrow) / 360 x 1e4,  carry(-1) = -(r + funding) / 360 x 1e4, per calendar day to the next row.
Each position change pays the future's half-spread and fee and the fund's half-spread and commission.
Signal: z-score of the spread over a trailing window; enter beyond z0 against the sign of the spread, exit inside z1
or at the roll.  The parameters (z0, z1, window) are fitted on one pair by net Sharpe and applied unchanged to the
others in the transfer test.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

DEFAULT = {"z0": 1.5, "z1": 0.25, "window": 60}


def cost_bp(row, cfg: dict) -> float:
    """One-way cost of a unit basis position, bp of notional: future half-spread + fee, fund half-spread + commission."""
    F, E = row["F"], row["E"]
    fut = (cfg["tick"] / 2) / F + cfg.get("fee_future_usd", 0.0) / (cfg["multiplier"] * F)
    etf = (cfg["etf_tick"] / 2) / E + cfg.get("etf_commission_per_share", 0.0) / E
    return 1e4 * (fut + etf)


def positions(p: pd.DataFrame, z0: float, z1: float, window: int, col: str = "spread_bp") -> pd.DataFrame:
    s = p[col]
    mu = s.rolling(window, min_periods=window // 2).mean()
    sd = s.rolling(window, min_periods=window // 2).std()
    z = (s - mu) / sd
    pos = np.zeros(len(p))
    cur = 0
    contracts = p.contract.values
    for i in range(len(p)):
        zi = z.iloc[i]
        if i > 0 and contracts[i] != contracts[i - 1]:
            cur = 0  # the roll closes the position; the new contract's signal decides afresh
        if np.isnan(zi) or np.isnan(p.F.iloc[i]):
            cur = 0
        elif cur == 0:
            if zi > z0:
                cur = -1
            elif zi < -z0:
                cur = 1
        else:
            if abs(zi) < z1 or np.sign(zi) == cur:
                cur = 0
        pos[i] = cur
    out = p.copy()
    out["z"] = z
    out["pos"] = pos
    return out


def pnl(p: pd.DataFrame, cfg: dict, with_costs: bool = True) -> pd.DataFrame:
    """Daily P&L (bp of notional) given a `pos` column (position held from this close to the next)."""
    out = p.copy()
    dF = out.F.shift(-1) - out.F
    dE = out.E.shift(-1) + out["div"].shift(-1) - out.E
    same = out.contract.shift(-1) == out.contract
    ret = np.where(same, 1e4 * (dF / out.I - dE / out.E), np.nan)
    r = out.r.fillna(0.0)
    cal_days = pd.Series(out.index, index=out.index).shift(-1).sub(out.index.to_series()).dt.days.fillna(1).clip(lower=1).values
    carry = np.where(out.pos > 0, (r - cfg.get("etf_borrow_bp", 0) / 1e4) / 360 * 1e4, np.where(out.pos < 0, -(r + cfg.get("etf_funding_bp", cfg.get("etf_borrow_bp", 0)) / 1e4) / 360 * 1e4, 0.0)) * cal_days
    gross = out.pos * np.nan_to_num(ret) + carry
    # a position open when the contract changes is closed at that close (its next-day return is dropped): charge the
    # exit there, and treat the next row as a fresh entry
    prev = out.pos.shift(1).fillna(0.0).where(same.shift(1).fillna(True), 0.0)
    dpos = (out.pos - prev).abs()
    c = np.array([cost_bp(row, cfg) for _, row in out.iterrows()]) if with_costs else np.zeros(len(out))
    cost = dpos.values * c
    roll_exit = (~same) & (out.pos != 0)
    cost = cost + np.where(roll_exit, np.abs(out.pos) * c, 0.0)
    out["ret_bp"] = ret
    out["gross_bp"] = gross
    out["cost_bp"] = cost
    out["net_bp"] = gross - cost
    return out


def trades(p: pd.DataFrame) -> pd.DataFrame:
    """One row per round trip: entry, exit, side, days, gross, cost, net (bp).  A trade ends when the position goes
    flat, flips, or the contract rolls (the roll exit is charged on the last day of the old contract)."""
    rows, open_i = [], None
    pos, con = p.pos.values, p.contract.values
    n = len(p)

    def close(a, b):
        seg = p.iloc[a:b + 1]
        rows.append({"entry": p.index[a], "exit": p.index[b], "side": int(pos[a]), "days": int(b - a), "contract": con[a],
                     "gross_bp": float(seg.gross_bp.sum()), "cost_bp": float(seg.cost_bp.sum()), "net_bp": float(seg.net_bp.sum()), "z_entry": float(p.z.iloc[a])})

    for i in range(n):
        if open_i is None:
            if pos[i] != 0:
                open_i = i
            continue
        if con[i] != con[open_i] or pos[i] != pos[open_i]:
            if con[i] != con[open_i]:
                close(open_i, i - 1)          # rolled: exit cost sits on the old contract's last row
            else:
                close(open_i, i)              # flat (row i carries the exit cost) or flipped
            open_i = i if pos[i] != 0 else None
        elif i == n - 1:
            close(open_i, i)
            open_i = None
    return pd.DataFrame(rows, columns=["entry", "exit", "side", "days", "contract", "gross_bp", "cost_bp", "net_bp", "z_entry"])


def metrics(daily_net: pd.Series, tr: pd.DataFrame, n_boot: int = 1000, seed: int = 0) -> dict:
    x = daily_net.dropna().values
    n = len(x)
    if n < 10:
        return {"n_days": n}
    ann = 252 * x.mean()
    vol = np.sqrt(252) * x.std()
    cum = np.cumsum(x)
    dd = float((np.maximum.accumulate(cum) - cum).max())
    rng = np.random.default_rng(seed)
    block = 20
    nb = int(np.ceil(n / block))
    anns = []
    for _ in range(n_boot):
        starts = rng.integers(0, n, nb)
        idx = np.concatenate([(s + np.arange(block)) % n for s in starts])[:n]
        anns.append(252 * x[idx].mean())
    out = {"n_days": int(n), "days_in_position": int((daily_net.notna() & (daily_net != 0)).sum()), "ann_net_bp": float(ann), "ann_vol_bp": float(vol), "sharpe": float(ann / vol) if vol > 0 else np.nan,
           "max_dd_bp": dd, "ann_lo": float(np.percentile(anns, 2.5)) if anns else np.nan, "ann_hi": float(np.percentile(anns, 97.5)) if anns else np.nan}
    if len(tr):
        t = tr.net_bp.values
        boots = [rng.choice(t, len(t)).mean() for _ in range(n_boot)]
        out.update({"n_trades": int(len(tr)), "mean_trade_net_bp": float(t.mean()), "trade_lo": float(np.percentile(boots, 2.5)) if boots else np.nan, "trade_hi": float(np.percentile(boots, 97.5)) if boots else np.nan,
                    "hit_rate": float((t > 0).mean()), "mean_days": float(tr.days.mean()), "mean_gross_bp": float(tr.gross_bp.mean()), "mean_cost_bp": float(tr.cost_bp.mean())})
    else:
        out.update({"n_trades": 0})
    return out


def run(p: pd.DataFrame, cfg: dict, params: dict | None = None, with_costs: bool = True, n_boot: int = 1000) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    params = dict(DEFAULT, **(params or {}))
    q = positions(p, params["z0"], params["z1"], int(params["window"]))
    q = pnl(q, cfg, with_costs)
    tr = trades(q)
    m = metrics(q.net_bp, tr, n_boot)
    m.update({"z0": params["z0"], "z1": params["z1"], "window": int(params["window"]), "with_costs": with_costs})
    return m, q, tr


def fit(p: pd.DataFrame, cfg: dict, grid: dict | None = None) -> tuple[dict, pd.DataFrame]:
    """Grid search by net Sharpe (ties broken by fewer trades); returns the best parameters and the whole grid."""
    grid = grid or {"z0": [1.0, 1.5, 2.0], "z1": [0.0, 0.25, 0.5], "window": [40, 60, 90]}
    rows = []
    for z0, z1, w in itertools.product(grid["z0"], grid["z1"], grid["window"]):
        m, _, _ = run(p, cfg, {"z0": z0, "z1": z1, "window": w}, n_boot=0)
        rows.append({"z0": z0, "z1": z1, "window": w, "sharpe": m.get("sharpe", np.nan), "ann_net_bp": m.get("ann_net_bp", np.nan), "n_trades": m.get("n_trades", 0)})
    g = pd.DataFrame(rows)
    best = g.sort_values(["sharpe", "n_trades"], ascending=[False, True]).iloc[0]
    return {"z0": float(best.z0), "z1": float(best.z1), "window": int(best.window)}, g


def carry_to_expiry(p: pd.DataFrame, cfg: dict, entry_days: int = 60, with_costs: bool = True) -> pd.DataFrame:
    """The plain cash-and-carry: on the first day with <= entry_days to expiry, short the basis if the spread is
    positive (future rich to fair), long if negative, and hold to the roll.  One row per contract: the spread at
    entry, the realised net return in bp and annualised."""
    rows = []
    for s, g in p.groupby("contract", sort=False):
        g = g[g.F.notna() & g.spread_bp.notna()]
        g = g[g.days <= entry_days]
        if len(g) < 5:
            continue
        side = -np.sign(g.spread_bp.iloc[0])
        q = g.copy()
        q["pos"] = side
        q = pnl(q, cfg, with_costs)
        net = q.net_bp.iloc[:-1].sum()
        rows.append({"contract": s, "entry": g.index[0], "days": int(len(g) - 1), "spread_entry_bp": float(g.spread_bp.iloc[0]), "side": int(side),
                     "gross_bp": float(q.gross_bp.iloc[:-1].sum()), "cost_bp": float(q.cost_bp.sum()), "net_bp": float(net), "net_ann_bp": float(net * 365 / max(g.days.iloc[0] - g.days.iloc[-1], 1))})
    return pd.DataFrame(rows)
