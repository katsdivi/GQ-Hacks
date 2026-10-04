# strategy_b.py walkthrough (Rule-7 review packet)

File: strategy_b.py at ac2ffad (branch t13-strategy-a), 214 lines. Ran on training (run_strategy_b.py); tests in tests/test_strategy_b.py. Any bug found in review is fixed and disclosed with before/after numbers.

Tags at line end: **[TIME]** touches decision time, fill time, validity windows or the window. **[MONEY]** touches price, fee, half-spread, threshold or P&L.

## Lines 1 to 29

Module docstring: the pre-registered rule in words (window, 3 s medians, 60 s validity, entry after m seconds, exits, fill at the first Kalshi trade in [t + 1 s, t + 60 s] plus or minus 0.5 cent, costs, grid, placebo).

```python
  1  """Strategy B (HYPOTHESIS_v3.md "Strategy B" with Amendment 1 sections 3 and 5): Kalshi vs polymarket.com
  2  disagreement, trading Kalshi only.
  3
  4  Rule-7 file: written on branch t13-strategy-a, reviewed line by line by Divi (docs/review/strategy_b_walkthrough.md).
  5
  6  Per game, window [ESPN kickoff - 30 min, ESPN kickoff + 4.5 h] (Amendment 1 section 3), 1 s grid (align.py):
  7    Price per venue: trailing 3 s median of that venue's trade prices (align.trade_median_events, window (t-3 s, t]),
  8      P(home), raw timestamps (polymarket.com block time, never shifted). Grid label g = last value at or before
  9      the end of second g. Kalshi = all trades of both team markets (tick contract: both already P(home)).
 10    Valid: d(g) = Kalshi(g) - polymarket.com(g) is valid only if BOTH venues have a trade in the 60 s ending at the
 11      end of second g, i.e. ts in ((g + 1) s - 60 s, (g + 1) s).
 12    Entry: d valid and |d| >= k with the same sign for m consecutive seconds (counted only after the previous exit);
 13      decision stamped at the end of the m-th second, (g + 1) s. Trade Kalshi toward polymarket.com: buy P(home) if
 14      d < 0, sell if d > 0. 10 contracts, one position at a time.
 15    Exit: first later second with d valid and |d| < 1 cent ("converged"), else at entry label + T ("timeout"),
 16      else at the last window second ("window end"). Decision at (exit label + 1) s.
 17    Fill (Amendment 1 section 5): the first Kalshi trade with ts in [decision + 1 s, decision + 60 s]; buy at
 18      trade + 0.5 cent, sell at trade - 0.5 cent
 19      (v3 training fill model, half-spread 0.5 cent). No such trade at entry or at exit -> the trade is skipped and
 20      counted (a round trip is never half filled).
 21    Costs: Webull $0.02 per contract per fill (entry and exit, primary); Kalshi direct 0.07 x C x P x (1 - P)
 22      rounded up to the cent per order (comparison), P = fill price (P(1 - P) is the same for either side).
 23    Net edge per trade = net P&L per contract, in cents.
 24  Grid: k in {3, 5} cents x m in {10, 30} s x T in {60, 300} s.
 25  Placebo (v3): Kalshi from game A against polymarket.com from game B, the next game in kickoff order with kickoff
 26    within 30 min after A (cyclic within the 30 min slot); A's window and A's Kalshi fills.
 27  No prices are printed. Sealed games (kickoff >= 2026-08-01) are refused unless final_test=True.
 28  """
 29  from __future__ import annotations
```

Tests: none (docstring)

## Lines 30 to 61

Imports and fixed constants: the 8-setting grid, window -30 min / +4.5 h, 3 s median, 60 s validity, 1 cent exit gap, 1 s latency, 60 s fill window, 0.5 cent half-spread, 10 contracts, Webull $0.02, 30-trade selection floor; the Grid record (d and validity per second).

