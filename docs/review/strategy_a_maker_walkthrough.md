# strategy_a_maker.py walkthrough (Rule-7 review packet)

File: strategy_a_maker.py at 4ea3e46 (branch t15-final), 128 lines. Strategy A-maker (v3 Amendment 5 draft). The decision is strategy_a.decide unchanged (reviewed in strategy_a_walkthrough.md); this file adds only the limit order, its conservative fill and the maker costs.

Tags at line end: **[TIME]** touches decision time, fill time, windows, outages or timestamps. **[MONEY]** touches price, fee, spread, threshold or P&L. Tests per block: every test that calls a function defined in the block.

## Lines 1 to 29

Module docstring: Strategy A's decision at theta 0.80, a limit buy at the as-of price - 1 cent, filled only on a trade-through one tick below the limit in (t + 1 s, kickoff], held to settlement; Webull primary and the Kalshi TAKER formula as an upper-bound comparison (maker fee not confirmed first-party); same-rule underdog placebo.

```python
  1  """Strategy A-maker (HYPOTHESIS_v3.md Amendment 5 draft): Strategy A's decision with a resting limit order.
  2
  3  Rule-7 file: written on branch t20-amaker, reviewed line by line by Divi (docs/review/strategy_a_maker_walkthrough.md).
  4
  5  Per game, theta = 0.80 fixed (no grid):
  6    Decision: exactly Strategy A's (strategy_a.decide): t = ESPN kickoff - 5 min; each team's own-market price =            [TIME]
  7      trailing 3 s median of trades, as-of t; both markets must have traded in (t - 10 min, t]; favorite = higher           [TIME] [MONEY]
  8      price; enter iff the favorite's price >= theta. Same seal, ESPN-kickoff, missing-market and exclusion skips.
  9    Order: limit buy on the leg's own market at L = (as-of price at t) - 0.01, rounded to the market's tick.
 10    Fill (conservative, queue-agnostic): filled at L only if a trade on that market prints at <= L - 0.01 in                [MONEY]
 11      (t + 1 s, kickoff]; otherwise unfilled: no trade, counted ("unfilled"). A print AT L does not count (we may be        [TIME] [MONEY]
 12      behind the queue); only a trade-through one tick below proves our order would have traded.                            [TIME] [MONEY]
 13    Hold to settlement (Kalshi's recorded result; ties and scalar settlements as Strategy A).
 14    Costs: Webull $0.02 per contract (primary, entry only). Comparison line: Kalshi's maker fee is NOT confirmed            [MONEY]
 15      first-party (kalshi.com/docs/kalshi-fee-schedule.pdf returned HTTP 429 on 2026-10-03; secondary sources state         [MONEY]
 16      0.0175 x C x P x (1 - P) rounded up, and not every market charges it), so the comparison line uses the TAKER          [MONEY]
 17      formula 0.07 x C x P x (1 - P) rounded up as an upper bound, labelled "direct (taker formula, upper bound)".          [MONEY]
 18    Placebo: the underdog's own market with the same maker rule (L = underdog as-of price - 0.01), when the                 [MONEY]
 19      favorite passes theta.
 20  No prices are printed. Sealed games (kickoff >= 2026-08-01) are refused unless final_test=True.
 21  """
 22  from __future__ import annotations
 23
 24  import math
 25
 26  import pandas as pd
 27
 28  import strategy_a as A
 29
```

Tests: none (constants/docstring)

## Lines 30 to 54

Constants (theta 0.80, 1 cent offset, 1 s latency); limit_price: (as-of - 1 cent) rounded to the tick; maker_fill: first own-market trade strictly after t + 1 s and at or before kickoff whose price is at or below L - 1 tick; _row: the skip row.

