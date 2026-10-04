# holdout_mid.py walkthrough (Rule-7 review packet)

File: holdout_mid.py at c5bb4ee (branch t15-final), 379 lines. The v2 confirmatory runner (Amendments 2 to 4): instruments, window, machine choice and outages, pinned-run window end, book-wipe exclusion, qualification, per-game lag, placebo pairs, Holm decision, receipt diagnostic. Tags here are keyword-assisted (timestamps, windows, outages, kickoff, seal -> [TIME]; mid, price, pin levels -> [MONEY]) and checked by hand on the lines named below.

Tags at line end: **[TIME]** touches decision time, fill time, windows, outages or timestamps. **[MONEY]** touches price, fee, spread, threshold or P&L. Tests per block: every test that calls a function defined in the block.

## Lines 1 to 37

Module docstring: the per-game procedure and the decision, item by item (instruments, window, machines and outages, qualification, lag, placebo, decision, book-wipe exclusion, receipt diagnostic).

```python
  1  """Amendment 2 confirmatory runner (HYPOTHESIS_v2.md, committed 8a509ff): book-mid lead test on recorded games.
  2
  3  Per candidate game (data/live/holdout_candidates.csv) and per test (Kalshi vs polymarket.com, Kalshi vs
  4  Polymarket US):
  5    1. Instruments: Kalshi home-team market f"{event}-{HOME}", polymarket.com home token (collector_home_token in
  6       holdout_maps/polymarket_com_map.json), Polymarket US slug (holdout_maps/polymarket_us_map.json). One
  7       instrument per venue; the two books of a game are never merged. [Clarification needed: Amendment 2 does
  8       not name the instrument; home is the default here.]
  9    2. Window: kickoff - 90 min to the earlier of kickoff + 4.5 h or the first second from which either venue's
 10       defined mid stays >= 0.98 or <= 0.02 for 60 s (the window ends at the start of that run).
 11    3. Machines: Vultr if neither venue has an outage longer than 60 s inside the window, else the Mac if it has
 12       none, else excluded. One machine per game, never spliced. Outages: GAPS table rows for the venue (and
 13       "all"), plus the span before a feed's start (first heartbeat with a delivered message; the first recorded
 14       file only on a machine with no heartbeat log). For Kalshi every kalshi_ws gap is an outage, and so is any
 15       time the REST fallback was connected (REST polling degrades timing and biases Kalshi late).
 16    4. Qualifying: >= 50 mid changes (xcorr_lead.n_mid_changes) on each venue inside the window.
 17    5. Lag: xcorr_lead.game_lag_mid on the window.
 18    6. Placebo: Kalshi from game A vs the other venue from game B = the next qualifying game in kickoff order
 19       with kickoff within 30 min of A, recorded on the same machine as A; both series cut to A's window.
 20    7. Decision: xcorr_lead.decide, min_lead_s 1.0 (polymarket.com) or 1.5 (Polymarket US).
 21    8. Book-wipe exclusion (Amendment 3 draft): polymarket.com sports books cancel all resting limit orders at
 22       the official game start. Per game, on the test's other venue: the first second at or after kickoff -
 23       30 min whose book has neither side; excluded for BOTH venues from 2 min before it to 5 min after that
 24       book is two-sided again (to the window end if it never is). No such second -> excluded [T - 2 min,
 25       T + 20 min], T = the earlier of the ESPN kickoff and the polymarket.com market's gameStartTime (frozen
 26       map field game_start), for both venue tests. A both-sides-empty book writes no row in the 2026-10-03
 27       recordings (only a "book_empty" marker row would show it), so on those recordings the fallback applies
 28       to every game.
 29       Mid changes never span an excluded interval; the qualifying count and the lag use the rest.
 30    9. Diagnostic (Amendment 3, reported, NOT a decision rule): per machine and venue, median and p90 of receipt
 31       time minus the venue-side timestamp (recv_ns - src_ts_ns, seconds) over the rows of the instruments and
 32       windows of the games run on that machine. Only rows that carry a venue-side timestamp count: Kalshi
 33       websocket orderbook_delta rows (ts_ms) and polymarket.com book and trade rows; Polymarket US rows never
 34       carry one (reported as n_rows 0). Only the two timestamp columns are read.
 35  No prices are printed: outputs are counts, lags and decisions. Refuses games with kickoff >= 2026-08-01 unless
 36  holdout_run=True (the run is once, after Saturday's last game, when Divi says go).
 37  """
```

