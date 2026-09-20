# delta-one-basis — ETF, index future and cash basket: fair value, lead-lag, and what transfers to a new product

**Question.** A delta-one desk carries the S&P 500 as three instruments — the E-mini, the ETF, the basket — and lives off the differences between them. Where does the basis sit against a fair value with measured financing and dividends, how fast does a deviation close, who leads whom at the bar level, and does everything fitted on ES/SPY carry unchanged to NQ/QQQ, RTY/IWM and a European pair?

**Answer (§Results).** The fair value is measured, not assumed; the basis is a slow financing level plus fast noise; the ETF leads the cash index and the index's lag grows with the number of stale names; the accrual model, the mean-reversion dynamics and the strategy parameters transfer (with wide intervals), and the lead-lag transfers in direction but not in size.
- *Fair value.* The dividend accrual inside the quarter is read off the fund's own price against the index: half-way through a quarter 42 % of SPY's dividends have gone ex, 81 % three-quarters through. With that profile the SPY premium to fair has sd 16.8 bp over 2005–2026 (6.9 bp over the last five years) against 23.9 bp with no accrual model; the point-in-time dividend forecast misses by 6 % on SPY, 21 % on QQQ, 32 % on IWM and 75 % on the Euro Stoxx fund, which is why the model helps SPY, is neutral on QQQ and hurts IWM.
- *Basis.* With both legs marked at the 16:00 cash close (505 days, 2024-04-29–2026-09-18), the ES front contract implies financing of **bills + 50 bp** (median; sd 51), NQ bills + 42, RTY bills + 71; the ES→next calendar spread implies bills + 67 bp, so the roll is priced richer than the front. Over the 2005–2026 daily history the ES median spread was 111 bp in 2008, below bills in 2010–12 and 40 bp in 2025.
- *Mean reversion.* Richness to fair (bp of index) has an OLS half-life of 1.2 days on ES, 1.9 on NQ, 1.8 on RTY; the noise-robust estimator (lag-2 over lag-1 autocovariance) says the persistent component has a half-life of 25, 15 and 9 days. Within the day the deviation of the minute richness from its daily mean has a half-life of **1.4 min** [0.9, 2.3] on ES, 0.6 on NQ, 2.6 on RTY (against the index; 0.8 against the fund).
- *Lead-lag.* At one-minute resolution the future and the ETF are simultaneous (ES: LLR 0.97 [0.94, 1.00], θ* = 0): the seconds-scale lead the literature reports needs the depth data this repository has a loader for and no purchase of. The ETF leads the cash index by about half a minute (θ* = 30 s at the 30 s grid) with LLR 1.12 [1.08, 1.15] on SPY/SPX, 1.24 on QQQ/NDX and **3.96** [3.50, 4.31] on IWM/RUT — the stale-price lag of the index grows with the number of small names in it; one year of SPY/SPX minutes gives LLR 1.13 [1.12, 1.14] with a monthly range of 1.11–1.17. The Epps curve shows it the other way: the 1-minute return correlation of IWM with its index is 0.69 and reaches 0.98 at an hour.
- *Strategy.* A z-score rule on the front contract's implied financing spread (parameters fitted on ES, run unchanged elsewhere) nets **34 bp per year of notional on ES** [2, 74], 62 [20, 107] on NQ and 77 [15, 171] on RTY, Sharpe 1.2/1.9/1.2, with a one-way cost of 0.31 bp on ES; the result moves between 26 and 78 bp with the near-expiry mask, and one three-day trade across the June-2026 Russell reconstitution is 58 % of the RTY total. The same rule on the 17:00-marked futures closes against the 16:00 cash close "earns" 327, 759 and 309 bp a year with Sharpe above 2 — an artefact of marking the legs an hour apart, and the reason the clean series exists. Cash-and-carry to the roll nets -2 bp/yr on ES: the spread is real but the roll gives the last two weeks of it back.
- *Transfer.* NQ: profile transfers; dynamics transfer; strategy transfers; lead-lag direction transfers, size does not. RTY: accrual model hurts (no model is best); dynamics transfer; strategy transfers; lead-lag direction transfers, size does not. SX5E: profile transfers; lead-lag does not transfer.

