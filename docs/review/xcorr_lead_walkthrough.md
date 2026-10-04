# xcorr_lead.py walkthrough (Rule-7 review packet)

File: xcorr_lead.py at e364bb9 (branch t15-final), 209 lines. The v2 lead-test statistics: the Amendment 2 mid rule (book midpoints, never carried across an empty side), the 1 s mid-change cross-correlation lag per game, Mann-Whitney real vs placebo, the decision rule and Holm across the two venue tests (v2 Amendment 3 item 3). The confirmatory run uses mid_snapshots, mid_grid, mid_changes, n_mid_changes, game_lag_mid, decide_holm (via holdout_mid.py) and _book_wide (via laggard.py); game_lag (trade-based) and mann_whitney_p_custom are exploratory / cross-check only.

Tags at line end: **[TIME]** touches decision time, fill time, windows, outages or timestamps. **[MONEY]** touches price, fee, spread, threshold or P&L. Tests per block: every test that calls a function defined in the block.

## Lines 1 to 32

Module docstring (written for the trade-based Part A draft; see review notes) and constants: 3 s median window, max lag 15 s, 50-trade qualification (Part A only), 30 qualifying games, 1 s minimum lead, 60% share.

```python
  1  """Cross-correlation lead test (HYPOTHESIS_v2.md Amendment 2 draft, Parts A and B).
  2
  3  Per game: both venues' trailing 3 s median trade prices on the common 1 s grid (align.py), then the   [TIME] [MONEY]
  4  lag (s) maximising corr(Kalshi return at g, other-venue return at g + lag), max lag 15 s              [TIME]
  5  (leadlag.xcorr_lag). Positive = Kalshi first. Corrected lag = lag - D (median match-to-block delay    [TIME]
  6  for polymarket.com, 0 for Polymarket US).
  7
  8  Decision (drafted rule): on the qualifying games (>= 50 trades on each venue in kickoff - 2 h to      [TIME]
  9  + 5 h), with the unrelated-games placebo built the same way as the null:                              [TIME]
 10    Kalshi leads iff median corrected lag >= 1 s AND two-sided Mann-Whitney real vs placebo p < 0.05
 11    AND >= 60% of qualifying games have corrected lag > 0; symmetric for the other venue;
 12    fewer than 30 qualifying games -> "inconclusive".
 13
 14  No prices are printed; this module returns lags and decisions only.
 15  """
 16  from __future__ import annotations
 17
 18  import math
 19
 20  import numpy as np
 21  import pandas as pd
 22
 23  import align
 24  import leadlag
 25
 26  PRICE_WINDOW_S = 3.0                                                                                  [MONEY]
 27  MAX_LAG_S = 15                                                                                        [TIME]
 28  MIN_TRADES = 50
 29  MIN_GAMES = 30
 30  MIN_LEAD_S = 1.0                                                                                      [TIME]
 31  MIN_SHARE = 0.60
 32
```

Tests: none (constants/docstring)

## Lines 33 to 53

game_lag: trade-based lag (exploratory, never confirmatory): trailing 3 s median trade prices on the 1 s grid, common grid, leadlag.xcorr_lag. Then the ns constant, the empty-side sentinel and the book row kinds.

```python
 33
 34  def game_lag(ticks_x: pd.DataFrame, venue_x: str, ticks_y: pd.DataFrame, venue_y: str,
 35               max_lag_s: int = MAX_LAG_S) -> float:                                                         [TIME]
 36      """xcorr lag of venue_x (Kalshi) vs venue_y; positive = x first. NaN if the grids do not overlap."""   [TIME]
 37      gx = align.to_grid(align.trade_median_events(ticks_x, venue_x, PRICE_WINDOW_S))                        [TIME] [MONEY]
 38      gy = align.to_grid(align.trade_median_events(ticks_y, venue_y, PRICE_WINDOW_S))                        [TIME] [MONEY]
 39      if gx.empty or gy.empty:
 40          return float("nan")
 41      gx, gy = align.common_grid(gx, gy)                                                                     [TIME]
 42      if len(gx) < 2 * max_lag_s + 2:                                                                        [TIME]
 43          return float("nan")
 44      lag, corr = leadlag.xcorr_lag(gx, gy, max_lag_s)                                                       [TIME]
 45      return float(lag) if np.isfinite(corr[lag]) else float("nan")                                          [TIME]
 46
 47
 48  NS = 1_000_000_000
 49  _EMPTY = -1.0   # sentinel for "last snapshot had an empty side" so a grid carry never fills across it     [TIME]
 50
 51
 52  BOOK_KINDS = ["bid", "ask", "book_empty"]
 53
```

