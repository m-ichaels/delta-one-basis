// Hayashi-Yoshida (2005) covariance of two asynchronously observed log-price series over a grid of time shifts, for
// every day at once: the compute-heavy part of d1basis/leadlag.py (per_day and contrast), which keeps the Python
// reference and calls this when it is built.
//
//     HY(theta) = sum_i sum_j dX_i dY_j 1[ (a_i, b_i] overlaps (s0_j, s1_j] ]
//
// with X's intervals (a_i, b_i] = (tx_i, tx_{i+1}] and Y's intervals shifted by theta, (s0_j, s1_j] =
// (ty_j - theta, ty_{j+1} - theta].  For one X interval the overlapping Y intervals are a contiguous run [j_lo, j_hi),
// so the inner sum is a difference of the cumulative sum of dY.  Python calls hy_cov once per day and shift, and each
// call finds j_lo and j_hi with two searchsorted calls; here one call covers every day and shift, dX and the cumulative
// sum are computed once per day, and a two-pointer sweep finds both ends of every run (they only move forward as i
// grows), O(n + m) per shift.
//
// The arithmetic is numpy's, operation for operation: the shifted times are rounded as numpy rounds them, the
// cumulative sum is sequential, and every sum is numpy's pairwise summation, so both implementations return the same
// bits (tests/test_leadlag.py compares them).  build_ext.py turns off fused multiply-add for the same reason.
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace py = pybind11;
using Values = py::array_t<double, py::array::c_style | py::array::forcecast>;
using DayIds = py::array_t<int64_t, py::array::c_style>;  // integer ids only: a fractional id is refused, not truncated
using Rows = std::vector<std::ptrdiff_t>;

// numpy's pairwise summation (pairwise_sum_DOUBLE, numpy/_core/src/umath/loops_utils.h.src): a plain loop below 8
// terms, eight interleaved accumulators up to 128, and above that two halves split at a multiple of 8.  np.sum adds
// the result to the identity 0.0.
static double pairwise_sum(const double* a, std::ptrdiff_t n) {
    if (n < 8) {
        double res = 0.0;
        for (std::ptrdiff_t i = 0; i < n; ++i) res += a[i];
        return res;
    }
    if (n <= 128) {
        double r[8];
        for (int k = 0; k < 8; ++k) r[k] = a[k];
        std::ptrdiff_t i = 8;
        for (; i < n - (n % 8); i += 8)
            for (int k = 0; k < 8; ++k) r[k] += a[i + k];
        double res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for (; i < n; ++i) res += a[i];
        return res;
    }
    std::ptrdiff_t n2 = n / 2;
    n2 -= n2 % 8;
    return pairwise_sum(a, n2) + pairwise_sum(a + n2, n - n2);
}

// The sweep needs sorted clocks; NaN fails the test too.
static void require_sorted(const double* t, std::ptrdiff_t n, const char* name) {
    for (std::ptrdiff_t i = 1; i < n; ++i)
        if (!(t[i] >= t[i - 1])) throw std::invalid_argument(std::string(name) + " must be non-decreasing");
}

// Working arrays, reused from one day to the next.
struct Work {
    std::vector<double> dx, cum, s, term, sq;
    std::vector<double> tx, x, ty, y;  // one day's rows of each series
};

