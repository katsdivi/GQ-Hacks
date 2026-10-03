"""Strategy A (HYPOTHESIS_v3.md, with Amendment 1 committed 9507d6a): Kalshi favorite-longshot, hold to settlement.

Rule-7 file (same review rule as strategy.py): written on a branch, reviewed line by line by Divi before main.

Per game and theta:
  t = ESPN kickoff - 5 min.
  Decision (backward as-of only, rows with ts <= t): each team's OWN market price = trailing 3 s median of
    that market's trade prices, last value at or before t (align.trade_median_events). Favorite = higher
    own-market price. Skip if the favorite's market has no trade in [t - 10 min, t] (staleness). Enter iff
    favorite price >= theta.
  Fill (Amendment 1 section 4): first trade on the favorite's own market at or after t + 1.0 s, plus 1 cent
    half-spread. No such trade within 5 min after t -> skip, reason "no post-decision trade".
  Settlement: $1 per contract if the favorite wins, $0 if it loses, $0.5 on a tie (docs/strategy_a_rules.md).
  Costs (v3 line 20): Webull $0.02 per contract per fill, entry only (primary); Kalshi direct
    0.07 x C x P x (1 - P) rounded up to the cent per order (comparison). Settlement fee 0.
  Placebo: buy the underdog's own market under the same decision and the same fill rule.

Input trades follow the tick contract (price = P(home wins)); the away team's own-market price is 1 - price
on rows of the away market. No prices are printed. Sealed games (kickoff >= 2026-08-01) are refused unless
final_test=True.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

import align

NS = 1_000_000_000
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
THETAS = (0.70, 0.80, 0.90)
QTY = 10
ENTRY_BEFORE_KICKOFF_S = 5 * 60
STALE_S = 10 * 60
LATENCY_S = 1.0               # docs/spec_provisional.md default latency
FILL_WINDOW_S = 5 * 60        # Amendment 1 section 4: no trade within 5 min after t -> skip
HALF_SPREAD = 0.01            # v3: as-of price + 1 cent
MEDIAN_WINDOW_S = 3.0
MIN_TRADES_SELECT = 50        # v3 selection: thetas with at least 50 trades
WEBULL_PER_CONTRACT = 0.02
KALSHI_DIRECT_RATE = 0.07
KICKOFF_SOURCES = ("espn", "espn_event_id")   # ESPN only (v3, docs/strategy_a_rules.md)


def fee_webull(price: float, qty: int = QTY) -> float:
    return WEBULL_PER_CONTRACT * qty


def fee_kalshi_direct(price: float, qty: int = QTY) -> float:
    raw = KALSHI_DIRECT_RATE * qty * price * (1 - price)
    return math.ceil(round(raw * 100, 9)) / 100       # round up to the cent per order


@dataclass
class Game:
    game_id: str
    league: str
    home: str              # Kalshi team codes; market ids are f"{event}-{code}"
    away: str
    event: str
    kickoff: pd.Timestamp  # ESPN kickoff, UTC
    kickoff_source: str
    result: float          # home win 1.0 / home loss 0.0 / tie 0.5 / NaN unsettled


def own_market_trades(trades: pd.DataFrame, g: Game, team: str) -> pd.DataFrame:
    """That team's own market, as its own YES price (flip back from P(home) for the away market)."""
    t = trades[(trades["market_id"] == f"{g.event}-{team}") & (trades["kind"] == "trade")]
    t = t[["ts", "price"]].sort_values("ts", kind="stable")
    if team == g.away:
        t = t.assign(price=1.0 - t["price"])
    return t.reset_index(drop=True)


def asof_median(tr: pd.DataFrame, t_ns: int) -> float:
    """Trailing 3 s median of trade prices, last value at or before t (backward as-of)."""
    past = tr[tr["ts"] <= t_ns]
    if past.empty:
        return float("nan")
    ev = align.trade_median_events(past.assign(venue="k", kind="trade"), "k", MEDIAN_WINDOW_S)
    return float(ev["price"].iloc[-1])


def first_fill(tr: pd.DataFrame, t_ns: int) -> tuple[int, float] | None:
    """First trade at or after t + latency and within FILL_WINDOW_S after t."""
    lo, hi = t_ns + int(LATENCY_S * NS), t_ns + FILL_WINDOW_S * NS
    after = tr[(tr["ts"] >= lo) & (tr["ts"] <= hi)]
    if after.empty:
        return None
    r = after.iloc[0]
    return int(r["ts"]), float(r["price"])