Tests: none (constants/docstring)

## Lines 38 to 72

Imports and constants: window kickoff - 90 min to + 4.5 h, pin level 0.98 / 0.02 for 60 s, 60 s outage limit, 50 mid changes, 30 min placebo slot, wipe search and fallback [T - 2, T + 20] min, 15 s REST heartbeat cover, the two tests (polymarket.com min lead 1.0 s, Polymarket US 1.5 s), and the Amendment 4 cutoff.

```python
 38  from __future__ import annotations
 39
 40  import glob
 41  import json
 42  import re
 43  from dataclasses import dataclass, field
 44  from pathlib import Path
 45
 46  import numpy as np
 47  import pandas as pd
 48  import pyarrow.dataset as ds
 49
 50  import xcorr_lead as X
 51
 52  NS = 1_000_000_000                                                                                             [TIME]
 53  SEAL = pd.Timestamp("2026-08-01", tz="UTC")                                                                    [TIME]
 54  PRE_S, POST_S = 90 * 60, int(4.5 * 3600)       # window: kickoff - 90 min (Amendment 3 draft) to + 4.5 h       [TIME]
 55  PIN_HI, PIN_LO, PIN_S = 0.98, 0.02, 60                                                                         [TIME] [MONEY]
 56  MAX_OUTAGE_S = 60
 57  MIN_CHANGES = 50                                                                                               [MONEY]
 58  PLACEBO_KICKOFF_S = 30 * 60
 59  WIPE_SEARCH_S = 30 * 60              # look for a full clear from kickoff - 30 min                             [TIME]
 60  WIPE_PRE_S, WIPE_POST_S = 2 * 60, 5 * 60                                                                       [TIME]
 61  WIPE_FALLBACK = (-2 * 60, 20 * 60)   # no clear found: [T - 2 min, T + 20 min], T = min(ESPN, gameStartTime)   [TIME]
 62  REST_HEARTBEAT_COVER_S = 15          # one connected kalshi_rest heartbeat covers this many seconds            [TIME]
 63  HB_FEED = {"kalshi": "kalshi_ws", "polymarket": "polymarket", "polymarket_us": "polymarket_us"}
 64  TESTS = {"polymarket.com": ("polymarket", 1.0), "Polymarket US": ("polymarket_us", 1.5)}
 65  KICKOFF_CUTOFF = pd.Timestamp("2026-10-03 20:00", tz="America/New_York")   # v2 Amendment 4 (f6aa3b5)          [TIME]
 66
 67
 68  def amendment4(cands: pd.DataFrame) -> pd.DataFrame:
 69      """v2 Amendment 4: keep only candidates with ESPN kickoff at or before 20:00 ET Oct 3 (106 of 112)."""     [TIME]
 70      return cands[pd.to_datetime(cands["kickoff_utc"], utc=True) <= KICKOFF_CUTOFF].copy()                      [TIME]
 71
 72
```

Tests: `test_holdout_mid.py::test_amendment4_cutoff`, `test_holdout_mid.py::test_run_all_applies_holm (via run_all)`

## Lines 73 to 108

Machine: one recorder root (Vultr or Mac) with its GAPS table and heartbeat log; its recorded files per venue; a feed's start = first heartbeat with a delivered message (first file only if no heartbeat log).

```python
 73  @dataclass
 74  class Machine:
 75      name: str                      # "vultr" or "mac"
 76      root: Path                     # contains data/live/<venue>/<YYYYMMDD>/<unix>_<pid>.parquet
 77      gaps_md: Path                                                                                         [TIME]
 78      heartbeat_dir: Path | None = None                                                                     [TIME]
 79      year: int = 2026               # GAPS tables carry no year
 80      _gaps: pd.DataFrame | None = field(default=None, repr=False)                                          [TIME]
 81      _start: dict = field(default_factory=dict, repr=False)                                                [TIME]
 82
 83      def files(self, venue: str) -> list[str]:
 84          return sorted(glob.glob(str(self.root / "data" / "live" / venue / "*" / "*.parquet")))
 85
 86      def feed_start_ns(self, venue: str) -> int | None:                                                    [TIME]
 87          """First heartbeat of the feed with a delivered message (last_ok set). Only a machine without a   [TIME]
 88          heartbeat log falls back to the first recorded file's unix-second prefix. No rows are read."""    [TIME]
 89          if venue not in self._start:                                                                      [TIME]
 90              hb = self.heartbeat_first_ok(HB_FEED[venue]) if self.heartbeat_dir else None                  [TIME]
 91              if hb is not None or self.heartbeat_dir:                                                      [TIME]
 92                  self._start[venue] = hb                                                                   [TIME]
 93              else:
 94                  fs = [int(Path(f).name.split("_")[0]) for f in self.files(venue)]
 95                  self._start[venue] = min(fs) * NS if fs else None                                         [TIME]
 96          return self._start[venue]                                                                         [TIME]
 97
 98      def heartbeat_first_ok(self, feed: str) -> int | None:                                                [TIME]
 99          for f in sorted(glob.glob(str(self.heartbeat_dir / "*.jsonl"))):                                  [TIME]
100              for line in open(f):
101                  try:
102                      r = json.loads(line)
103                  except ValueError:
104                      continue
105                  if r.get("venue") == feed and r.get("last_ok_utc"):                                       [TIME]
106                      return pd.Timestamp(r["last_ok_utc"]).value                                           [TIME]
107          return None
108
```

