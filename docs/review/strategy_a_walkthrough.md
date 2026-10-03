# strategy_a.py walkthrough (Rule-7 review packet)

File: strategy_a.py at f26bfe1 (branch t13-strategy-a), 311 lines. Strategy A has NOT been run on any data; only the fake-game tests below.

Tags at line end: **[TIME]** touches decision time, fill time, the 5-min skip, or settlement. **[MONEY]** touches price, fee, cap or P&L. Tests are in tests/test_strategy_a.py unless named otherwise.

## Lines 1 to 29

Module docstring: the pre-registered rule in words (decision at kickoff - 5 min, own-market 3 s median, staleness, theta, fill rule, cap, settlement, costs, placebo, preseason). No code runs here; it is the spec the code below must match.

```python
  1  """Strategy A (HYPOTHESIS_v3.md, with Amendment 1 committed 9507d6a): Kalshi favorite-longshot, hold to settlement.
  2
  3  Rule-7 file (same review rule as strategy.py): written on a branch, reviewed line by line by Divi before main.
  4
  5  Per game and theta:
  6    t = ESPN kickoff - 5 min.                                                                                                           [TIME]
  7    Decision (backward as-of only, rows with ts <= t): each team's OWN market price = trailing 3 s median of                            [TIME]
  8      that market's trade prices, last value at or before t (align.trade_median_events). Favorite = higher
  9      own-market price. Skip if the favorite's market has no trade in [t - 10 min, t] (staleness). Enter iff                            [TIME]
 10      favorite price >= theta.
 11    Fill (Amendment 1 section 4): first trade on the favorite's own market at or after t + 1.0 s, plus 1 cent                           [TIME]
 12      half-spread, capped at 1 - tick of that market (v3 Amendment 3 draft: 1.00 is not a valid Kalshi price;                           [MONEY]
 13      tick = the step of the market's top price range in Kalshi's metadata, 0.01 if not known). No such trade                           [MONEY]
 14      within 5 min after t -> skip, reason "no post-decision trade".                                                                    [TIME]
 15    Settlement: $1 per contract if the favorite wins, $0 if it loses, $0.5 on a tie (docs/strategy_a_rules.md).                         [TIME]
 16      load_games applies Kalshi's recorded scalar settlement where the games file has no result                                         [TIME]
 17      (apply_scalar_settlements, from data/raw/kalshi_market_meta.csv); the games file itself is never edited.                          [TIME]
 18    Costs (v3 line 20): Webull $0.02 per contract per fill, entry only (primary); Kalshi direct                                         [MONEY]
 19      0.07 x C x P x (1 - P) rounded up to the cent per order (comparison). Settlement fee 0.                                           [MONEY]
 20    Placebo: buy the underdog's own market under the same decision and the same fill rule.
 21    Preseason robustness (v3 Amendment 3 draft): NFL games with ESPN kickoff (ET date) before that season's
 22      regular-season opener (2025: Thu Sep 4, 2025; 2026: Wed Sep 9, 2026) are flagged "preseason" (49 in training, incl. the Hall of
 23      Fame game); they stay in the primary run, and summarize_side_by_side reports the run without them next to
 24      it. Theta selection uses the primary run only.
 25
 26  Input trades follow the tick contract (price = P(home wins)); the away team's own-market price is 1 - price
 27  on rows of the away market. No prices are printed. Sealed games (kickoff >= 2026-08-01) are refused unless
 28  final_test=True.
 29  """
```

Tests: none (docstring)

## Lines 30 to 60

Imports and the fixed constants: seal date, theta grid (0.70/0.80/0.90), 10 contracts, decision 5 min before kickoff, 10 min staleness, 1 s latency, 5 min fill window, 1 cent half-spread, Webull $0.02 and Kalshi 0.07 fee rates, default tick 0.01, NFL opener dates, expected preseason count 49.

