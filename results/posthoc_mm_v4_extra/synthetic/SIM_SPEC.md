# SIM_SPEC: synthetic market simulation for the HYPOTHESIS_v4 maker

**Label: SYNTHETIC SIMULATION, calibrated to one day of observed data; not market evidence; not a test of HYPOTHESIS_v4.**

Committed before any simulation is run. Purpose: stress-test the maker logic and show under which market conditions
it would or would not make money, and where the observed day sits. Requested by Divi ("add synthetic data from
observing the market and stuff to just test it out").

## Calibration (calibration.json in this folder, scripts/mm_v4_calibrate.py)

From the 88 posthoc-mm-signal polymarket.com games (Oct 3, kickoff by 20:00 ET, Vultr; windows feadc99; maker code
1d3d68a), quoting window minus the kickoff cut, venue time, residue removed:
- spread (time-weighted, cents, clipped to 1..10): 1 c 53.7%, 2 c 13.8%, 3 c 6.3%, 4 c 3.6%, 5 c 3.1%, 6 c 4.1%,
  7 c 4.1%, 8 c 3.5%, 9 c 2.5%, 10 c+ 5.2%;
- top-of-book changes: median 17.9 per minute;
- taker trades: mean 0.51 per minute (median 0.20); size quantiles p10 2.5, p25 5.1, p50 20.2, p75 97.8,
  p90 325, p99 9,534 contracts;
- through share: 4.1% of trades print strictly through the prevailing best;
- mid volatility, std of 10 s mid change: pre-game 0.044 c, first half 1.07 c, second half 1.21 c;
- jumps (|60 s mid move| >= 10 c): 0.84 per hour; size quantiles p25 11.5, p50 13, p75 17, p90 22 c;
- informed share: mean signed mid move 60 s after a trade 0.437 c; with fixed informed impact d_inf = 1 c,
  informed share = 0.437.

## Simulator (scripts/mm_v4_sim.py)

One synthetic game: window kickoff - 90 min to kickoff + 4.5 h, 1 s steps, kickoff cut as in the maker.
- Mid: start Uniform(0.2, 0.8); Gaussian step each second with sd = vol10s(phase) / sqrt(10); phases pre-game,
  first half, second half (split at the midpoint of the post-cut window); jumps Poisson at the calibrated hourly rate
  (pre-game rate 0), size drawn from the calibrated quantiles (piecewise-linear inverse CDF between 10 c and p90,
  capped at 30 c), random sign; mid clipped to [0.02, 0.98].
- Book: updates Poisson at the calibrated rate, and forced whenever the mid leaves [bid, ask]; spread drawn from
  the calibrated distribution; bid = floor((mid - spread/2), 1 c), ask = bid + spread; displayed sizes drawn from the
  trade-size distribution x 10.
- Taker trades: Poisson at the calibrated mean rate; size from the calibrated distribution; with probability
  informed_share the trade is informed and the mid moves d_inf = 1 c in its direction right after it (permanent);
  otherwise direction is a fair coin with no impact. Price = best ask (buy) or best bid (sell); with probability
  through_share it prints 1 c through.
- Settlement: outcome ~ Bernoulli(final mid).
- Maker: the committed simulate() and score() from scripts/posthoc_mm_v4.py (1d3d68a), Arm A (min_spread 0) and
  Arm B (min_spread 0.03), F1 strict trade-through, maker fee 0, called through a thin adapter that builds a Book and
  trade arrays from the synthetic path.

## Scenarios (fixed seeds)

- base: calibrated parameters, N = 500 games, seed 20261011.
- informed share 0.5x and 2x: N = 200 each, seeds 20261012, 20261013.
- jump frequency 0.5x and 2x: N = 200 each, seeds 20261014, 20261015.
- spread regime narrow (always 1 c) and wide (calibrated + 2 c): N = 200 each, seeds 20261016, 20261017.

## Outputs

Per scenario and arm: fills, contracts, mean P&L per contract at +60 s and held to settlement, game-bootstrap 95% CI
(2,000 reps, seed 20261011), share of games positive. Observed day for comparison: N maker +1.09 c/contract at
+60 s [0.17, 2.12] (863eb69). Not variants; no variants.csv rows.

## Tests (tests/test_mm_v4_sim.py)

Seed reproduces identical games; the adapter feeds the maker without lookahead (changing the synthetic path after T
does not change fills before T); calibration readouts on 60 base games match calibration.json within tolerance
(spread 1 c share, trade rate, through share, informed mean move).

## Amendment 1 (2026-10-04 08:06 ET, before any simulation run)

The calibration-readout test failed with the original book rule (1 c spread share 41% vs calibrated 54%), because
every forced re-centre redrew the spread and wide spreads persist longer. Fix: the spread is redrawn only at Poisson
book updates; a forced re-centre (mid leaves [bid, ask]) keeps the current spread. No simulation result had been
computed; only the test's calibration readout on 60 games was seen.