Tests: **none found**

## Lines 54 to 84

Book snapshots for one venue and one market: one row per recorded snapshot with bid and ask (NaN = side empty; a 'book_empty' marker row = both empty), the mid (NaN when either side is empty), and the number of non-empty sides (book-wipe rule).

```python
 54
 55  def _book_wide(ticks: pd.DataFrame, venue: str) -> pd.DataFrame:
 56      """One row per recorded snapshot ts with columns bid, ask (NaN = side empty). The collector writes the bid   [TIME] [MONEY]
 57      and ask rows of a snapshot with the same receipt ts and no row for an empty side. A snapshot with BOTH       [TIME] [MONEY]
 58      sides empty writes no row in the 2026-10-03 recordings, so it is invisible there; a "book_empty" marker      [TIME] [MONEY]
 59      row (kind "book_empty", any price) is read as a snapshot with neither side."""                               [MONEY]
 60      b = ticks[(ticks["venue"] == venue) & ticks["kind"].isin(BOOK_KINDS)]                                        [TIME] [MONEY]
 61      if b.empty:
 62          return pd.DataFrame(columns=["bid", "ask"], dtype="float64")
 63      assert b["market_id"].nunique() == 1, f"{venue}: one market per venue, got {b['market_id'].nunique()}"
 64      w = b.assign(price=b["price"].where(b["kind"] != "book_empty")) \                                            [MONEY]
 65           .pivot_table(index="ts", columns="kind", values="price", aggfunc="last", dropna=False).sort_index()     [TIME] [MONEY]
 66      for k in ("bid", "ask"):                                                                                     [MONEY]
 67          if k not in w:                                                                                           [MONEY]
 68              w[k] = np.nan                                                                                        [MONEY]
 69      return w[["bid", "ask"]]                                                                                     [MONEY]
 70
 71
 72  def mid_snapshots(ticks: pd.DataFrame, venue: str) -> pd.Series:                                                 [TIME] [MONEY]
 73      """Mid per recorded top-of-book snapshot (HYPOTHESIS_v2.md Amendment 2): index ts (ns), value                [TIME] [MONEY]
 74      (bid + ask) / 2, NaN when either side is empty. One market per venue (the runner picks it)."""               [TIME]
 75      w = _book_wide(ticks, venue)                                                                                 [TIME] [MONEY]
 76      return (w["bid"] + w["ask"]) / 2                                                                             [MONEY]
 77
 78
 79  def sides_snapshots(ticks: pd.DataFrame, venue: str) -> pd.Series:                                               [MONEY]
 80      """Number of non-empty sides (0, 1, 2) per recorded snapshot ts (book-wipe rule, Amendment 3 draft)."""      [MONEY]
 81      w = _book_wide(ticks, venue)                                                                                 [MONEY]
 82      return w["bid"].notna().astype(int) + w["ask"].notna().astype(int)                                           [MONEY]
 83
 84
```

Tests: `test_book_wipe.py::test_wipe_found_and_mid_undefined_while_empty`, `test_mid_rule.py::test_duplicate_rows_add_no_changes`, `test_mid_rule.py::test_empty_side_30s_has_no_mid_and_no_changes`, `test_book_wipe.py::test_fifteen_minute_copy_leaks_under_plus10_not_plus20 (via game_lag_mid)`, `test_book_wipe.py::test_requote_copying_kalshi_is_not_a_lead_after_exclusion (via game_lag_mid)`, `test_mid_rule.py::test_two_sided_books_match_previous_function (via game_lag_mid)`

## Lines 85 to 116

mid_grid: 1 s grid, each label = last snapshot at or before the end of that second, carried forward only, never across an empty side (sentinel). mid_changes: change from the previous DEFINED mid, never across an excluded interval. n_mid_changes: the 50-change qualification count.

