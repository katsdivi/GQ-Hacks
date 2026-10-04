# strategy_a.py walkthrough (Rule-7 review packet)

File: strategy_a.py at c510374 (branch t13-strategy-a), 316 lines. Strategy A has NOT been run on any data; only the fake-game tests below.

Tags at line end: **[TIME]** touches decision time, fill time, the 5-min skip, or settlement. **[MONEY]** touches price, fee, cap or P&L. Tests are in tests/test_strategy_a.py unless named otherwise.

## Lines 1 to 30

Module docstring: the pre-registered rule in words (decision at kickoff - 5 min, own-market 3 s median, staleness on both markets, theta, fill rule, cap, settlement, costs, placebo, preseason). No code runs here; it is the spec the code below must match.

```python
  1  """Strategy A (HYPOTHESIS_v3.md, with Amendment 1 committed 9507d6a): Kalshi favorite-longshot, hold to settlement.
  2
  3  Rule-7 file (same review rule as strategy.py): written on a branch, reviewed line by line by Divi before main.
  4
  5  Per game and theta:
  6    t = ESPN kickoff - 5 min.                                                                                                           [TIME]
  7    Decision (backward as-of only, rows with ts <= t): each team's OWN market price = trailing 3 s median of                            [TIME]
  8      that market's trade prices, last value at or before t (align.trade_median_events). Favorite = higher
  9      own-market price, decided only when BOTH markets are fresh: skip the game if either team's market has no                          [TIME]
 10      trade in (t - 10 min, t] (staleness, v3 Amendment 3 draft section 6, both markets). Enter iff favorite                            [TIME]
 11      price >= theta.
 12    Fill (Amendment 1 section 4): first trade on the favorite's own market at or after t + 1.0 s, plus 1 cent                           [TIME]
 13      half-spread, capped at 1 - tick of that market (v3 Amendment 3 draft: 1.00 is not a valid Kalshi price;                           [MONEY]
 14      tick = the step of the market's top price range in Kalshi's metadata, 0.01 if not known). No such trade                           [MONEY]
 15      within 5 min after t -> skip, reason "no post-decision trade".                                                                    [TIME]
 16    Settlement: $1 per contract if the favorite wins, $0 if it loses, $0.5 on a tie (docs/strategy_a_rules.md).                         [TIME]
 17      load_games applies Kalshi's recorded scalar settlement where the games file has no result                                         [TIME]
 18      (apply_scalar_settlements, from data/raw/kalshi_market_meta.csv); the games file itself is never edited.                          [TIME]
 19    Costs (v3 line 20): Webull $0.02 per contract per fill, entry only (primary); Kalshi direct                                         [MONEY]
 20      0.07 x C x P x (1 - P) rounded up to the cent per order (comparison). Settlement fee 0.                                           [MONEY]
 21    Placebo: buy the underdog's own market under the same decision and the same fill rule.
 22    Preseason robustness (v3 Amendment 3 draft): NFL games with ESPN kickoff (ET date) before that season's
 23      regular-season opener (2025: Thu Sep 4, 2025; 2026: Wed Sep 9, 2026) are flagged "preseason" (49 in training, incl. the Hall of
 24      Fame game); they stay in the primary run, and summarize_side_by_side reports the run without them next to
 25      it. Theta selection uses the primary run only.
 26
 27  Input trades follow the tick contract (price = P(home wins)); the away team's own-market price is 1 - price
 28  on rows of the away market. No prices are printed. Sealed games (kickoff >= 2026-08-01) are refused unless
 29  final_test=True.
 30  """
```

Tests: none (docstring)

## Lines 31 to 61

Imports and the fixed constants: seal date, theta grid (0.70/0.80/0.90), 10 contracts, decision 5 min before kickoff, 10 min staleness, 1 s latency, 5 min fill window, 1 cent half-spread, Webull $0.02 and Kalshi 0.07 fee rates, default tick 0.01, NFL opener dates, expected preseason count 49.

