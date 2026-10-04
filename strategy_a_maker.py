"""Strategy A-maker (HYPOTHESIS_v3.md Amendment 5 draft): Strategy A's decision with a resting limit order.

Rule-7 file: written on branch t20-amaker, reviewed line by line by Divi (docs/review/strategy_a_maker_walkthrough.md).

Per game, theta = 0.80 fixed (no grid):
  Decision: exactly Strategy A's (strategy_a.decide): t = ESPN kickoff - 5 min; each team's own-market price =
    trailing 3 s median of trades, as-of t; both markets must have traded in (t - 10 min, t]; favorite = higher
    price; enter iff the favorite's price >= theta. Same seal, ESPN-kickoff, missing-market and exclusion skips.
  Order: limit buy on the leg's own market at L = (as-of price at t) - 0.01, rounded to the market's tick.
  Fill (conservative, queue-agnostic): filled at L only if a trade on that market prints at <= L - 0.01 in
    (t + 1 s, kickoff]; otherwise unfilled: no trade, counted ("unfilled"). A print AT L does not count (we may be
    behind the queue); only a trade-through one tick below proves our order would have traded.
  Hold to settlement (Kalshi's recorded result; ties and scalar settlements as Strategy A).
  Costs: Webull $0.02 per contract (primary, entry only). Comparison line: Kalshi's maker fee is NOT confirmed
    first-party (kalshi.com/docs/kalshi-fee-schedule.pdf returned HTTP 429 on 2026-10-03; secondary sources state
    0.0175 x C x P x (1 - P) rounded up, and not every market charges it), so the comparison line uses the TAKER
    formula 0.07 x C x P x (1 - P) rounded up as an upper bound, labelled "direct (taker formula, upper bound)".
  Placebo: the underdog's own market with the same maker rule (L = underdog as-of price - 0.01), when the
    favorite passes theta.
No prices are printed. Sealed games (kickoff >= 2026-08-01) are refused unless final_test=True.
"""
from __future__ import annotations

import math

import pandas as pd

import strategy_a as A

NS = 1_000_000_000
THETA = 0.80
LIMIT_OFFSET = 0.01          # L = as-of price at t - 1 cent
LATENCY_S = 1.0              # fills only from trades strictly after t + 1 s (same latency as A)
EPS = 1e-9


def limit_price(asof: float, tick: float) -> float:
    """(as-of price - 1 cent) rounded to the market tick."""
    return round(round((asof - LIMIT_OFFSET) / tick) * tick, 4)


def maker_fill(tr: pd.DataFrame, t_ns: int, kickoff_ns: int, limit: float, tick: float) -> int | None:
    """Timestamp of the first trade on the leg's own market with ts in (t + 1 s, kickoff] at a price <= L - 1 tick
    (a trade-through), else None. tr = the leg's own-market trades (ts, own YES price)."""
    lo = t_ns + int(LATENCY_S * NS)
    w = tr[(tr["ts"] > lo) & (tr["ts"] <= kickoff_ns) & (tr["price"] <= limit - tick + EPS)]
    return int(w["ts"].iloc[0]) if len(w) else None


def _row(g: A.Game, placebo: bool, team, skip: str) -> dict:
    return {"game_id": g.game_id, "league": g.league, "theta": THETA, "placebo": placebo, "team": team,
            "attempted": False, "entered": False, "skip": skip, "preseason": A.is_preseason(g)}