Tests: `test_holdout_mid.py::test_feed_start_prefers_heartbeat`, `test_holdout_mid.py::test_receipt_diagnostic`

## Lines 109 to 134

Machine.rows: one market's rows in a time range (no prices printed); receipt_lags_s: receipt minus venue timestamp (diagnostic only, two timestamp columns read); gaps: the parsed outage table.

```python
109      def rows(self, venue: str, market: str, lo_ns: int, hi_ns: int) -> pd.DataFrame:                         [TIME]
110          fs = self.files(venue)
111          if not fs:
112              return pd.DataFrame(columns=["ts", "venue", "market_id", "kind", "price"])                       [TIME] [MONEY]
113          d = ds.dataset(fs, format="parquet")
114          f = (ds.field("market_id") == market) & (ds.field("ts") >= lo_ns) & (ds.field("ts") <= hi_ns)        [TIME]
115          return d.to_table(filter=f, columns=["ts", "venue", "market_id", "kind", "price"]).to_pandas()       [TIME] [MONEY]
116
117      def receipt_lags_s(self, venue: str, market: str, lo_ns: int, hi_ns: int) -> np.ndarray:                 [TIME]
118          """recv_ns - src_ts_ns in seconds for rows with a venue-side timestamp (diagnostic only; reads ts,   [TIME]
119          market_id and the two timestamp columns, never prices)."""                                           [MONEY]
120          fs = self.files(venue)
121          if not fs:
122              return np.array([])
123          d = ds.dataset(fs, format="parquet")
124          if "src_ts_ns" not in d.schema.names or "recv_ns" not in d.schema.names:                             [TIME]
125              return np.array([])
126          f = (ds.field("market_id") == market) & (ds.field("ts") >= lo_ns) & (ds.field("ts") <= hi_ns)        [TIME]
127          t = d.to_table(filter=f, columns=["recv_ns", "src_ts_ns"]).to_pandas().dropna()                      [TIME]
128          return (t["recv_ns"].astype("int64") - t["src_ts_ns"].astype("int64")).to_numpy() / NS               [TIME]
129
130      def gaps(self) -> pd.DataFrame:                                                                          [TIME]
131          if self._gaps is None:                                                                               [TIME]
132              self._gaps = parse_gaps(self.gaps_md, self.rest_intervals(), self.year)                          [TIME]
133          return self._gaps                                                                                    [TIME]
134
```

Tests: **none found**

## Lines 135 to 158

REST-fallback spans from the heartbeat log (each connected heartbeat covers 15 s; counted as Kalshi outage), the GAPS row pattern and the ET-to-UTC parse of GAPS times.

```python
135      def rest_intervals(self) -> list[tuple[int, int]]:
136          if not self.heartbeat_dir:                                                                                                   [TIME]
137              return []
138          out = []
139          for f in sorted(glob.glob(str(self.heartbeat_dir / "*.jsonl"))):                                                             [TIME]
140              for line in open(f):
141                  try:
142                      r = json.loads(line)
143                  except ValueError:
144                      continue
145                  if r.get("venue") == "kalshi_rest" and r.get("connected"):
146                      t = pd.Timestamp(r["recv_utc"]).value                                                                            [TIME]
147                      out.append((t, t + REST_HEARTBEAT_COVER_S * NS))                                                                 [TIME]
148          return out
149
150
151  ROW = re.compile(r"^\|\s*(\w{3} \w{3} \d{2} \d{2}:\d{2}:\d{2})\s*\|\s*(\w{3} \w{3} \d{2} \d{2}:\d{2}:\d{2})\s*\|\s*([\w.]+)\s*\|")
152
153
154  def _et(s: str, year: int = 2026) -> int:                                                                                            [TIME]
155      """'Sat Oct 03 09:19:06' (ET, as written in the GAPS tables) -> UTC ns."""
156      return pd.to_datetime(f"{s} {year}", format="%a %b %d %H:%M:%S %Y").tz_localize("America/New_York").value
157
158
```