```python
 85  def mid_grid(snap: pd.Series) -> pd.Series:                                                                    [TIME] [MONEY]
 86      """1 s grid label g -> mid of the last snapshot at or before the end of second g (backward only).          [TIME] [MONEY]
 87      A second with no snapshot carries the previous snapshot's state; if that state had an empty side the       [TIME] [MONEY]
 88      mid stays undefined (NaN) until a two-sided snapshot arrives."""                                           [TIME]
 89      if snap.empty:
 90          return pd.Series(dtype="float64")
 91      g = snap.index.to_numpy() // NS                                                                            [TIME]
 92      last = pd.Series(snap.fillna(_EMPTY).to_numpy(), index=g).groupby(level=0).last()                          [TIME] [MONEY]
 93      full = np.arange(last.index.min(), last.index.max() + 1, dtype="int64")                                    [TIME] [MONEY]
 94      return last.reindex(full).ffill().replace(_EMPTY, np.nan)                                                  [TIME] [MONEY]
 95
 96
 97  def mid_changes(grid: pd.Series, exclude=()) -> pd.Series:                                                     [TIME]
 98      """Per grid second: defined mid minus the previous DEFINED mid; NaN where the mid is undefined or no       [TIME] [MONEY]
 99      earlier defined mid exists. Duplicate rows cannot create a change (the mid does not move).                 [TIME] [MONEY]
100      exclude: (lo_g, hi_g) grid-second intervals, inclusive (book-wipe rule). Mids inside are dropped, and a    [TIME]
101      change never spans an excluded interval: the first defined mid after it has no previous mid."""            [TIME]
102      g = grid.copy()                                                                                            [TIME]
103      seg = np.zeros(len(g), dtype="int64")                                                                      [TIME]
104      for lo, hi in exclude:                                                                                     [TIME]
105          g[(g.index >= lo) & (g.index <= hi)] = np.nan                                                          [TIME] [MONEY]
106          seg += (g.index > hi).astype("int64")                                                                  [TIME]
107      prev = g.groupby(seg).ffill().groupby(seg).shift(1)                                                        [TIME]
108      return (g - prev).where(g.notna())                                                                         [TIME] [MONEY]
109
110
111  def n_mid_changes(grid: pd.Series, exclude=()) -> int:
112      """Amendment 2 qualification count: grid seconds whose defined mid differs from the previous defined mid   [MONEY]
113      (outside excluded intervals)."""
114      c = mid_changes(grid, exclude)
115      return int((c.notna() & (c.abs() > 1e-12)).sum())                                                          [MONEY]
116
```

Tests: `test_book_wipe.py::test_change_never_spans_exclusion`, `test_book_wipe.py::test_wipe_found_and_mid_undefined_while_empty`, `test_mid_rule.py::test_duplicate_rows_add_no_changes`, `test_mid_rule.py::test_empty_side_30s_has_no_mid_and_no_changes`, `test_book_wipe.py::test_fifteen_minute_copy_leaks_under_plus10_not_plus20 (via game_lag_mid)`, `test_book_wipe.py::test_requote_copying_kalshi_is_not_a_lead_after_exclusion (via game_lag_mid)`, `test_mid_rule.py::test_two_sided_books_match_previous_function (via game_lag_mid)`

## Lines 117 to 148

game_lag_mid: the confirmatory per-game lag: correlation of Kalshi's mid change at g with the other venue's at g + lag, lag -15..15 s, pairwise over seconds where both are defined; argmax (positive = Kalshi first). mann_whitney_p: scipy two-sided.

```python
117
118  def game_lag_mid(ticks_x: pd.DataFrame, venue_x: str, ticks_y: pd.DataFrame, venue_y: str,                  [TIME]
119                   max_lag_s: int = MAX_LAG_S, exclude=()) -> float:                                          [TIME]
120      """Book-midpoint version (Amendment 2 confirmatory test): xcorr of 1 s mid changes, mids defined only   [TIME] [MONEY]
121      when both sides exist, never filled across an empty side. Seconds without a defined change on either    [TIME]
122      venue drop out of the correlation (pairwise). Positive = x (Kalshi) first. exclude: grid-second         [TIME]
123      intervals dropped for BOTH venues (book-wipe rule, Amendment 3 draft)."""                               [TIME]
124      gx, gy = mid_grid(mid_snapshots(ticks_x, venue_x)), mid_grid(mid_snapshots(ticks_y, venue_y))           [TIME] [MONEY]
125      if gx.empty or gy.empty:
126          return float("nan")
127      lo, hi = max(gx.index.min(), gy.index.min()), min(gx.index.max(), gy.index.max())                       [TIME]
128      if hi - lo + 1 < 2 * max_lag_s + 2:                                                                     [TIME]
129          return float("nan")
130      idx = np.arange(lo, hi + 1, dtype="int64")                                                              [TIME]
131      rx, ry = mid_changes(gx, exclude).reindex(idx), mid_changes(gy, exclude).reindex(idx)                   [TIME] [MONEY]
132      corr = {lag: float(rx.corr(ry.shift(-lag))) for lag in range(-max_lag_s, max_lag_s + 1)}                [TIME]
133      corr = {k: (v if v == v else -np.inf) for k, v in corr.items()}
134      lag = max(corr, key=corr.get)                                                                           [TIME]
135      return float(lag) if np.isfinite(corr[lag]) else float("nan")
136
137
138  def mann_whitney_p(a, b) -> float:
139      """Two-sided Mann-Whitney U test (scipy.stats.mannwhitneyu, default method). NaNs dropped."""
140      from scipy.stats import mannwhitneyu
141      a, b = np.asarray(a, float), np.asarray(b, float)
142      a, b = a[~np.isnan(a)], b[~np.isnan(b)]
143      if len(a) == 0 or len(b) == 0:
144          return float("nan")
145      if np.unique(np.concatenate([a, b])).size == 1:
146          return 1.0
147      return float(mannwhitneyu(a, b, alternative="two-sided").pvalue)
148
```