```python
 30  from __future__ import annotations
 31
 32  import json
 33  import math
 34  from dataclasses import dataclass, field
 35  from datetime import date
 36  from decimal import ROUND_CEILING, Decimal
 37
 38  import pandas as pd
 39
 40  import align
 41
 42  NS = 1_000_000_000
 43  SEAL = pd.Timestamp("2026-08-01", tz="UTC")
 44  THETAS = (0.70, 0.80, 0.90)                                                                                [MONEY]
 45  QTY = 10                                                                                                   [MONEY]
 46  ENTRY_BEFORE_KICKOFF_S = 5 * 60                                                                            [TIME]
 47  STALE_S = 10 * 60                                                                                          [TIME]
 48  LATENCY_S = 1.0               # docs/spec_provisional.md default latency                                   [TIME]
 49  FILL_WINDOW_S = 5 * 60        # Amendment 1 section 4: no trade within 5 min after t -> skip               [TIME]
 50  HALF_SPREAD = 0.01            # v3: as-of price + 1 cent                                                   [MONEY]
 51  MEDIAN_WINDOW_S = 3.0
 52  MIN_TRADES_SELECT = 50        # v3 selection: thetas with at least 50 trades
 53  WEBULL_PER_CONTRACT = 0.02                                                                                 [MONEY]
 54  KALSHI_DIRECT_RATE = 0.07                                                                                  [MONEY]
 55  KICKOFF_SOURCES = ("espn", "espn_event_id")   # ESPN only (v3, docs/strategy_a_rules.md)
 56  DEFAULT_TICK = 0.01                                                                                        [MONEY]
 57  NFL_OPENER = {2025: date(2025, 9, 4),            # regular-season opener (ET date), by season start year
 58                2026: date(2026, 9, 9)}            # Wed Sep 9, 2026 (Patriots at Seahawks), per Divi
 59  TRAINING_PRESEASON_N = 49
 60
```

Tests: `test_strategy_a_fees.py::test_constants_match_decimal`, `test_load_games_ticks_and_preseason_assert`, `test_preseason_flag_and_side_by_side`, `test_no_trade_within_5_min_after_t_skips`, `test_fill_is_first_trade_after_latency_plus_cent`

## Lines 61 to 87

Fees (Webull flat $0.02 per contract; Kalshi direct 0.07 x C x P x (1 - P) in exact decimal, rounded up to the cent) and the Game record (codes, event, ESPN kickoff, settlement result, per-team tick, exclusion reason).

```python
 61
 62  def fee_webull(price: float, qty: int = QTY) -> float:
 63      return WEBULL_PER_CONTRACT * qty                                                                                [MONEY]
 64
 65
 66  def fee_kalshi_direct(price: float, qty: int = QTY) -> float:
 67      """0.07 x C x P x (1 - P), exact decimal, rounded UP to the cent per order. P is trade price + 1 cent,          [MONEY]
 68      on the cent grid; rounding the float to 4 places recovers it exactly (and keeps a sub-cent tick if one
 69      ever appears instead of forcing it to a cent)."""
 70      p = Decimal(str(round(float(price), 4)))                                                                        [MONEY]
 71      raw = Decimal(str(KALSHI_DIRECT_RATE)) * Decimal(int(qty)) * p * (1 - p)                                        [MONEY]
 72      return float(raw.quantize(Decimal("0.01"), rounding=ROUND_CEILING))                                             [MONEY]
 73
 74
 75  @dataclass
 76  class Game:
 77      game_id: str
 78      league: str
 79      home: str              # Kalshi team codes; market ids are f"{event}-{code}"
 80      away: str
 81      event: str
 82      kickoff: pd.Timestamp  # ESPN kickoff, UTC                                                                      [TIME]
 83      kickoff_source: str
 84      result: float          # home win 1.0 / home loss 0.0 / tie 0.5 / NaN unsettled                                 [TIME]
 85      tick: dict = field(default_factory=dict)    # team code -> price step of its market (DEFAULT_TICK if absent)    [MONEY]
 86      exclude: str = ""      # non-empty: the game is not traded (reason), e.g. a team market missing from the data
 87
```

Tests: `test_strategy_a_fees.py::test_fees_match_t9_costs`, `test_strategy_a_fees.py::test_direct_fee_no_float_ceil_overcharge`, `test_fill_capped_at_one_minus_tick`, `test_staleness_and_away_favorite_and_tie`

## Lines 88 to 117

