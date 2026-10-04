"""Write README_repo.md (the repo README) with every result value read from the note's key files.

Reads numbers.tex, extra.tex, phantom.tex, fmt.tex (run make_tables.py and make_fmt.py first). Nothing typed.
Usage: python3 make_readme.py  -> README_repo.md (copy to staleline/README.md)
"""
from __future__ import annotations
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEF = re.compile(r"\\defval\{([^}]*)\}\{(.*)\}\s*(?:%.*)?$")


def load() -> dict[str, str]:
    out = {}
    for fn in ("numbers.tex", "extra.tex", "phantom.tex", "fmt.tex"):
        for line in (HERE / fn).read_text().splitlines():
            m = DEF.match(line.strip())
            if m:
                out[m.group(1)] = m.group(2)
    return out


def md(v: str) -> str:
    v = v.replace("{,}", ",").replace("$-$", "-").replace("\\%", "%")
    v = re.sub(r"\$([0-9.]+)\\times 10\^\{(-?[0-9]+)\}\$", r"\1e\2", v)
    return v


def main() -> None:
    K = load()
    g = lambda k: md(K[k])  # noqa: E731  KeyError = missing key, fails loudly
    ci = lambda a, b: f"[{g(a)}, {g(b)}]"  # noqa: E731
    text = f"""# StaleLine

**Is Kalshi fast? Is Kalshi priced right?** StaleLine records Kalshi, polymarket.com and Polymarket US order books for the same football games, tests a pre-registered lead-lag hypothesis once on sealed holdout games, and paper-trades three pre-registered Kalshi strategies (favorite-longshot taker A, maker A-maker, cross-venue disagreement B) after real fees, spread and latency. Paper trading only.

- **Quant note (5 pages):** [`paper/StaleLine_note.pdf`](paper/StaleLine_note.pdf). Appendix (pre-registration trail, post-hoc table, disclosures): [`paper/StaleLine_appendix.pdf`](paper/StaleLine_appendix.pdf). Note sources: `paper/note_src/` (every number is generated from a committed file; `python3 check_note.py`).
- **Pre-registration:** `HYPOTHESIS_v2.md` (lead test and trade-the-laggard, Amendments 1 to 5) and `HYPOTHESIS_v3.md` (Strategies A, B and A-maker, Amendments 1 to 5), each a dated commit before the single holdout run (`{g('run_sha')}`, {g('run_start')} to {g('run_end')}). Disclosures: `docs/holdout_run_disclosure.md`.

## Headline results

| | sample | n | result | 95% CI | Sharpe (ann.) |
|---|---|---|---|---|---|
| Lead test, Kalshi vs polymarket.com (book midpoints) | holdout | {g('OOS_lead_polymarket_com_n_qualifying')} games | "{g('f_OOS_lead_polymarket_com_decision')}": median lag {g('f_OOS_lead_polymarket_com_detail_median_corrected_lag_s')} s, p = {g('lead_pmcom_mw_p')} | | |
| Lead test, Kalshi vs Polymarket US | holdout | {g('OOS_lead_Polymarket_US_n_qualifying')} games | "{g('f_OOS_lead_Polymarket_US_decision')}": median lag {g('f_OOS_lead_Polymarket_US_detail_median_corrected_lag_s')} s, p = {g('lead_pmus_mw_p')}; **not interpreted** (30 s cache, see below) | | |
| Laggard vs polymarket.com, 1 s latency | holdout | {g('laggard_pmcom_1s_n')} trades | {g('laggard_pmcom_1s_edge_c')} c/contract | {g('laggard_pmcom_1s_ci')} | |
| Strategy A, theta {g('f_A_theta')} | training | {g('A_n_trades')} | ROC {g('f_A_roc_webull')} (Kalshi direct {g('f_A_roc_direct')}) | | {g('f_A_sharpe')} |
| Strategy A, theta {g('f_A_theta')} | holdout | {g('OOS_A_n_trades')} | ROC {g('f_OOS_A_roc_webull')} (Kalshi direct {g('f_OOS_A_roc_direct')}) | {ci('f_OOS_A_roc_webull_ci_0', 'f_OOS_A_roc_webull_ci_1')} | {g('f_OOS_A_sharpe')} |
| Strategy A-maker | holdout | {g('OOS_A_maker_fills')} fills of {g('OOS_A_maker_attempts')} | ROC {g('f_OOS_A_maker_roc_webull')} | {ci('f_OOS_A_maker_roc_webull_ci_0', 'f_OOS_A_maker_roc_webull_ci_1')} | |
| Strategy B ({g('f_B_selected_setting_k')} c, {g('B_selected_setting_m')} s, {g('B_selected_setting_T')} s) | training | {g('B_n_trades')} | {g('f_B_edge_webull_cents_per_contract')} c/contract | | {g('f_B_sharpe')} |
| Strategy B | holdout | {g('OOS_B_n_trades')} | {g('f_OOS_B_edge_webull_cents')} c/contract | {ci('f_OOS_B_edge_webull_ci_0', 'f_OOS_B_edge_webull_ci_1')} | {g('f_OOS_B_sharpe')} |
| Combined book A + B | holdout | {g('OOS_combined_n_trades')} | P&L ${g('f_OOS_combined_pnl_total')}, max DD ${g('f_OOS_combined_max_drawdown_dollars')} | | {g('f_OOS_combined_sharpe')} |

Costs: Webull ${g('spec_webull_fee')} per contract per fill (primary); Kalshi direct {g('spec_kalshi_rate')} x C x P(1-P) rounded up to the cent (comparison); every result also at costs x2. Deflated Sharpe ratio: A {g('dsr_A_prereg')} at {g('count_trials_prereg')} pre-registered trials, {g('dsr_A_final')} at {g('count_trials_final')} logged trials (`experiments/variants.csv`).

**Reading:** Kalshi and polymarket.com reprice in the same second; the favorite-longshot bias exists in direction (underdog placebo ROC {g('f_A_placebo_roc_webull')}) but is smaller than taker costs. Kalshi football prices are efficient net of costs at retail speed.

## Three traps that faked an edge (and how we caught them)

1. **Thin trade prints fake lags.** Trade-based lead-lag invents a lead for the busier venue when the other is thin; book midpoints do not (simulation: `paper/figs/synthetic_bias.png`, `docs/results/activity_bias.md`, note Figure 2a). The holdout test therefore uses book midpoints.
2. **Cached quotes fake leads.** The Polymarket US quote endpoint we polled is served with `max-age` {g('diag_pmus_cache_max_age_s')} s; quotes changed every {g('f_diag_pmus_quote_change_interval_median_of_game_medians_s')} s (median) and real trades reached us {g('f_diag_pmus_receipt_minus_venue_delay_median_s')} s late. The laggard looked like +{g('laggard_pmus_1s_edge_c')} c/contract on polled quotes; fills confirmed by real Polymarket US trades lost {g('f_diag_pmus_partial_run_1p0s_confirmed_mean_c')} c (n {g('diag_pmus_partial_run_1p0s_confirmed_n_fills')}). Diagnostics: `results/holdout_diag/`.
3. **Leg-conditional execution fakes arbitrage.** A Kalshi vs polymarket.com arbitrage measurement showed {g('f_posthoc_idea11_L1_original_c_per_contract')} c/contract only because it counted a trade when the second leg would still clear later; with one-legged fills counted it is {g('f_posthoc_idea11_L1_corrected_hold_c_per_contract')} c (`results/posthoc/`).

## Post-hoc work (after the holdout run)

Every post-hoc idea has a spec committed before its run, is selected on training only, and is logged as a variant; none changes a pre-registered result. Summary table: `results/posthoc/SUMMARY.md`; running ledger: `results/posthoc/LEDGER.md`. None found an edge. The training-positive book (every training cell with positive return) returns {g('f_posthoc_posbook_roc_mean')} {ci('f_posthoc_posbook_roc_ci_0', 'f_posthoc_posbook_roc_ci_1')} on the holdout. Walk-forward meta-models predict winners (AUC {g('posthoc_meta_auc_m1')}) but not profit (correlation {g('posthoc_meta_ridge_corr')}). Later training-only searches added {g('led_new_trials')} trials ({g('led_grand_total')} disclosed in total, see `results/posthoc/LEDGER.md`); White's Reality Check over the largest combined set ({g('rc_all_trials')} trials) gives p = {g('rc_all_p')}. Kalshi vs CME on 14 playoff games: CME quotes often stay stale after a Kalshi move, but taking them loses {g('cme_cells_best_c')} to {g('cme_cells_worst_c')} c per contract to the spread. Descriptive: Kalshi was better calibrated than ESPN's win probability in all {g('posthoc_idea9_kalshi_brier_lower_rows')} variants; Kalshi complement violations lasted a median {g('f_posthoc_idea1_violation_duration_median_s')} s.

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
"""
    for bad in ("\u2014", "\u2013", "{{"):
        assert bad not in text, bad
    (HERE / "README_repo.md").write_text(text)
    print("README_repo.md written")


if __name__ == "__main__":
    main()