```python
 30  NS = 1_000_000_000
 31  THETA = 0.80
 32  LIMIT_OFFSET = 0.01          # L = as-of price at t - 1 cent                                                         [MONEY]
 33  LATENCY_S = 1.0              # fills only from trades strictly after t + 1 s (same latency as A)                     [TIME]
 34  EPS = 1e-9
 35
 36
 37  def limit_price(asof: float, tick: float) -> float:                                                                  [MONEY]
 38      """(as-of price - 1 cent) rounded to the market tick."""                                                         [MONEY]
 39      return round(round((asof - LIMIT_OFFSET) / tick) * tick, 4)                                                      [MONEY]
 40
 41
 42  def maker_fill(tr: pd.DataFrame, t_ns: int, kickoff_ns: int, limit: float, tick: float) -> int | None:               [TIME] [MONEY]
 43      """Timestamp of the first trade on the leg's own market with ts in (t + 1 s, kickoff] at a price <= L - 1 tick   [TIME] [MONEY]
 44      (a trade-through), else None. tr = the leg's own-market trades (ts, own YES price)."""                           [TIME]
 45      lo = t_ns + int(LATENCY_S * NS)                                                                                  [TIME]
 46      w = tr[(tr["ts"] > lo) & (tr["ts"] <= kickoff_ns) & (tr["price"] <= limit - tick + EPS)]                         [TIME] [MONEY]
 47      return int(w["ts"].iloc[0]) if len(w) else None                                                                  [TIME]
 48
 49
 50  def _row(g: A.Game, placebo: bool, team, skip: str) -> dict:
 51      return {"game_id": g.game_id, "league": g.league, "theta": THETA, "placebo": placebo, "team": team,
 52              "attempted": False, "entered": False, "skip": skip, "preseason": A.is_preseason(g)}
 53
 54
```

Tests: `test_strategy_a_maker.py::test_limit_rounding_and_costs_x2`, `test_strategy_a_maker.py::test_decision_unchanged_from_a_and_theta_fixed (via evaluate_game)`, `test_strategy_a_maker.py::test_fill_only_on_trade_through (via evaluate_game)`, `test_strategy_a_maker.py::test_no_fill_from_trade_before_t_plus_1s_or_after_kickoff (via evaluate_game)`, `test_strategy_a_maker.py::test_unfilled_counted_and_placebo_same_rule (via evaluate_game)`

## Lines 55 to 82

_leg: decision skip; theta check on the favorite; the limit (skip if it falls outside the price grid); attempted; unsettled skip; the trade-through fill or 'unfilled'; payout from the settlement (tie 0.5); Webull and taker-formula fees at L; P&L and return on capital.

```python
 55  def _leg(d: dict, g: A.Game, team: str, asof: float, placebo: bool) -> dict:
 56      row = _row(g, placebo, team, d["skip"])
 57      if d["skip"]:
 58          return row
 59      if d["fav_px"] < THETA:                                                                                       [MONEY]
 60          row["skip"] = "below theta"
 61          return row
 62      tick = g.tick.get(team, A.DEFAULT_TICK)                                                                       [MONEY]
 63      lim = limit_price(asof, tick)                                                                                 [MONEY]
 64      if lim < tick - EPS or lim > 1 - tick + EPS:                                                                  [MONEY]
 65          row["skip"] = "limit outside the price grid"
 66          return row
 67      row.update(attempted=True, limit_price=lim)
 68      if g.result != g.result:                                                                                      [TIME]
 69          row["skip"] = "unsettled"                                                                                 [TIME]
 70          return row
 71      fill_ts = maker_fill(d["_tr"][team], d["t_ns"], g.kickoff.value, lim, tick)                                   [TIME]
 72      if fill_ts is None:                                                                                           [TIME]
 73          row["skip"] = "unfilled"                                                                                  [TIME]
 74          return row
 75      team_result = g.result if team == g.home else 1.0 - g.result       # tie stays 0.5                            [MONEY]
 76      fw, fd = A.fee_webull(lim), A.fee_kalshi_direct(lim)                                                          [MONEY]
 77      gross = (team_result - lim) * A.QTY                                                                           [MONEY]
 78      row.update(entered=True, fill_ts=fill_ts, fill_price=lim, payout=team_result, fee_webull=fw, fee_direct=fd,   [MONEY]
 79                 pnl_webull=gross - fw, pnl_direct=gross - fd,                                                      [MONEY]
 80                 roc_webull=(gross - fw) / (lim * A.QTY + fw), roc_direct=(gross - fd) / (lim * A.QTY + fd))        [MONEY]
 81      return row
 82
```