Tests: `test_holdout_mid.py::test_seal_guard_and_rest_cover (via parse_gaps)`

## Lines 159 to 190

parse_gaps: GAPS rows to (venue, start, end); every kalshi_ws gap and every REST-connected span is a Kalshi outage; kalshi_rest gaps alone are not; 'all' rows (restarts) apply to every feed. _merge: union of intervals.

```python
159  def parse_gaps(md: Path, rest: list[tuple[int, int]], year: int = 2026) -> pd.DataFrame:                         [TIME]
160      """GAPS table rows -> (venue, start_ns, end_ns). Times are ET (GAPS rows carry no year). For the lead test   [TIME]
161      Kalshi is out whenever the websocket is: every kalshi_ws gap is a Kalshi outage, and every span where the    [TIME]
162      REST fallback was connected (heartbeat) is one too. Reported as venue "kalshi"."""                           [TIME]
163      rows = []
164      if md and Path(md).exists():
165          for line in open(md):
166              m = ROW.match(line)
167              if not m:
168                  continue
169              a, b, v = _et(m.group(1), year), _et(m.group(2), year), m.group(3)                                   [TIME]
170              if v == "kalshi_ws":
171                  rows.append(("kalshi", a, b))
172              elif v == "kalshi_rest":
173                  continue          # REST being down is not an outage while the websocket delivers                [TIME]
174              else:
175                  rows.append((v, a, b))
176      rows += [("kalshi", lo, hi) for lo, hi in _merge(rest)]                                                      [TIME]
177      return pd.DataFrame(rows, columns=["venue", "start_ns", "end_ns"])                                           [TIME]
178
179
180  def _merge(iv: list[tuple[int, int]]) -> list[tuple[int, int]]:
181      """Union of intervals (consecutive REST heartbeats become one span)."""                                      [TIME]
182      out = []
183      for lo, hi in sorted(iv):                                                                                    [TIME]
184          if out and lo <= out[-1][1]:                                                                             [TIME]
185              out[-1] = (out[-1][0], max(out[-1][1], hi))                                                          [TIME]
186          else:
187              out.append((lo, hi))                                                                                 [TIME]
188      return out
189
190
```

Tests: `test_holdout_mid.py::test_seal_guard_and_rest_cover`

## Lines 191 to 220

outage_reason: a machine is unusable for a game if either feed started late, never recorded, or has one logged gap overlapping the window by more than 60 s. pinned_end: first second from which either venue's mid stays at or beyond 0.98 / 0.02 for 60 s.

```python
191  def outage_reason(m: Machine, venues: tuple[str, str], lo: int, hi: int) -> str:                               [TIME]
192      """Empty string if no outage > 60 s inside [lo, hi] on either venue, else the reason."""                   [TIME]
193      g = m.gaps()                                                                                               [TIME]
194      for v in venues:
195          st = m.feed_start_ns(v)                                                                                [TIME]
196          if st is None:
197              return f"{m.name}: {v} never recorded"
198          if st - lo > MAX_OUTAGE_S * NS:                                                                        [TIME]
199              return f"{m.name}: {v} not recording for {(min(st, hi) - lo) / NS:.0f} s of the window"            [TIME]
200          for r in g[g["venue"].isin([v, "all"])].itertuples():
201              ov = min(r.end_ns, hi) - max(r.start_ns, lo)                                                       [TIME]
202              if ov > MAX_OUTAGE_S * NS:                                                                         [TIME]
203                  return f"{m.name}: {v} outage {ov / NS:.0f} s in window"                                       [TIME]
204      return ""
205
206
207  def pinned_end(gx: pd.Series, gy: pd.Series, lo_g: int, hi_g: int) -> int:                                     [TIME]
208      """First grid second from which either defined mid stays >= 0.98 or <= 0.02 for 60 s; else hi_g."""        [TIME] [MONEY]
209      idx = np.arange(lo_g, hi_g + 1)                                                                            [TIME]
210      best = hi_g                                                                                                [TIME]
211      for g in (gx, gy):
212          s = g.reindex(idx)
213          pin = ((s >= PIN_HI) | (s <= PIN_LO)).astype(int).to_numpy()                                           [MONEY]
214          run = np.convolve(pin, np.ones(PIN_S, dtype=int), mode="valid")       # run[i] = pins in [i, i + 60)   [TIME]
215          hits = np.flatnonzero(run == PIN_S)                                                                    [TIME]
216          if len(hits):
217              best = min(best, int(idx[hits[0]]))
218      return best
219
220
```