```python
 31  from __future__ import annotations
 32
 33  import json
 34  import math
 35  from dataclasses import dataclass, field
 36  from datetime import date
 37  from decimal import ROUND_CEILING, Decimal
 38
 39  import pandas as pd
 40
 41  import align
 42
 43  NS = 1_000_000_000
 44  SEAL = pd.Timestamp("2026-08-01", tz="UTC")
 45  THETAS = (0.70, 0.80, 0.90)                                                                                [MONEY]
 46  QTY = 10                                                                                                   [MONEY]
 47  ENTRY_BEFORE_KICKOFF_S = 5 * 60                                                                            [TIME]
 48  STALE_S = 10 * 60                                                                                          [TIME]
 49  LATENCY_S = 1.0               # docs/spec_provisional.md default latency                                   [TIME]
 50  FILL_WINDOW_S = 5 * 60        # Amendment 1 section 4: no trade within 5 min after t -> skip               [TIME]
 51  HALF_SPREAD = 0.01            # v3: as-of price + 1 cent                                                   [MONEY]
 52  MEDIAN_WINDOW_S = 3.0
 53  MIN_TRADES_SELECT = 50        # v3 selection: thetas with at least 50 trades
 54  WEBULL_PER_CONTRACT = 0.02                                                                                 [MONEY]
 55  KALSHI_DIRECT_RATE = 0.07                                                                                  [MONEY]
 56  KICKOFF_SOURCES = ("espn", "espn_event_id")   # ESPN only (v3, docs/strategy_a_rules.md)
 57  DEFAULT_TICK = 0.01                                                                                        [MONEY]
 58  NFL_OPENER = {2025: date(2025, 9, 4),            # regular-season opener (ET date), by season start year
 59                2026: date(2026, 9, 9)}            # Wed Sep 9, 2026 (Patriots at Seahawks), per Divi
 60  TRAINING_PRESEASON_N = 49
 61
```

Tests: `test_strategy_a_fees.py::test_constants_match_decimal`, `test_load_games_ticks_and_preseason_assert`, `test_preseason_flag_and_side_by_side`, `test_no_trade_within_5_min_after_t_skips`, `test_fill_is_first_trade_after_latency_plus_cent`

## Lines 62 to 88

Fees (Webull flat $0.02 per contract; Kalshi direct 0.07 x C x P x (1 - P) in exact decimal, rounded up to the cent) and the Game record (codes, event, ESPN kickoff, settlement result, per-team tick, exclusion reason).

```python
 62
 63  def fee_webull(price: float, qty: int = QTY) -> float:
 64      return WEBULL_PER_CONTRACT * qty                                                                                [MONEY]
 65
 66
 67  def fee_kalshi_direct(price: float, qty: int = QTY) -> float:
 68      """0.07 x C x P x (1 - P), exact decimal, rounded UP to the cent per order. P is trade price + 1 cent,          [MONEY]
 69      on the cent grid; rounding the float to 4 places recovers it exactly (and keeps a sub-cent tick if one
 70      ever appears instead of forcing it to a cent)."""
 71      p = Decimal(str(round(float(price), 4)))                                                                        [MONEY]
 72      raw = Decimal(str(KALSHI_DIRECT_RATE)) * Decimal(int(qty)) * p * (1 - p)                                        [MONEY]
 73      return float(raw.quantize(Decimal("0.01"), rounding=ROUND_CEILING))                                             [MONEY]
 74
 75
 76  @dataclass
 77  class Game:
 78      game_id: str
 79      league: str
 80      home: str              # Kalshi team codes; market ids are f"{event}-{code}"
 81      away: str
 82      event: str
 83      kickoff: pd.Timestamp  # ESPN kickoff, UTC                                                                      [TIME]
 84      kickoff_source: str
 85      result: float          # home win 1.0 / home loss 0.0 / tie 0.5 / NaN unsettled                                 [TIME]
 86      tick: dict = field(default_factory=dict)    # team code -> price step of its market (DEFAULT_TICK if absent)    [MONEY]
 87      exclude: str = ""      # non-empty: the game is not traded (reason), e.g. a team market missing from the data
 88
```

Tests: `test_strategy_a_fees.py::test_fees_match_t9_costs`, `test_strategy_a_fees.py::test_direct_fee_no_float_ceil_overcharge`, `test_fill_capped_at_one_minus_tick`, `test_staleness_and_away_favorite_and_tie`

## Lines 89 to 118