Tests: `test_strategy_a_maker.py::test_decision_unchanged_from_a_and_theta_fixed (via evaluate_game)`, `test_strategy_a_maker.py::test_fill_only_on_trade_through (via evaluate_game)`, `test_strategy_a_maker.py::test_no_fill_from_trade_before_t_plus_1s_or_after_kickoff (via evaluate_game)`, `test_strategy_a_maker.py::test_unfilled_counted_and_placebo_same_rule (via evaluate_game)`

## Lines 84 to 112

evaluate_game: seal guard, ESPN-only kickoffs, load-time exclusion, missing-market exclusion, Strategy A's decision, then the favorite leg and the underdog placebo leg. costs_x2: fees x2 and the fill 1 cent worse on the same fill set.

```python
 84  def evaluate_game(trades: pd.DataFrame, g: A.Game, final_test: bool = False) -> list[dict]:                      [TIME]
 85      """One row for the favorite leg and one for the underdog placebo leg (theta 0.80)."""
 86      if g.kickoff >= A.SEAL and not final_test:                                                                   [TIME]
 87          raise ValueError(f"{g.game_id}: kickoff on/after 2026-08-01 is sealed (needs final_test)")               [TIME]
 88      if g.kickoff_source not in A.KICKOFF_SOURCES:
 89          return [_row(g, p, None, f"kickoff not from ESPN ({g.kickoff_source})") for p in (False, True)]
 90      if g.exclude:
 91          return [_row(g, p, None, g.exclude) for p in (False, True)]
 92      present = set(trades.loc[trades["kind"] == "trade", "market_id"].unique()) if len(trades) else set()
 93      missing = [f"{g.event}-{t}" for t in (g.home, g.away) if f"{g.event}-{t}" not in present]
 94      if missing:
 95          return [_row(g, p, None, f"missing market ({', '.join(missing)}: no rows in the trade file)")
 96                  for p in (False, True)]
 97      d = A.decide(trades, g)
 98      if d["skip"]:
 99          return [_row(g, p, None, d["skip"]) for p in (False, True)]
100      return [_leg(d, g, d["fav"], d["fav_px"], placebo=False), _leg(d, g, d["dog"], d["dog_px"], placebo=True)]
101
102
103  def costs_x2(e: pd.DataFrame) -> pd.DataFrame:                                                                   [MONEY]
104      """Costs x2 for the maker line: fees x2 and the fill one tick (1 cent) worse, same fill set."""              [MONEY]
105      p2 = (e["fill_price"] + 0.01).clip(upper=0.99)                                                               [MONEY]
106      fw = 2 * p2.map(A.fee_webull)                                                                                [MONEY]
107      fd = 2 * p2.map(A.fee_kalshi_direct)                                                                         [MONEY]
108      gross = (e["payout"] - p2) * A.QTY                                                                           [MONEY]
109      return e.assign(fill_price=p2, pnl_webull=gross - fw, pnl_direct=gross - fd,                                 [MONEY]
110                      roc_webull=(gross - fw) / (p2 * A.QTY + fw), roc_direct=(gross - fd) / (p2 * A.QTY + fd))    [MONEY]
111
112
```

Tests: `test_strategy_a_maker.py::test_decision_unchanged_from_a_and_theta_fixed`, `test_strategy_a_maker.py::test_fill_only_on_trade_through`, `test_strategy_a_maker.py::test_limit_rounding_and_costs_x2`, `test_strategy_a_maker.py::test_no_fill_from_trade_before_t_plus_1s_or_after_kickoff`, `test_strategy_a_maker.py::test_unfilled_counted_and_placebo_same_rule`

