# delta-one-basis — run summary (2026-09-19, source pair ES, 186 s)

Data: 80 daily symbols 2005-01-03 .. 2026-09-18; 1-minute archive 80 symbols, 23 days (2026-08-23 .. 2026-09-18); FirstRate sample 2022-09-30 .. 2023-09-29; Databento depth days: 0.

## Fair value and mean reversion (daily)

| pair | days | richness mean / sd (bp) | spread median / sd (bp/yr) | last spread | fwd spread mean | HL rho OLS | HL rho noise-robust | HL spread noise-robust | 16:00 marks |
|---|---|---|---|---|---|---|---|---|---|
| ES | 4212 (2005-01-03..2026-09-18) | 3.7 / 16.2 | 20.9 / 125.6 | 18.7 | 66.7 (125 d) | 0.64 [0.50, 0.74] | 3.97 [1.12, > 500] | 2.21 [0.49, > 500] | 10 % |
| ES 16:00 only | 505 (2024-04-29..2026-09-18) | 6.9 / 7.2 | 49.8 / 51.0 | 18.7 | 66.7 | 1.17 [0.66, 1.65] | 24.62 [2.86, > 500] | > 500 [2.68, > 500] | 100 % |
| NQ | 4212 (2005-01-03..2026-09-18) | 3.5 / 19.5 | 21.5 / 152.9 | 9.6 | 65.8 (125 d) | 0.42 [0.34, 0.48] | 1.10 [0.36, 7.70] | 0.61 [0.19, > 500] | 10 % |
| NQ 16:00 only | 505 (2024-04-29..2026-09-18) | 6.2 / 7.1 | 41.7 / 47.7 | 9.6 | 65.8 | 1.87 [1.16, 2.19] | 15.24 [3.12, > 500] | > 500 [3.70, > 500] | 100 % |
| RTY | 1793 (2017-07-10..2026-09-18) | 20.4 / 19.6 | 130.4 / 147.2 | 3.0 | 5.4 (124 d) | 1.62 [1.04, 2.02] | 8.37 [2.21, 62.00] | 12.30 [2.84, > 500] | 10 % |
| RTY 16:00 only | 505 (2024-04-29..2026-09-18) | 9.8 / 10.3 | 70.7 / 105.8 | 3.0 | 5.4 | 1.85 [1.11, 2.25] | 8.63 [2.34, 12.71] | 12.87 [3.24, 19.69] | 100 % |

## Fund premium to the index (daily)

| pair | fund | days | premium mean (bp) | sd all / last 5y | sd with SPY profile | uniform | no accrual model | HL (days) | dividend forecast MAE |
|---|---|---|---|---|---|---|---|---|---|
| ES | SPY | 5409 | 3.9 | 16.8 / 6.9 | 16.8 | 17.0 | 23.9 | 1.77 [1.20, 2.09] | 6 % (seasonal 7, median 8) |
| NQ | QQQ | 5284 | 1.1 | 11.7 / 5.1 | 11.6 | 11.7 | 12.6 | 0.93 [0.53, 1.47] | 21 % (seasonal 31, median 17) |
| RTY | IWM | 5402 | -2.5 | 19.4 / 13.3 | 21.4 | 20.8 | 18.8 | 1.27 [0.87, 1.57] | 32 % (seasonal 48, median 28) |
| SX5E | EXW1.DE | 3377 | -0.1 | 52.0 / 48.8 | 51.9 | 51.8 | 53.8 | 16.05 [6.12, 8.58] | 75 % (seasonal 59, median 106) |

## Lead-lag, 1-minute bars (theta* > 0: first leg leads; seconds)

