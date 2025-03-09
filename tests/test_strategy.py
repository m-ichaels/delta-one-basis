import numpy as np
import pandas as pd

from d1basis import strategy as S

CFG = {"tick": 0.25, "multiplier": 50, "etf_tick": 0.01, "fee_future_usd": 1.30, "etf_commission_per_share": 0.002, "etf_borrow_bp": 30}


def _panel(n=12):
    idx = pd.bdate_range("2026-01-05", periods=n)
    I = np.full(n, 5000.0)
    F = np.linspace(5010.0, 5000.0, n)          # the future converges to the index
    E = np.full(n, 500.0)
    p = pd.DataFrame({"F": F, "I": I, "E": E, "div": 0.0, "r": 0.0, "contract": "ESH26.CME", "spread_bp": 0.0, "z": 0.0, "days": np.arange(n, 0, -1)}, index=idx)
    return p


def test_cost_bp():
    c = S.cost_bp({"F": 5000.0, "E": 500.0}, CFG)
    expected = 1e4 * ((0.125 / 5000) + 1.30 / (50 * 5000) + (0.005 / 500) + 0.002 / 500)
    assert abs(c - expected) < 1e-12


def test_pnl_reconciles_to_the_basis_move():
    p = _panel()
    p["pos"] = 0.0
    p.loc[p.index[2:8], "pos"] = -1.0                       # short the rich basis for six days
    q = S.pnl(p, CFG, with_costs=False)
    # each day the future falls 10/11 points while I and E are flat: short basis earns that in bp of I, less the
    # funding of the long fund at r + 30 bp (r = 0 here) per calendar day
    cal = np.array([(p.index[i + 1] - p.index[i]).days for i in range(2, 8)])
    step = 1e4 * (10.0 / 11) / 5000 - 0.003 / 360 * 1e4 * cal
    assert np.allclose(q.gross_bp.iloc[2:8], step)
    assert q.gross_bp.iloc[0] == 0 and q.gross_bp.iloc[9] == 0
    q2 = S.pnl(p, CFG, with_costs=True)
    c = S.cost_bp(p.iloc[2], CFG)
    assert q2.cost_bp.iloc[2] > 0 and q2.cost_bp.iloc[8] > 0 and q2.cost_bp.iloc[3] == 0
    assert abs(q2.cost_bp.sum() - (S.cost_bp(p.iloc[2], CFG) + S.cost_bp(p.iloc[8], CFG))) < 1e-9
    tr = S.trades(q2)
    assert len(tr) == 1 and tr.side.iloc[0] == -1 and tr.days.iloc[0] == 6
    assert abs(tr.net_bp.iloc[0] - (step.sum() - q2.cost_bp.sum())) < 1e-9


def test_roll_closes_the_position_and_charges_the_exit():
    p = _panel()
    p.loc[p.index[6:], "contract"] = "ESM26.CME"
    p["pos"] = 1.0
    q = S.pnl(p, CFG, with_costs=True)
    assert np.isnan(q.ret_bp.iloc[5])                     # the cross-contract return is dropped
    assert q.cost_bp.iloc[5] > 0 and q.cost_bp.iloc[6] > 0  # exit on the old, entry on the new
    tr = S.trades(q)
    assert len(tr) == 2 and list(tr.contract) == ["ESH26.CME", "ESM26.CME"]


def test_carry_earns_the_dividend_and_pays_the_rebate():
    p = _panel(4)                                         # Mon .. Thu: one calendar day between rows
    p["pos"] = 1.0                                        # long future, short fund: pays the dividend, earns r - borrow
    p["r"] = 0.04
    p.loc[p.index[2], "div"] = 1.0
    q = S.pnl(p, CFG, with_costs=False)
    carry = (0.04 - 0.003) / 360 * 1e4
    step = 1e4 * (10.0 / 3) / 5000                        # the future converges down: the long basis loses it
    assert abs(q.gross_bp.iloc[0] - (-step + carry)) < 1e-9
    assert abs(q.gross_bp.iloc[1] - (-step - 1e4 * 1.0 / 500 + carry)) < 1e-9   # and pays the dividend on the short
    p2 = _panel(6)                                        # Mon .. Mon: the Friday row carries three days of carry
    p2["pos"] = 1.0
    p2["r"] = 0.04
    q2 = S.pnl(p2, CFG, with_costs=False)
    assert abs(q2.gross_bp.iloc[4] - (-1e4 * 2.0 / 5000 + 3 * carry)) < 1e-9


def test_positions_enter_and_exit_on_z():
    p = _panel(200)
    rng = np.random.default_rng(0)
    p["spread_bp"] = rng.standard_normal(200).cumsum() * 0.1 + rng.standard_normal(200) * 5
    q = S.positions(p, 1.5, 0.25, 40)
    assert set(q.pos.unique()) <= {-1.0, 0.0, 1.0}
    entered = q[(q.pos != 0) & (q.pos.shift(1) == 0)]
    assert (entered.z.abs() > 1.5).all()
    assert np.sign(entered.z).eq(-entered.pos).all()