Tests: `test_holdout_mid.py::test_run_all_applies_holm (via run_all)`, `test_holdout_mid.py::test_runner_end_to_end (via run_test)`, `test_holdout_mid.py::test_seal_guard_and_rest_cover (via run_test)`

## Lines 221 to 248

wipe_exclusion: first full book clear on the other venue from kickoff - 30 min (never visible in these recordings), else the fallback [T - 2 min, T + 20 min], T = min(ESPN kickoff, gameStartTime). instruments: Kalshi home market, polymarket.com home token, Polymarket US slug, gameStartTime.

```python
221  def wipe_exclusion(to: pd.DataFrame, other: str, ko_ns: int, end_g: int,                                       [TIME]
222                     game_start_ns: int | None = None) -> tuple[tuple[int, int], str]:                           [TIME]
223      """Excluded grid seconds (lo_g, hi_g inclusive) and the source ("clear" or "fallback").                    [TIME]
224      ko_ns = ESPN kickoff (clear search starts at ko - 30 min); the fallback is anchored at                     [TIME]
225      T = min(ko_ns, game_start_ns) when the polymarket.com gameStartTime is known."""                           [TIME]
226      ko_g = ko_ns // NS                                                                                         [TIME]
227      t_g = min(ko_ns, game_start_ns) // NS if game_start_ns is not None else ko_g                               [TIME]
228      sides = X.sides_snapshots(to, other)
229      if len(sides):
230          g = pd.Series(sides.to_numpy(), index=sides.index.to_numpy() // NS).groupby(level=0).last()            [TIME]
231          empty = g[(g.index >= ko_g - WIPE_SEARCH_S) & (g == 0)]                                                [TIME]
232          if len(empty):
233              c = int(empty.index[0])
234              back = g[(g.index > c) & (g == 2)]
235              hi = int(back.index[0]) + WIPE_POST_S if len(back) else end_g                                      [TIME]
236              return (c - WIPE_PRE_S, min(hi, end_g)), "clear"                                                   [TIME]
237      return (t_g + WIPE_FALLBACK[0], t_g + WIPE_FALLBACK[1]), "fallback"                                        [TIME]
238
239
240  def instruments(c, maps: dict) -> dict:
241      home = c.game_id.split("_")[-1].upper()
242      pc = maps["polymarket_com"].get(c.kalshi_ticker)
243      pu = [s for s, r in maps["polymarket_us"].items() if r.get("kalshi_event") == c.kalshi_ticker]
244      gs = pc.get("game_start") if pc else None       # polymarket.com gameStartTime, used by both venue tests   [TIME]
245      return {"kalshi": f"{c.kalshi_ticker}-{home}", "polymarket": pc["collector_home_token"] if pc else None,
246              "polymarket_us": pu[0] if pu else None, "game_start_ns": pd.Timestamp(gs).value if gs else None}   [TIME]
247
248
```

Tests: `test_book_wipe.py::test_fallback_when_no_clear_recorded`, `test_book_wipe.py::test_fifteen_minute_copy_leaks_under_plus10_not_plus20`, `test_book_wipe.py::test_requote_copying_kalshi_is_not_a_lead_after_exclusion`, `test_book_wipe.py::test_wipe_found_and_mid_undefined_while_empty`, `test_holdout_mid.py::test_receipt_diagnostic (via receipt_diagnostic)`, `test_holdout_mid.py::test_run_all_applies_holm (via run_all)`, `test_holdout_mid.py::test_runner_end_to_end (via run_test)`, `test_holdout_mid.py::test_seal_guard_and_rest_cover (via run_test)`

## Lines 249 to 281

game_on_machine: rows in the window, mid grids, window end at the pin, outage check, exclusion, the 50-change qualification on each venue outside the exclusion, then the per-game lag (xcorr_lead.game_lag_mid).