Data checked 2026-09-19. Python package `d1basis` (numpy/pandas/DuckDB), 24 tests, CI runs the whole pipeline on the checked-in data. Nothing here is simulated except the known-answer tests; no Databento depth was bought (0 paid days). Databento's keyless one-session sample of ESZ5 MBP-1 (2025-09-21, 82,548 top-of-book mid changes, median gap 0.27 ms in the cash session) runs through the loader in 16 s, but its equity samples are NVDA on another day, so the seconds-scale future-vs-fund pair is still the one number that needs a purchase.

---

## Layout

```
tools/databento_sample.py  the keyless Databento samples through the MBP-1 loader -> data/reference/databento_sample.json
tools/download.py      Yahoo daily bars since 2005 and dividends (futures continuous + listed contracts, indices, ETFs, top holdings);
                       Yahoo 1-minute bars in 7-day windows over the trailing 30 days, 2-minute over 60, hourly over 730, appended to
                       data/intraday/bars_*.parquet (run daily: the archive is the input that cannot be downloaded later);
                       NY Fed EFFR/SOFR, ECB EUR short-term rate, US Treasury par curve; SSGA SPY holdings, stockanalysis top-25
                       holdings for QQQ/IWM; the FirstRateData free one-year 1-minute sample (SPY QQQ DIA SPX NDX RUT DJI)
d1basis/calendar.py    NYSE holidays by rule, third-Friday expiries pulled to Thursday, front/second contract, the 8-day roll window
d1basis/fairvalue.py   financing curve (bills interpolated in tenor, or EFFR/SOFR/ESTR flat), point-in-time dividend forecast, the
                       within-quarter accrual profile measured from the fund, fair futures price, richness, implied financing and
                       its spread, the fund premium, AR(1) half-life with block bootstrap and the noise-robust variant
d1basis/panel.py       the daily panel per pair: front contract marked at the cash close (hourly bar) or the daily close (flagged),
                       second contract, calendar-spread implied financing
d1basis/leadlag.py     Hayashi-Yoshida covariance with a time shift on asynchronous series (searchsorted + cumsum), the
                       Hoffmann-Rosenbaum-Vetter estimator, the Huth-Abergel lead-lag ratio, day bootstrap, Epps curve, a
                       Bachelier-with-lag simulator for the known-answer test
d1basis/basket.py      cap-weighted basket of the fund's largest holdings from their bars; coverage and tracking
d1basis/strategy.py    the basis strategy (z-score of the spread, roll handling, costs, carry), trades, metrics, the grid fit,
                       cash-and-carry to the roll
d1basis/transfer.py    the new-products verdicts
d1basis/data.py        loaders, DuckDB views, the Databento MBP-1 loader (csv export or .dbn) -> mid-quote series
d1basis/run.py, cli    the pipeline and the command line: python -m d1basis run|panel|leadlag|strategy|transfer|sql
configs/pairs.json     the four triangles: ES/SPY/S&P 500, NQ/QQQ/Nasdaq-100, RTY/IWM/Russell 2000, (no future)/EXW1.DE/Euro Stoxx 50
tests/                 24 tests;  scripts/  run_all.sh, plots.py, summarize.py, report.py, readme.py, make_notebook.py
data/reference/        daily bars, dividends, rates, holdings, contracts, the FirstRate parquet;  data/intraday/  the bar archive
data/derived/          panels, premiums, minute richness, strategy series, trades, the transfer table (parquet, DuckDB views)
results/               run.json, summary.md, figures/;  report.pdf;  notebooks/results.ipynb
```

Install: `pip install -e .[test]`; `python -m pytest`; `scripts/run_all.sh [--skip-download] [--fast]` (download → run → figures → summary → report → README → notebook → tests; a full run is about five minutes after the downloads). The README is generated from `scripts/README.template.md` by `scripts/readme.py` so every number is the run's.

---

## Data

