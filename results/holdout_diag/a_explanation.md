# a. Lag selection and the polymarket.com lag distribution (exploratory, post-run)

Code that picks the lag, xcorr_lead.py:135-138 (game_lag_mid, identical at RUN_COMMIT 872ff43):

    corr = {lag: float(rx.corr(ry.shift(-lag))) for lag in range(-max_lag_s, max_lag_s + 1)}
    corr = {k: (v if v == v else -np.inf) for k, v in corr.items()}
    lag = max(corr, key=corr.get)
    return float(lag) if np.isfinite(corr[lag]) else float("nan")

- Range: integer lags -15 to +15 s (MAX_LAG_S = 15, xcorr_lead.py:30), on 1 s mid changes; positive = Kalshi first.
- NaN correlations become -inf (never chosen unless all are NaN, then the game's lag is NaN).
- Tie-breaking: Python max() over a dict returns the FIRST maximal key in insertion order, and the dict is built in
  the order -15, -14, ..., +15. So an exact tie goes to the MOST NEGATIVE lag. The tie-break cannot favor 0 or
  positive lags.

Findings (a_corr_profiles.csv recomputes every game's profile with the same lines; recomputed lag = recorded lag in
318 of 318: real 88 + 76, placebo 83 + 71):
- Exact ties (within 1e-12) at the maximum: 0 games in every group, including 0 of 76 Polymarket US real games.
- polymarket.com real: 77 games at lag 0, 11 at +1, 0 negative. Median correlation at lag 0 is 0.371 vs 0.056 for
  the best negative lag; median margin between the best lag and the next best is 0.155. Median number of seconds where
  both venues' mids moved: 449 at lag 0, 306 at -1, 364 at +1. So the 0.000 negative share is not a tie-break or
  range artifact: in these games the profile has a clear peak at 0 (or +1) at the 1 s resolution of the grid.
- Polymarket US real: lags spread from -14 to +15; 17 of 76 games are at +13, +14 or +15 (the top of the search
  range: 5, 6, 6). Median margin 0.012; median correlation at the chosen lag is small (lag-0 median 0.004).
- Placebo pairs (both venues): lags spread over the whole range, median margins 0.003 to 0.005.