```python
 30
 31  from dataclasses import dataclass
 32
 33  import numpy as np
 34  import pandas as pd
 35
 36  import align
 37  from strategy_a import fee_kalshi_direct
 38
 39  NS = 1_000_000_000
 40  SEAL = pd.Timestamp("2026-08-01", tz="UTC")
 41  K_GRID, M_GRID, T_GRID = (0.03, 0.05), (10, 30), (60, 300)                                          [MONEY]
 42  SETTINGS = [(k, m, t) for k in K_GRID for m in M_GRID for t in T_GRID]
 43  PRE_S, POST_S = 30 * 60, int(4.5 * 3600)                                                            [TIME]
 44  MEDIAN_WINDOW_S = 3.0                                                                               [TIME]
 45  STALE_S = 60                                                                                        [TIME]
 46  EXIT_GAP = 0.01                                                                                     [MONEY]
 47  LATENCY_S = 1.0                                                                                     [TIME]
 48  FILL_WINDOW_S = 60                                                                                  [TIME]
 49  HALF_SPREAD = 0.005                                                                                 [MONEY]
 50  QTY = 10                                                                                            [MONEY]
 51  WEBULL_PER_CONTRACT = 0.02                                                                          [MONEY]
 52  MIN_TRADES_SELECT = 30                                                                              [MONEY]
 53  EPS = 1e-9
 54
 55
 56  @dataclass
 57  class Grid:
 58      lo_g: int
 59      d: np.ndarray          # Kalshi - polymarket.com per second (NaN if either price undefined)
 60      valid: np.ndarray      # bool: both venues traded in the 60 s ending at the end of the second
 61
```

Tests: `test_timeout_and_m_and_k`, `test_select_setting_needs_30_trades`

## Lines 62 to 87

venue_grid: per-second 3 s median price (backward, carried forward) and 'traded in the last 60 s' flag for one venue. build_grid: d = Kalshi minus polymarket.com, valid only where both flags hold and both prices exist.

```python
 62
 63  def venue_grid(trades: pd.DataFrame, venue: str, lo_g: int, hi_g: int) -> tuple[np.ndarray, np.ndarray]:
 64      """(price, has_recent_trade) per grid second lo_g..hi_g. Backward only: label g uses trades with             [TIME]
 65      ts < (g + 1) s."""                                                                                           [TIME]
 66      n = hi_g - lo_g + 1
 67      tr = trades[(trades["venue"] == venue) & (trades["kind"] == "trade")]
 68      if tr.empty:
 69          return np.full(n, np.nan), np.zeros(n, bool)
 70      ev = align.trade_median_events(tr, venue, MEDIAN_WINDOW_S)                                                   [TIME]
 71      # to_grid spans from the first trade (pre-window trades included), so reindexing carries the last value in
 72      px = align.to_grid(ev).reindex(np.arange(lo_g, hi_g + 1)).ffill()                                            [TIME]
 73      ts = np.sort(tr["ts"].to_numpy(dtype="int64"))
 74      ends = (np.arange(lo_g, hi_g + 1, dtype="int64") + 1) * NS        # end of each second                       [TIME]
 75      last = np.searchsorted(ts, ends, side="left") - 1                 # last trade with ts < end                 [TIME]
 76      last_ts = np.where(last >= 0, ts[np.clip(last, 0, None)], np.iinfo(np.int64).min)                            [TIME]
 77      recent = (last >= 0) & (last_ts > ends - STALE_S * NS)                                                       [TIME]
 78      return px.to_numpy(float), recent
 79
 80
 81  def build_grid(k_trades: pd.DataFrame, p_trades: pd.DataFrame, lo_ns: int, hi_ns: int) -> Grid:
 82      lo_g, hi_g = lo_ns // NS, hi_ns // NS - 1                                                                    [TIME]
 83      kp, kr = venue_grid(k_trades, "kalshi", lo_g, hi_g)
 84      pp, pr = venue_grid(p_trades, "polymarket", lo_g, hi_g)
 85      d = kp - pp                                                                                                  [MONEY]
 86      return Grid(lo_g, d, kr & pr & ~np.isnan(d))
 87
```

Tests: `test_entry_after_m_seconds_and_fill_after_latency`, `test_staleness_60s_blocks_entry`, `test_no_lookahead_future_rows_do_not_change_trade`

## Lines 88 to 130

signals: run lengths of same-sign |d| >= k; entry at the first second where the run reaches m (counted only after the last exit); direction toward polymarket.com; exit at the first later valid |d| < 1 cent, else entry + T, else window end. Decisions stamped (label + 1) s.