Preseason flag (ET kickoff date before that season's opener; unknown season raises), fill cap = 1 - tick of the team's market, and the tick read from Kalshi's price_ranges (step of the top range).

```python
 89
 90  def is_preseason(g: Game) -> bool:
 91      """NFL preseason = ESPN kickoff (US Eastern date) before that season's regular-season opener. 2025 opener
 92      Thu Sep 4, 2025; 2026 opener Wed Sep 9, 2026; 2025 training: 49 games (Hall of Fame game and the rest of the preseason). A season with no
 93      opener date set raises rather than guess."""
 94      if g.league.upper() != "NFL":
 95          return False
 96      d = g.kickoff.tz_convert("America/New_York").date()
 97      season = d.year if d.month >= 3 else d.year - 1
 98      if season not in NFL_OPENER:
 99          raise ValueError(f"{g.game_id}: no NFL regular-season opener set for season {season}")
100      return d < NFL_OPENER[season]
101
102
103  def fill_cap(g: Game, team: str) -> float:                                                                                                      [MONEY]
104      return round(1.0 - g.tick.get(team, DEFAULT_TICK), 4)                                                                                       [MONEY]
105
106
107  def top_step(price_ranges: str | None) -> float:
108      """Step of the range that contains the top of the price grid, from Kalshi's price_ranges JSON."""
109      try:
110          rs = json.loads(price_ranges) if isinstance(price_ranges, str) else None
111      except ValueError:
112          rs = None
113      if not rs:
114          return float("nan")
115      top = max(rs, key=lambda r: float(r["end"]))                                                                                                [MONEY]
116      return float(top["step"])                                                                                                                   [MONEY]
117
118
```

Tests: `test_preseason_flag_and_side_by_side`, `test_fill_capped_at_one_minus_tick`, `test_load_games_ticks_and_preseason_assert`

## Lines 119 to 156

Scalar settlement step: fills only blank results from Kalshi's recorded scalar value (home market, else 1 - away), never edits the file. team_markets: resolves both team market ids from the trade file so hyphenated codes (M-OH) survive, and flags a game missing either market.

```python
119  def apply_scalar_settlements(games: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
120      """Copy of games with blank settlement_result filled from Kalshi's own metadata: home market result
121      "scalar" -> its settlement_value_dollars; else away market "scalar" -> 1 - its value. Rows with a result
122      are unchanged; a blank with no scalar record stays blank. Adds settlement_source."""
123      g = games.copy()
124      g["settlement_source"] = g["settlement_result"].notna().map({True: "yes/no", False: ""})                        [TIME]
125      m = meta.set_index(["game_id", "side"])
126      for i in g.index[g["settlement_result"].isna()]:                                                                [TIME]
127          gid = g.at[i, "game_id"]
128          for side in ("home", "away"):
129              if (gid, side) not in m.index:
130                  continue
131              r = m.loc[(gid, side)]
132              v = pd.to_numeric(r.get("settlement_value_dollars"), errors="coerce")                                   [TIME]
133              if r.get("result") == "scalar" and v == v:                                                              [TIME]
134                  g.at[i, "settlement_result"] = float(v) if side == "home" else round(1.0 - float(v), 4)             [TIME]
135                  g.at[i, "settlement_source"] = f"kalshi scalar ({side} market)"                                     [TIME]
136                  break
137      return g
138
139
140  def team_markets(event: str, home_ticker: str, away_code: str, market_ids) -> tuple[str, str, str]:
141      """(home code, away code, exclude reason) from the market ids actually present in a game's trade file.
142      Team codes are everything after f"{event}-" in the ticker, so a code with a hyphen (Miami (OH) is "M-OH")
143      survives; the games file's away code came from ticker.rsplit("-", 1) and reads "OH" there. The away market is
144      the one other market of the event whose code ends with the file's away code. A game whose file does not hold
145      both team markets is excluded, never traded from one side."""
146      home = home_ticker[len(event) + 1:]
147      ids = set(market_ids)
148      others = [m for m in ids if m != home_ticker and m.startswith(event + "-")
149                and m[len(event) + 1:].split("-")[-1] == away_code.split("-")[-1]]
150      if home_ticker not in ids or len(others) != 1:
151          missing = [t for t, ok in ((home_ticker, home_ticker in ids), (f"{event}-{away_code}", len(others) == 1))
152                     if not ok]
153          return home, away_code, f"missing market ({', '.join(missing)}: no rows in the trade file)"
154      return home, others[0][len(event) + 1:], ""
155
156
```

Tests: `test_scalar_settlement_step_on_the_four_blank_games`, `test_team_markets_keeps_hyphenated_codes_and_flags_missing`, `test_load_games_ticks_and_preseason_assert`

## Lines 157 to 181

load_games: reads the games file and Kalshi metadata, applies the scalar step, resolves team markets and ticks per game, builds Game records, and asserts 49 NFL preseason games on the training file.

```python
157  def load_games(games_csv, meta_csv, ticks_dir=None,
158                 expect_preseason: int | None = TRAINING_PRESEASON_N) -> list[Game]:
159      """Games for Strategy A: the games file (never edited) + Kalshi metadata (scalar settlements, ticks).
160      ticks_dir (data/raw/kalshi_only): team market ids are resolved from each game's trade file (market_id
161      column only), see team_markets."""
162      raw = pd.read_csv(games_csv)
163      meta = pd.read_csv(meta_csv)
164      g = apply_scalar_settlements(raw, meta)                                                                          [TIME]
165      step = {(r.game_id, r.side): top_step(r.price_ranges) for r in meta.itertuples()}                                [MONEY]
166      out = []
167      for r in g.itertuples():
168          home, away, excl = r.home, r.away, ""
169          if ticks_dir is not None:
170              ids = pd.read_parquet(f"{ticks_dir}/{r.game_id}.parquet", columns=["market_id"])["market_id"].unique()
171              home, away, excl = team_markets(r.kalshi_event, r.kalshi_ticker, r.away, ids)
172          tick = {team: step[(r.game_id, side)] for team, side in ((home, "home"), (away, "away"))                     [MONEY]
173                  if not math.isnan(step.get((r.game_id, side), float("nan")))}                                        [MONEY]
174          out.append(Game(r.game_id, r.league, home, away, r.kalshi_event,
175                          pd.Timestamp(r.kickoff_utc_espn), r.kickoff_source, r.settlement_result, tick, excl))        [TIME]
176      if expect_preseason is not None:
177          n = sum(is_preseason(x) for x in out)
178          assert n == expect_preseason, f"NFL preseason games: {n}, expected {expect_preseason}"
179      return out
180
181
```

Tests: `test_load_games_ticks_and_preseason_assert`, `test_scalar_settlement_step_on_the_four_blank_games`

## Lines 182 to 209

Price helpers. own_market_trades: one team's own market as its own YES price (away rows flipped back from P(home)). asof_median: trailing 3 s median of trades at or before t, last value. first_fill: first trade in [t + 1 s, t + 5 min].

```python
182  def own_market_trades(trades: pd.DataFrame, g: Game, team: str) -> pd.DataFrame:
183      """That team's own market, as its own YES price (flip back from P(home) for the away market)."""
184      t = trades[(trades["market_id"] == f"{g.event}-{team}") & (trades["kind"] == "trade")]
185      t = t[["ts", "price"]].sort_values("ts", kind="stable")                                            [TIME]
186      if team == g.away:
187          t = t.assign(price=1.0 - t["price"])                                                           [MONEY]
188      return t.reset_index(drop=True)
189
190
191  def asof_median(tr: pd.DataFrame, t_ns: int) -> float:
192      """Trailing 3 s median of trade prices, last value at or before t (backward as-of)."""
193      past = tr[tr["ts"] <= t_ns]                                                                        [TIME]
194      if past.empty:
195          return float("nan")
196      ev = align.trade_median_events(past.assign(venue="k", kind="trade"), "k", MEDIAN_WINDOW_S)         [TIME] [MONEY]
197      return float(ev["price"].iloc[-1])                                                                 [TIME] [MONEY]
198
199
200  def first_fill(tr: pd.DataFrame, t_ns: int) -> tuple[int, float] | None:
201      """First trade at or after t + latency and within FILL_WINDOW_S after t."""                        [TIME]
202      lo, hi = t_ns + int(LATENCY_S * NS), t_ns + FILL_WINDOW_S * NS                                     [TIME]
203      after = tr[(tr["ts"] >= lo) & (tr["ts"] <= hi)]                                                    [TIME]
204      if after.empty:
205          return None
206      r = after.iloc[0]                                                                                  [TIME]
207      return int(r["ts"]), float(r["price"])                                                             [TIME] [MONEY]
208
209
```

Tests: `test_fill_is_first_trade_after_latency_plus_cent`, `test_fill_exactly_at_t_plus_latency_counts`, `test_no_trade_within_5_min_after_t_skips`, `test_decision_ignores_trades_after_t`, `test_staleness_and_away_favorite_and_tie`

## Lines 210 to 234

decide: the theta-free decision at t = kickoff - 5 min. Both own-market as-of prices; skip if either is missing; skip if EITHER market has no trade in (t - 10 min, t] (staleness on both markets, v3 A3 draft section 6), before any favorite is chosen; skip on equal prices; favorite = higher price.

```python
210  def decide(trades: pd.DataFrame, g: Game) -> dict:
211      """Theta-free part of the decision: favorite, as-of prices, staleness. Uses rows with ts <= t only."""
212      t_ns = (g.kickoff - pd.Timedelta(seconds=ENTRY_BEFORE_KICKOFF_S)).value                                      [TIME]
213      tr = {team: own_market_trades(trades, g, team) for team in (g.home, g.away)}
214      px = {team: asof_median(tr[team], t_ns) for team in tr}                                                      [TIME] [MONEY]
215      out = {"game_id": g.game_id, "league": g.league, "t_ns": t_ns, "skip": ""}                                   [TIME]
216      if any(math.isnan(p) for p in px.values()):                                                                  [MONEY]
217          out["skip"] = "no pre-decision price on both markets"
218          return out
219      # Staleness on BOTH markets, before the favorite is chosen: a stale price on either side could pick the
220      # wrong favorite. Window (t - 10 min, t], rows with ts <= t only.
221      stale = [team for team in (g.home, g.away)                                                                   [TIME]
222               if tr[team][(tr[team]["ts"] > t_ns - STALE_S * NS) & (tr[team]["ts"] <= t_ns)].empty]               [TIME]
223      if stale:                                                                                                    [TIME]
224          out["skip"] = f"stale (no trade in the 10 min before t: {', '.join(f'{g.event}-{x}' for x in stale)})"   [TIME]
225          return out                                                                                               [TIME]
226      if px[g.home] == px[g.away]:                                                                                 [MONEY]
227          out["skip"] = "no favorite (equal prices)"
228          return out
229      fav = g.home if px[g.home] > px[g.away] else g.away                                                          [MONEY]
230      dog = g.away if fav == g.home else g.home
231      out.update(fav=fav, dog=dog, fav_px=px[fav], dog_px=px[dog], _tr=tr)                                         [MONEY]
232      return out
233
234
```

Tests: `test_decision_ignores_trades_after_t`, `test_staleness_on_both_markets`, `test_staleness_and_away_favorite_and_tie`, `test_fill_is_first_trade_after_latency_plus_cent`

## Lines 235 to 262

_leg: one leg (favorite, or underdog placebo) at one theta. Skips in order (decision skip, below theta, no post-decision trade, unsettled); fill = min(trade + 1 cent, 1 - tick); payout from the settlement (tie 0.5); fees, P&L and return on capital for both fee lines.

```python
235  def _leg(d: dict, g: Game, team: str, theta: float, placebo: bool) -> dict:
236      row = {"game_id": g.game_id, "league": g.league, "theta": theta, "placebo": placebo,
237             "team": team, "entered": False, "skip": d["skip"], "preseason": is_preseason(g)}
238      if d["skip"]:
239          return row
240      if d["fav_px"] < theta:                                                                                  [MONEY]
241          row["skip"] = "below theta"                                                                          [MONEY]
242          return row
243      fill = first_fill(d["_tr"][team], d["t_ns"])                                                             [TIME]
244      if fill is None:                                                                                         [TIME]
245          row["skip"] = "no post-decision trade"                                                               [TIME]
246          return row
247      if g.result != g.result:                                                                                 [TIME]
248          row["skip"] = "unsettled"                                                                            [TIME]
249          return row
250      fill_ts, trade_px = fill                                                                                 [TIME] [MONEY]
251      cap = fill_cap(g, team)                                                                                  [MONEY]
252      capped = round(trade_px + HALF_SPREAD, 4) > cap                                                          [MONEY]
253      price = min(round(trade_px + HALF_SPREAD, 4), cap)                                                       [MONEY]
254      team_result = g.result if team == g.home else 1.0 - g.result       # tie stays 0.5                       [TIME] [MONEY]
255      fw, fd = fee_webull(price), fee_kalshi_direct(price)                                                     [MONEY]
256      gross = (team_result - price) * QTY                                                                      [MONEY]
257      row.update(entered=True, fill_ts=fill_ts, fill_price=price, fill_capped=capped, payout=team_result,      [TIME] [MONEY]
258                 fee_webull=fw, fee_direct=fd, pnl_webull=gross - fw, pnl_direct=gross - fd,                   [MONEY]
259                 roc_webull=(gross - fw) / (price * QTY + fw), roc_direct=(gross - fd) / (price * QTY + fd))   [MONEY]
260      return row
261
262
```

Tests: `test_fill_is_first_trade_after_latency_plus_cent`, `test_fill_exactly_at_t_plus_latency_counts`, `test_no_trade_within_5_min_after_t_skips`, `test_fill_capped_at_one_minus_tick`, `test_staleness_and_away_favorite_and_tie`, `test_placebo_uses_same_fill_rule_and_seal`

## Lines 263 to 287

evaluate_game: seal guard (refuses kickoff >= 2026-08-01 unless final_test), ESPN-only kickoffs, load-time exclusion, missing-market exclusion (never pick the favorite from one side), then one favorite row and one placebo row per theta.

```python
263  def evaluate_game(trades: pd.DataFrame, g: Game, thetas=THETAS, final_test: bool = False) -> list[dict]:
264      """One row per theta for the favorite leg and one for the underdog placebo leg."""
265      if g.kickoff >= SEAL and not final_test:                                                                 [TIME]
266          raise ValueError(f"{g.game_id}: kickoff on/after 2026-08-01 is sealed (needs final_test)")           [TIME]
267      if g.kickoff_source not in KICKOFF_SOURCES:
268          return [{"game_id": g.game_id, "league": g.league, "theta": th, "placebo": p, "entered": False,
269                   "skip": f"kickoff not from ESPN ({g.kickoff_source})", "preseason": is_preseason(g)}
270                  for th in thetas for p in (False, True)]
271      if g.exclude:
272          return [{"game_id": g.game_id, "league": g.league, "theta": th, "placebo": p, "entered": False,
273                   "skip": g.exclude, "preseason": is_preseason(g)} for th in thetas for p in (False, True)]
274      present = set(trades.loc[trades["kind"] == "trade", "market_id"].unique()) if len(trades) else set()
275      missing = [f"{g.event}-{t}" for t in (g.home, g.away) if f"{g.event}-{t}" not in present]
276      if missing:      # never pick the favorite from one side
277          return [{"game_id": g.game_id, "league": g.league, "theta": th, "placebo": p, "entered": False,
278                   "skip": f"missing market ({', '.join(missing)}: no rows in the trade file)",
279                   "preseason": is_preseason(g)} for th in thetas for p in (False, True)]
280      d = decide(trades, g)
281      rows = []
282      for th in thetas:
283          rows.append(_leg(d, g, d.get("fav"), th, placebo=False))
284          rows.append(_leg(d, g, d.get("dog"), th, placebo=True))
285      return rows
286
287
```

Tests: `test_placebo_uses_same_fill_rule_and_seal`, `test_game_with_one_missing_market_is_excluded_not_traded`, `test_preseason_flag_and_side_by_side`, `test_fill_is_first_trade_after_latency_plus_cent`

## Lines 288 to 316

Summaries: per theta and leg, trade count, mean return on capital (both fee lines), capped-fill count and skip counts; the primary vs no-preseason side-by-side table; theta selection = best Webull return among thetas with >= 50 favorite trades (ties to the lower theta).

```python
288  def summarize(rows: pd.DataFrame) -> pd.DataFrame:
289      """Per theta and leg: trades, mean return on capital, skip counts (incl. no post-decision trade)."""
290      out = []
291      for (th, pl), r in rows.groupby(["theta", "placebo"]):
292          e = r[r["entered"]]
293          out.append({"theta": th, "placebo": pl, "n_trades": len(e),
294                      "roc_webull_mean": e["roc_webull"].mean() if len(e) else float("nan"),                             [MONEY]
295                      "roc_direct_mean": e["roc_direct"].mean() if len(e) else float("nan"),                             [MONEY]
296                      "n_capped_fills": int(e["fill_capped"].sum()) if "fill_capped" in e else 0,                        [MONEY]
297                      "skipped_no_post_decision_trade": int((r["skip"] == "no post-decision trade").sum()),
298                      "n_skipped_stale": int(r["skip"].str.startswith("stale").sum()),
299                      "skipped_other": int((~r["entered"] & ~r["skip"].isin(["below theta", "no post-decision trade"])
300                                            & ~r["skip"].str.startswith("stale")).sum())})
301      return pd.DataFrame(out)
302
303
304  def summarize_side_by_side(rows: pd.DataFrame) -> pd.DataFrame:
305      """Primary run (all games) and the robustness run without NFL preseason, one table, column "sample"."""
306      return pd.concat([summarize(rows).assign(sample="primary"),
307                        summarize(rows[~rows["preseason"].astype(bool)]).assign(sample="no NFL preseason")],
308                       ignore_index=True)
309
310
311  def select_theta(summary: pd.DataFrame) -> float | None:
312      """v3: best mean return on capital on train among thetas with at least 50 trades (favorite leg, Webull line)."""   [MONEY]
313      s = summary[(~summary["placebo"]) & (summary["n_trades"] >= MIN_TRADES_SELECT)]                                    [MONEY]
314      if s.empty:
315          return None
316      return float(s.sort_values(["roc_webull_mean", "theta"], ascending=[False, True]).iloc[0]["theta"])                [MONEY]
```

Tests: `test_no_trade_within_5_min_after_t_skips`, `test_fill_capped_at_one_minus_tick`, `test_preseason_flag_and_side_by_side`, `test_select_theta_needs_50_trades`, `test_staleness_on_both_markets`

## Where a lookahead could hide, and why each is safe

1. **The decision prices and staleness (lines 191 to 197, called at 214; staleness 221 to 225).** The favorite and the theta check use each team's own-market price at t = kickoff - 5 min (line 212). Line 193 keeps only trades with `ts <= t_ns` *before* the median is computed, so the 3 s rolling median at line 196 (align.trade_median_events, window (t - 3 s, t], `closed="right"`) can only see past and current trades, and line 197 takes the last value at or before t. The staleness check on both markets (line 222) is also bounded by `ts <= t_ns`, and it runs before the favorite is chosen (line 229). Tests: `test_decision_ignores_trades_after_t` (trades after t do not change the favorite or the entry), `test_staleness_on_both_markets`.

2. **The fill (lines 200 to 207, used at 243 and 250 to 253).** The fill is the one place that is *meant* to read the future, and it is bounded on both sides: no earlier than t + 1 s (line 202, `lo`, the latency, so the trade that triggered the decision cannot be the fill) and no later than t + 5 min (`hi`). It reads only the leg's own market (`d["_tr"][team]`) and only the first such trade (line 206). Nothing from the fill feeds back into the decision: `decide` (lines 210 to 232) has already returned before `first_fill` is called. Tests: `test_fill_is_first_trade_after_latency_plus_cent` (a trade 0.5 s after t is ignored), `test_fill_exactly_at_t_plus_latency_counts`, `test_no_trade_within_5_min_after_t_skips`.

3. **The settlement and whole-file checks (lines 247 to 248, 254, 274 to 279).** The game result is known only after the game, so it must never decide whether or what to enter. It is read only at line 247 (skip if unsettled) and line 254 (payout), both after the entry decision and the fill are fixed; theta, the favorite and the fill do not depend on it. The unsettled skip uses whether a result exists, not its value (0 training games are unsettled after the scalar step). The missing-market check at lines 274 to 279 looks at the whole trade file, including rows after t. That is safe: if a market's only rows are after t, the game would be skipped anyway at line 216 (no pre-decision price on both markets), so the check can only change the skip reason, never turn a skip into a trade or change a trade. The scalar settlement step (lines 119 to 137) uses only Kalshi's settlement fields. Tests: `test_staleness_and_away_favorite_and_tie`, `test_scalar_settlement_step_on_the_four_blank_games`, `test_game_with_one_missing_market_is_excluded_not_traded`.

## Points for your line-by-line review (choices to confirm)

- Lines 221 to 225 (changed 18:20 ET): staleness is now checked on both markets before the favorite is chosen (was favorite only). In `test_staleness_on_both_markets` case (c), the previous rule entered HHH; the new rule skips. The skip happens before the equal-price check, so a stale game is always counted as stale.
- Line 97: the season of a kickoff is its ET year, minus 1 for January and February (playoffs). A March to July game would count as the new season; there are none in NFL training.
- Lines 202 to 203: the fill window ends at t + 5 min = the ESPN kickoff, so no fill happens after kickoff.
- Line 253: the cap is 0.99 for every training market (all 2,534 at a 0.01 step), so `fill_capped` is the same as the earlier fixed cap on this data.
- Lines 148 to 150: the away market is matched by the last hyphen piece of its code ("M-OH" matches "OH"). If an event ever had two other markets ending the same way, the game is excluded (line 150), not guessed.
