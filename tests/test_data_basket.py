import os

import numpy as np
import pandas as pd

from d1basis import basket as B
from d1basis import data as D


def test_load_mbp1_csv(tmp_path):
    p = tmp_path / "mbp1.csv"
    rows = ["ts_event,rtype,publisher_id,instrument_id,action,side,depth,price,size,flags,ts_in_delta,sequence,bid_px_00,ask_px_00,bid_sz_00,ask_sz_00,symbol"]
    px = [(5000000000000, 5000250000000), (5000000000000, 5000250000000), (5000250000000, 5000500000000), (0, 5000500000000)]
    for k, (b, a) in enumerate(px):
        rows.append(f"2026-09-14T13:30:00.{k:03d}000000Z,1,1,1,A,B,0,{b},1,0,0,{k},{b},{a},5,5,ESZ6")
    p.write_text("\n".join(rows))
    df = D.load_mbp1(str(p))
    assert list(df.columns) == ["ts", "symbol", "bid", "ask", "mid"]
    assert len(df) == 2                       # unchanged mid dropped, empty bid dropped
    assert abs(df.mid.iloc[0] - 5000.125) < 1e-9 and abs(df.mid.iloc[1] - 5000.375) < 1e-9
    assert df.ts.dt.tz is not None


def test_session_mask():
    idx = pd.DatetimeIndex(["2026-09-14 13:29", "2026-09-14 13:30", "2026-09-14 19:59", "2026-09-14 20:00", "2026-09-13 15:00"], tz="UTC")
    m = D.session_mask(idx, "America/New_York", "09:30", "16:00")
    assert list(m) == [False, True, True, False, False]


def test_basket_levels_and_tracking(tmp_path, monkeypatch):
    hd = tmp_path / "holdings"
    hd.mkdir()
    pd.DataFrame({"ticker": ["AAA", "BBB", "CCC"], "name": ["a", "b", "c"], "weight": [6.0, 3.0, 1.0], "shares": [1, 1, 1]}).to_csv(hd / "XYZ.csv", index=False)
    monkeypatch.setattr(D, "REF", str(tmp_path))
    idx = pd.date_range("2026-09-14 13:30", periods=4, freq="1min", tz="UTC")
    closes = pd.DataFrame({"AAA": [100, 101, 101, 102.0], "BBB": [50, 50, 51, 51.0]}, index=idx)
    level, cov = B.basket_levels("XYZ", closes, top=3)
    assert cov["n_names"] == 2 and abs(cov["weight_covered"] - 9.0) < 1e-12
    r1 = (6 / 9) * np.log(101 / 100) + (3 / 9) * 0.0
    assert abs(level.iloc[1] - r1) < 1e-12
    tr = B.tracking(level, level * 1.0)
    assert tr["corr"] > 0.999 if tr["n"] >= 10 else np.isnan(tr["corr"])
