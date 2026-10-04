# laggard.py walkthrough (Rule-7 review packet)

File: laggard.py at 82fe822 (branch t15-final), 231 lines. Trade-the-laggard evaluator (v2 Amendment 2 setting, Amendment 3 items 16 to 16b). It also relies on leadlag.detect_jumps (trailing window only: compares p[g] with min/max over labels g-10..g) and strategy.signals (entry on a detected jump if the gap >= 3 cents; exit at the first later label with gap < 1 cent, else timeout; decision at label + 1 s). Tags are keyword-assisted (timestamps, delay, latency, window, breaks -> [TIME]; price, mid, gap, fee, P&L, size -> [MONEY]) and checked by hand on the lines named below.

Tags at line end: **[TIME]** touches decision time, fill time, windows, outages or timestamps. **[MONEY]** touches price, fee, spread, threshold or P&L. Tests per block: every test that calls a function defined in the block.

## Lines 1 to 37

Module docstring: the fixed setting, the mid rule, breaks (no mid carried across a kickoff cut, an outage or the window end), timing (decision at label + 1 s, fill at decision + the market's delay + latency), the fill rule and its skips, capacity, costs, the seal.

```python
  1  """Trade-the-laggard evaluator on recorded books (HYPOTHESIS_v2.md Amendment 2, one pre-registered setting).
  2
  3  Rule-7 file (same review rule as strategy.py / backtest.py): written on branch t14-laggard, reviewed line by
  4  line by Divi before main. Synthetic tests only (tests/test_laggard.py); not run on any recorded game.
  5
  6  Setting (Amendment 2, fixed): Kalshi is the leader. A Kalshi mid jump of >= 4 cents within a trailing 10 s
  7  window (leadlag.detect_jumps) opens a position on the follower venue if the gap Kalshi mid - follower mid, in
  8  the jump direction, is >= 3 cents at that second; exit when the gap is < 1 cent or after 60 s; 10 contracts;
  9  one position at a time (strategy.signals).
 10  Mids: Amendment 2 mid rule (xcorr_lead.mid_snapshots / mid_grid): 1 s grid, defined only when both sides
 11  exist. Breaks: every excluded interval (book-wipe rule, kickoff cut) and every heartbeat outage of either venue
 12  (GAPS rows, passed in as `outages`). Inside a break neither venue has a mid, and after it a venue's mid stays
 13  undefined until that venue's first snapshot received after the break ends: a mid is never carried across a
 14  break, and none is carried past the window end. So no entry happens in or right after a break and a gap is
 15  never measured across one.
 16  Timing: a decision from grid label g is knowable at (g + 1) s (strategy.decision_time_ns). The order is sent
 17  then and fills at decision + venue delay + latency:
 18    polymarket.com: the market's own sports taker delay (v2 Amendment 3): seconds_delay from
 19    data/live/holdout_seconds_delay.csv (CLOB field seconds_delay, read 2026-10-03 16:22 ET, frozen; all 112
 20    holdout markets at 1 s), joined by condition id. A market missing from the file gets 3 s (the help-center
 21    figure) and is counted (delay_source "missing->3"). latency_s in the output is the total time from decision
 22    to fill, so each market's latency curve starts at its own delay (1, 1.25, ..., 11 s for a 1 s market).
 23    Polymarket US: no documented delay, 0 s.
 24  Fills (Amendment 2): the follower's recorded best ask (buy) / best bid (sell) in the last snapshot at or
 25  before the fill time (backward as-of, ts <= fill time). Skipped and counted, never filled from an older quote:
 26  the needed side empty in that snapshot ("no quote"); the fill time inside a break, or a break between that
 27  snapshot and the fill time ("break"); the fill time at or after the window end ("after window end"). Exits
 28  use the same rule; a round trip whose exit is skipped is skipped as a whole.
 29  Capacity (polymarket.com): the collector records the size at the best level. A taker fill at the best quote
 30  can take at most that level (deeper levels are worse prices), so capacity per trade = best-level size at the
 31  fill time, in contracts, and in dollars at the fill cost (P for a buy, 1 - P for a sell, in home terms).
 32  Polymarket US sizes are not recorded (the batch poll carries no sizes), so its capacity is NaN (not measurable).
 33  Costs: costs.fee on every fill: polymarket.com 0.05 x C x P x (1 - P) to 5 decimals; Polymarket US 0.0695 x C x
 34  P x (1 - P), banker's rounding to the cent, by fill timestamp.
 35  Sealed games (kickoff >= 2026-08-01) are refused unless holdout_run=True (the recorded books exist only from
 36  2026-10-03, so the one pre-registered run is a holdout run, made once with the lead test).
 37  """
```

Tests: none (constants/docstring)

## Lines 38 to 60

Imports and constants: the Amendment 2 setting (4 cent jump in 10 s, 3 cent entry gap, 1 cent exit gap, 60 s timeout, 10 contracts), the delay fallback (polymarket.com 3 s only for a market missing from the delay file; Polymarket US 0 s), the delay file path, the latency grid, the output labels.

```python
 38  from __future__ import annotations
 39
 40  from pathlib import Path
 41
 42  import numpy as np
 43  import pandas as pd
 44
 45  import costs                                                                                                      [MONEY]
 46  import leadlag
 47  import strategy
 48  import xcorr_lead as X
 49
 50  NS = 1_000_000_000                                                                                                [TIME]
 51  SEAL = pd.Timestamp("2026-08-01", tz="UTC")                                                                       [TIME]
 52  SETTING = dict(jump_cents=4.0, window_s=10, entry_gap_cents=3.0, exit_gap_cents=1.0, timeout_s=60, qty=10)        [TIME] [MONEY]
 53  VENUE_DELAY_S = {"polymarket": 3.0, "polymarket_us": 0.0}  # polymarket.com 3.0: ONLY for a market missing from
 54  #   holdout_seconds_delay.csv (0 of 112); every holdout market uses its own value (all 1 s, read 16:22 ET)        [TIME]
 55  SECONDS_DELAY_CSV = Path("data/live/holdout_seconds_delay.csv")                                                   [TIME]
 56  LATENCIES_S = (0.0, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)     # added to the venue delay                                [TIME]
 57  LABELS = {"polymarket": "paper only; polymarket.com not available to US residents",
 58            "polymarket_us": "US-executable version (Polymarket US); state eligibility as in HYPOTHESIS_v2.md"}
 59
 60
```

Tests: none (constants/docstring)

## Lines 61 to 83

load_seconds_delay: condition id -> seconds_delay from the frozen file (blanks left out). venue_delay: the market's delay or the counted 3 s fallback. _breaks_g: exclusions and outages as inclusive grid-second intervals.

```python
 61  def load_seconds_delay(path: Path = SECONDS_DELAY_CSV) -> dict:                                                    [TIME]
 62      """condition id -> seconds_delay (int) from the frozen file; blank values are left out (missing)."""           [TIME]
 63      d = pd.read_csv(path, dtype={"market_id": str})
 64      d = d[pd.to_numeric(d["seconds_delay"], errors="coerce").notna()]                                              [TIME]
 65      return dict(zip(d["market_id"], d["seconds_delay"].astype(int)))                                               [TIME]
 66
 67
 68  def venue_delay(venue: str, condition: str | None = None, delays: dict | None = None) -> tuple[float, str]:        [TIME]
 69      """(delay seconds, source). polymarket.com: the market's seconds_delay, else 3 s counted as missing."""        [TIME]
 70      if venue != "polymarket":
 71          return VENUE_DELAY_S[venue], "none documented"
 72      if delays is not None and condition in delays:                                                                 [TIME]
 73          return float(delays[condition]), "seconds_delay file"                                                      [TIME]
 74      return VENUE_DELAY_S["polymarket"], "missing->3"
 75
 76
 77  def _breaks_g(exclude, outages) -> list[tuple[int, int]]:                                                          [TIME]
 78      """Grid-second intervals (inclusive): exclusions as given, outages (ns, [a, b)) widened to whole seconds."""   [TIME]
 79      out = [(int(a), int(b)) for a, b in exclude]                                                                   [TIME]
 80      out += [(int(a) // NS, (int(b) - 1) // NS) for a, b in outages]                                                [TIME]
 81      return sorted(out)
 82
 83
```

Tests: `test_laggard.py::test_fill_scheduled_across_outage_is_skipped`, `test_laggard.py::test_mid_not_carried_across_outage`, `test_laggard.py::test_per_market_delay_from_file_and_missing_counted`, `test_laggard.py::test_capacity_is_best_level_size_at_fill (via evaluate_game)`, `test_laggard.py::test_mid_not_carried_past_window_end_and_fill_after_end_skipped (via evaluate_game)`, `test_laggard.py::test_no_lookahead_future_rows_do_not_change_past_decisions (via evaluate_game)`, `test_laggard.py::test_sealed_game_needs_holdout_flag_and_unknown_venue_raises (via evaluate_game)`

## Lines 84 to 116

_grid: Amendment 2 mid grid over the window, last state carried only to the window end, NaN inside every break and until this venue's first snapshot after it. book: the follower's snapshots with bid, ask and best-level sizes.

```python
 84  def _grid(ticks: pd.DataFrame, venue: str, lo_g: int, hi_g: int, breaks) -> pd.Series:                             [TIME]
 85      """Mid grid over [lo_g, hi_g]. mid_grid stops at the last snapshot; a quiet book keeps its state, so           [TIME] [MONEY]
 86      seconds after the last snapshot take that snapshot's mid (NaN if it was one-sided), up to the window end       [TIME] [MONEY]
 87      only. Inside a break the mid is NaN, and after it the mid stays NaN until this venue's first snapshot          [TIME] [MONEY]
 88      received after the break (no carry across a break). None before the first snapshot."""                         [TIME]
 89      snap = X.mid_snapshots(ticks, venue)                                                                           [MONEY]
 90      m = X.mid_grid(snap)                                                                                           [MONEY]
 91      g = m.reindex(range(lo_g, hi_g + 1))                                                                           [TIME]
 92      if len(m):
 93          g.loc[int(m.index[-1]) + 1:] = m.iloc[-1]
 94      labels = np.unique(snap.index.to_numpy() // NS) if len(snap) else np.array([], dtype="int64")                  [TIME]
 95      for a, b in breaks:                                                                                            [TIME]
 96          i = np.searchsorted(labels, b, side="right")      # first snapshot second after the break                  [TIME]
 97          resume = int(labels[i]) if i < len(labels) else hi_g + 1                                                   [TIME]
 98          g.loc[max(a, lo_g):min(resume - 1, hi_g)] = np.nan                                                         [TIME]
 99      return g
100
101
102  def book(ticks: pd.DataFrame, venue: str) -> pd.DataFrame:
103      """Follower snapshots: ts (ns, sorted), bid, ask, bid_size, ask_size; NaN = that side empty (or no size)."""   [TIME] [MONEY]
104      w = X._book_wide(ticks, venue)
105      out = pd.DataFrame({"ts": w.index.to_numpy(dtype="int64"), "bid": w["bid"].to_numpy(float),                    [TIME] [MONEY]
106                          "ask": w["ask"].to_numpy(float)})                                                          [MONEY]
107      b = ticks[(ticks["venue"] == venue) & ticks["kind"].isin(["bid", "ask"])]                                      [MONEY]
108      if "size" in b and len(b):                                                                                     [MONEY]
109          sz = b.pivot_table(index="ts", columns="kind", values="size", aggfunc="last").reindex(w.index)             [TIME] [MONEY]
110          for k in ("bid", "ask"):                                                                                   [MONEY]
111              out[f"{k}_size"] = sz[k].to_numpy(float) if k in sz else np.nan                                        [MONEY]
112      else:
113          out["bid_size"] = out["ask_size"] = np.nan                                                                 [MONEY]
114      return out
115
116
```

Tests: `test_laggard.py::test_fill_scheduled_across_outage_is_skipped`, `test_laggard.py::test_mid_not_carried_across_kickoff_cut`, `test_laggard.py::test_mid_not_carried_across_outage`, `test_laggard.py::test_mid_not_carried_past_window_end_and_fill_after_end_skipped`, `test_laggard.py::test_capacity_is_best_level_size_at_fill (via evaluate_game)`, `test_laggard.py::test_no_lookahead_future_rows_do_not_change_past_decisions (via evaluate_game)`, `test_laggard.py::test_per_market_delay_from_file_and_missing_counted (via evaluate_game)`, `test_laggard.py::test_sealed_game_needs_holdout_flag_and_unknown_venue_raises (via evaluate_game)`

## Lines 117 to 147

quote_at: the best ask or bid of the last snapshot at or before the fill time, skipped (never an older quote) when the side is empty, when the fill time is in a break or a break lies between the snapshot and the fill, or at/after the window end. signals: both grids, Kalshi jumps (leadlag.detect_jumps), entries and exits (strategy.signals).

```python
117  def quote_at(q: pd.DataFrame, t_ns: int, side: str, breaks_ns=(), end_ns: int | None = None) -> tuple:           [TIME]
118      """(price, size, skip) for best ask (side "ask") or bid of the last snapshot with ts <= t_ns.                [TIME] [MONEY]
119      skip is "" when usable. Never uses a snapshot from before a break that starts at or before t_ns, and never   [TIME]
120      fills at or after the window end."""                                                                         [TIME]
121      if end_ns is not None and t_ns >= end_ns:                                                                    [TIME]
122          return float("nan"), float("nan"), "after window end"                                                    [TIME]
123      i = int(np.searchsorted(q["ts"].to_numpy(), t_ns, side="right")) - 1                                         [TIME]
124      if i < 0:
125          return float("nan"), float("nan"), "no quote"
126      snap_ts = int(q["ts"].iloc[i])                                                                               [TIME]
127      for a, b in breaks_ns:                                                                                       [TIME]
128          if a <= t_ns and snap_ts < b:          # fill in the break, or the snapshot predates the break's end     [TIME]
129              return float("nan"), float("nan"), "break"                                                           [TIME]
130      px = float(q[side].iloc[i])                                                                                  [MONEY]
131      if np.isnan(px):                                                                                             [MONEY]
132          return px, float("nan"), "no quote"                                                                      [MONEY]
133      return px, float(q[f"{side}_size"].iloc[i]) if f"{side}_size" in q else float("nan"), ""                     [MONEY]
134
135
136  def signals(k_ticks: pd.DataFrame, o_ticks: pd.DataFrame, venue: str, lo_ns: int, hi_ns: int,                    [TIME]
137              exclude=(), setting: dict = SETTING, outages=()) -> pd.DataFrame:                                    [TIME]
138      """Entry/exit decisions from the two mid grids over [lo_ns, hi_ns). Uses grid labels <= g for label g."""    [TIME] [MONEY]
139      lo_g, hi_g = lo_ns // NS, hi_ns // NS - 1                                                                    [TIME]
140      br = _breaks_g(exclude, outages)                                                                             [TIME]
141      gk = _grid(k_ticks, "kalshi", lo_g, hi_g, br)                                                                [TIME]
142      go = _grid(o_ticks, venue, lo_g, hi_g, br)                                                                   [TIME]
143      jumps = leadlag.detect_jumps(gk, setting["jump_cents"], setting["window_s"])                                 [TIME] [MONEY]
144      return strategy.signals(gk, go, jumps, setting["entry_gap_cents"], setting["exit_gap_cents"],
145                              setting["timeout_s"], qty=setting["qty"])                                            [TIME] [MONEY]
146
147
```

Tests: `test_laggard.py::test_fill_scheduled_across_outage_is_skipped`, `test_laggard.py::test_capacity_is_best_level_size_at_fill (via evaluate_game)`, `test_laggard.py::test_mid_not_carried_across_outage (via evaluate_game)`, `test_laggard.py::test_mid_not_carried_past_window_end_and_fill_after_end_skipped (via evaluate_game)`, `test_laggard.py::test_no_lookahead_future_rows_do_not_change_past_decisions (via evaluate_game)`, `test_laggard.py::test_per_market_delay_from_file_and_missing_counted (via evaluate_game)`, `test_laggard.py::test_sealed_game_needs_holdout_flag_and_unknown_venue_raises (via evaluate_game)`

## Lines 148 to 174

fill_trades: entry and exit at decision + total latency; any skip skips the whole round trip; fees (costs.fee by fill timestamp) on both fills; P&L in home terms, net cents per contract; capacity = best-level size at the entry fill, in contracts and in dollars at the fill cost.

```python
148  def fill_trades(sig: pd.DataFrame, q: pd.DataFrame, venue: str, latency_s: float, breaks_ns=(),                    [TIME]
149                  end_ns: int | None = None) -> pd.DataFrame:                                                        [TIME]
150      """Round trips at one latency. latency_s = total decision-to-fill time (venue delay included)."""              [TIME]
151      lat = int(round(latency_s * NS))                                                                               [TIME]
152      rows = []
153      for s in sig.itertuples():
154          t_in, t_out = s.entry_decision_ns + lat, s.exit_decision_ns + lat                                          [TIME]
155          side_in, side_out = ("ask", "bid") if s.direction == 1 else ("bid", "ask")                                 [MONEY]
156          px_in, sz_in, sk_in = quote_at(q, t_in, side_in, breaks_ns, end_ns)                                        [TIME] [MONEY]
157          px_out, _, sk_out = quote_at(q, t_out, side_out, breaks_ns, end_ns)                                        [TIME] [MONEY]
158          row = {"latency_s": latency_s, "entry_g": s.entry_g, "direction": s.direction, "qty": s.qty,               [TIME] [MONEY]
159                 "exit_reason": s.exit_reason, "entry_fill_ns": t_in, "exit_fill_ns": t_out}                         [TIME]
160          if sk_in or sk_out:
161              rows.append({**row, "filled": False, "skip": f"{sk_in} at entry" if sk_in else f"{sk_out} at exit"})
162              continue
163          b_in, b_out = ("buy", "sell") if s.direction == 1 else ("sell", "buy")
164          f_in = costs.fee(px_in, s.qty, b_in, venue, ts=t_in)                                                       [TIME] [MONEY]
165          f_out = costs.fee(px_out, s.qty, b_out, venue, ts=t_out)                                                   [TIME] [MONEY]
166          pnl = s.direction * (px_out - px_in) * s.qty - f_in - f_out                                                [MONEY]
167          cost_in = px_in if s.direction == 1 else 1 - px_in                                                         [TIME] [MONEY]
168          rows.append({**row, "filled": True, "skip": "", "entry_px": px_in, "exit_px": px_out,                      [MONEY]
169                       "fee_entry": f_in, "fee_exit": f_out, "pnl_cents": round(pnl * 100, 6),                       [MONEY]
170                       "edge_cents_per_contract": round(pnl * 100 / s.qty, 6),                                       [MONEY]
171                       "cap_contracts": sz_in, "cap_dollars": sz_in * cost_in})                                      [TIME] [MONEY]
172      return pd.DataFrame(rows)
173
174
```

Tests: `test_laggard.py::test_capacity_is_best_level_size_at_fill (via evaluate_game)`, `test_laggard.py::test_fill_scheduled_across_outage_is_skipped (via evaluate_game)`, `test_laggard.py::test_mid_not_carried_across_outage (via evaluate_game)`, `test_laggard.py::test_mid_not_carried_past_window_end_and_fill_after_end_skipped (via evaluate_game)`, `test_laggard.py::test_no_lookahead_future_rows_do_not_change_past_decisions (via evaluate_game)`, `test_laggard.py::test_per_market_delay_from_file_and_missing_counted (via evaluate_game)`, `test_laggard.py::test_sealed_game_needs_holdout_flag_and_unknown_venue_raises (via evaluate_game)`

## Lines 175 to 199

evaluate_game: seal guard, the market's delay, signals once, fills at every latency (total = delay + added latency), tagged with the delay and its source.

```python
175  def evaluate_game(game_id: str, kickoff_utc, k_ticks: pd.DataFrame, o_ticks: pd.DataFrame, venue: str,              [TIME]
176                    lo_ns: int, hi_ns: int, exclude=(), latencies=LATENCIES_S, holdout_run: bool = False,             [TIME]
177                    setting: dict = SETTING, outages=(), condition: str | None = None,                                [TIME]
178                    delays: dict | None = None) -> pd.DataFrame:                                                      [TIME]
179      """All latencies for one game on one follower venue. One row per (latency, signal).                             [TIME]
180      exclude: grid-second intervals (inclusive); outages: ns intervals [a, b) of either venue (GAPS rows).           [TIME]
181      condition / delays: polymarket.com condition id and load_seconds_delay() (missing -> 3 s, counted)."""          [TIME]
182      if venue not in VENUE_DELAY_S:
183          raise ValueError(f"no follower venue {venue!r}")
184      k = pd.Timestamp(kickoff_utc)                                                                                   [TIME]
185      k = k.tz_localize("UTC") if k.tzinfo is None else k.tz_convert("UTC")
186      if k >= SEAL and not holdout_run:                                                                               [TIME]
187          raise ValueError(f"{game_id}: kickoff {k} is a holdout game; needs holdout_run=True (run once)")            [TIME]
188      delay, source = venue_delay(venue, condition, delays)                                                           [TIME]
189      sig = signals(k_ticks, o_ticks, venue, lo_ns, hi_ns, exclude, setting, outages)                                 [TIME]
190      q = book(o_ticks, venue)
191      breaks_ns = [(a * NS, (b + 1) * NS) for a, b in _breaks_g(exclude, outages)]                                    [TIME]
192      out = [fill_trades(sig, q, venue, delay + L, breaks_ns, hi_ns).assign(added_latency_s=L) for L in latencies]    [TIME]
193      out = [o for o in out if len(o)]
194      if not out:
195          return pd.DataFrame(columns=["game_id", "venue", "latency_s", "filled", "venue_delay_s", "delay_source"])   [TIME]
196      return pd.concat(out, ignore_index=True).assign(game_id=game_id, venue=venue, venue_delay_s=delay,              [TIME]
197                                                      delay_source=source)                                            [TIME]
198
199
```

Tests: `test_laggard.py::test_capacity_is_best_level_size_at_fill`, `test_laggard.py::test_fill_scheduled_across_outage_is_skipped`, `test_laggard.py::test_mid_not_carried_across_outage`, `test_laggard.py::test_mid_not_carried_past_window_end_and_fill_after_end_skipped`, `test_laggard.py::test_no_lookahead_future_rows_do_not_change_past_decisions`, `test_laggard.py::test_per_market_delay_from_file_and_missing_counted`, `test_laggard.py::test_sealed_game_needs_holdout_flag_and_unknown_venue_raises`

## Lines 200 to 231

capacity: per game and latency, median and total capacity (NaN where sizes are not recorded). latency_curve: per total latency, trade count, mean net edge per contract with a normal 95% CI, total P&L, skip counts by reason.

```python
200  def capacity(trades: pd.DataFrame) -> pd.DataFrame:
201      """Per game and latency: median capacity per filled trade and the total, contracts and dollars.                   [TIME]
202      NaN where sizes are not recorded (Polymarket US)."""                                                              [MONEY]
203      f = trades[trades["filled"].astype(bool)] if len(trades) else trades
204      if not len(f):
205          return pd.DataFrame(columns=["game_id", "venue", "latency_s", "n_trades", "cap_contracts_median",             [TIME] [MONEY]
206                                       "cap_dollars_median", "cap_contracts_total", "cap_dollars_total"])               [MONEY]
207      return (f.groupby(["game_id", "venue", "latency_s"])                                                              [TIME]
208               .agg(n_trades=("cap_contracts", "size"), cap_contracts_median=("cap_contracts", "median"),               [MONEY]
209                    cap_dollars_median=("cap_dollars", "median"),                                                       [MONEY]
210                    cap_contracts_total=("cap_contracts", lambda x: x.sum(min_count=1)),                                [MONEY]
211                    cap_dollars_total=("cap_dollars", lambda x: x.sum(min_count=1)))                                    [MONEY]
212               .reset_index())                                                                                          [TIME]
213
214
215  def latency_curve(trades: pd.DataFrame) -> pd.DataFrame:                                                              [TIME]
216      """out/latency_curve.csv contract: latency_s, n_trades, edge_cents_mean (net, per contract), 95% normal CI,       [TIME] [MONEY]
217      pnl_total (dollars). Also skip counts (no quote, break, after window end). Filled round trips only.               [TIME] [MONEY]
218      Group by latency_s = total decision-to-fill time, so mix markets only when they share a delay."""                 [TIME]
219      rows = []
220      for lat, d in trades.groupby("latency_s"):                                                                        [TIME]
221          f = d[d["filled"].astype(bool)]
222          e = f["edge_cents_per_contract"].to_numpy(float) if len(f) else np.array([])                                  [MONEY]
223          m = float(e.mean()) if len(e) else float("nan")
224          se = float(e.std(ddof=1) / np.sqrt(len(e))) if len(e) > 1 else float("nan")
225          rows.append({"latency_s": lat, "n_trades": len(e), "edge_cents_mean": m,                                      [TIME] [MONEY]
226                       "edge_ci_low": m - 1.96 * se, "edge_ci_high": m + 1.96 * se,                                     [MONEY]
227                       "pnl_total": float(f["pnl_cents"].sum()) / 100 if len(f) else 0.0,                               [MONEY]
228                       "n_skipped_no_quote": int((d["skip"].astype(str).str.startswith("no quote")).sum()),
229                       "n_skipped_break": int((d["skip"].astype(str).str.startswith("break")).sum()),                   [TIME]
230                       "n_skipped_after_end": int((d["skip"].astype(str).str.startswith("after window end")).sum())})   [TIME]
231      return pd.DataFrame(rows)
```

Tests: `test_laggard.py::test_capacity_is_best_level_size_at_fill`, `test_laggard.py::test_empty_side_at_fill_skips_instead_of_carrying_old_ask`, `test_laggard.py::test_fill_scheduled_across_outage_is_skipped`, `test_laggard.py::test_latency_curve_starts_at_market_delay_and_edge_dies_after_follower_moves`, `test_laggard.py::test_mid_not_carried_past_window_end_and_fill_after_end_skipped`

## Where a lookahead could hide, and why each is safe

1. **The decision grids (lines 84 to 99, 136 to 145).** Both mid grids take, at label g, the last snapshot received before the end of second g and only carry it forward, never across a break (lines 95 to 98) or past the window end (line 93 stops at hi_g). leadlag.detect_jumps compares p[g] with the min and max over the trailing labels g - 10..g only, and strategy.signals stamps a decision at (g + 1) s (strategy.decision_time_ns). The exit is chosen at the first later label whose gap is below 1 cent, using that label's data and stamped one second later. Tests: `test_no_lookahead_future_rows_do_not_change_past_decisions` (cutting all rows after the exit fill leaves the trade unchanged), `test_mid_not_carried_across_outage`, `test_mid_not_carried_across_kickoff_cut`, `test_mid_not_carried_past_window_end_and_fill_after_end_skipped`.

2. **The fill (lines 117 to 133, 154 to 157).** A fill reads the last snapshot with receipt time at or before decision + delay + latency (`searchsorted(..., side="right") - 1`), never a later one, and never one from before a break or the window end. The delay is the frozen per-market value (read once, 16:22 ET), not anything observed in the game. Tests: `test_fill_uses_quote_at_exactly_fill_time_never_after`, `test_fill_scheduled_across_outage_is_skipped`, `test_empty_side_at_fill_skips_instead_of_carrying_old_ask`.

3. **The window end it is given (line 192, `hi_ns`).** The runner passes the lead-test window end, which ends early at the start of a 60 s pinned run (holdout_mid.pinned_end). Fills at or after it are skipped ("after window end"), which uses up to 60 s of future data to drop trades near a decided game. See the holdout_mid walkthrough, point 1; flagged for your decision. With hi_ns = kickoff + 4.5 h fixed instead, nothing here would read the future.

## Points for your line-by-line review (choices to confirm)

- Lines 224 to 226: the latency curve CI is a normal CI over TRADES (trades within a game are not independent). docs/stats_plan.md says CIs are a block bootstrap by game (2,000 draws, seed 20261003). This file does not follow it. Options: switch to the game bootstrap (as run_strategy_b.boot_ci) before the run, or report the normal CI labelled as such. Not changed.
- Line 220: the curve groups by TOTAL latency; a polymarket.com market on the 3 s fallback would mix with 1 s markets at equal totals (0 of 112 holdout markets are missing, so not on this run).
- Line 93: after a venue's last snapshot its state is carried to the window end (a quiet book keeps its quotes); empty-book periods are not visible in these recordings (v2 Amendment 3 item 15a).
- Line 166: P&L is in home terms for both directions; a sell of P(home) on polymarket.com is in practice a buy of the away token. Fees use the home-terms price; P(1 - P) is symmetric, so the fee is the same.
- Line 171: capacity is taken at the ENTRY fill only; the exit's size is not checked.
- Lines 3 to 4: this file has run only on synthetic books (tests and the dry run); its first recorded-data run is the one holdout run.
