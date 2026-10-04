# Idea 11 results. POST-HOC, EXPLORATORY (formed after the holdout was seen)

Windows: 88 (feadc99, polymarket.com rows, qualifying, no exclusion flags, vultr). Spec: SPEC.md (277769a).

Residue levels removed (0 < size < 0.01): Kalshi 133078 of 18135721 book rows; polymarket.com 0 of 6479794 (loaded rows, incl. placebo loads).

## (a) Lag diagnostics (descriptive, not variants). + = Kalshi first

### a1_receipt

| n | n_nan | median_s | share_pos | sd_s | iqr_s | placebo_n | placebo_median_s | placebo_iqr_s | mannwhitney_p |
|---|---|---|---|---|---|---|---|---|---|
| 88 | 0 | 0.09 | 0.9886 | 0.1354 | 0.0225 | 83 | 0.08 | 1.285 | 0.6443 |

Real per-game lags, 10 ms bins (s: games): -0.18: 1, +0.06: 1, +0.08: 8, +0.09: 50, +0.10: 4, +0.11: 2, +0.12: 6, +0.13: 1, +0.17: 1, +0.18: 2, +0.22: 1, +0.24: 1, +0.26: 1, +0.27: 1, +0.29: 1, +0.30: 2, +0.31: 1, +0.59: 1, +0.63: 1, +0.64: 1, +0.83: 1

### a2_venue

| n | n_nan | median_s | share_pos | sd_s | iqr_s | placebo_n | placebo_median_s | placebo_iqr_s | mannwhitney_p |
|---|---|---|---|---|---|---|---|---|---|
| 88 | 0 | 0.07 | 0.9659 | 0.2043 | 0 | 83 | -0.16 | 1.08 | 0.02374 |

Real per-game lags, 10 ms bins (s: games): -0.93: 1, -0.65: 1, -0.21: 1, +0.03: 1, +0.05: 1, +0.06: 16, +0.07: 51, +0.08: 3, +0.10: 2, +0.13: 1, +0.14: 1, +0.25: 1, +0.26: 1, +0.29: 1, +0.30: 1, +0.33: 1, +0.61: 1, +0.65: 1, +0.81: 1, +0.87: 1

### a3. Offset signature and pre-fixed reading

a1 per-game lag SD 135.4 ms, IQR 22.5 ms; a2 SD 204.3 ms, IQR 0.0 ms.

Rule (fixed in SPEC before the run): if a2 per-game lags have IQR <= 10 ms and a1 per-game lags do not show the same positive median, the venue-time result is read as a timestamp offset; if a1 median lag >= +30 ms with share > 0 >= 0.6, it is read as a receipt-side lead of that size; otherwise inconclusive.

Reading: venue-time result read as a TIMESTAMP OFFSET (a2 IQR <= 10 ms and a1 does not show the same positive median).

### a4. Receipt minus venue time (ms), book snapshots in windows, cut excluded

| venue | n | median | p10 | p90 |
|---|---|---|---|---|
| kalshi | 8334238 | 29.6 | 27.6 | 34.6 |
| polymarket | 1667925 | 52.2 | 50.2 | 222.5 |

## (b) Cross-venue arbitrage: market-efficiency measurement; polymarket.com is not available to US persons; not a strategy available to the authors

Opportunities: 3039 in 84 games (home leg 1600, away leg 1439). Duration median 0.051 s, p90 1.343 s. Share lasting >= 0.25 / 0.5 / 1.0 / 2.0 s: 0.320 / 0.231 / 0.129 / 0.078. Median executable size at t: 7.25.

| L (s) | attempts | executed | missed | no book / side empty | games executed | contracts | total P&L $ | 95% CI | per contract $ | 95% CI | ex top 5 total $ | ex top 5 per contract $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.25 | 3039 | 517 | 2488 | 34 | 61 | 3841.78 | 0.00 | [0.00, 0.00] | 0.0000 | [0.0000, 0.0000] | 0.00 | 0.0000 |
| 0.5 | 3039 | 543 | 2464 | 32 | 59 | 3797.77 | 0.00 | [0.00, 0.00] | 0.0000 | [0.0000, 0.0000] | 0.00 | 0.0000 |
| 1.0 | 3039 | 453 | 2554 | 32 | 57 | 3272.75 | 0.00 | [0.00, 0.00] | 0.0000 | [0.0000, 0.0000] | 0.00 | 0.0000 |