| layer | source | span | notes |
|---|---|---|---|
| futures, daily | Yahoo: `ES=F NQ=F RTY=F` (front-month continuous) and the listed contracts `ESU26.CME ESZ26.CME ESH27.CME …` | 2005– / 2021– | the continuous holds the expiring contract through its last day (daily) or rolls on the Monday of expiry week (hourly); the panel identifies the contract from the listed series when they exist and from that rule otherwise |
| futures, intraday | Yahoo 1-minute (30 days back), 2-minute (60 days), hourly (730 days) for the same symbols | 2026-08-23– | 1-minute bars are labelled at the bar start; the archive grows each day the downloader runs |
| indices, ETFs, holdings | `^GSPC ^NDX ^RUT ^STOXX50E`, `SPY QQQ IWM EXW1.DE FEZ`, the top-25 holdings of each fund at the same intervals; SPY's full holdings from SSGA, QQQ/IWM top-25 from stockanalysis (the sponsors' files are not served to scripts) | as above | the basket is the fund's largest names at fixed weights; IWM's top 25 are 6.9 % of the fund and the basket is a proxy, said so in every table |
| one year of minutes | FirstRateData free sample: SPY, QQQ, DIA and the SPX, NDX, RUT, DJI indices at 1 minute | 2022-09-30–2023-09-29 | the ETF-versus-index lead-lag by month |
| financing | Treasury par curve 1m–1y (2005–), NY Fed EFFR (2016–) and SOFR (2018–), ECB €STR (2019–) | | fair value uses bills interpolated to the contract's tenor; EFFR/SOFR are alternatives in `fairvalue.rate_at` |
| dividends | the funds' distributions from Yahoo (ex-date, amount) | 2005– | the index's dividend points are the fund's distribution grossed up by its fee, times the fund/index ratio |
| **not free, and said so** | CME MDP3 depth (Databento) — the seconds-scale lead-lag and queue-level basis; Eurex FESX; iShares/Invesco holdings files | — | `data.load_mbp1` reads Databento's MBP-1 csv/dbn into a mid series the lead-lag code takes unchanged; tested on a synthetic file and on the keyless ESZ5 sample (`tools/databento_sample.py`); 0 paid days |

Costs used by the strategy (`configs/pairs.json`): the future's half tick and CME fee ($1.30), the fund's half cent and $0.002/share, the long fund funded at r + 30 bp, the short fund's cash earning r − 30 bp.

---

## Method

**Fair value.** For index $I$, fund $E$, futures price $F$, $\tau$ years to the contract's last trading day (act/360), financing $r(t,\tau)$ and expected index dividend points $D(t,T)$ going ex before expiry,

$$F^* = \big(I - \mathrm{PV}\,D\big)(1 + r\tau),\qquad \rho = 10^4\,\frac{F - F^*}{I},\qquad r_{\text{impl}} = \frac{(F + D)/I - 1}{\tau},\qquad s = 10^4\,(r_{\text{impl}} - r).$$

$D$ is the point-in-time forecast of the fund's distribution for each quarter touched (half the same quarter a year earlier times trailing growth, half the median of the last four), grossed up by the fee, times $\kappa_q = I/E$ at the last ex-date, times the share of the quarter's accrual that falls in the window. That share comes from the fund itself: a unit-trust ETF holds its constituents' dividends as cash from their ex-dates to its own, so $A(t) = E_t - I_t/\kappa_q + \text{fee}(t)$ traces when the index pays; its median across 86 quarters, by fraction of the quarter elapsed, is the accrual profile (Figure 1). The fund's fair price inside the quarter is $E^* = I/\kappa_q + \hat A(t)$ and its premium $e = 10^4 (E - E^*)/E$.

**Marks.** The cash legs close at 16:00 ET; the CME daily close is 17:00. The panel marks the future with the hourly bar that ends at 16:00 where hourly bars exist (2024-04-29 onwards, flag `16:00`) and with the daily close elsewhere (flag `daily`), and every table says which series it uses. A basis series whose legs are marked an hour apart looks like it mean-reverts in half a day and "pays" a strategy hundreds of bp a year; §Results shows both so the reader can see the trap.