// HY(theta[q]) into res[q], q < k, for one pair of series with n, m >= 2 observations on sorted clocks.
static void hy_sweep(const double* tX, const double* X, std::ptrdiff_t n, const double* tY, const double* Y,
                     std::ptrdiff_t m, const double* theta, std::ptrdiff_t k, double* res, Work& w) {
    w.dx.resize(n - 1);
    w.term.resize(n - 1);
    w.cum.resize(m);
    w.s.resize(m);
    for (std::ptrdiff_t i = 0; i + 1 < n; ++i) w.dx[i] = X[i + 1] - X[i];
    // cum[j] = dY_0 + ... + dY_{j-1}, i.e. numpy's concatenate([[0.0], cumsum(dy)]): cumsum starts from dY_0 itself
    w.cum[0] = 0.0;
    w.cum[1] = Y[1] - Y[0];
    for (std::ptrdiff_t j = 2; j < m; ++j) w.cum[j] = w.cum[j - 1] + (Y[j] - Y[j - 1]);

    for (std::ptrdiff_t q = 0; q < k; ++q) {
        for (std::ptrdiff_t j = 0; j < m; ++j) w.s[j] = tY[j] - theta[q];  // s0_j = s[j], s1_j = s[j + 1]
        std::ptrdiff_t lo = 0;  // number of s1_j <= a_i: searchsorted(s1, a, side="right")
        std::ptrdiff_t hi = 0;  // number of s0_j <  b_i: searchsorted(s0, b, side="left")
        for (std::ptrdiff_t i = 0; i + 1 < n; ++i) {
            while (lo < m - 1 && w.s[lo + 1] <= tX[i]) ++lo;
            while (hi < m - 1 && w.s[hi] < tX[i + 1]) ++hi;
            w.term[i] = w.dx[i] * (w.cum[std::max(hi, lo)] - w.cum[lo]);
        }
        res[q] = 0.0 + pairwise_sum(w.term.data(), n - 1);
    }
}

// np.sum(np.diff(x) ** 2)
static double sum_sq_increments(const double* x, std::ptrdiff_t n, Work& w) {
    w.sq.resize(n - 1);
    for (std::ptrdiff_t i = 0; i + 1 < n; ++i) {
        const double d = x[i + 1] - x[i];
        w.sq[i] = d * d;
    }
    return 0.0 + pairwise_sum(w.sq.data(), n - 1);
}

// The rows of each day in their original order, by increasing day id: what x[day == d] selects for each d.  Day ids
// follow the clock, so a day is normally one run of rows and costs one map lookup.
static std::map<int64_t, Rows> rows_by_day(const int64_t* day, std::ptrdiff_t n) {
    std::map<int64_t, Rows> rows;
    Rows* run = nullptr;
    for (std::ptrdiff_t i = 0; i < n; ++i) {
        if (run == nullptr || day[i] != day[i - 1]) run = &rows[day[i]];
        run->push_back(i);
    }
    return rows;
}

// One day's rows of a series, copied into contiguous arrays.
static void gather(const double* t, const double* v, const Rows& rows, std::vector<double>& t_out,
                   std::vector<double>& v_out) {
    t_out.resize(rows.size());
    v_out.resize(rows.size());
    for (std::size_t r = 0; r < rows.size(); ++r) {
        t_out[r] = t[rows[r]];
        v_out[r] = v[rows[r]];
    }
}

// contrast(): HY(theta) for each theta in grid, for one pair of series.  tx, x: X's observation times (seconds,
// non-decreasing) and log prices; ty, y: the same for Y.  theta > 0 pairs Y's increment at s with X's increment around
// s - theta (X leads).
static py::array_t<double> hy_grid(const Values& tx, const Values& x, const Values& ty, const Values& y,
                                   const Values& grid) {
    const std::ptrdiff_t n = tx.size(), m = ty.size(), k = grid.size();
    if (x.size() != n || y.size() != m) throw std::invalid_argument("times and prices must have the same length");
    py::array_t<double> out(k);
    double* res = out.mutable_data();
    if (n < 2 || m < 2) {  // no increment on one side: HY is 0 at every shift, as in hy_cov
        std::fill(res, res + k, 0.0);
        return out;
    }
    require_sorted(tx.data(), n, "tx");
    require_sorted(ty.data(), m, "ty");
    {
        py::gil_scoped_release release;  // plain arrays from here on
        Work w;
        hy_sweep(tx.data(), x.data(), n, ty.data(), y.data(), m, grid.data(), k, res, w);
    }
    return out;
}