```python
249  def game_on_machine(m: Machine, c, inst: dict, other: str) -> dict:
250      ko = pd.Timestamp(c.kickoff_utc).value                                                                 [TIME]
251      lo, hi = ko - PRE_S * NS, ko + POST_S * NS                                                             [TIME]
252      tk = m.rows("kalshi", inst["kalshi"], lo, hi)                                                          [TIME]
253      to = m.rows(other, inst[other], lo, hi)                                                                [TIME]
254      out = {"machine": m.name, "kalshi_rows": len(tk), "other_rows": len(to)}
255      if tk.empty or to.empty:
256          out["reason"] = f"{m.name}: no rows ({'kalshi' if tk.empty else other})"
257          return out
258      gx, gy = X.mid_grid(X.mid_snapshots(tk, "kalshi")), X.mid_grid(X.mid_snapshots(to, other))             [MONEY]
259      end_g = pinned_end(gx, gy, lo // NS, hi // NS - 1)                                                     [TIME]
260      end = (end_g + 1) * NS if end_g < hi // NS - 1 else hi                                                 [TIME]
261      out.update(window_start_ns=lo, window_end_ns=end)                                                      [TIME]
262      r = outage_reason(m, ("kalshi", other), lo, end)                                                       [TIME]
263      if r:
264          out["reason"] = r
265          return out
266      lo_g, hi_g = lo // NS, end // NS - 1                                                                   [TIME]
267      ex, src = wipe_exclusion(to, other, ko, hi_g, inst.get("game_start_ns"))                               [TIME]
268      exc = [ex]
269      out.update(excl_lo_g=ex[0], excl_hi_g=ex[1], excl_source=src,                                          [TIME]
270                 excluded_s=max(0, min(ex[1], hi_g) - max(ex[0], lo_g) + 1))                                 [TIME]
271      nx, ny = X.n_mid_changes(gx.loc[lo_g:hi_g], exc), X.n_mid_changes(gy.loc[lo_g:hi_g], exc)              [TIME] [MONEY]
272      out.update(n_changes_kalshi=nx, n_changes_other=ny)
273      if nx < MIN_CHANGES or ny < MIN_CHANGES:                                                               [MONEY]
274          out["reason"] = f"not qualifying ({nx} / {ny} mid changes, need {MIN_CHANGES})"                    [MONEY]
275          out["qualifying"] = False
276          return out
277      tkw, tow = tk[(tk.ts >= lo) & (tk.ts < end)], to[(to.ts >= lo) & (to.ts < end)]                        [TIME]
278      out.update(qualifying=True, reason="", lag_s=X.game_lag_mid(tkw, "kalshi", tow, other, exclude=exc))   [MONEY]
279      return out
280
281
```

Tests: `test_holdout_mid.py::test_run_all_applies_holm (via run_all)`, `test_holdout_mid.py::test_runner_end_to_end (via run_test)`, `test_holdout_mid.py::test_seal_guard_and_rest_cover (via run_test)`

## Lines 282 to 303

run_test, per game: seal guard; no mapped instrument -> listed; machines tried in preference order (Vultr first); a machine with an outage is skipped, a non-qualifying result ends the search; otherwise excluded with every machine's reason.

```python
282  def run_test(cands: pd.DataFrame, maps: dict, machines: list[Machine], test: str,
283               holdout_run: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, dict]:                                    [TIME]
284      other, min_lead = TESTS[test]                                                                                      [MONEY]
285      if not holdout_run and (pd.to_datetime(cands["kickoff_utc"], utc=True) >= SEAL).any():                             [TIME]
286          raise ValueError("holdout games (kickoff >= 2026-08-01) need holdout_run=True; run once, when Divi says go")   [TIME]
287      per = []
288      for c in cands.sort_values("kickoff_utc").itertuples():                                                            [TIME]
289          inst = instruments(c, maps)
290          row = {"game_id": c.game_id, "kickoff_utc": c.kickoff_utc, "test": test}                                       [TIME]
291          if inst[other] is None:
292              per.append({**row, "machine": "", "reason": f"no {other} instrument mapped"})
293              continue
294          reasons = []
295          for m in machines:                    # order = preference (Vultr first)
296              r = game_on_machine(m, c, inst, other)
297              if not r.get("reason") or r.get("qualifying") is False:
298                  per.append({**row, **r})
299                  break
300              reasons.append(r["reason"])
301          else:
302              per.append({**row, "machine": "", "reason": "excluded: " + "; ".join(reasons)})
303      per = pd.DataFrame(per)
```