```python
 88
 89  def _runlen(c: np.ndarray) -> np.ndarray:
 90      """Length of the run of True ending at each index."""
 91      r = np.zeros(len(c), dtype=np.int64)
 92      run = 0
 93      for i, x in enumerate(c):
 94          run = run + 1 if x else 0
 95          r[i] = run
 96      return r
 97
 98
 99  def signals(grid: Grid, k: float, m: int, t_s: int) -> pd.DataFrame:
100      """Round-trip decisions on the grid. A label-g decision is stamped (g + 1) s."""                                     [TIME]
101      d, v = grid.d, grid.valid
102      n = len(d)
103      up = v & (d >= k - EPS)                                                                                              [MONEY]
104      dn = v & (d <= -k + EPS)                                                                                             [MONEY]
105      r_up, r_dn = _runlen(up), _runlen(dn)
106      conv = v & (np.abs(d) < EXIT_GAP - EPS)                                                                              [MONEY]
107      rows, s = [], 0
108      while s < n:
109          # first i >= s + m - 1 whose same-sign run reaches m counting only seconds >= s                                  [TIME]
110          idx = np.arange(s + m - 1, n)                                                                                    [TIME]
111          ok = ((r_up[s + m - 1:] >= m) | (r_dn[s + m - 1:] >= m)) if len(idx) else np.array([], bool)                     [TIME]
112          hits = idx[ok]
113          if not len(hits):
114              break
115          e = int(hits[0])                                                                                                 [TIME]
116          direction = 1 if d[e] < 0 else -1               # buy Kalshi P(home) when Kalshi is below polymarket.com         [MONEY]
117          later = np.flatnonzero(conv[e + 1:min(e + t_s, n - 1) + 1])                                                      [TIME]
118          if len(later):                                                                                                   [TIME]
119              x, reason = e + 1 + int(later[0]), "converged"                                                               [TIME]
120          elif e + t_s <= n - 1:                                                                                           [TIME]
121              x, reason = e + t_s, "timeout"                                                                               [TIME]
122          else:                                                                                                            [TIME]
123              x, reason = n - 1, "window end"                                                                              [TIME]
124          rows.append({"entry_g": grid.lo_g + e, "exit_g": grid.lo_g + x, "direction": direction, "exit_reason": reason,
125                       "entry_dec_ns": (grid.lo_g + e + 1) * NS, "exit_dec_ns": (grid.lo_g + x + 1) * NS,                  [TIME]
126                       "d_at_entry_cents": round(float(d[e]) * 100, 2)})                                                   [MONEY]
127          s = x + 1                                                                                                        [TIME]
128      return pd.DataFrame(rows, columns=["entry_g", "exit_g", "direction", "exit_reason", "entry_dec_ns",
129                                         "exit_dec_ns", "d_at_entry_cents"])
130
```

Tests: `test_entry_after_m_seconds_and_fill_after_latency`, `test_timeout_and_m_and_k`, `test_staleness_60s_blocks_entry`, `test_sell_direction_and_seal`, `test_no_lookahead_future_rows_do_not_change_trade`

## Lines 131 to 163

first_fill: first Kalshi trade in [decision + 1 s, decision + 60 s]. fill_trades: entry and exit fills with the 0.5 cent half-spread against us, both fills or the trade is skipped and counted; Webull and Kalshi-direct fees on both fills; P&L and net edge per contract.