| pair | legs | days | theta* [95 %] | rho* | rho(0) | LLR [95 %] | P(first leads) |
|---|---|---|---|---|---|---|---|
| ES | future vs etf | 19 | 0 [-30, 0] | 0.984 | 0.984 | 0.97 [0.94, 1.00] | 0.01 |
| ES | future vs index | 19 | 30 [0, 30] | 0.991 | 0.955 | 1.09 [1.06, 1.12] | 0.96 |
| ES | etf vs index | 19 | 30 [30, 30] | 1.004 | 0.964 | 1.12 [1.08, 1.15] | 0.98 |
| ES | future vs basket | 19 | 30 [-30, 30] | 0.841 | 0.839 | 1.02 [0.97, 1.05] | 0.41 |
| ES | etf vs basket | 19 | 30 [0, 30] | 0.855 | 0.850 | 1.04 [1.01, 1.07] | 0.60 |
| ES | basket vs index | 19 | 30 [-30, 30] | 0.880 | 0.874 | 1.02 [0.99, 1.06] | 0.53 |
| ES | SPY vs SPX (FirstRate 2022-09-30..2023-09-29) | 251 | 30 [30, 30] | 1.034 | 0.972 | 1.13 [1.12, 1.14] | 1.00 |
| NQ | future vs etf | 19 | 0 [-30, 0] | 0.973 | 0.973 | 0.97 [0.94, 1.01] | 0.00 |
| NQ | future vs index | 19 | 30 [30, 30] | 0.983 | 0.916 | 1.21 [1.15, 1.29] | 1.00 |
| NQ | etf vs index | 19 | 30 [30, 30] | 0.994 | 0.928 | 1.24 [1.18, 1.31] | 1.00 |
| NQ | future vs basket | 19 | 0 [-30, 30] | 0.942 | 0.942 | 1.01 [0.98, 1.05] | 0.21 |
| NQ | etf vs basket | 19 | 0 [0, 30] | 0.961 | 0.961 | 1.03 [1.01, 1.06] | 0.19 |
| NQ | basket vs index | 19 | 30 [30, 30] | 0.980 | 0.931 | 1.17 [1.12, 1.23] | 1.00 |
| NQ | QQQ vs NDX (FirstRate 2022-09-30..2023-09-29) | 251 | 30 [30, 30] | 1.058 | 0.972 | 1.18 [1.17, 1.19] | 1.00 |
| RTY | future vs etf | 19 | 0 [-30, 0] | 0.957 | 0.957 | 0.97 [0.93, 1.00] | 0.00 |
| RTY | future vs index | 19 | 30 [30, 30] | 1.095 | 0.716 | 3.74 [3.18, 4.12] | 1.00 |
| RTY | etf vs index | 19 | 30 [30, 30] | 1.101 | 0.688 | 3.96 [3.50, 4.31] | 1.00 |
| RTY | future vs basket | 19 | 30 [30, 30] | 0.674 | 0.547 | 1.90 [1.60, 2.14] | 1.00 |
| RTY | etf vs basket | 19 | 30 [30, 30] | 0.692 | 0.545 | 2.03 [1.72, 2.29] | 1.00 |
| RTY | basket vs index | 19 | 30 [30, 30] | 0.875 | 0.635 | 1.72 [1.44, 1.96] | 1.00 |
| SX5E | etf vs index | 20 | -30 [-30, 30] | 0.948 | 0.861 | 1.20 [1.04, 1.39] | 0.23 |

## Minute richness and basket

- ES: 19 days, 7395 bars; richness sd vs index 7.37 bp (within-day 0.75), vs fund 6.17 (within-day 0.46); within-day half-life vs index 1.42 min [0.92, 2.27], vs fund 1.47 [0.75, 3.55]
- ES basket: 24 names, 51.0 % of the fund; 1-minute return correlation with the fund 0.889, tracking error 2.15 bp per bar
- NQ: 19 days, 7262 bars; richness sd vs index 7.49 bp (within-day 1.21), vs fund 6.01 (within-day 0.75); within-day half-life vs index 0.64 min [0.46, 0.88], vs fund 0.81 [0.42, 2.11]
- NQ basket: 25 names, 71.6 % of the fund; 1-minute return correlation with the fund 0.978, tracking error 1.45 bp per bar
- RTY: 19 days, 6814 bars; richness sd vs index 4.50 bp (within-day 3.54), vs fund 3.40 (within-day 0.87); within-day half-life vs index 2.63 min [2.25, 3.05], vs fund 0.79 [0.49, 1.98]
- RTY basket: 23 names, 6.9 % of the fund; 1-minute return correlation with the fund 0.718, tracking error 3.98 bp per bar

## Strategy (net of costs)