Tests: `test_holdout_mid.py::test_runner_end_to_end`, `test_holdout_mid.py::test_seal_guard_and_rest_cover`, `test_holdout_mid.py::test_run_all_applies_holm (via run_all)`

## Lines 304 to 329

run_test, placebo and decision: each qualifying game A paired with the next qualifying game B on the same machine with kickoff within 30 min; Kalshi from A against the other venue from B over A's window and A's exclusion; xcorr_lead.decide.

```python
304      q = per[per.get("qualifying", pd.Series(False, index=per.index)).fillna(False).astype(bool)].copy()
305      q["ko"] = pd.to_datetime(q["kickoff_utc"], utc=True)                                                                 [TIME]
306      q = q.sort_values("ko").reset_index(drop=True)
307      by = {m.name: m for m in machines}
308      pl = []
309      for i, a in q.iterrows():
310          nxt = q[(q.index > i) & (q["machine"] == a["machine"]) &
311                  ((q["ko"] - a["ko"]).dt.total_seconds() <= PLACEBO_KICKOFF_S)]
312          if nxt.empty:
313              continue
314          b = nxt.iloc[0]
315          m = by[a["machine"]]
316          ca = cands[cands.game_id == a["game_id"]].iloc[0]
317          cb = cands[cands.game_id == b["game_id"]].iloc[0]
318          lo, end = int(a["window_start_ns"]), int(a["window_end_ns"])                                                     [TIME]
319          tk = m.rows("kalshi", instruments(ca, maps)["kalshi"], lo, end - 1)                                              [TIME]
320          to = m.rows(other, instruments(cb, maps)[other], lo, end - 1)                                                    [TIME]
321          exc = [(int(a["excl_lo_g"]), int(a["excl_hi_g"]))]      # A's window, A's exclusion                              [TIME]
322          pl.append({"game_a": a["game_id"], "game_b": b["game_id"], "machine": a["machine"],
323                     "lag_s": X.game_lag_mid(tk, "kalshi", to, other, exclude=exc) if len(tk) and len(to)                  [MONEY]
324                     else float("nan")})
325      pl = pd.DataFrame(pl, columns=["game_a", "game_b", "machine", "lag_s"])                                              [MONEY]
326      dec = X.decide(q["lag_s"].to_numpy(float), pl["lag_s"].to_numpy(float), 0.0, "kalshi", other, min_lead_s=min_lead)   [MONEY]
327      return per, pl, dec
328
329
```

Tests: none (constants/docstring)

## Lines 330 to 349

load_maps and run_all: on the holdout run apply Amendment 4 first, run both tests, then Holm across them (xcorr_lead.decide_holm), plus the receipt diagnostic.

```python
330  def load_maps(d: Path) -> dict:
331      return {"polymarket_com": json.loads((d / "polymarket_com_map.json").read_text()),
332              "polymarket_us": json.loads((d / "polymarket_us_map.json").read_text())}
333
334
335  def run_all(cands: pd.DataFrame, maps: dict, machines: list[Machine], holdout_run: bool = False) -> dict:             [TIME]
336      """Both venue tests, then Holm across them (Amendment 3 draft). Returns per-test tables and final decisions."""
337      if holdout_run:                                                                                                   [TIME]
338          cands = amendment4(cands)
339      res = {t: run_test(cands, maps, machines, t, holdout_run) for t in TESTS}                                         [TIME]
340      inputs = {}
341      for t, (per, pl, _dec) in res.items():
342          q = per[per.get("qualifying", pd.Series(False, index=per.index)).fillna(False).astype(bool)]
343          inputs[t] = (q["lag_s"].to_numpy(float), pl["lag_s"].to_numpy(float), TESTS[t][0], TESTS[t][1])               [MONEY]
344      final = X.decide_holm(inputs)
345      out = {t: {"per_game": res[t][0], "placebo": res[t][1], "decision": final[t]} for t in TESTS}
346      out["receipt_diagnostic"] = receipt_diagnostic(cands, maps, machines, {t: res[t][0] for t in TESTS})
347      return out
348
349
```

Tests: `test_holdout_mid.py::test_run_all_applies_holm`

## Lines 350 to 379

receipt_diagnostic: per machine and venue, median and p90 of receipt minus venue timestamp over each game's instruments and window (reported only).