```python
131
132  def first_fill(k_ts: np.ndarray, k_px: np.ndarray, dec_ns: int) -> tuple[int, float] | None:
133      """First Kalshi trade with ts in [dec + 1 s, dec + 60 s] (k_ts sorted)."""                                        [TIME]
134      lo, hi = dec_ns + int(LATENCY_S * NS), dec_ns + FILL_WINDOW_S * NS                                                [TIME]
135      i = int(np.searchsorted(k_ts, lo, side="left"))                                                                   [TIME]
136      if i >= len(k_ts) or k_ts[i] > hi:                                                                                [TIME]
137          return None
138      return int(k_ts[i]), float(k_px[i])                                                                               [TIME] [MONEY]
139
140
141  def fill_trades(sig: pd.DataFrame, k_trades: pd.DataFrame, half_spread: float = HALF_SPREAD,
142                  fee_mult: float = 1.0) -> pd.DataFrame:
143      tr = k_trades[(k_trades["venue"] == "kalshi") & (k_trades["kind"] == "trade")].sort_values("ts", kind="stable")
144      k_ts, k_px = tr["ts"].to_numpy(dtype="int64"), tr["price"].to_numpy(float)                                        [MONEY]
145      out = []
146      for s in sig.itertuples():
147          a, b = first_fill(k_ts, k_px, s.entry_dec_ns), first_fill(k_ts, k_px, s.exit_dec_ns)                          [TIME]
148          row = s._asdict()
149          row.pop("Index", None)
150          if a is None or b is None:
151              out.append({**row, "filled": False, "skip": "no entry fill" if a is None else "no exit fill"})
152              continue
153          p_in = round(a[1] + s.direction * half_spread, 4)        # buy pays up, sell receives less                    [MONEY]
154          p_out = round(b[1] - s.direction * half_spread, 4)                                                            [MONEY]
155          fw = 2 * WEBULL_PER_CONTRACT * QTY * fee_mult                                                                 [MONEY]
156          fd = (fee_kalshi_direct(p_in, QTY) + fee_kalshi_direct(p_out, QTY)) * fee_mult                                [MONEY]
157          gross = s.direction * (p_out - p_in) * QTY                                                                    [MONEY]
158          out.append({**row, "filled": True, "skip": "", "entry_fill_ts": a[0], "exit_fill_ts": b[0],
159                      "entry_px": p_in, "exit_px": p_out, "fee_webull": fw, "fee_direct": fd,                           [MONEY]
160                      "pnl_webull": gross - fw, "pnl_direct": gross - fd,                                               [MONEY]
161                      "edge_webull_cents": (gross - fw) / QTY * 100, "edge_direct_cents": (gross - fd) / QTY * 100})    [MONEY]
162      return pd.DataFrame(out)
163
```

Tests: `test_entry_after_m_seconds_and_fill_after_latency`, `test_no_fill_within_60s_skips_whole_trade`, `test_sell_direction_and_seal`, `test_no_lookahead_future_rows_do_not_change_trade`

## Lines 164 to 188

window from the ESPN kickoff; evaluate_game: seal guard, one grid per game, all settings, valid-share info.

```python
164
165  def window(espn_kickoff) -> tuple[int, int]:                                                             [TIME]
166      k = pd.Timestamp(espn_kickoff)                                                                       [TIME]
167      k = k.tz_localize("UTC") if k.tzinfo is None else k.tz_convert("UTC")                                [TIME]
168      return k.value - PRE_S * NS, k.value + POST_S * NS                                                   [TIME]
169
170
171  def evaluate_game(game_id: str, espn_kickoff, k_trades: pd.DataFrame, p_trades: pd.DataFrame,
172                    settings=SETTINGS, final_test: bool = False, half_spread: float = HALF_SPREAD,
173                    fee_mult: float = 1.0) -> tuple[pd.DataFrame, dict]:
174      """All settings for one (Kalshi, polymarket.com) pair. Returns (trades, info with valid share)."""
175      if pd.Timestamp(espn_kickoff) >= SEAL and not final_test:                                            [TIME]
176          raise ValueError(f"{game_id}: kickoff on/after 2026-08-01 is sealed (needs final_test)")
177      lo, hi = window(espn_kickoff)                                                                        [TIME]
178      g = build_grid(k_trades, p_trades, lo, hi)
179      out = []
180      for k, m, t_s in settings:
181          f = fill_trades(signals(g, k, m, t_s), k_trades, half_spread, fee_mult)
182          if len(f):
183              out.append(f.assign(k=k, m=m, T=t_s))
184      info = {"game_id": game_id, "valid_share": float(g.valid.mean()) if len(g.valid) else 0.0}
185      cols = ["k", "m", "T", "filled", "skip"]
186      return (pd.concat(out, ignore_index=True).assign(game_id=game_id) if out
187              else pd.DataFrame(columns=cols + ["game_id"])), info
188
```

Tests: `test_entry_after_m_seconds_and_fill_after_latency`, `test_sell_direction_and_seal`

## Lines 189 to 214

placebo_pairs: slots of games within 30 min of the slot's first kickoff, each paired with the next in kickoff order, cyclic. select_setting: best mean Webull net edge per trade among settings with >= 30 trades (ties: more trades).

