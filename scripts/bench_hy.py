#!/usr/bin/env python3
"""Time the per-day x lag-grid Hayashi-Yoshida computation, the Python reference against the compiled C++, on the
checked-in data with the project's own lag grids -> results/hy_timing.json.
python scripts/bench_hy.py [--runs 7]   (needs the compiled core: python build_ext.py build_ext --inplace)

The inputs are the leadlag.per_day calls of the pipeline's lead-lag step, recorded from run.intraday_pair and
run.firstrate_pair: one call per pair of series, on the 1-minute bars with GRID_1M, the 2-minute bars with GRID_2M and
the FirstRate year with GRID_1M.  Each implementation makes every one of those calls (Python: hy_cov per day and shift;
C++: one call per pair of series); the best of --runs is kept, and the two sets of outputs are compared."""
import argparse
import datetime as dt
import json
import os
import platform
import sys
import timeit

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from d1basis import data as D  # noqa: E402
from d1basis import leadlag as LL  # noqa: E402
from d1basis import run as RUN  # noqa: E402


def record_calls() -> dict:
    """{set: [per_day arguments, ...]}: every per_day call of the lead-lag step, by data set."""
    calls, where, per_day = {"bars_1m": [], "bars_2m": [], "firstrate_1m": []}, ["bars"], LL.per_day

    def record(*args):
        grid = args[-1]
        name = "firstrate_1m" if where[0] == "firstrate" else ("bars_1m" if np.array_equal(grid, RUN.GRID_1M) else "bars_2m")
        calls[name].append(args)
        return per_day(*args)

    LL.per_day = record
    try:
        for k, c in D.pairs().items():
            where[0] = "bars"
            RUN.intraday_pair(k, c, None, None, 2)       # no panel: the lead-lag legs only; the bootstrap is not timed
            where[0] = "firstrate"
            RUN.firstrate_pair(c, 2)
    finally:
        LL.per_day = per_day
    return calls


def run_all(calls: list, python: bool) -> list:
    ext = LL._ext
    if python:
        LL._ext = None
    try:
        return [LL.per_day(*a) for a in calls]
    finally:
        LL._ext = ext


def best(calls: list, python: bool, runs: int) -> float:
    return min(timeit.repeat(lambda: run_all(calls, python), number=1, repeat=runs))   # timeit turns gc off


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=7)
    a = ap.parse_args()
    if not LL.HAVE_EXT:
        sys.exit("the compiled core is not built: python build_ext.py build_ext --inplace (build.ps1 on Windows)")
    sets = record_calls()
    out = {"what": "leadlag.per_day for every pair of series in the pipeline's lead-lag step: the HY covariance over the "
                   "lag grid for every day, with the per-day sums of squares; Python (hy_cov per day and shift) against "
                   "the C++ core (cpp/hy.cpp, one call per pair of series)",
           "data": "checked-in bars: 1-minute (GRID_1M, -900..900 s by 30 s), 2-minute (GRID_2M, -1800..1800 s by 60 s) "
                   "and the FirstRate year at one minute (GRID_1M)",
           "timing": "best of `runs` runs (timeit, gc off) for each implementation", "runs": a.runs,
           "date": str(dt.date.today()), "sets": {}}
    every = []
    for name, calls in sets.items():
        py_s, cpp_s = best(calls, True, a.runs), best(calls, False, a.runs)
        days = sum(len(r[1]) for r in run_all(calls, False))
        out["sets"][name] = {"calls": len(calls), "days": days, "shifts": int(len(calls[0][-1])),
                             "observations": int(sum(len(c[0]) + len(c[2]) for c in calls)),
                             "python_s": py_s, "cpp_s": cpp_s, "speedup": py_s / cpp_s}
        every += calls
        print(f"{name}: {len(calls)} calls, {days} days, Python {py_s:.3f} s, C++ {cpp_s:.4f} s, {py_s / cpp_s:.1f}x", flush=True)
    py_s, cpp_s = best(every, True, a.runs), best(every, False, a.runs)
    c, p = run_all(every, False), run_all(every, True)
    out["total"] = {"calls": len(every), "days": sum(len(r[1]) for r in c), "python_s": py_s, "cpp_s": cpp_s, "speedup": py_s / cpp_s}
    same = [u[3] == v[3] and all(np.array_equal(s, t) for s, t in zip(u[:3], v[:3])) for u, v in zip(c, p)]
    out["agreement"] = {"calls": len(every), "bit_identical": int(sum(same)),
                        "max_abs_diff": float(max(np.max(np.abs(s - t), initial=0.0) for u, v in zip(c, p) for s, t in zip(u[:3], v[:3])))}
    out["machine"] = {"platform": platform.platform(), "processor": platform.processor(), "cpu_count": os.cpu_count(),
                      "python": platform.python_version(), "numpy": np.__version__, "extension": os.path.basename(LL._ext.__file__)}
    with open(os.path.join(ROOT, "results", "hy_timing.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
    t = out["total"]
    print(f"total: {t['calls']} calls, {t['days']} days, Python {t['python_s']:.3f} s, C++ {t['cpp_s']:.4f} s, {t['speedup']:.1f}x; "
          f"{out['agreement']['bit_identical']} of {t['calls']} calls bit-identical -> results/hy_timing.json")


if __name__ == "__main__":
    main()