```python
350  def receipt_diagnostic(cands: pd.DataFrame, maps: dict, machines: list[Machine], per: dict) -> pd.DataFrame:
351      """Amendment 3 diagnostic, reported only (no rule uses it): median and p90 of receipt time minus the
352      venue-side timestamp, per machine and venue, over each game's instruments and window on the machine the    [TIME]
353      game was run on (games with a window on a machine, qualifying or not)."""                                  [TIME]
354      by = {m.name: m for m in machines}
355      cand = cands.set_index("game_id")
356      lags: dict[tuple[str, str], list] = {}
357      seen = set()
358      for t, p in per.items():
359          if "window_start_ns" not in p:                                                                         [TIME]
360              continue
361          other = TESTS[t][0]
362          for r in p.dropna(subset=["window_start_ns"]).itertuples():                                            [TIME]
363              if not r.machine:
364                  continue
365              inst = instruments(cand.loc[[r.game_id]].reset_index().iloc[0], maps)
366              for v in ("kalshi", other):
367                  key = (r.machine, v, inst[v], int(r.window_start_ns))                                          [TIME]
368                  if inst[v] is None or key in seen:
369                      continue
370                  seen.add(key)
371                  lags.setdefault((r.machine, v), []).append(
372                      by[r.machine].receipt_lags_s(v, inst[v], int(r.window_start_ns), int(r.window_end_ns)))    [TIME]
373      rows = []
374      for (mach, v), xs in sorted(lags.items()):
375          x = np.concatenate(xs) if xs else np.array([])
376          rows.append({"machine": mach, "venue": v, "n_rows": len(x),
377                       "median_s": float(np.median(x)) if len(x) else float("nan"),
378                       "p90_s": float(np.quantile(x, 0.9)) if len(x) else float("nan")})
379      return pd.DataFrame(rows, columns=["machine", "venue", "n_rows", "median_s", "p90_s"])
```

Tests: `test_holdout_mid.py::test_receipt_diagnostic`, `test_holdout_mid.py::test_run_all_applies_holm (via run_all)`

## Where a lookahead could hide, and why each is safe

1. **Window end at a pinned run (lines 207 to 218, used at 259 to 261).** The window ends at the START of the first 60 s run in which either mid stays at or beyond 0.98 / 0.02; knowing that a run starting at s lasts 60 s takes the next 60 s of data. For the lead test this is a measurement window over a finished game, symmetric for both venues and for the placebo (which uses A's window), so it cannot favour a lead. **It also bounds the laggard evaluator** (scripts/final_test_run.py passes window_end_ns): laggard fills at or after the pin start are skipped as "after window end", which uses up to 60 s of future data to drop trades near a decided game. Flagged for your decision (see review notes). Test: `test_runner_end_to_end` (pinned game).

2. **Machine choice and exclusions (lines 191 to 204, 282 to 302).** A game's machine is chosen and games are excluded from logged outages and feed start times only (GAPS tables, heartbeats), never from prices or lags; the same rule applies to every game and to the placebo, which reuses A's machine. Qualification (50 mid changes, line 271) counts changes over the whole window, a measure of activity, not of who leads, applied identically to both venues. Tests: `test_runner_end_to_end`, `test_seal_guard_and_rest_cover`, `test_feed_start_prefers_heartbeat`.

3. **The book-wipe exclusion (lines 221 to 237).** The clear search reads the other venue's book after kickoff - 30 min, and on these recordings the fallback is always used: a fixed interval from the scheduled kickoff (ESPN, or the earlier polymarket.com gameStartTime from the frozen map), which uses no recorded data at all. Tests: `test_book_wipe.py`.

## Points for your line-by-line review (choices to confirm)

- Lines 259 to 261 + scripts/final_test_run.py: the laggard inherits the pin-based window end (point 1). Options: keep it (pre-registered window, disclosed), or cut the laggard at the fixed kickoff + 4.5 h instead. Not changed.
- Line 241: the Kalshi home code is the last part of game_id, upper-cased. A hyphenated code (Miami (OH) "M-OH") would break this; the 5:40 PM audit found none among the 112 candidates and all 112 home instruments exist.
- Line 297: a game that fails qualification on Vultr is NOT retried on the Mac (only outages and missing rows move a game to the next machine), so machine choice never depends on the result.
- Lines 310 to 311: the placebo partner must be on the SAME machine; a qualifying game with no same-machine partner within 30 min gets no placebo pair.
- Line 326: the per-test decision here uses alpha 0.05; run_all replaces it with the Holm decision (line 344). Only run_all's result is reported.
- Line 338: Amendment 4 is applied only when holdout_run=True, so tests and training paths see all candidates.