Tests: `test_activity_bias.py::test_mann_whitney_sanity`, `test_book_wipe.py::test_fifteen_minute_copy_leaks_under_plus10_not_plus20`, `test_book_wipe.py::test_requote_copying_kalshi_is_not_a_lead_after_exclusion`, `test_mid_rule.py::test_two_sided_books_match_previous_function`, `test_mw_holm.py::test_custom_matches_scipy_asymptotic`, `test_mw_holm.py::test_holm_levels_and_stop`, `test_holdout_mid.py::test_runner_end_to_end (via decide)`, `test_mw_holm.py::test_fixed_verdict_80_games_5s_lead (via decide)`, `test_mw_holm.py::test_fixed_verdict_zero_lag_linked (via decide)`

## Lines 149 to 171

mann_whitney_p_custom: the earlier hand-written normal approximation with tie and continuity correction, kept only to cross-check scipy (equal to 1e-9 on tied whole-second lags).

```python
149
150  def mann_whitney_p_custom(a, b) -> float:
151      """Cross-check only (tests): the earlier hand-written version. Normal approximation, tie and continuity
152      correction."""
153      a, b = np.asarray(a, float), np.asarray(b, float)
154      a, b = a[~np.isnan(a)], b[~np.isnan(b)]
155      n1, n2 = len(a), len(b)
156      if n1 == 0 or n2 == 0:
157          return float("nan")
158      allv = np.concatenate([a, b])
159      ranks = pd.Series(allv).rank(method="average").to_numpy()
160      u1 = ranks[:n1].sum() - n1 * (n1 + 1) / 2
161      mu = n1 * n2 / 2
162      _, counts = np.unique(allv, return_counts=True)
163      n = n1 + n2
164      tie = (counts ** 3 - counts).sum() / (n * (n - 1)) if n > 1 else 0.0
165      sigma = math.sqrt(n1 * n2 / 12 * ((n + 1) - tie))
166      if sigma == 0:
167          return 1.0
168      z = (abs(u1 - mu) - 0.5) / sigma
169      return float(math.erfc(max(z, 0.0) / math.sqrt(2)))
170
171
```

Tests: `test_mw_holm.py::test_custom_matches_scipy_asymptotic`

## Lines 172 to 209

decide: < 30 qualifying games -> inconclusive; else a lead needs median lag >= min lead AND Mann-Whitney p < its level AND >= 60% of games on that side. decide_holm: the smaller p judged at 0.025, the larger at 0.05 only if the first passes, else at 0 (cannot pass).