| pair | series | params | days | trades | mean trade net (bp) [95 %] | hit | net bp/yr [95 %] | Sharpe | max DD (bp) | costless bp/yr | carry-to-roll: n, mean net bp/yr, hit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ES | 16:00 marks | z0 1.0, z1 0.5, w 60 | 522 | 64 | 1.1 [0.3, 1.9] | 0.62 | 34 [2, 74] | 1.21 | 15 | 55 | 10, -2, 0.60 |
| ES | 17:00 close marks | z0 1.0, z1 0.5, w 60 | 4695 | 586 | 10.4 [9.1, 12.1] | 0.73 | 327 [260, 423] | 2.42 | 466 | 402 | 87, 30, 0.60 |
| NQ | 16:00 marks | z0 1.0, z1 0.5, w 60 | 522 | 62 | 2.1 [1.1, 3.1] | 0.71 | 62 [20, 107] | 1.92 | 13 | 74 | 10, -12, 0.40 |
| NQ | 17:00 close marks | z0 1.0, z1 0.5, w 60 | 4695 | 629 | 22.5 [19.8, 24.9] | 0.90 | 759 [646, 913] | 2.91 | 385 | 857 | 87, 14, 0.51 |
| RTY | 16:00 marks | z0 1.0, z1 0.5, w 60 | 522 | 52 | 3.1 [0.6, 6.8] | 0.60 | 77 [15, 171] | 1.20 | 17 | 108 | 10, -39, 0.20 |
| RTY | 17:00 close marks | z0 1.0, z1 0.5, w 60 | 1997 | 219 | 11.2 [8.5, 14.3] | 0.70 | 309 [187, 446] | 2.01 | 67 | 353 | 37, -21, 0.27 |

Sensitivity of the transferred strategy to the near-expiry mask (net bp/yr on the 16:00 series):
- ES: 6 d: 26 (Sharpe 0.72, 66 trades), 10 d: 26 (Sharpe 0.72, 66 trades), 15 d: 34 (Sharpe 1.21, 64 trades), 20 d: 78 (Sharpe 1.15, 62 trades), 25 d: 69 (Sharpe 1.02, 55 trades)
- NQ: 6 d: 71 (Sharpe 1.84, 59 trades), 10 d: 71 (Sharpe 1.84, 59 trades), 15 d: 62 (Sharpe 1.92, 62 trades), 20 d: 67 (Sharpe 2.19, 55 trades), 25 d: 59 (Sharpe 1.95, 57 trades)
- RTY: 6 d: 24 (Sharpe 0.33, 51 trades), 10 d: 24 (Sharpe 0.33, 51 trades), 15 d: 77 (Sharpe 1.20, 52 trades), 20 d: 61 (Sharpe 0.95, 53 trades), 25 d: 52 (Sharpe 0.81, 49 trades)

## Transfer table

| pair   |   prem_sd_own |   prem_sd_transferred |   prem_sd_uniform |   prem_sd_none |   hl_rho_own |   hl_rho_source |   hl_rho_own_iv |   mse_ratio_transferred |   mse_ratio_random_walk |   strat_net_own |   strat_net_transferred |   theta_own |   theta_source |   llr_own |   llr_source | verdict                                                                                                                    |
|:-------|--------------:|----------------------:|------------------:|---------------:|-------------:|----------------:|----------------:|------------------------:|------------------------:|----------------:|------------------------:|------------:|---------------:|----------:|-------------:|:---------------------------------------------------------------------------------------------------------------------------|
| ES     |         16.81 |                 16.81 |             17.02 |          23.91 |         1.17 |            1.17 |           24.62 |                    1    |                    1.29 |           33.54 |                   33.54 |          30 |             30 |      1.12 |         1.12 | profile transfers; dynamics transfer; strategy transfers; lead-lag transfers                                               |
| NQ     |         11.65 |                 11.62 |             11.72 |          12.59 |         1.87 |            1.17 |           15.24 |                    1.04 |                    1.18 |           66.04 |                   61.54 |          30 |             30 |      1.24 |         1.12 | profile transfers; dynamics transfer; strategy transfers; lead-lag direction transfers, size does not                      |
| RTY    |         19.38 |                 21.4  |             20.78 |          18.78 |         1.85 |            1.17 |            8.63 |                    1.03 |                    1.18 |           78.94 |                   76.9  |          30 |             30 |      3.96 |         1.12 | accrual model hurts (no model is best); dynamics transfer; strategy transfers; lead-lag direction transfers, size does not |
| SX5E   |         51.97 |                 51.93 |             51.8  |          53.8  |       nan    |          nan    |          nan    |                  nan    |                  nan    |          nan    |                  nan    |         -30 |             30 |      1.2  |         1.12 | profile transfers; lead-lag does not transfer                                                                              |