```python
189
190  def placebo_pairs(games: pd.DataFrame) -> list[tuple[str, str]]:
191      """(A, B): B = the next game in kickoff order with kickoff within 30 min after A's slot start, cyclic
192      within the slot (games whose kickoffs are within 30 min of the slot's first game). A game alone in its slot
193      has no partner."""
194      g = games.sort_values(["espn_kickoff", "game_id"]).reset_index(drop=True)
195      ko = pd.to_datetime(g["espn_kickoff"], utc=True)
196      pairs, i = [], 0
197      while i < len(g):
198          j = i
199          while j + 1 < len(g) and (ko[j + 1] - ko[i]) <= pd.Timedelta(minutes=30):                                 [TIME]
200              j += 1
201          slot = list(g["game_id"][i:j + 1])
202          if len(slot) > 1:
203              pairs += [(slot[x], slot[(x + 1) % len(slot)]) for x in range(len(slot))]
204          i = j + 1
205      return pairs
206
207
208  def select_setting(summary: pd.DataFrame):
209      """v3: best mean net edge per trade (Webull line) among settings with at least 30 trades."""
210      s = summary[summary["n_trades"] >= MIN_TRADES_SELECT]
211      if s.empty:
212          return None
213      b = s.sort_values(["edge_webull_cents", "n_trades"], ascending=[False, False]).iloc[0]                        [MONEY]
214      return (float(b["k"]), int(b["m"]), int(b["T"]))
```

Tests: `test_placebo_pairs_cyclic_within_30_min`, `test_select_setting_needs_30_trades`

## Where a lookahead could hide, and why each is safe

1. **The price grid (lines 70 to 72) and validity (73 to 77).** The 3 s median is computed per trade over (t - 3 s, t] (align.trade_median_events, `closed="right"`), placed on the grid by `to_grid` (last value with ts < (g + 1) s) and only carried forward (`ffill`), never back. Validity at label g uses the last trade with ts < end of second g (line 75, `side="left"` on the end), so a trade later in time cannot make an earlier second valid. Test: `test_no_lookahead_future_rows_do_not_change_trade` (cutting all rows after the exit fill leaves the trade unchanged), `test_staleness_60s_blocks_entry`.

2. **The decision stamp (lines 109 to 127).** The entry label e is the m-th second of the run; the decision is stamped at (e + 1) s (line 125) because label e includes trades up to the end of second e. Run lengths (line 105) only look backward. The exit scan (line 117) looks forward from e, but each exit label x is chosen from d at x itself, and the exit decision is stamped (x + 1) s, so no exit uses a price after its own decision. Test: `test_entry_after_m_seconds_and_fill_after_latency` (hand-derived entry label S + 10, decision S + 11 s).

3. **The fills (lines 132 to 138, used at 147 and 153 to 154).** Fills are meant to read the future and are bounded: the first trade at or after decision + 1 s (latency) and no later than decision + 60 s. A fill can never use a trade from before decision + 1 s (`searchsorted` from `lo`), and a missing fill skips the round trip instead of falling back to an older price (lines 150 to 152). Nothing from a fill feeds back into a decision: signals (lines 99 to 129) are built before any fill is looked up. Tests: `test_entry_after_m_seconds_and_fill_after_latency`, `test_no_fill_within_60s_skips_whole_trade`.

## Points for your line-by-line review (choices to confirm)

- Line 70: Kalshi price = all trades of both team markets in P(home) (tick contract), not the home market alone. Fills (line 143) also use any Kalshi trade in P(home); a sell of P(home) is in practice a buy of the away market.
- Lines 103 to 105: a run must keep the same sign; a flip from +k to -k restarts the count.
- Line 117: convergence needs a VALID second with |d| < 1 cent; an invalid stretch never triggers an exit except by timeout or window end (v3: "an open position exits at T if d stays invalid").
- Line 127: after an exit at label x, a new run counts only seconds from x + 1, so an entry cannot reuse seconds from the previous position.
- Lines 153 to 154: the 0.5 cent half-spread can give a half-cent fill price; prices are not clipped to [0.01, 0.99].
- Lines 194 to 204: placebo slots start at each slot's first kickoff; a game more than 30 min after the slot start opens a new slot. 778 pairs from 963 games.