## Lines 113 to 128

summarize: per leg, games, attempts, fills, fill rate, unfilled count, mean fill, win rate, win rate minus fill, mean ROC (Webull, taker-formula upper bound), total P&L.

```python
113  def summarize(rows: pd.DataFrame) -> pd.DataFrame:
114      out = []
115      for pl, r in rows.groupby("placebo"):
116          a = r[r["attempted"].astype(bool)]
117          e = r[r["entered"].astype(bool)]
118          out.append({"leg": "placebo (underdog)" if pl else "favorite", "games": len(r), "attempts": len(a),
119                      "fills": len(e), "fill_rate": len(e) / len(a) if len(a) else math.nan,
120                      "unfilled": int((r["skip"] == "unfilled").sum()),
121                      "mean_fill": e["fill_price"].mean() if len(e) else math.nan,
122                      "win_rate": e["payout"].mean() if len(e) else math.nan,
123                      "win_minus_fill": (e["payout"].mean() - e["fill_price"].mean()) if len(e) else math.nan,
124                      "roc_webull": e["roc_webull"].mean() if len(e) else math.nan,
125                      "roc_direct_taker_upper": e["roc_direct"].mean() if len(e) else math.nan,
126                      "pnl_webull": e["pnl_webull"].sum() if len(e) else 0.0,
127                      "pnl_direct_taker_upper": e["pnl_direct"].sum() if len(e) else 0.0})
128      return pd.DataFrame(out)
```

Tests: `test_strategy_a_maker.py::test_unfilled_counted_and_placebo_same_rule`

## Where a lookahead could hide, and why each is safe

1. **The limit price (lines 37 to 39, 63).** L comes from the leg's as-of price at t, the same backward trailing 3 s median Strategy A uses (strategy_a.asof_median: trades with ts <= t only). Nothing after t sets the order. Test: `test_decision_unchanged_from_a_and_theta_fixed`.

2. **The fill (lines 42 to 47, 71).** The fill window is (t + 1 s, kickoff]: strictly after the 1 s latency, so the trades that formed the decision price and any trade inside the latency cannot fill us, and nothing after kickoff (when the order would be cancelled or the book wiped) counts. The fill needs a trade-through at or below L - 1 tick, which is the conservative, queue-agnostic rule: a print AT L may be someone ahead of us in the queue. Tests: `test_fill_only_on_trade_through`, `test_no_fill_from_trade_before_t_plus_1s_or_after_kickoff`.

3. **Settlement (lines 68 to 70, 75).** The result is read only to decide unsettled (whether a result exists) and the payout, after the order and its fill are fixed. Unfilled orders are counted, never dropped silently. Test: `test_unfilled_counted_and_placebo_same_rule`.

## Points for your line-by-line review (choices to confirm)

- Line 39: an as-of price that is a half tick (a 3 s median of two trades can be x.5 cents) puts L exactly on a half tick; Python rounds half to even. Rounding DOWN would be the more conservative buy; not changed.
- Line 46: the trade-through rule means a fill only happens when the market trades below our limit, i.e. when the price is moving against the position. This is the adverse-selection cost of resting orders and is what the placebo shows on training (every underdog fill lost).
- Line 64: a limit below one tick (underdog as-of 0.01) is not placed and is counted ("limit outside the price grid"; 6 placebo legs on training).
- Lines 76 to 80: the comparison line uses the TAKER formula as an upper bound; Kalshi's maker fee (secondary sources: 0.0175 x C x P x (1 - P), rounded up, on some markets) is not confirmed first-party.
- Lines 103 to 110: costs x2 for a maker order = fees x2 and the fill 1 cent worse (the analog of the taker's doubled half-spread), keeping the same fill set.
- Theta is fixed at 0.80 (no grid, one variant: favorite + placebo legs).
