# delta-one-basis

ETF, index future and cash basket for the S&P 500, Nasdaq-100 and Russell 2000, in a Python package (`d1basis`): a fair value with measured financing and dividends, Hayashi–Yoshida lead-lag on one-minute bars, a basis strategy, and a test of what carries from ES/SPY to the other pairs. All data is free and checked in.

The question: where does the basis sit against a fair value with measured financing and dividends, how fast does a deviation close, who leads whom, and does everything fitted on ES/SPY carry unchanged to NQ/QQQ, RTY/IWM and a European pair?

## Results

- **Financing.** With both legs marked at the 16:00 cash close (<<clean_days>> days, <<clean_from>>–<<clean_to>>), the ES front contract implies financing of bills + <<es_spread_median>> bp (NQ bills + <<nq_spread_median>>, RTY bills + <<rty_spread_median>>). The dividend accrual inside the quarter is read off the fund's own price: the SPY premium to fair has sd <<spy_prem_sd>> bp over 2005–2026, against <<spy_prem_sd_none>> bp with no accrual model.
- **Mean reversion.** Richness to fair has an OLS half-life of <<es_hl_ols>> days on ES. Within the day the minute richness reverts with a half-life of <<es_hl_min>> min [<<es_hl_min_lo>>, <<es_hl_min_hi>>].
- **Lead-lag.** At one-minute resolution the future and the ETF are simultaneous. The ETF leads the cash index by about <<es_theta_ei>> s (the grid's first step) with LLR <<es_llr_ei>> on SPY/SPX and <<rty_llr_ei>> on IWM/RUT: the index lags more where it holds more small names.
- **Strategy.** A z-score rule on the implied financing spread, fitted on ES, nets <<es_strat_net>> bp a year of notional on ES [<<es_strat_lo>>, <<es_strat_hi>>] and, unchanged, <<nq_strat_net>> bp on NQ and <<rty_strat_net>> bp on RTY. The same rule on 17:00-marked futures closes "earns" more with a Sharpe above 2, which is an artefact of marking the legs an hour apart.
- **Transfer.** The accrual model, the mean-reversion dynamics and the strategy parameters carry, with wide intervals. The lead-lag carries in direction, not in size.

| ES | NQ | RTY |
|---|---|---|
| bills + <<es_spread_median>> bp, strategy <<es_strat_net>> bp/yr | bills + <<nq_spread_median>> bp, strategy <<nq_strat_net>> bp/yr | bills + <<rty_spread_median>> bp, strategy <<rty_strat_net>> bp/yr |

![basis](results/figures/basis_history.png)
![transfer](results/figures/transfer.png)

All numbers are in `results/summary.md`; the detail is in [docs/method.md](docs/method.md).

## How it works

- **Data.** Yahoo daily bars since 2005, one-minute bars archived daily, NY Fed rates, the Treasury curve, SPY holdings and a FirstRateData one-year sample. Futures and ETF dividends come from the funds' own distributions.
- **Fair value.** F* = I(1 + rτ) − D, with the dividend accrued along a profile read off the fund's price against the index.
- **Mean reversion.** AR(1) half-life by OLS and by a noise-robust autocovariance ratio, with a block bootstrap.
- **Lead-lag.** Hayashi–Yoshida covariance over a grid of lags, with the Hoffmann–Rosenbaum–Vetter lead-lag ratio and a day bootstrap.
- **Strategy and transfer.** Long future against short fund when the implied spread is rich, costed on entry, exit and roll. Parameters fitted on ES are run unchanged on the other pairs.

## Limitations

- One-minute bars are the finest free data, so the seconds-scale future-vs-ETF lead is invisible. The MBP-1 loader is ready for depth data, which I have not bought.
- The 16:00-marked series is <<clean_days>> days long, so the strategy's intervals are wide and its sensitivity to the near-expiry mask is large.
- The baskets are the funds' largest names at fixed weights (IWM: <<rty_basket_cov>> % of the fund), not the replication basket.
- The Euro Stoxx pair has no free future, so it shows what a thin leg does to the estimators rather than a like-for-like pair.

## Run

```
pip install -e .[test]
python -m pytest                      # <<n_tests>> tests
python -m d1basis run --fast          # the pipeline on the checked-in data
scripts/run_all.sh --skip-download    # run, figures, summary, README, notebook, tests
```

The README and `docs/method.md` are written by `scripts/readme.py` from `results/run.json`. CI runs the pipeline on the checked-in data and checks that both render.