// per_day(): the days both series observe, in increasing order, and for each day on which both have at least three
// observations, HY(theta) over the grid and the sum of squared increments of each series.  day_x, day_y: the integer
// day id of every row.  Returns (covs[kept day, theta], sxs[kept day], sys[kept day], common day ids).
static py::tuple hy_per_day(const Values& tx, const Values& x, const Values& ty, const Values& y, const DayIds& day_x,
                            const DayIds& day_y, const Values& grid) {
    const std::ptrdiff_t n = tx.size(), m = ty.size(), k = grid.size();
    if (x.size() != n || day_x.size() != n || y.size() != m || day_y.size() != m)
        throw std::invalid_argument("times, prices and day ids must have the same length");
    const std::map<int64_t, Rows> rx = rows_by_day(day_x.data(), n), ry = rows_by_day(day_y.data(), m);

    // the common days, by a two-pointer pass over the two sorted day lists; the ones with three rows each are kept
    std::vector<int64_t> common;
    std::vector<std::pair<const Rows*, const Rows*>> kept;
    for (auto ix = rx.begin(), iy = ry.begin(); ix != rx.end() && iy != ry.end();) {
        if (ix->first < iy->first) {
            ++ix;
        } else if (iy->first < ix->first) {
            ++iy;
        } else {
            common.push_back(ix->first);
            if (ix->second.size() >= 3 && iy->second.size() >= 3) kept.emplace_back(&ix->second, &iy->second);
            ++ix;
            ++iy;
        }
    }
    const py::ssize_t nk = static_cast<py::ssize_t>(kept.size());
    // shaped as numpy shapes the Python's lists: (days, shifts), or (0,) when no day is kept
    py::array_t<double> covs = nk ? py::array_t<double>(std::vector<py::ssize_t>{nk, k}) : py::array_t<double>(0);
    py::array_t<double> sxs(nk), sys(nk);
    py::array_t<int64_t> days(static_cast<py::ssize_t>(common.size()));
    std::copy(common.begin(), common.end(), days.mutable_data());
    double* c = covs.mutable_data();
    double* sx = sxs.mutable_data();
    double* sy = sys.mutable_data();
    const double *tX = tx.data(), *X = x.data(), *tY = ty.data(), *Y = y.data(), *theta = grid.data();
    {
        py::gil_scoped_release release;  // plain arrays from here on
        Work w;
        for (py::ssize_t d = 0; d < nk; ++d) {
            gather(tX, X, *kept[d].first, w.tx, w.x);
            gather(tY, Y, *kept[d].second, w.ty, w.y);
            const std::ptrdiff_t nd = w.tx.size(), md = w.ty.size();
            require_sorted(w.tx.data(), nd, "tx within a day");
            require_sorted(w.ty.data(), md, "ty within a day");
            hy_sweep(w.tx.data(), w.x.data(), nd, w.ty.data(), w.y.data(), md, theta, k, c + d * k, w);
            sx[d] = sum_sq_increments(w.x.data(), nd, w);
            sy[d] = sum_sq_increments(w.y.data(), md, w);
        }
    }
    return py::make_tuple(covs, sxs, sys, days);
}

PYBIND11_MODULE(_hy, mod) {
    mod.doc() = "Hayashi-Yoshida covariance over a grid of time shifts: the compiled core of d1basis.leadlag";
    mod.def("hy_grid", &hy_grid, py::arg("tx"), py::arg("x"), py::arg("ty"), py::arg("y"), py::arg("grid"),
            "HY(theta) for each theta in grid: contrast()'s [hy_cov(tx, x, ty, y, th) for th in grid]");
    mod.def("hy_per_day", &hy_per_day, py::arg("tx"), py::arg("x"), py::arg("ty"), py::arg("y"), py::arg("day_x"),
            py::arg("day_y"), py::arg("grid"),
            "per_day()'s covs, sxs, sys and common days in one call: every day, every shift");
}