```python
172  def decide(real_lags, placebo_lags, d_s: float = 0.0, x: str = "kalshi", y: str = "other",                             [TIME]
173             min_lead_s: float = MIN_LEAD_S, alpha: float = 0.05) -> dict:                                               [TIME]
174      r = np.asarray(real_lags, float) - d_s                                                                             [TIME]
175      pl = np.asarray(placebo_lags, float) - d_s                                                                         [TIME]
176      r, pl = r[~np.isnan(r)], pl[~np.isnan(pl)]
177      out = {"n_qualifying": int(len(r)), "n_placebo": int(len(pl))}
178      if len(r) < MIN_GAMES:
179          out["result"] = f"inconclusive ({len(r)} qualifying games < {MIN_GAMES})"
180          return out
181      med, p = float(np.median(r)), mann_whitney_p(r, pl)                                                                [TIME]
182      share_pos, share_neg = float((r > 0).mean()), float((r < 0).mean())
183      out.update({"median_corrected_lag_s": med, "mann_whitney_p": p, "share_positive": share_pos,
184                  "share_negative": share_neg, "placebo_median_s": float(np.median(pl)) if len(pl) else float("nan")})
185      out["alpha"] = alpha
186      if med >= min_lead_s and p < alpha and share_pos >= MIN_SHARE:                                                     [TIME]
187          out["result"] = f"{x} leads"
188      elif med <= -min_lead_s and p < alpha and share_neg >= MIN_SHARE:                                                  [TIME]
189          out["result"] = f"{y} leads"
190      else:
191          out["result"] = "neither venue leads consistently"
192      return out
193
194
195  def decide_holm(inputs: dict, alpha: float = 0.05) -> dict:
196      """Holm across the venue tests (Amendment 3 draft): inputs = {test: (real_lags, placebo_lags, y, min_lead_s)}.
197      Step-down: the smaller Mann-Whitney p is judged at alpha / 2; only if that test's p passes is the larger p
198      judged at alpha. A test whose p fails its Holm level cannot be called a lead (other criteria unchanged)."""
199      p = {t: mann_whitney_p(np.asarray(r, float), np.asarray(pl, float)) for t, (r, pl, _y, _m) in inputs.items()}
200      order = sorted(p, key=lambda t: (np.inf if p[t] != p[t] else p[t]))
201      levels, still = {}, True
202      for i, t in enumerate(order):
203          lv = alpha / (len(order) - i)
204          levels[t] = lv if still else 0.0             # 0.0: Holm stopped, nothing below can pass
205          still = still and (p[t] == p[t]) and p[t] < lv
206      out = {}
207      for t, (r, pl, y, m) in inputs.items():
208          out[t] = {**decide(r, pl, 0.0, "kalshi", y, min_lead_s=m, alpha=levels[t]), "holm_level": levels[t]}
209      return out
```

Tests: `test_book_wipe.py::test_requote_copying_kalshi_is_not_a_lead_after_exclusion`, `test_holdout_mid.py::test_runner_end_to_end`, `test_mw_holm.py::test_fixed_verdict_80_games_5s_lead`, `test_mw_holm.py::test_fixed_verdict_zero_lag_linked`, `test_mw_holm.py::test_holm_levels_and_stop`

## Where a lookahead could hide, and why each is safe

1. **The mid grid (lines 85 to 94).** Each grid label takes the last snapshot with receipt time before the end of that second and only carries it FORWARD (`ffill`), never back; an empty-side snapshot is carried as the sentinel so a later second never inherits an older two-sided mid across it (line 92 to 94). The grid is built from the recorder's receipt timestamps, which are the times we could have known each quote. Tests: `test_mid_rule.py`.

2. **The lag statistic (lines 131 to 134).** game_lag_mid correlates changes at g with changes at g + lag for lags in both directions over the whole window. That uses "future" seconds by design: it is a MEASUREMENT of who moves first across a finished game, not a trading decision, and both directions are scanned symmetrically (-15 to +15 s), so it cannot favour Kalshi. No trading decision in the project reads it. Tests: `test_activity_bias.py` (quote-based cases), `test_holdout_mid.py` (planted 5 s lead found).

3. **The placebo and the decision (lines 172 to 209).** The placebo lags come from unrelated game pairs on the same machine and the same window rules (holdout_mid.py), and the decision compares real vs placebo lags only through counts, medians and Mann-Whitney; nothing in decide() looks at prices. Holm levels are fixed before any p is seen (alpha / 2, then alpha). Tests: `test_mw_holm.py`.

## Points for your line-by-line review (choices to confirm)

- Lines 1 to 12: the module docstring describes the trade-based Part A draft (qualification by >= 50 trades, a D correction). The confirmatory book-mid test qualifies on >= 50 mid changes (holdout_mid.py, MIN_CHANGES) and uses d_s = 0 (receipt times on both venues). The docstring is stale; the code paths used by the run are right.
- Line 134: `max(corr, key=corr.get)` breaks a tie toward the FIRST lag in the dict, i.e. the most negative lag (other venue first). Conservative against "Kalshi leads"; worth stating in the note.
- Line 133: a lag whose correlation is NaN (no overlapping defined changes) scores -inf; if all are NaN the game's lag is NaN and it drops out of decide().
- Line 33 to 45: game_lag (trade-based) has no direct test; it feeds only the exploratory trade-based table, never the confirmatory decision.
- Line 145: if every real and placebo lag is identical, p = 1 (scipy would otherwise warn/NaN).
- Lines 186 to 189: "neither venue leads consistently" covers both a real tie and a failed Holm level; the per-test dict records `holm_level` so the reader can tell which.
- Line 63: the one-market-per-venue assert makes a mis-mapped instrument fail loudly rather than mix two markets.