Preseason flag (ET kickoff date before that season's opener; unknown season raises), fill cap = 1 - tick of the team's market, and the tick read from Kalshi's price_ranges (step of the top range).

```python
 88
 89  def is_preseason(g: Game) -> bool:
 90      """NFL preseason = ESPN kickoff (US Eastern date) before that season's regular-season opener. 2025 opener
 91      Thu Sep 4, 2025; 2026 opener Wed Sep 9, 2026; 2025 training: 49 games (Hall of Fame game and the rest of the preseason). A season with no
 92      opener date set raises rather than guess."""
 93      if g.league.upper() != "NFL":
 94          return False
 95      d = g.kickoff.tz_convert("America/New_York").date()
 96      season = d.year if d.month >= 3 else d.year - 1
 97      if season not in NFL_OPENER:
 98          raise ValueError(f"{g.game_id}: no NFL regular-season opener set for season {season}")
 99      return d < NFL_OPENER[season]
100
101
102  def fill_cap(g: Game, team: str) -> float:                                                                                                      [MONEY]
103      return round(1.0 - g.tick.get(team, DEFAULT_TICK), 4)                                                                                       [MONEY]
104
105
106  def top_step(price_ranges: str | None) -> float:
107      """Step of the range that contains the top of the price grid, from Kalshi's price_ranges JSON."""
108      try:
109          rs = json.loads(price_ranges) if isinstance(price_ranges, str) else None
110      except ValueError:
111          rs = None
112      if not rs:
113          return float("nan")
114      top = max(rs, key=lambda r: float(r["end"]))                                                                                                [MONEY]
115      return float(top["step"])                                                                                                                   [MONEY]
116
117
```

Tests: `test_preseason_flag_and_side_by_side`, `test_fill_capped_at_one_minus_tick`, `test_load_games_ticks_and_preseason_assert`

## Lines 118 to 155

Scalar settlement step: fills only blank results from Kalshi's recorded scalar value (home market, else 1 - away), never edits the file. team_markets: resolves both team market ids from the trade file so hyphenated codes (M-OH) survive, and flags a game missing either market.

```python
118  def apply_scalar_settlements(games: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
119      """Copy of games with blank settlement_result filled from Kalshi's own metadata: home market result
120      "scalar" -> its settlement_value_dollars; else away market "scalar" -> 1 - its value. Rows with a result
121      are unchanged; a blank with no scalar record stays blank. Adds settlement_source."""
122      g = games.copy()
123      g["settlement_source"] = g["settlement_result"].notna().map({True: "yes/no", False: ""})                        [TIME]
124      m = meta.set_index(["game_id", "side"])
125      for i in g.index[g["settlement_result"].isna()]:                                                                [TIME]
126          gid = g.at[i, "game_id"]
127          for side in ("home", "away"):
128              if (gid, side) not in m.index:
129                  continue
130              r = m.loc[(gid, side)]
131              v = pd.to_numeric(r.get("settlement_value_dollars"), errors="coerce")                                   [TIME]
132              if r.get("result") == "scalar" and v == v:                                                              [TIME]
133                  g.at[i, "settlement_result"] = float(v) if side == "home" else round(1.0 - float(v), 4)             [TIME]
134                  g.at[i, "settlement_source"] = f"kalshi scalar ({side} market)"                                     [TIME]
135                  break
136      return g
137
138
139  def team_markets(event: str, home_ticker: str, away_code: str, market_ids) -> tuple[str, str, str]:
140      """(home code, away code, exclude reason) from the market ids actually present in a game's trade file.
141      Team codes are everything after f"{event}-" in the ticker, so a code with a hyphen (Miami (OH) is "M-OH")
142      survives; the games file's away code came from ticker.rsplit("-", 1) and reads "OH" there. The away market is
143      the one other market of the event whose code ends with the file's away code. A game whose file does not hold
144      both team markets is excluded, never traded from one side."""
145      home = home_ticker[len(event) + 1:]
146      ids = set(market_ids)
147      others = [m for m in ids if m != home_ticker and m.startswith(event + "-")
148                and m[len(event) + 1:].split("-")[-1] == away_code.split("-")[-1]]
149      if home_ticker not in ids or len(others) != 1:
150          missing = [t for t, ok in ((home_ticker, home_ticker in ids), (f"{event}-{away_code}", len(others) == 1))
151                     if not ok]
152          return home, away_code, f"missing market ({', '.join(missing)}: no rows in the trade file)"
153      return home, others[0][len(event) + 1:], ""
154
155
```

Tests: `test_scalar_settlement_step_on_the_four_blank_games`, `test_team_markets_keeps_hyphenated_codes_and_flags_missing`, `test_load_games_ticks_and_preseason_assert`

## Lines 156 to 180

load_games: reads the games file and Kalshi metadata, applies the scalar step, resolves team markets and ticks per game, builds Game records, and asserts 49 NFL preseason games on the training file.

```python
156  def load_games(games_csv, meta_csv, ticks_dir=None,
157                 expect_preseason: int | None = TRAINING_PRESEASON_N) -> list[Game]:
158      """Games for Strategy A: the games file (never edited) + Kalshi metadata (scalar settlements, ticks).
159      ticks_dir (data/raw/kalshi_only): team market ids are resolved from each game's trade file (market_id
160      column only), see team_markets."""
161      raw = pd.read_csv(games_csv)
162      meta = pd.read_csv(meta_csv)
163      g = apply_scalar_settlements(raw, meta)                                                                          [TIME]
164      step = {(r.game_id, r.side): top_step(r.price_ranges) for r in meta.itertuples()}                                [MONEY]
165      out = []
166      for r in g.itertuples():
167          home, away, excl = r.home, r.away, ""
168          if ticks_dir is not None:
169              ids = pd.read_parquet(f"{ticks_dir}/{r.game_id}.parquet", columns=["market_id"])["market_id"].unique()
170              home, away, excl = team_markets(r.kalshi_event, r.kalshi_ticker, r.away, ids)
171          tick = {team: step[(r.game_id, side)] for team, side in ((home, "home"), (away, "away"))                     [MONEY]
172                  if not math.isnan(step.get((r.game_id, side), float("nan")))}                                        [MONEY]
173          out.append(Game(r.game_id, r.league, home, away, r.kalshi_event,
174                          pd.Timestamp(r.kickoff_utc_espn), r.kickoff_source, r.settlement_result, tick, excl))        [TIME]
175      if expect_preseason is not None:
176          n = sum(is_preseason(x) for x in out)
177          assert n == expect_preseason, f"NFL preseason games: {n}, expected {expect_preseason}"
178      return out
179
180
```

Tests: `test_load_games_ticks_and_preseason_assert`, `test_scalar_settlement_step_on_the_four_blank_games`

## Lines 181 to 208

Price helpers. own_market_trades: one team's own market as its own YES price (away rows flipped back from P(home)). asof_median: trailing 3 s median of trades at or before t, last value. first_fill: first trade in [t + 1 s, t + 5 min].

```python
181  def own_market_trades(trades: pd.DataFrame, g: Game, team: str) -> pd.DataFrame:
182      """That team's own market, as its own YES price (flip back from P(home) for the away market)."""
183      t = trades[(trades["market_id"] == f"{g.event}-{team}") & (trades["kind"] == "trade")]
184      t = t[["ts", "price"]].sort_values("ts", kind="stable")                                            [TIME]
185      if team == g.away:
186          t = t.assign(price=1.0 - t["price"])                                                           [MONEY]
187      return t.reset_index(drop=True)
188
189
190  def asof_median(tr: pd.DataFrame, t_ns: int) -> float:
191      """Trailing 3 s median of trade prices, last value at or before t (backward as-of)."""
192      past = tr[tr["ts"] <= t_ns]                                                                        [TIME]
193      if past.empty:
194          return float("nan")
195      ev = align.trade_median_events(past.assign(venue="k", kind="trade"), "k", MEDIAN_WINDOW_S)         [TIME] [MONEY]
196      return float(ev["price"].iloc[-1])                                                                 [TIME] [MONEY]
197
198
199  def first_fill(tr: pd.DataFrame, t_ns: int) -> tuple[int, float] | None:
200      """First trade at or after t + latency and within FILL_WINDOW_S after t."""                        [TIME]
201      lo, hi = t_ns + int(LATENCY_S * NS), t_ns + FILL_WINDOW_S * NS                                     [TIME]
202      after = tr[(tr["ts"] >= lo) & (tr["ts"] <= hi)]                                                    [TIME]
203      if after.empty:
204          return None
205      r = after.iloc[0]                                                                                  [TIME]
206      return int(r["ts"]), float(r["price"])                                                             [TIME] [MONEY]
207
208
```

Tests: `test_fill_is_first_trade_after_latency_plus_cent`, `test_fill_exactly_at_t_plus_latency_counts`, `test_no_trade_within_5_min_after_t_skips`, `test_decision_ignores_trades_after_t`, `test_staleness_and_away_favorite_and_tie`

## Lines 209 to 229

decide: the theta-free decision at t = kickoff - 5 min. Both own-market as-of prices; skip if either is missing or they are equal; favorite = higher price; stale if the favorite has no trade in (t - 10 min, t].

```python
209  def decide(trades: pd.DataFrame, g: Game) -> dict:
210      """Theta-free part of the decision: favorite, as-of prices, staleness. Uses rows with ts <= t only."""
211      t_ns = (g.kickoff - pd.Timedelta(seconds=ENTRY_BEFORE_KICKOFF_S)).value                                  [TIME]
212      tr = {team: own_market_trades(trades, g, team) for team in (g.home, g.away)}
213      px = {team: asof_median(tr[team], t_ns) for team in tr}                                                  [TIME] [MONEY]
214      out = {"game_id": g.game_id, "league": g.league, "t_ns": t_ns, "skip": ""}
215      if any(math.isnan(p) for p in px.values()):                                                              [MONEY]
216          out["skip"] = "no pre-decision price on both markets"
217          return out
218      if px[g.home] == px[g.away]:                                                                             [MONEY]
219          out["skip"] = "no favorite (equal prices)"
220          return out
221      fav = g.home if px[g.home] > px[g.away] else g.away                                                      [MONEY]
222      dog = g.away if fav == g.home else g.home
223      recent = tr[fav][(tr[fav]["ts"] > t_ns - STALE_S * NS) & (tr[fav]["ts"] <= t_ns)]                        [TIME]
224      if recent.empty:
225          out["skip"] = "stale (no favorite trade in the 10 min before t)"                                     [TIME]
226      out.update(fav=fav, dog=dog, fav_px=px[fav], dog_px=px[dog], _tr=tr)                                     [MONEY]
227      return out
228
229
```

Tests: `test_decision_ignores_trades_after_t`, `test_staleness_and_away_favorite_and_tie`, `test_fill_is_first_trade_after_latency_plus_cent`

## Lines 230 to 257

_leg: one leg (favorite, or underdog placebo) at one theta. Skips in order (decision skip, below theta, no post-decision trade, unsettled); fill = min(trade + 1 cent, 1 - tick); payout from the settlement (tie 0.5); fees, P&L and return on capital for both fee lines.

```python
230  def _leg(d: dict, g: Game, team: str, theta: float, placebo: bool) -> dict:
231      row = {"game_id": g.game_id, "league": g.league, "theta": theta, "placebo": placebo,
232             "team": team, "entered": False, "skip": d["skip"], "preseason": is_preseason(g)}
233      if d["skip"]:
234          return row
235      if d["fav_px"] < theta:                                                                                  [MONEY]
236          row["skip"] = "below theta"                                                                          [MONEY]
237          return row
238      fill = first_fill(d["_tr"][team], d["t_ns"])                                                             [TIME]
239      if fill is None:                                                                                         [TIME]
240          row["skip"] = "no post-decision trade"                                                               [TIME]
241          return row
242      if g.result != g.result:                                                                                 [TIME]
243          row["skip"] = "unsettled"                                                                            [TIME]
244          return row
245      fill_ts, trade_px = fill                                                                                 [TIME] [MONEY]
246      cap = fill_cap(g, team)                                                                                  [MONEY]
247      capped = round(trade_px + HALF_SPREAD, 4) > cap                                                          [MONEY]
248      price = min(round(trade_px + HALF_SPREAD, 4), cap)                                                       [MONEY]
249      team_result = g.result if team == g.home else 1.0 - g.result       # tie stays 0.5                       [TIME] [MONEY]
250      fw, fd = fee_webull(price), fee_kalshi_direct(price)                                                     [MONEY]
251      gross = (team_result - price) * QTY                                                                      [MONEY]
252      row.update(entered=True, fill_ts=fill_ts, fill_price=price, fill_capped=capped, payout=team_result,      [TIME] [MONEY]
253                 fee_webull=fw, fee_direct=fd, pnl_webull=gross - fw, pnl_direct=gross - fd,                   [MONEY]
254                 roc_webull=(gross - fw) / (price * QTY + fw), roc_direct=(gross - fd) / (price * QTY + fd))   [MONEY]
255      return row
256
257
```

Tests: `test_fill_is_first_trade_after_latency_plus_cent`, `test_fill_exactly_at_t_plus_latency_counts`, `test_no_trade_within_5_min_after_t_skips`, `test_fill_capped_at_one_minus_tick`, `test_staleness_and_away_favorite_and_tie`, `test_placebo_uses_same_fill_rule_and_seal`

## Lines 258 to 282

evaluate_game: seal guard (refuses kickoff >= 2026-08-01 unless final_test), ESPN-only kickoffs, load-time exclusion, missing-market exclusion (never pick the favorite from one side), then one favorite row and one placebo row per theta.

```python
258  def evaluate_game(trades: pd.DataFrame, g: Game, thetas=THETAS, final_test: bool = False) -> list[dict]:
259      """One row per theta for the favorite leg and one for the underdog placebo leg."""
260      if g.kickoff >= SEAL and not final_test:                                                                 [TIME]
261          raise ValueError(f"{g.game_id}: kickoff on/after 2026-08-01 is sealed (needs final_test)")           [TIME]
262      if g.kickoff_source not in KICKOFF_SOURCES:
263          return [{"game_id": g.game_id, "league": g.league, "theta": th, "placebo": p, "entered": False,
264                   "skip": f"kickoff not from ESPN ({g.kickoff_source})", "preseason": is_preseason(g)}
265                  for th in thetas for p in (False, True)]
266      if g.exclude:
267          return [{"game_id": g.game_id, "league": g.league, "theta": th, "placebo": p, "entered": False,
268                   "skip": g.exclude, "preseason": is_preseason(g)} for th in thetas for p in (False, True)]
269      present = set(trades.loc[trades["kind"] == "trade", "market_id"].unique()) if len(trades) else set()
270      missing = [f"{g.event}-{t}" for t in (g.home, g.away) if f"{g.event}-{t}" not in present]
271      if missing:      # never pick the favorite from one side
272          return [{"game_id": g.game_id, "league": g.league, "theta": th, "placebo": p, "entered": False,
273                   "skip": f"missing market ({', '.join(missing)}: no rows in the trade file)",
274                   "preseason": is_preseason(g)} for th in thetas for p in (False, True)]
275      d = decide(trades, g)
276      rows = []
277      for th in thetas:
278          rows.append(_leg(d, g, d.get("fav"), th, placebo=False))
279          rows.append(_leg(d, g, d.get("dog"), th, placebo=True))
280      return rows
281
282
```

Tests: `test_placebo_uses_same_fill_rule_and_seal`, `test_game_with_one_missing_market_is_excluded_not_traded`, `test_preseason_flag_and_side_by_side`, `test_fill_is_first_trade_after_latency_plus_cent`

## Lines 283 to 311

Summaries: per theta and leg, trade count, mean return on capital (both fee lines), capped-fill count and skip counts; the primary vs no-preseason side-by-side table; theta selection = best Webull return among thetas with >= 50 favorite trades (ties to the lower theta).

```python
283  def summarize(rows: pd.DataFrame) -> pd.DataFrame:
284      """Per theta and leg: trades, mean return on capital, skip counts (incl. no post-decision trade)."""
285      out = []
286      for (th, pl), r in rows.groupby(["theta", "placebo"]):
287          e = r[r["entered"]]
288          out.append({"theta": th, "placebo": pl, "n_trades": len(e),
289                      "roc_webull_mean": e["roc_webull"].mean() if len(e) else float("nan"),                             [MONEY]
290                      "roc_direct_mean": e["roc_direct"].mean() if len(e) else float("nan"),                             [MONEY]
291                      "n_capped_fills": int(e["fill_capped"].sum()) if "fill_capped" in e else 0,                        [MONEY]
292                      "skipped_no_post_decision_trade": int((r["skip"] == "no post-decision trade").sum()),
293                      "skipped_stale": int(r["skip"].str.startswith("stale").sum()),
294                      "skipped_other": int((~r["entered"] & ~r["skip"].isin(["below theta", "no post-decision trade"])
295                                            & ~r["skip"].str.startswith("stale")).sum())})
296      return pd.DataFrame(out)
297
298
299  def summarize_side_by_side(rows: pd.DataFrame) -> pd.DataFrame:
300      """Primary run (all games) and the robustness run without NFL preseason, one table, column "sample"."""
301      return pd.concat([summarize(rows).assign(sample="primary"),
302                        summarize(rows[~rows["preseason"].astype(bool)]).assign(sample="no NFL preseason")],
303                       ignore_index=True)
304
305
306  def select_theta(summary: pd.DataFrame) -> float | None:
307      """v3: best mean return on capital on train among thetas with at least 50 trades (favorite leg, Webull line)."""   [MONEY]
308      s = summary[(~summary["placebo"]) & (summary["n_trades"] >= MIN_TRADES_SELECT)]                                    [MONEY]
309      if s.empty:
310          return None
311      return float(s.sort_values(["roc_webull_mean", "theta"], ascending=[False, True]).iloc[0]["theta"])                [MONEY]
```

Tests: `test_no_trade_within_5_min_after_t_skips`, `test_fill_capped_at_one_minus_tick`, `test_preseason_flag_and_side_by_side`, `test_select_theta_needs_50_trades`

## Where a lookahead could hide, and why each is safe

1. **The decision price (lines 190 to 196, called at 213).** The favorite and the theta check use each team's own-market price at t = kickoff - 5 min (line 211). Line 192 keeps only trades with `ts <= t_ns` *before* the median is computed, so the 3 s rolling median at line 195 (align.trade_median_events, window (t - 3 s, t], `closed="right"`) can only see past and current trades, and line 196 takes the last value at or before t. Staleness (line 223) is also bounded by `ts <= t_ns`. Test: `test_decision_ignores_trades_after_t` (adding trades after t does not change the favorite or the entry).

2. **The fill (lines 199 to 206, used at 238 and 245 to 248).** The fill is the one place that is *meant* to read the future, and it is bounded on both sides: no earlier than t + 1 s (line 201, `lo`, the latency, so the trade that triggered the decision cannot be the fill) and no later than t + 5 min (`hi`). It reads only the leg's own market (`d["_tr"][team]`) and only the first such trade (line 205). Nothing from the fill feeds back into the decision: `decide` (lines 209 to 227) has already returned before `first_fill` is called. Tests: `test_fill_is_first_trade_after_latency_plus_cent` (a trade 0.5 s after t is ignored), `test_fill_exactly_at_t_plus_latency_counts`, `test_no_trade_within_5_min_after_t_skips`.

3. **The settlement and whole-file checks (lines 242 to 243, 249, 269 to 274).** The game result is known only after the game, so it must never decide whether or what to enter. It is read only at line 242 (skip if unsettled) and line 249 (payout), both after the entry decision and the fill are fixed; theta, the favorite and the fill do not depend on it. The unsettled skip uses whether a result exists, not its value (0 training games are unsettled after the scalar step). The missing-market check at lines 269 to 274 looks at the whole trade file, including rows after t. That is safe: if a market's only rows are after t, the game would be skipped anyway at line 215 (no pre-decision price on both markets), so the check can only change the skip reason, never turn a skip into a trade or change a trade. The scalar settlement step (lines 118 to 136) uses only Kalshi's settlement fields. Tests: `test_staleness_and_away_favorite_and_tie`, `test_scalar_settlement_step_on_the_four_blank_games`, `test_game_with_one_missing_market_is_excluded_not_traded`.

## Points for your line-by-line review (not bugs found, choices to confirm)

- Line 223: staleness is checked on the favorite's market only. The underdog's as-of price (line 213) can be old. It decides which team is the favorite, so a stale underdog price could flip the favorite choice. v3 states staleness for the favorite only; this follows it.
- Line 96: the season of a kickoff is its ET year, minus 1 for January and February (playoffs). A March to July game would count as the new season; there are none in NFL training.
- Lines 201 to 202: the fill window ends at t + 5 min = the ESPN kickoff, so no fill happens after kickoff.
- Line 248: the cap is 0.99 for every training market (all 2,534 at a 0.01 step), so `fill_capped` is the same as the earlier fixed cap on this data.
- Line 147 to 148: the away market is matched by the last hyphen piece of its code ("M-OH" matches "OH"). If an event ever had two other markets ending the same way, the game is excluded (line 149), not guessed.