def decide(trades: pd.DataFrame, g: Game) -> dict:
    """Theta-free part of the decision: favorite, as-of prices, staleness. Uses rows with ts <= t only."""
    t_ns = (g.kickoff - pd.Timedelta(seconds=ENTRY_BEFORE_KICKOFF_S)).value
    tr = {team: own_market_trades(trades, g, team) for team in (g.home, g.away)}
    px = {team: asof_median(tr[team], t_ns) for team in tr}
    out = {"game_id": g.game_id, "league": g.league, "t_ns": t_ns, "skip": ""}
    if any(math.isnan(p) for p in px.values()):
        out["skip"] = "no pre-decision price on both markets"
        return out
    if px[g.home] == px[g.away]:
        out["skip"] = "no favorite (equal prices)"
        return out
    fav = g.home if px[g.home] > px[g.away] else g.away
    dog = g.away if fav == g.home else g.home
    recent = tr[fav][(tr[fav]["ts"] > t_ns - STALE_S * NS) & (tr[fav]["ts"] <= t_ns)]
    if recent.empty:
        out["skip"] = "stale (no favorite trade in the 10 min before t)"
    out.update(fav=fav, dog=dog, fav_px=px[fav], dog_px=px[dog], _tr=tr)
    return out


def _leg(d: dict, g: Game, team: str, theta: float, placebo: bool) -> dict:
    row = {"game_id": g.game_id, "league": g.league, "theta": theta, "placebo": placebo,
           "team": team, "entered": False, "skip": d["skip"]}
    if d["skip"]:
        return row
    if d["fav_px"] < theta:
        row["skip"] = "below theta"
        return row
    fill = first_fill(d["_tr"][team], d["t_ns"])
    if fill is None:
        row["skip"] = "no post-decision trade"
        return row
    if g.result != g.result:
        row["skip"] = "unsettled"
        return row
    fill_ts, trade_px = fill
    price = trade_px + HALF_SPREAD
    team_result = g.result if team == g.home else 1.0 - g.result       # tie stays 0.5
    fw, fd = fee_webull(price), fee_kalshi_direct(price)
    gross = (team_result - price) * QTY
    row.update(entered=True, fill_ts=fill_ts, fill_price=price, payout=team_result,
               fee_webull=fw, fee_direct=fd, pnl_webull=gross - fw, pnl_direct=gross - fd,
               roc_webull=(gross - fw) / (price * QTY + fw), roc_direct=(gross - fd) / (price * QTY + fd))
    return row


def evaluate_game(trades: pd.DataFrame, g: Game, thetas=THETAS, final_test: bool = False) -> list[dict]:
    """One row per theta for the favorite leg and one for the underdog placebo leg."""
    if g.kickoff >= SEAL and not final_test:
        raise ValueError(f"{g.game_id}: kickoff on/after 2026-08-01 is sealed (needs final_test)")
    if g.kickoff_source not in KICKOFF_SOURCES:
        return [{"game_id": g.game_id, "league": g.league, "theta": th, "placebo": p, "entered": False,
                 "skip": f"kickoff not from ESPN ({g.kickoff_source})"} for th in thetas for p in (False, True)]
    d = decide(trades, g)
    rows = []
    for th in thetas:
        rows.append(_leg(d, g, d.get("fav"), th, placebo=False))
        rows.append(_leg(d, g, d.get("dog"), th, placebo=True))
    return rows


def summarize(rows: pd.DataFrame) -> pd.DataFrame:
    """Per theta and leg: trades, mean return on capital, skip counts (incl. no post-decision trade)."""
    out = []
    for (th, pl), r in rows.groupby(["theta", "placebo"]):
        e = r[r["entered"]]
        out.append({"theta": th, "placebo": pl, "n_trades": len(e),
                    "roc_webull_mean": e["roc_webull"].mean() if len(e) else float("nan"),
                    "roc_direct_mean": e["roc_direct"].mean() if len(e) else float("nan"),
                    "skipped_no_post_decision_trade": int((r["skip"] == "no post-decision trade").sum()),
                    "skipped_stale": int(r["skip"].str.startswith("stale").sum()),
                    "skipped_other": int((~r["entered"] & ~r["skip"].isin(["below theta", "no post-decision trade"])
                                          & ~r["skip"].str.startswith("stale")).sum())})
    return pd.DataFrame(out)


def select_theta(summary: pd.DataFrame) -> float | None:
    """v3: best mean return on capital on train among thetas with at least 50 trades (favorite leg, Webull line)."""
    s = summary[(~summary["placebo"]) & (summary["n_trades"] >= MIN_TRADES_SELECT)]
    if s.empty:
        return None
    return float(s.sort_values(["roc_webull_mean", "theta"], ascending=[False, True]).iloc[0]["theta"])