def _leg(d: dict, g: A.Game, team: str, asof: float, placebo: bool) -> dict:
    row = _row(g, placebo, team, d["skip"])
    if d["skip"]:
        return row
    if d["fav_px"] < THETA:
        row["skip"] = "below theta"
        return row
    tick = g.tick.get(team, A.DEFAULT_TICK)
    lim = limit_price(asof, tick)
    if lim < tick - EPS or lim > 1 - tick + EPS:
        row["skip"] = "limit outside the price grid"
        return row
    row.update(attempted=True, limit_price=lim)
    if g.result != g.result:
        row["skip"] = "unsettled"
        return row
    fill_ts = maker_fill(d["_tr"][team], d["t_ns"], g.kickoff.value, lim, tick)
    if fill_ts is None:
        row["skip"] = "unfilled"
        return row
    team_result = g.result if team == g.home else 1.0 - g.result       # tie stays 0.5
    fw, fd = A.fee_webull(lim), A.fee_kalshi_direct(lim)
    gross = (team_result - lim) * A.QTY
    row.update(entered=True, fill_ts=fill_ts, fill_price=lim, payout=team_result, fee_webull=fw, fee_direct=fd,
               pnl_webull=gross - fw, pnl_direct=gross - fd,
               roc_webull=(gross - fw) / (lim * A.QTY + fw), roc_direct=(gross - fd) / (lim * A.QTY + fd))
    return row


def evaluate_game(trades: pd.DataFrame, g: A.Game, final_test: bool = False) -> list[dict]:
    """One row for the favorite leg and one for the underdog placebo leg (theta 0.80)."""
    if g.kickoff >= A.SEAL and not final_test:
        raise ValueError(f"{g.game_id}: kickoff on/after 2026-08-01 is sealed (needs final_test)")
    if g.kickoff_source not in A.KICKOFF_SOURCES:
        return [_row(g, p, None, f"kickoff not from ESPN ({g.kickoff_source})") for p in (False, True)]
    if g.exclude:
        return [_row(g, p, None, g.exclude) for p in (False, True)]
    present = set(trades.loc[trades["kind"] == "trade", "market_id"].unique()) if len(trades) else set()
    missing = [f"{g.event}-{t}" for t in (g.home, g.away) if f"{g.event}-{t}" not in present]
    if missing:
        return [_row(g, p, None, f"missing market ({', '.join(missing)}: no rows in the trade file)")
                for p in (False, True)]
    d = A.decide(trades, g)
    if d["skip"]:
        return [_row(g, p, None, d["skip"]) for p in (False, True)]
    return [_leg(d, g, d["fav"], d["fav_px"], placebo=False), _leg(d, g, d["dog"], d["dog_px"], placebo=True)]


def costs_x2(e: pd.DataFrame) -> pd.DataFrame:
    """Costs x2 for the maker line: fees x2 and the fill one tick (1 cent) worse, same fill set."""
    p2 = (e["fill_price"] + 0.01).clip(upper=0.99)
    fw = 2 * p2.map(A.fee_webull)
    fd = 2 * p2.map(A.fee_kalshi_direct)
    gross = (e["payout"] - p2) * A.QTY
    return e.assign(fill_price=p2, pnl_webull=gross - fw, pnl_direct=gross - fd,
                    roc_webull=(gross - fw) / (p2 * A.QTY + fw), roc_direct=(gross - fd) / (p2 * A.QTY + fd))


def summarize(rows: pd.DataFrame) -> pd.DataFrame:
    out = []
    for pl, r in rows.groupby("placebo"):
        a = r[r["attempted"].astype(bool)]
        e = r[r["entered"].astype(bool)]
        out.append({"leg": "placebo (underdog)" if pl else "favorite", "games": len(r), "attempts": len(a),
                    "fills": len(e), "fill_rate": len(e) / len(a) if len(a) else math.nan,
                    "unfilled": int((r["skip"] == "unfilled").sum()),
                    "mean_fill": e["fill_price"].mean() if len(e) else math.nan,
                    "win_rate": e["payout"].mean() if len(e) else math.nan,
                    "win_minus_fill": (e["payout"].mean() - e["fill_price"].mean()) if len(e) else math.nan,
                    "roc_webull": e["roc_webull"].mean() if len(e) else math.nan,
                    "roc_direct_taker_upper": e["roc_direct"].mean() if len(e) else math.nan,
                    "pnl_webull": e["pnl_webull"].sum() if len(e) else 0.0,
                    "pnl_direct_taker_upper": e["pnl_direct"].sum() if len(e) else 0.0})
    return pd.DataFrame(out)