Settlement check (games with an executed opportunity at any L: 63): disagreements 63: ['cfb_20261003_aamu_jkst', 'cfb_20261003_akr_cmu', 'cfb_20261003_alcn_gram', 'cfb_20261003_alst_cook', 'cfb_20261003_ark_txam', 'cfb_20261003_army_lt', 'cfb_20261003_arpb_sou', 'cfb_20261003_aub_tenn', 'cfb_20261003_bc_smu', 'cfb_20261003_bgsu_moh', 'cfb_20261003_byu_tcu', 'cfb_20261003_cal_unlv', 'cfb_20261003_cit_scst', 'cfb_20261003_colg_harv', 'cfb_20261003_cor_gtwn', 'cfb_20261003_day_drke', 'cfb_20261003_elon_unh', 'cfb_20261003_emu_mass', 'cfb_20261003_fla_mizz', 'cfb_20261003_gaso_ccar', 'cfb_20261003_inst_sdak', 'cfb_20261003_iw_sfa', 'cfb_20261003_lou_ncst', 'cfb_20261003_md_neb', 'cfb_20261003_mer_vmi', 'cfb_20261003_mhu_liu', 'cfb_20261003_mia_clem', 'cfb_20261003_mich_minn', 'cfb_20261003_morg_vill', 'cfb_20261003_msu_wis', 'cfb_20261003_mtu_ku', 'cfb_20261003_navy_afa', 'cfb_20261003_ncat_bry', 'cfb_20261003_nd_unc', 'cfb_20261003_norf_rmu', 'cfb_20261003_ohio_kent', 'cfb_20261003_orst_csu', 'cfb_20261003_osu_iowa', 'cfb_20261003_penn_dart', 'cfb_20261003_pur_ill', 'cfb_20261003_rich_laf', 'cfb_20261003_syr_conn', 'cfb_20261003_tem_usf', 'cfb_20261003_tnst_wiu', 'cfb_20261003_tol_ball', 'cfb_20261003_tows_monm', 'cfb_20261003_ttu_colo', 'cfb_20261003_ucf_hou', 'cfb_20261003_uk_scar', 'cfb_20261003_ulm_usa', 'cfb_20261003_una_eky', 'cfb_20261003_ust_pre', 'cfb_20261003_utsa_rice', 'cfb_20261003_uva_fsu', 'cfb_20261003_valp_more', 'cfb_20261003_wash_usc', 'cfb_20261003_wmu_buff', 'cfb_20261003_wof_fur', 'cfb_20261003_wvu_isu', 'cfb_20261003_wyo_ndsu', 'cfb_20261003_ysu_siu', 'cfb_20261004_suu_utu', 'cfb_20261004_web_cp']. Kalshi: data/holdout_raw/settlements.csv; polymarket.com: Gamma API outcomePrices (cached data/pm_resolution/).
Taker delay defaulted to 1 s (condition missing from holdout_seconds_delay.csv): 0 games.

## Notes added after the run (04:30 ET, no numbers above changed)

- (b) above is INVALID for P&L and the settlement check: polymarket.com resolutions came back empty (Gamma query
  lacked closed=true), so P&L was NaN (printed 0) and every game showed as a disagreement. Corrected by a
  settlement-only step over the saved executions (fix 7f35e9d): see RESULTS_b.md. Opportunity counts, durations,
  sizes and executed/missed counts above are unaffected and identical there.
- a3 reading: BOTH pre-fixed conditions hold (a2 IQR 0 ms with a1 median +90 ms not equal to a2's +70 ms; and a1
  median +90 ms >= +30 ms with share > 0 = 0.989). The rule lists the offset branch first and the script applied
  it in that order. Note also that the a1 placebo median is +80 ms and Mann-Whitney real vs placebo p = 0.64 on
  the receipt clock (p = 0.024 on venue time), so the receipt-clock lag is not distinguishable from unrelated-game
  pairs.

## Lag reading note (2026-10-04 04:33 ET)

Venue-time lag is a constant offset (IQR 0 ms). Receipt-time lag (+90 ms) matches the unrelated-game placebo (+80 ms, p = 0.64). No evidence of a lead in either direction.

The a3 rule text and every computed value above are unchanged.
