"""The new-products test: everything fitted on the source pair (ES / SPY / S&P 500) is applied unchanged to the others.

What is fitted on the source and carried over:
  1. the dividend accrual profile (when inside the quarter the index pays) -> the fund's fair price on the other pairs;
     scored by the sd of the fund premium with the source profile, the pair's own profile, and uniform accrual;
  2. the AR(1) coefficient of the richness (on the series marked at the cash close) -> a one-step forecast on the
     other pair; scored by the forecast MSE against the pair's own coefficient and against a random walk;
  3. the strategy parameters (z0, z1, window) chosen on the source by net Sharpe -> run unchanged; scored against the
     pair's own in-sample best;
  4. the lead-lag horizon theta* and the lead-lag ratio -> compared with the pair's own, inside or outside the
     source's bootstrap interval.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def verdict(row: dict) -> str:
    bits = []
    if pd.notna(row.get("prem_sd_transferred")) and pd.notna(row.get("prem_sd_own")):
        if pd.notna(row.get("prem_sd_none")) and row["prem_sd_none"] < min(row["prem_sd_own"], row["prem_sd_transferred"]):
            bits.append("accrual model hurts (no model is best)")
        else:
            bits.append("profile transfers" if row["prem_sd_transferred"] <= 1.1 * row["prem_sd_own"] else "profile does not transfer")
    if pd.notna(row.get("mse_ratio_transferred")):
        bits.append("dynamics transfer" if row["mse_ratio_transferred"] <= 1.05 else "dynamics do not transfer")
    if pd.notna(row.get("strat_net_transferred")) and pd.notna(row.get("strat_net_own")):
        if row["strat_net_transferred"] > 0 and row["strat_net_transferred"] >= 0.5 * row["strat_net_own"]:
            bits.append("strategy transfers")
        elif row["strat_net_transferred"] > 0:
            bits.append("strategy transfers weakly")
        else:
            bits.append("strategy does not transfer")
    if pd.notna(row.get("theta_own")) and pd.notna(row.get("theta_source_lo")):
        inside = row["theta_source_lo"] <= row["theta_own"] <= row["theta_source_hi"]
        same_sign = np.sign(row["theta_own"]) == np.sign(row.get("theta_source", np.nan)) or row["theta_own"] == 0
        llr_inside = pd.notna(row.get("llr_source_lo")) and row["llr_source_lo"] <= row.get("llr_own", np.nan) <= row["llr_source_hi"]
        if inside and same_sign and llr_inside:
            bits.append("lead-lag transfers")
        elif same_sign:
            bits.append("lead-lag direction transfers, size does not")
        else:
            bits.append("lead-lag does not transfer")
    return "; ".join(bits)


def table(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["verdict"] = [verdict(r) for r in rows]
    return df
