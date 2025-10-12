#!/usr/bin/env python3
"""The keyless Databento samples: one Globex session of ESZ5 MBP-1 (2025-09-22) and one day of NVDA on XNAS/ARCX
(2025-09-16).  Downloads to data/raw/databento (git-ignored), runs the MBP-1 loader on the real file and writes a
small summary to data/reference/databento_sample.json.  No equity leg shares a day with the futures sample, so the
seconds-scale future-vs-fund lead-lag still needs a paid pull; this proves the loader on real data.
python tools/databento_sample.py"""
import json
import os
import sys
import time
import urllib.request

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from d1basis import data as D  # noqa: E402
from d1basis import leadlag as LL  # noqa: E402

RAW = os.path.join(D.DATA, "raw", "databento")
URL = "https://hist.databento.com/v0/dataset/sample/download/glbx.mdp3/mbp-1?sample_type=futures"


def main():
    os.makedirs(RAW, exist_ok=True)
    p = os.path.join(RAW, "glbx_mdp3_mbp1_sample.csv")
    if not os.path.exists(p):
        t = time.monotonic()
        urllib.request.urlretrieve(URL, p)
        print(f"downloaded {os.path.getsize(p) / 1e6:.0f} MB in {time.monotonic() - t:.0f}s")
    t = time.monotonic()
    mid = D.load_mbp1(p)
    sym = mid.symbol.iloc[0]
    ts = mid.ts
    gaps_ms = np.diff(ts.values.astype("datetime64[ns]").astype("int64")) / 1e6
    # the cash session, New York time
    loc = ts.dt.tz_convert("America/New_York")
    rth = mid[(loc.dt.hour * 60 + loc.dt.minute >= 570) & (loc.dt.hour * 60 + loc.dt.minute < 960)]
    g_rth = np.diff(rth.ts.values.astype("datetime64[ns]").astype("int64")) / 1e6
    # HY autocorrelation-style check: the mid's own increments against themselves shifted (sanity of the tick path)
    tx, x, dx = LL.series_from_ticks(rth.ts, rth.mid)
    grid = np.array([-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0])
    c = LL.contrast(tx, x, tx, x, grid)
    out = {"file": os.path.basename(p), "symbol": sym, "date": str(ts.dt.date.iloc[0]), "rows_loaded": int(len(mid)), "mid_changes_session": int(len(mid)),
           "mid_changes_rth": int(len(rth)), "median_gap_ms_session": float(np.median(gaps_ms)), "median_gap_ms_rth": float(np.median(g_rth)),
           "p10_gap_ms_rth": float(np.percentile(g_rth, 10)), "p90_gap_ms_rth": float(np.percentile(g_rth, 90)),
           "spread_ticks_median": float(((rth.ask - rth.bid) / 0.25).median()), "self_contrast_rho0": float(c.rho.iloc[3]),
           "seconds_to_load": round(time.monotonic() - t, 1), "paired_equity_leg": None,
           "note": "keyless sample; the equities samples (NVDA, 2025-09-16) share no day with it, so no future-vs-fund pair at tick resolution"}
    with open(os.path.join(D.REF, "databento_sample.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
