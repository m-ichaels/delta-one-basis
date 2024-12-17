"""The cash basket: a capitalisation-weighted portfolio of the fund's largest holdings built from their bars, its
coverage of the fund, and how closely it tracks the fund and the index at the bar frequency."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import data as D


def basket_levels(etf: str, closes: pd.DataFrame, top: int = 25) -> tuple[pd.Series, dict]:
    """Basket log-level series on the bars' grid from the top-`top` holdings present in `closes` (wide, UTC index).
    Weights are the holdings file's, renormalised over the names with bars; missing bars are forward-filled inside the
    day.  Returns the basket level (starts at the first bar of each day from the previous level) and a coverage dict."""
    h = D.holdings(etf).head(top).copy()
    h["ticker"] = h.ticker.astype(str).str.replace(".", "-", regex=False)
    names = [t for t in h.ticker if t in closes.columns]
    if not names:
        return pd.Series(dtype=float), {"n_names": 0, "weight_covered": 0.0}
    w = h.set_index("ticker").loc[names, "weight"].astype(float)
    cov = float(w.sum())
    w = w / w.sum()
    px = closes[names].ffill()
    lr = np.log(px).diff()
    lr = lr.where(lr.notna(), 0.0)
    # the first bar of each name carries no return; a name with no bar in a period contributes zero
    r = (lr * w.values).sum(axis=1)
    level = r.cumsum()
    return level, {"n_names": len(names), "weight_covered": cov, "names": names}


def tracking(level_a: pd.Series, level_b: pd.Series) -> dict:
    """Correlation of increments and the annualised tracking error (bp) of two log-level series on a common grid."""
    df = pd.concat([level_a.rename("a"), level_b.rename("b")], axis=1).dropna()
    d = df.diff().dropna()
    if len(d) < 10:
        return {"n": int(len(d)), "corr": np.nan, "te_bp_per_bar": np.nan}
    return {"n": int(len(d)), "corr": float(d.a.corr(d.b)), "te_bp_per_bar": float(1e4 * (d.a - d.b).std())}
