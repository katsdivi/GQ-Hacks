# Power and placebo-design simulation, sim box run 2026-10-03

Synthetic data only. Code at fa5b19f (tests/placebo_design_sim.py, tests/power_sim_quotes.py, driver tests/sim_box_run.sh). Seed 20261003, 8 worker processes on the 8-core sim box, OMP/BLAS threads 1, run under tmux. Driver log: driver.log (it prints "nproc 1" because GNU nproc obeys OMP_NUM_THREADS=1; the pool used 8 processes).

## Part (b): placebo Design 1 vs Design 2 (wall 585 s, 500 reps per cell)

Files in b/: placebo_design_reps.csv (one row per rep, design and scenario: full-rule result and the Mann-Whitney p), placebo_design_wilson.csv (rates with Wilson 95% CIs, computed from the per-rep rows), ring_0.csv / ring_1.csv (ring lag tables, M = 3000 per venue), run.log.

Design 1: each qualifying game paired with the next one (n - 1 placebo pairs). Design 2: each game paired with the next K = 5 (about 5n pairs, each Kalshi series reused up to 5 times).

Scenarios: lead (Kalshi leads 5 s, per-game jitter N(0, 2 s)), zero (zero lag, linked), rev (the other venue leads by the same jitter), shift_iid (real and placebo lags both round(2 + N(0, 2 s)), independent: the shared-shift null the rule uses), shift_clustered (same marginal, half the variance is a per-Kalshi-game effect shared by that game's real lag and its placebo pairs: sensitivity only, not in the rule). The shared-shift nulls are drawn at the lag level: an unrelated-game placebo built from series is spread over [-15, 15] s whatever the timestamps, so it cannot be centered at +2 s.

Regression check: the lead and zero cells reproduce the 14:52 ET run (experiments/sims/placebo_design/) exactly, 24 of 24 cells.

Full-rule "Kalshi leads" rate [Wilson 95% CI], 500 reps:

| venue | scenario | n | Design 1 | Design 2 |
|---|---|---|---|---|
| polymarket.com | lead | 30 | 0.616 [0.573, 0.658] | 0.928 [0.902, 0.948] |
| polymarket.com | lead | 40 | 0.736 [0.696, 0.773] | 0.992 [0.980, 0.997] |
| polymarket.com | lead | 60 | 0.852 [0.818, 0.880] | 1.000 [0.992, 1.000] |
| polymarket.com | zero | 30/40/60 | 0.000 [0.000, 0.008] each | 0.000 [0.000, 0.008] each |
| polymarket.com | shift_iid | 30 | 0.052 [0.036, 0.075] | 0.046 [0.031, 0.068] |
| polymarket.com | shift_iid | 40 | 0.058 [0.041, 0.082] | 0.036 [0.023, 0.056] |
| polymarket.com | shift_iid | 60 | 0.048 [0.032, 0.070] | 0.058 [0.041, 0.082] |
| Polymarket US | lead | 30 | 0.620 [0.577, 0.661] | 0.892 [0.862, 0.916] |
| Polymarket US | lead | 40 | 0.720 [0.679, 0.758] | 0.958 [0.937, 0.972] |
| Polymarket US | lead | 60 | 0.838 [0.803, 0.868] | 1.000 [0.992, 1.000] |
| Polymarket US | zero | 30/40/60 | 0.000 [0.000, 0.008] each | 0.000 [0.000, 0.008] each |
| Polymarket US | shift_iid | 30 | 0.028 [0.017, 0.046] | 0.014 [0.007, 0.029] |
| Polymarket US | shift_iid | 40 | 0.040 [0.026, 0.061] | 0.038 [0.024, 0.059] |
| Polymarket US | shift_iid | 60 | 0.022 [0.012, 0.039] | 0.032 [0.020, 0.051] |

Reverse lead: "Kalshi leads" 0.000 [0.000, 0.008] in every cell; "other venue leads" D1 0.49 to 0.83, D2 0.85 to 1.00. Shared-shift clustered: every cell 0.000 to 0.010 under both designs (conservative, not oversized). Mann-Whitney-only rates are in placebo_design_wilson.csv. Under the zero-lag null the MW-only rate for Design 1 is 0.082 to 0.120 (above nominal; Design 2 0.000 to 0.002): with every real lag exactly 0, MW rejects whenever the small Design 1 placebo sample happens to sit off 0. The full rule's median gate (median >= 1 s) blocks all of these, so the full-rule rate is 0.

### Preset decision rule

"Adopt Design 2 only if its full-rule false-positive Wilson upper bound is <= 6% at every n under BOTH the zero-lag null and the shared-shift null. Otherwise Design 1."

- Zero-lag null: Design 2 upper bound 0.8% at every n, both venues. Passes.
- Shared-shift null (shift_iid), Design 2 upper bounds: polymarket.com 6.8% (n 30), 5.6% (n 40), 8.2% (n 60): FAILS at n = 30 and 60. Polymarket US 2.9%, 5.9%, 5.1%: passes.
- Verdict, rule applied to both venue tests together: **Design 1.** (Applied per venue, Polymarket US alone would pass for Design 2; the rule as written does not say per venue.)
- Note: a test sized exactly at 5% gives an expected 25 of 500, Wilson upper about 7.3%; the upper bound is at most 6% only if k <= 19. So the rule can fail a correctly sized design by chance, and it did here: Design 2's point estimates under shift_iid (0.036 to 0.058 on polymarket.com) are no higher than Design 1's (0.048 to 0.058).

## Part (a): power at n = 30, 40, 60, 80

Started 19:57:33Z (15:57 ET), ended 23:03:13Z (19:03 ET), wall 11,140 s, exit 0 (driver.log). Code tests/power_sim_quotes.py at fa5b19f, seed 20261003, 500 studies per cell, 8 processes. Files in a/: power_sim_quotes.csv (counts per cell), power_sim_quotes_studies.csv (one row per study), run.log.

Cases: no_link (unrelated series), zero_lag, lead_5s (every game 5 s), lead_jitter (per-game true lag 5 s + N(0, 2 s), rounded, clipped to [0, 12]). Each study: n qualifying games plus a no-link placebo of the same size (n pairs; the pre-registered Design 1 uses about n - 1), xcorr_lead.decide with the venue's min lead (1.0 s polymarket.com, 1.5 s Polymarket US). alpha 0.025 is the Holm level for the smaller of the two venue p values; 0.05 applies to the second test only if the first passes.

Full-rule "Kalshi leads" rate [Wilson 95% CI], 500 studies:

| venue | n | lead 5 s + N(0, 2 s) jitter, alpha 0.025 | same, alpha 0.05 | fixed 5 s lead, alpha 0.025 | no-link null, alpha 0.025 | zero-lag null, alpha 0.025 | reverse lead called, any case |
|---|---|---|---|---|---|---|---|
| polymarket.com | 30 | 0.496 [0.452, 0.540] | 0.614 [0.571, 0.656] | 0.542 [0.498, 0.585] | 0.008 [0.003, 0.020] | 0.000 [0.000, 0.008] | 0 of 1500 |
| polymarket.com | 40 | 0.618 [0.575, 0.660] | 0.692 [0.650, 0.731] | 0.680 [0.638, 0.719] | 0.006 [0.002, 0.017] | 0.000 [0.000, 0.008] | 0 of 1500 |
| polymarket.com | 60 | 0.782 [0.744, 0.816] | 0.856 [0.823, 0.884] | 0.812 [0.775, 0.844] | 0.012 [0.006, 0.026] | 0.000 [0.000, 0.008] | 0 of 1500 |
| polymarket.com | 80 | 0.892 [0.862, 0.916] | 0.940 [0.916, 0.958] | 0.892 [0.862, 0.916] | 0.006 [0.002, 0.017] | 0.000 [0.000, 0.008] | 0 of 1500 |
| Polymarket US | 30 | 0.466 [0.423, 0.510] | 0.588 [0.544, 0.630] | 0.522 [0.478, 0.565] | 0.010 [0.004, 0.023] | 0.000 [0.000, 0.008] | 0 of 1500 |
| Polymarket US | 40 | 0.590 [0.546, 0.632] | 0.696 [0.654, 0.735] | 0.648 [0.605, 0.689] | 0.006 [0.002, 0.017] | 0.000 [0.000, 0.008] | 0 of 1500 |
| Polymarket US | 60 | 0.796 [0.758, 0.829] | 0.860 [0.827, 0.888] | 0.802 [0.765, 0.835] | 0.006 [0.002, 0.017] | 0.000 [0.000, 0.008] | 0 of 1500 |
| Polymarket US | 80 | 0.848 [0.814, 0.877] | 0.902 [0.873, 0.925] | 0.872 [0.840, 0.898] | 0.004 [0.001, 0.014] | 0.000 [0.000, 0.008] | 0 of 1500 |

## Note text for HYPOTHESIS_v2.md Amendment 3 (draft; to be appended on main only when Divi says so)

Note to Amendment 3: power (appended <HH:MM> ET 2026-10-03; changes no rule). Simulation run (a), seed 20261003, 500 studies per cell, started 15:57 ET and finished 19:03 ET (docs/results/sim/README.md, part (a)). If Kalshi truly leads by 5 s with per-game jitter N(0, 2 s), the full rule calls "Kalshi leads" in 47% to 80% of studies with 30 to 60 qualifying games at alpha 0.025 (the Holm level for the smaller p), and in 59% to 86% at alpha 0.05; with 80 games, 85% to 89% at alpha 0.025. With no link it called a lead in at most 1.2% of studies per cell (Wilson upper bound 2.6%), with zero lag in 0 of 500 per cell, and it never called the reverse direction. Smaller leads are caught less often, so an inconclusive result does not mean there is no lead. The simulated placebo has n pairs; the pre-registered Design 1 has about n - 1.