**Mean reversion.** $\rho_{t+1} = c + \phi\,\rho_t + \varepsilon$ by OLS, half-life $-\ln 2/\ln\phi$, circular block bootstrap (20-step blocks). Under i.i.d. measurement noise the observed series is ARMA(1,1) and $\phi = \gamma(2)/\gamma(1)$, the ratio of the lag-2 to the lag-1 autocovariance, which the noise does not touch; both are reported. Within the day, the minute richness less its daily mean is pooled across days with a day bootstrap.

**Lead-lag.** For two series observed at their own times, the Hayashi–Yoshida covariance with a shift $\theta$ applied to the second,

$$\mathrm{HY}(\theta) = \sum_i\sum_j \Delta X_i\,\Delta Y_j\;\mathbf 1\big[(t_{i-1}, t_i] \cap (s_{j-1} - \theta,\ s_j - \theta] \neq \varnothing\big],\qquad \rho(\theta) = \frac{\mathrm{HY}(\theta)}{\sqrt{\sum \Delta X_i^2 \sum \Delta Y_j^2}},$$

the Hoffmann–Rosenbaum–Vetter estimator $\hat\theta = \arg\max_\theta |\mathrm{HY}(\theta)|$ over a grid (30 s steps on 1-minute bars, so the resolution is the bar), and the Huth–Abergel lead-lag ratio $\mathrm{LLR} = \sum_{\theta>0}\rho(\theta)^2 / \sum_{\theta<0}\rho(\theta)^2$ ($> 1$: the first leg leads). Days are the bootstrap unit. The overlap sum is two `searchsorted` calls and a cumulative sum, $O((n+m)\log m)$ per shift, so the same code runs on ticks. The Epps curve is the correlation of previous-tick-sampled returns by sampling interval.

**Strategy.** Position $+1$ = long future / short fund, $-1$ the reverse, in units of notional; daily P&L in bp $= \text{pos}\,[\Delta F/I - (\Delta E + \text{div})/E]\,10^4 + \text{carry}$, carry per calendar day $(r - 30\,\text{bp})/360$ for the short fund's cash and $-(r + 30\,\text{bp})/360$ for the long fund's funding; each position change pays the half-spreads and fees. Signal: $z$ of the front contract's spread $s$ over a trailing window; enter against the sign beyond $z_0$, exit inside $z_1$ or at the roll (eight trading days before expiry, when the panel switches contract); the spread is masked in the last 15 days (a few bp of price is hundreds of bp of financing at $\tau$ of two weeks) and the sensitivity to that mask is reported. $(z_0, z_1, \text{window})$ are chosen on ES by net Sharpe over a 27-point grid and applied unchanged to the other pairs; each pair's own in-sample best is shown beside it. Cash-and-carry: 60 days out, short the basis if the spread is positive and hold to the roll.

