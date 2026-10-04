# StaleLine

## Status: HYPOTHESIS_v4 is the live hypothesis (untested)

- **Hypothesis:** HYPOTHESIS_v4 (`main` 94aa1a0, frozen 2026-10-04 07:56 ET): a passive polymarket.com maker joining the best bid and ask, 10 contracts, inventory cap +/- 50. Arm A always quotes; Arm B quotes only while the spread is >= 3 c. These arms are not the v3 strategies A and B below.
- **Status:** not tested yet. Test set 1 had 0 eligible games (1d3d68a). The confirmatory test set 2 is all college and NFL games from Oct 8 to Oct 13, 00:00 ET, and needs a live order-book recorder that is not running yet.
- **Origin (descriptive, one day, simulated, not pre-registered):** on recorded Oct 3 polymarket.com books, 88 games, maker fee 0: +$46.53 at +60 s, +1.09 c per contract [0.17, 2.12]; +0.15 c without the top 5 games; under the reading rule (59 games with fills) all four conditions pass, so we treat it as a real lead that needs more testing on live games; 57.6% of the 59 games with fills were positive (38.6% of all 88), and over all 88 the game-share condition fails (863eb69). Those games fall in the holdout period; no committed file records authorization to use them.
- **Why the holdout cannot test it:** Aug to Oct 2 has only polymarket.com taker trades, no order books.
- **Before v4:** the pre-registered v3 strategies (not v4) did not survive their single holdout test, and 566 post-hoc trials found no other edge; details below, under the v3 headings.


**Is Kalshi fast? Is Kalshi priced right?** StaleLine records Kalshi, polymarket.com and Polymarket US order books for the same football games, tested a pre-registered lead-lag hypothesis (v2) and three Kalshi strategies (v3) once on sealed holdout games, and now carries HYPOTHESIS_v4 (a passive polymarket.com maker) as its live, untested hypothesis; the v3 strategies are favorite-longshot taker A, maker A-maker, cross-venue disagreement B, paper-traded after real fees, spread and latency. Paper trading only.

- **Quant note (5 pages):** [`paper/StaleLine_note.pdf`](paper/StaleLine_note.pdf). Appendix (pre-registration trail, post-hoc table, disclosures): [`paper/StaleLine_appendix.pdf`](paper/StaleLine_appendix.pdf). Note sources: `paper/note_src/` (every number is generated from a committed file; `python3 check_note.py`).
- **Pre-registration:** `HYPOTHESIS_v2.md` (lead test and trade-the-laggard, Amendments 1 to 5) and `HYPOTHESIS_v3.md` (Strategies A, B and A-maker, Amendments 1 to 5), each a dated commit before the single holdout run (`872ff43`, 2026-10-04 02:00:23 ET to 02:32:24 ET). Disclosures: `docs/holdout_run_disclosure.md`.

## Before v4: v3 study results (not v4)

Nothing in this section or the next two is v4; v4 has no result yet.

| | sample | n | result | 95% CI | Sharpe (ann.) |
|---|---|---|---|---|---|
| Lead test, Kalshi vs polymarket.com (book midpoints) | holdout | 88 games | "Neither venue leads consistently": median lag 0.0 s, p = 0.709 | | |
| Lead test, Kalshi vs Polymarket US | holdout | 76 games | "Kalshi leads": median lag 7.5 s, p = 3.24e-8; **not interpreted** (30 s cache, see below) | | |
| Laggard vs polymarket.com, 1 s latency | holdout | 521 trades | -3.60 c/contract | [-4.72, -2.58] | |
| Strategy A, theta 0.80 | training | 302 | ROC -0.007 (Kalshi direct 0.007) | | -0.60 |
| Strategy A, theta 0.80 | holdout | 263 | ROC -0.030 (Kalshi direct -0.015) | [-0.069, 0.006] | -3.81 |
| Strategy A-maker | holdout | 9 fills of 314 | ROC -0.150 | [-0.496, 0.111] | |
| Strategy B (5 c, 10 s, 300 s) | training | 9,242 | -4.86 c/contract | | -8.59 |
| Strategy B | holdout | 2,478 | -4.67 c/contract | [-4.98, -4.36] | -7.76 |
| Combined book A + B | holdout | 2,741 | P&L $-1,232, max DD $1,224 | | -7.78 |

Costs: Webull $0.02 per contract per fill (primary); Kalshi direct 0.07 x C x P(1-P) rounded up to the cent (comparison); every result also at costs x2. Deflated Sharpe ratio: A 1.27e-9 at 22 pre-registered trials, 2.91e-12 at 77 logged trials (`experiments/variants.csv`).

**Reading:** Kalshi and polymarket.com reprice in the same second; the favorite-longshot bias exists in direction (underdog placebo ROC -0.463) but is smaller than taker costs. Kalshi football prices are efficient net of costs at retail speed.