**Transfer.** Four things fitted on ES/SPY are applied unchanged: the accrual profile (scored by the sd of the fund premium with the source profile, the pair's own, uniform accrual, and none), the AR(1) coefficient (one-step forecast MSE with the ES $\phi$ over the pair's own, and a random walk over the pair's own), the strategy parameters (net bp/yr with ES parameters against the pair's own), and the lead-lag (θ* and LLR inside or outside ES's bootstrap interval).

---

## Results

### When the index pays

![accrual](results/figures/accrual_profile.png)

*Figure 1. Left: cumulative share of the quarter's dividends gone ex by fraction of the quarter, measured from each fund's price against its index (median across quarters; SPY's interquartile band). Right: SPY against the index inside the last two quarters, measured and modelled.*

| fund | days | premium sd, all / last 5y (bp) | with the SPY profile | uniform accrual | no accrual model | premium half-life (days) | dividend forecast MAE (blend / seasonal / median) |
|---|---|---|---|---|---|---|---|
| SPY (S&P 500) | 5409 | 16.8 / 6.9 | 16.8 | 17.0 | 23.9 | 1.77 [1.20, 2.09] | 6 / 7 / 8 % |
| QQQ (Nasdaq-100) | 5284 | 11.7 / 5.1 | 11.6 | 11.7 | 12.6 | 0.93 [0.53, 1.47] | 21 / 31 / 17 % |
| IWM (Russell 2000) | 5402 | 19.4 / 13.3 | 21.4 | 20.8 | 18.8 | 1.27 [0.87, 1.57] | 32 / 48 / 28 % |
| EXW1.DE (Euro Stoxx 50) | 3377 | 52.0 / 48.8 | 51.9 | 51.8 | 53.8 | 16.05 [6.12, 8.58] | 75 / 59 / 106 % |

### The basis

![basis](results/figures/basis_history.png)

*Figure 2. Left: median implied financing spread of the front contract over bills, by year, from the daily closes (17:00 futures against 16:00 cash — noisy day to day, unbiased over a year). Right: the last year of the ES front spread, with the 16:00 marks, and the calendar-spread-implied forward financing.*

| pair | series | days | richness mean / sd (bp) | spread median / sd (bp/yr) | last | forward spread | half-life OLS (days) | half-life noise-robust |
|---|---|---|---|---|---|---|---|---|
| ES | 16:00 marks | 505 | 6.9 / 7.2 | 50 / 51 | 19 | 67 | 1.17 [0.66, 1.65] | 24.6 [2.9, > 500] |
| ES | daily closes, 2005– | 4212 | 3.7 / 16.2 | 21 / 126 | 19 | 67 | 0.64 [0.50, 0.74] | 4.0 [1.1, > 500] |
| NQ | 16:00 marks | 505 | 6.2 / 7.1 | 42 / 48 | 10 | 66 | 1.87 [1.16, 2.19] | 15.2 [3.1, > 500] |
| NQ | daily closes, 2005– | 4212 | 3.5 / 19.5 | 22 / 153 | 10 | 66 | 0.42 [0.34, 0.48] | 1.1 [0.4, 7.7] |
| RTY | 16:00 marks | 505 | 9.8 / 10.3 | 71 / 106 | 3 | 5 | 1.85 [1.11, 2.25] | 8.6 [2.3, 12.7] |
| RTY | daily closes, 2005– | 1793 | 20.4 / 19.6 | 130 / 147 | 3 | 5 | 1.62 [1.04, 2.02] | 8.4 [2.2, 62.0] |

![minute](results/figures/minute_basis.png)

*Figure 3. Left: ES richness to fair minute by minute on the last day of the archive, against the index and against the SPY-implied index. Right: within-day half-life of the richness deviation by pair.*

- **ES**: 19 days, 7,395 minutes; richness sd 7.4 bp against the index and 6.2 against the fund-implied index (within-day 0.75 / 0.46 bp); within-day half-life 1.42 min [0.92, 2.27] against the index, 1.47 [0.75, 3.55] against the fund.
- **NQ**: 19 days, 7,262 minutes; richness sd 7.5 bp against the index and 6.0 against the fund-implied index (within-day 1.21 / 0.75 bp); within-day half-life 0.64 min [0.46, 0.88] against the index, 0.81 [0.42, 2.11] against the fund.
- **RTY**: 19 days, 6,814 minutes; richness sd 4.5 bp against the index and 3.4 against the fund-implied index (within-day 3.54 / 0.87 bp); within-day half-life 2.63 min [2.25, 3.05] against the index, 0.79 [0.49, 1.98] against the fund.

### Lead-lag

![leadlag](results/figures/leadlag.png)

*Figure 4. The Hayashi–Yoshida contrast $\rho(\theta)$ on 1-minute bars, per pair and leg pair; θ* and LLR in the legend.*

| pair | legs | days | θ* (s) [95 %] | ρ* | ρ(0) | LLR [95 %] | P(first leads) |
|---|---|---|---|---|---|---|---|
| ES | future vs etf | 19 | 0 [-30, 0] | 0.984 | 0.984 | 0.97 [0.94, 1.00] | 0.01 |
| ES | future vs index | 19 | 30 [0, 30] | 0.991 | 0.955 | 1.09 [1.06, 1.12] | 0.96 |
| ES | etf vs index | 19 | 30 [30, 30] | 1.004 | 0.964 | 1.12 [1.08, 1.15] | 0.98 |
| ES | future vs basket | 19 | 30 [-30, 30] | 0.841 | 0.839 | 1.02 [0.97, 1.05] | 0.41 |
| ES | etf vs basket | 19 | 30 [0, 30] | 0.855 | 0.850 | 1.04 [1.01, 1.07] | 0.60 |
| ES | basket vs index | 19 | 30 [-30, 30] | 0.880 | 0.874 | 1.02 [0.99, 1.06] | 0.53 |
| ES | SPY vs SPX, FirstRate year | 251 | 30 [30, 30] | 1.034 | 0.972 | 1.13 [1.12, 1.14] | 1.00 |
| NQ | future vs etf | 19 | 0 [-30, 0] | 0.973 | 0.973 | 0.97 [0.94, 1.01] | 0.00 |
| NQ | future vs index | 19 | 30 [30, 30] | 0.983 | 0.916 | 1.21 [1.15, 1.29] | 1.00 |
| NQ | etf vs index | 19 | 30 [30, 30] | 0.994 | 0.928 | 1.24 [1.18, 1.31] | 1.00 |
| NQ | future vs basket | 19 | 0 [-30, 30] | 0.942 | 0.942 | 1.01 [0.98, 1.05] | 0.21 |
| NQ | etf vs basket | 19 | 0 [0, 30] | 0.961 | 0.961 | 1.03 [1.01, 1.06] | 0.19 |
| NQ | basket vs index | 19 | 30 [30, 30] | 0.980 | 0.931 | 1.17 [1.12, 1.23] | 1.00 |
| NQ | QQQ vs NDX, FirstRate year | 251 | 30 [30, 30] | 1.058 | 0.972 | 1.18 [1.17, 1.19] | 1.00 |
| RTY | future vs etf | 19 | 0 [-30, 0] | 0.957 | 0.957 | 0.97 [0.93, 1.00] | 0.00 |
| RTY | future vs index | 19 | 30 [30, 30] | 1.095 | 0.716 | 3.74 [3.18, 4.12] | 1.00 |
| RTY | etf vs index | 19 | 30 [30, 30] | 1.101 | 0.688 | 3.96 [3.50, 4.31] | 1.00 |
| RTY | future vs basket | 19 | 30 [30, 30] | 0.674 | 0.547 | 1.90 [1.60, 2.14] | 1.00 |
| RTY | etf vs basket | 19 | 30 [30, 30] | 0.692 | 0.545 | 2.03 [1.72, 2.29] | 1.00 |
| RTY | basket vs index | 19 | 30 [30, 30] | 0.875 | 0.635 | 1.72 [1.44, 1.96] | 1.00 |
| SX5E | etf vs index | 20 | -30 [-30, 30] | 0.948 | 0.861 | 1.20 [1.04, 1.39] | 0.23 |

![leadlag_time](results/figures/leadlag_time.png)

*Figure 5. Left: the daily lead-lag ratio, ETF vs index (solid) and future vs ETF (dotted). Middle: ETF vs cash index by month over the FirstRate year. Right: the Epps curve.*

- **ES** basket: 24 names, 51.0 % of the fund, 1-minute return correlation with the fund 0.889, tracking error 2.15 bp per minute. Epps: future vs fund 0.983 at 1 min → 1.000 at 60; fund vs index 0.964 → 0.999.
- **NQ** basket: 25 names, 71.6 % of the fund, 1-minute return correlation with the fund 0.978, tracking error 1.45 bp per minute. Epps: future vs fund 0.968 at 1 min → 0.999 at 60; fund vs index 0.928 → 0.999.
- **RTY** basket: 23 names, 6.9 % of the fund, 1-minute return correlation with the fund 0.718, tracking error 3.98 bp per minute. Epps: future vs fund 0.907 at 1 min → 0.995 at 60; fund vs index 0.687 → 0.981.

### The strategy

![strategy](results/figures/strategy.png)

*Figure 6. Left: cumulative net P&L of the z-score basis strategy with the ES-fitted parameters on the 16:00-marked series. Middle: the same rule on the 17:00-marked history — the marking artefact. Right: cash-and-carry to the roll on the clean series.*

| pair | series | params | days | trades | mean trade net (bp) [95 %] | hit | net bp/yr [95 %] | Sharpe | max DD (bp) | costless | own in-sample best |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ES | 16:00 marks | z0 1.0, z1 0.5, w 60 | 522 | 64 | 1.1 [0.3, 1.9] | 0.62 | 34 [2, 74] | 1.21 | 15 | 55 | 34 (z0 1.0, z1 0.5, w 60) |
| ES | 17:00 closes (artefact) | z0 1.0, z1 0.5, w 60 | 4695 | 586 | 10.4 [9.1, 12.1] | 0.73 | 327 [260, 423] | 2.42 | 466 | 402 | 348 (z0 1.0, z1 0.25, w 40) |
| NQ | 16:00 marks | z0 1.0, z1 0.5, w 60 | 522 | 62 | 2.1 [1.1, 3.1] | 0.71 | 62 [20, 107] | 1.92 | 13 | 74 | 66 (z0 1.0, z1 0.5, w 90) |
| NQ | 17:00 closes (artefact) | z0 1.0, z1 0.5, w 60 | 4695 | 629 | 22.5 [19.8, 24.9] | 0.90 | 759 [646, 913] | 2.91 | 385 | 857 | 776 (z0 1.0, z1 0.25, w 40) |
| RTY | 16:00 marks | z0 1.0, z1 0.5, w 60 | 522 | 52 | 3.1 [0.6, 6.8] | 0.60 | 77 [15, 171] | 1.20 | 17 | 108 | 79 (z0 1.0, z1 0.25, w 60) |
| RTY | 17:00 closes (artefact) | z0 1.0, z1 0.5, w 60 | 1997 | 219 | 11.2 [8.5, 14.3] | 0.70 | 309 [187, 446] | 2.01 | 67 | 353 | 332 (z0 1.0, z1 0.25, w 40) |

Sensitivity to the near-expiry mask (net bp/yr, ES parameters): ES 6 d 26, 10 d 26, 15 d 34, 20 d 78, 25 d 69; NQ 6 d 71, 10 d 71, 15 d 62, 20 d 67, 25 d 59; RTY 6 d 24, 10 d 24, 15 d 77, 20 d 61, 25 d 52.

### Transfer

![transfer](results/figures/transfer.png)

| pair | accrual: own / ES / uniform / none (sd bp) | richness HL own / ES (days) | MSE ratio ES φ / RW | strategy own / ES (bp/yr) | LLR ETF vs index, own / ES | verdict |
|---|---|---|---|---|---|---|
| ES (S&P 500) | 16.8 / 16.8 / 17.0 / 23.9 | 1.17 / 1.17 | 1.00 / 1.29 | 34 / 34 | 1.12 / 1.12 | profile transfers; dynamics transfer; strategy transfers; lead-lag transfers |
| NQ (Nasdaq-100) | 11.7 / 11.6 / 11.7 / 12.6 | 1.87 / 1.17 | 1.04 / 1.18 | 66 / 62 | 1.24 / 1.12 | profile transfers; dynamics transfer; strategy transfers; lead-lag direction transfers, size does not |
| RTY (Russell 2000) | 19.4 / 21.4 / 20.8 / 18.8 | 1.85 / 1.17 | 1.03 / 1.18 | 79 / 77 | 3.96 / 1.12 | accrual model hurts (no model is best); dynamics transfer; strategy transfers; lead-lag direction transfers, size does not |
| SX5E (Euro Stoxx 50) | 52.0 / 51.9 / 51.8 / 53.8 | — | — | — | 1.20 / 1.12 | profile transfers; lead-lag does not transfer |

---

## Validation

- Fair value: $F^* = I(1+r\tau) - D$ to $10^{-12}$ on a hand case; the implied financing of the fair price is the input rate; the dividend window integrates to the quarter's forecast under uniform accrual; the point-in-time forecast uses only distributions already ex.
- Calendar: third Fridays incl. the Juneteenth pull-forward (ESM26 expired Thursday 18 June 2026), holiday rules, the 8-day roll, contract symbol round trips.
- Mean reversion: AR(1) recovers φ = 0.9 on a simulated path; with heavy i.i.d. noise OLS reads φ < 0.6 while the autocovariance ratio stays within 0.05 of 0.9; the pooled-segment estimator recovers φ = 0.8 with its bootstrap interval covering it.
- Lead-lag: the HY sum equals the realised covariance on synchronous data and the lagged cross-covariance for a whole-step shift; on two Poisson-sampled Brownian motions with a known lag of 2 the estimator returns 2 ± 0.5 and flips sign when the legs are swapped; the day bootstrap covers the estimate; the Epps correlation rises with the interval.
- Strategy: P&L reconciles to the basis move and the calendar-day carry on a constructed panel; costs are charged on entry, exit and the roll; the roll closes the trade on the old contract; entries obey the z rule.
- Data: the Databento MBP-1 loader on a synthetic csv (fixed-point scaling, unchanged mids dropped, tz-aware); session masks; basket weights renormalised over the names with bars.
- Everything reported carries a bootstrap interval; the artefact series is shown next to the clean one; the strategy's mask sensitivity is printed rather than tuned away.

## Limits, stated

- One-minute bars are the finest free data: the future-vs-ETF lead (seconds) is invisible here, and the "θ* = 30 s" of ETF-vs-index is the grid's first step, not a measurement to the second. The MBP-1 loader is the path to the real number.
- The 16:00-marked series is 505 days long; the strategy's interval is wide and its mask sensitivity is large. The 2005–2026 history is used only for quantities that average over the marking noise.
- The baskets are the funds' largest names at fixed weights (IWM: 6.9 % of the fund), not the replication basket; the Russell index itself is the stale-price benchmark.
- The Euro Stoxx pair has no free future and an ETF that trades a fraction of the minutes; it is in the transfer table to show what a thin leg does to the estimators, not as a like-for-like pair.
- Dividend forecasts are from the funds' distributions, not from constituent declarations; the errors are stated per fund and the IWM case shows what a lumpy distribution history does to the fair value.

## References

- Hayashi, T. and Yoshida, N. (2005). On covariance estimation of non-synchronously observed diffusion processes. *Bernoulli* 11(2). [doi:10.3150/bj/1116340299](https://doi.org/10.3150/bj/1116340299)
- Hoffmann, M., Rosenbaum, M. and Vetter, M. (2013). Estimation of the lead-lag parameter from non-synchronous data. *Bernoulli* 19(2). [arXiv:1011.1178](https://arxiv.org/abs/1011.1178)
- Huth, N. and Abergel, F. (2014). High frequency lead/lag relationships — empirical facts. *Journal of Empirical Finance* 26. [arXiv:1111.7103](https://arxiv.org/abs/1111.7103)
- Epps, T. W. (1979). Comovements in stock prices in the very short run. *JASA* 74(366).
- Cornell, B. and French, K. R. (1983). The pricing of stock index futures. *Journal of Futures Markets* 3(1) — the cost-of-carry fair value used here.

## CV bullet

- **Delta-One Basis and Lead-Lag: ETF, Futures and Cash** | Python, DuckDB, SQL | `delta-one-basis` — Fair value of the ES/SPY/basket triangle with financing from the bill curve and dividends read off the fund's own accrual profile: the front implies bills + 50 bp, richness half-life 1.2 days (1.4 min within the day); Hayashi–Yoshida/HRV lead-lag on 1-minute bars puts the ETF 30 s ahead of the cash index (LLR 1.12, 3.96 on the Russell); a basis strategy nets 34 bp/yr [2, 74] on ES and the ES-fitted model transfers to NQ and RTY with the lead-lag size the one thing that does not.