## Three traps from the v3 study that faked an edge (not v4)

1. **Thin trade prints fake lags.** Trade-based lead-lag invents a lead for the busier venue when the other is thin; book midpoints do not (simulation: `paper/figs/synthetic_bias.png`, `docs/results/activity_bias.md`, note Figure 2a). The holdout test therefore uses book midpoints.
2. **Cached quotes fake leads.** The Polymarket US quote endpoint we polled is served with `max-age` 30 s; quotes changed every 31.6 s (median) and real trades reached us 19.2 s late. The v3 laggard on Polymarket US (not v4) looked like +1.48 c/contract on polled quotes; fills confirmed by real Polymarket US trades lost -4.09 c (n 14), because the quote endpoint was cached. Diagnostics: `results/holdout_diag/`.
3. **Leg-conditional execution fakes arbitrage.** A Kalshi vs polymarket.com arbitrage measurement showed 1.65 c/contract only because it counted a trade when the second leg would still clear later; with one-legged fills counted it is -1.57 c (v3 data, not v4) (`results/posthoc/`).

## Post-hoc work on the v3 study (after the holdout run, not v4)

Every post-hoc idea has a spec committed before its run, is selected on training only, and is logged as a variant; none changes a pre-registered result. Summary table: `results/posthoc/SUMMARY.md`; running ledger: `results/posthoc/LEDGER.md`. None found an edge. The training-positive book (every training cell with positive return) returns -0.019 [-0.060, 0.021] on the holdout. Walk-forward meta-models predict winners (AUC 0.77) but not profit (correlation 0.015). Later training-only searches added 485 trials (566 disclosed in total, see `results/posthoc/LEDGER.md`); White's Reality Check over the largest combined set (479 trials) gives p = 0.47. Kalshi vs CME on 14 playoff games: CME quotes often stay stale after a Kalshi move, but taking them loses -1.5 to -6.6 c per contract to the spread. Descriptive: Kalshi was better calibrated than ESPN's win probability in all 8 variants; Kalshi complement violations lasted a median 0.011 s.

## Reproduce

One command checks every number in the note:

```bash
scripts/reproduce.sh   # 1) all tests, 2) the holdout pipeline on synthetic fixtures, 3) every note number regenerated
                       # from committed outputs + note recompiled + checks (no missing or hand-typed number,
                       # body <= 5 pages), 4) training numbers recomputed and diffed if the raw data is present
```

The holdout was run once (`results/holdout/RUN_LOG.md`); its recorded inputs are verified by `results/holdout_inputs_manifest.txt` (sha256). Rerunning it needs those recordings, which are vendor data and not redistributed. Post-hoc code and results live on the `posthoc-*` branches (read by the note build with `git show origin/<branch>`). The next pre-registered test is `HYPOTHESIS_v4.md` (passive maker, Oct 8 to 12 games).

Training numbers only (needs the raw training data under `data/`, see below):

```bash
scripts/reproduce_training.sh      # builds .venv-run from requirements.txt if missing, runs A, B and the book
                                   # report, diffs results/numbers.json against the committed file
```

The environment is pinned (`requirements.txt`: pandas 2.3.2, numpy 1.26.4; pandas 3 changes the default datetime unit). The raw vendor data is not in the repository; rebuild it with the ingest scripts (`python -m ingest.kalshi_only_train`, `python -m ingest.download_all`, `python -m ingest.kalshi_market_meta`, `python -m ingest.french_factors`, then `python scripts/build_b_games_espn.py`). The holdout run is `scripts/final_test_run.py --i-am-the-one-run` (refuses to run twice); `--dry-run` runs the same pipeline on synthetic fixtures.

## Data and venues

- Venue data is used read-only. No code places, amends or cancels an order on any venue, except paper orders to the Webull sandbox (execution/webull.py refuses any other host). Kalshi credentials are used only to open the read-only market-data websocket. polymarket.com data is read only: US residents cannot trade it.
- No raw vendor data and no API keys are in the repository (`data/`, `out/`, `.env` are gitignored).

## Shared data format

Every venue lands in `data/ticks/<game_id>.parquet` (and the live recorder in `data/live/<venue>/`):

| column | meaning |
|---|---|
| `ts` | UTC nanoseconds (int64) |
| `venue` | `kalshi` / `polymarket` / `polymarket_us` (`cme` for the retired v1) |
| `market_id` | venue's own symbol or ticker |
| `kind` | `trade` / `bid` / `ask` |
| `price` | 0 to 1, always P(home team wins); away-team contracts flipped with `1 - price` at ingest |
| `size` | contracts |
| `side` | `buy` / `sell` / `unknown` |

## Team

Divyam Kataria, Alden, Andrew, Olmer. Gator Quant Hacks 2026, Systematic Trading track.
