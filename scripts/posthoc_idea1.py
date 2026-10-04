"""IDEA 1, Kalshi complement lag. POST-HOC, EXPLORATORY (formed after seeing the holdout).

Spec: results/posthoc_latency/SPEC_idea1.md (committed before this script ran on real data).
At each Kalshi book update of either team market, test whether buying both YES (or both NO) at the asks clears
1.00 after fees (C = 10 per leg). On the first update of each clearing run, while no position is held in the
game, attempt both legs at the first snapshot of each market received at or after t + L. Hold to settlement.

Usage: python scripts/posthoc_idea1.py   (writes results/posthoc_latency/idea1_results.csv and idea1_RESULTS.md)
"""
from __future__ import annotations

import glob
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import costs

NS = 1_000_000_000
SIZE = 10                       # intended contracts per leg (clearing test and size cap)
LATENCIES = (0.25, 0.5, 1.0)
SCHEDULES = ("direct", "webull")
PRIMARY = "direct"
KO_PRE_S, KO_POST_S = 2 * 60, 20 * 60
SEED_S = 6 * 3600               # rows loaded before window_start to seed book state
TAIL_S = 3600                   # rows loaded after window_end (unwind quotes only)
N_BOOT, BOOT_SEED = 2000, 20261003
LABEL = "POST-HOC, EXPLORATORY (formed after seeing the holdout)"

SRC = Path("/Users/divyamkataria/GQ HACKS/staleline")
OUT = Path("results/posthoc_latency")


# ---------------------------------------------------------------- pure pieces (unit tested)

def p4(x):
    """Prices to integer units of 1/10000 dollar."""
    return np.rint(np.asarray(x, dtype=float) * 10000).astype(np.int64)


def fee_units_10(price4: np.ndarray, schedule: str) -> np.ndarray:
    """Fee for one order of SIZE = 10 contracts, in 1/10000 dollar units, exact integer arithmetic.
    direct: ceil to the cent of 0.07 x 10 x P x (1 - P). webull: 0.02 x 10."""
    price4 = np.asarray(price4, dtype=np.int64)
    if schedule == "direct":
        num = 70 * price4 * (10000 - price4)          # fee in cents = num / 1e8
        cents = -(-num // 100_000_000)
        return cents * 100
    if schedule == "webull":
        return np.full(price4.shape, 2000, dtype=np.int64)
    raise ValueError(schedule)


def clears(pa4: np.ndarray, pb4: np.ndarray, schedule: str) -> np.ndarray:
    """Strict test 10 x (pa + pb) + fee(pa, 10) + fee(pb, 10) < 10.00, vectorized on integer price units.
    NaN prices must be passed as -1 (treated as not clearing)."""
    pa4, pb4 = np.asarray(pa4, dtype=np.int64), np.asarray(pb4, dtype=np.int64)
    ok = (pa4 > 0) & (pa4 < 10000) & (pb4 > 0) & (pb4 < 10000)
    tot = SIZE * (pa4 + pb4) + fee_units_10(np.clip(pa4, 0, 10000), schedule) + \
        fee_units_10(np.clip(pb4, 0, 10000), schedule)
    return ok & (tot < SIZE * 10000)


def order_fee(price: float, qty: float, schedule: str) -> float:
    return costs.fee(price, qty, "buy", "kalshi", route=schedule) if qty > 0 else 0.0


def snapshots(rows: pd.DataFrame, away: bool) -> pd.DataFrame:
    """Own-market top of book per snapshot (rows sharing recv_ns). Input rows are stored P(home) terms
    (kind bid/ask, price, size). Away market de-flip: own_ask = 1 - stored bid (size = stored bid size),
    own_bid = 1 - stored ask (size = stored ask size). Missing side -> NaN. Sorted by recv."""
    r = rows[rows["kind"].isin(["bid", "ask"])]
    if r.empty:
        return pd.DataFrame(columns=["recv_ns", "bid", "bsz", "ask", "asz"])
    w =r.pivot_table(index="recv_ns", columns="kind", values=["price", "size"], aggfunc="last")
    w.columns = [f"{a}_{b}" for a, b in w.columns]
    for c in ("price_bid", "price_ask", "size_bid", "size_ask"):
        if c not in w:
            w[c] = np.nan
    if away:
        out = pd.DataFrame({"bid": 1 - w["price_ask"], "bsz": w["size_ask"],
                            "ask": 1 - w["price_bid"], "asz": w["size_bid"]})
    else:
        out = pd.DataFrame({"bid": w["price_bid"], "bsz": w["size_bid"],
                            "ask": w["price_ask"], "asz": w["size_ask"]})
    out = out.round({"bid": 4, "ask": 4}).sort_index()
    out.index.name = "recv_ns"
    return out.reset_index()


def leg_quote(s: pd.DataFrame, i: int, direction: str) -> tuple[float, float]:
    """(price, size) to buy one leg at snapshot row i. YES: own ask. NO: 1 - own bid, size = own bid size."""
    if direction == "yes":
        return s["ask"].iat[i], s["asz"].iat[i]
    b = s["bid"].iat[i]
    return (round(1 - b, 4) if b == b else np.nan), s["bsz"].iat[i]


def sell_quote(s: pd.DataFrame, i: int, direction: str) -> tuple[float, float]:
    """Price to sell one leg at snapshot row i. YES: own bid. NO: 1 - own ask (the NO bid)."""
    if direction == "yes":
        return s["bid"].iat[i], s["bsz"].iat[i]
    a = s["ask"].iat[i]
    return (round(1 - a, 4) if a == a else np.nan), s["asz"].iat[i]


def first_at_or_after(s: pd.DataFrame, t_ns: int) -> int | None:
    i = int(np.searchsorted(s["recv_ns"].to_numpy(), t_ns, side="left"))
    return i if i < len(s) else None


def signal_table(h: pd.DataFrame, a: pd.DataFrame, lo: int, hi: int, ko_ns: int, schedule: str) -> pd.DataFrame:
    """One row per distinct update time t in [lo, hi) of either market, with each market's last snapshot at
    or before t (never later), and the YES / NO clearing flags. Updates in the kickoff cut never clear."""
    t = np.union1d(h["recv_ns"].to_numpy(), a["recv_ns"].to_numpy())
    t = t[(t >= lo) & (t < hi)]
    ih = np.searchsorted(h["recv_ns"].to_numpy(), t, side="right") - 1
    ia = np.searchsorted(a["recv_ns"].to_numpy(), t, side="right") - 1

    def col(s, idx, c):
        v = s[c].to_numpy(dtype=float)
        out = np.full(len(idx), np.nan)
        m = idx >= 0
        out[m] = v[idx[m]]
        return out

    ah, aa = col(h, ih, "ask"), col(a, ia, "ask")
    bh, ba = col(h, ih, "bid"), col(a, ia, "bid")

    def u(x):
        y = np.where(np.isnan(x), -1, x)
        return np.where(y < 0, -1, p4(np.where(y < 0, 0, y)))

    yes = clears(u(ah), u(aa), schedule)
    no = clears(u(np.where(np.isnan(bh), np.nan, 1 - bh)), u(np.where(np.isnan(ba), np.nan, 1 - ba)), schedule)
    cut = (t >= ko_ns - KO_PRE_S * NS) & (t <= ko_ns + KO_POST_S * NS)
    return pd.DataFrame({"t": t, "yes": yes & ~cut, "no": no & ~cut})


def runs(sig: pd.DataFrame, col: str, hi: int) -> pd.DataFrame:
    """Maximal runs of consecutive clearing updates: start t, end t (first non-clearing update, or hi if the
    run is open at the window end, flagged censored), duration in seconds."""
    f = sig[col].to_numpy()
    t = sig["t"].to_numpy()
    if len(f) == 0:
        return pd.DataFrame(columns=["start", "end", "dur_s", "censored", "dir"])
    prev = np.concatenate([[False], f[:-1]])
    nxt_false = np.concatenate([f[1:], [False]])
    starts = np.flatnonzero(f & ~prev)
    lasts = np.flatnonzero(f & ~nxt_false)
    ends, cens = [], []
    for j in lasts:
        if j + 1 < len(t):
            ends.append(t[j + 1]); cens.append(False)
        else:
            ends.append(hi); cens.append(True)
    st = t[starts]
    return pd.DataFrame({"start": st, "end": ends, "dur_s": (np.array(ends) - st) / NS, "censored": cens,
                         "dir": col})


@dataclass
class Attempt:
    t: int
    direction: str
    executed: bool
    reason: str = ""
    fill_h_ns: int | None = None
    fill_a_ns: int | None = None
    price_h: float = np.nan
    price_a: float = np.nan
    q_h: float = 0.0
    q_a: float = 0.0
    q: float = 0.0
    excess_leg: str = ""
    excess: float = 0.0
    unwind_price: float = np.nan
    unwind_ns: int | None = None


def attempt(h: pd.DataFrame, a: pd.DataFrame, t: int, direction: str, L: float, hi: int,
            schedule: str) -> Attempt:
    """Fill both legs at the first snapshot of each market received at or after t + L (never earlier),
    re-check the clearing test there, size each leg min(10, displayed), unwind the excess at the next quote."""
    tl = t + int(round(L * NS))
    ih, ia = first_at_or_after(h, tl), first_at_or_after(a, tl)
    if ih is None or ia is None or h["recv_ns"].iat[ih] >= hi or a["recv_ns"].iat[ia] >= hi:
        return Attempt(t, direction, False, "no snapshot at or after t+L in window")
    ph, sh = leg_quote(h, ih, direction)
    pa, sa = leg_quote(a, ia, direction)
    at = Attempt(t, direction, False, fill_h_ns=int(h["recv_ns"].iat[ih]), fill_a_ns=int(a["recv_ns"].iat[ia]),
                 price_h=ph, price_a=pa)
    if not (ph == ph and pa == pa and sh == sh and sa == sa and sh > 0 and sa > 0):
        at.reason = "side empty at t+L"
        return at
    if not bool(clears(p4([ph]), p4([pa]), schedule)[0]):
        at.reason = "sum no longer clears at t+L"
        return at
    at.executed = True
    at.q_h, at.q_a = min(SIZE, float(sh)), min(SIZE, float(sa))
    at.q = min(at.q_h, at.q_a)
    if at.q_h != at.q_a:
        leg, s, i0 = ("home", h, ih) if at.q_h > at.q_a else ("away", a, ia)
        at.excess_leg, at.excess = leg, abs(at.q_h - at.q_a)
        for j in range(i0 + 1, len(s)):
            px, _ = sell_quote(s, j, direction)
            if px == px:
                at.unwind_price, at.unwind_ns = px, int(s["recv_ns"].iat[j])
                break
    return at


def position_pnl(at: Attempt, sv_h: float | None, sv_a: float | None, schedule: str) -> float:
    """Net P&L of an executed position. sv_*: settlement value (0..1) of each team's YES market."""
    if sv_h is None or sv_a is None:
        return np.nan
    pay_h = sv_h if at.direction == "yes" else 1 - sv_h        # payout per contract of each leg held
    pay_a = sv_a if at.direction == "yes" else 1 - sv_a
    pnl = at.q * (pay_h + pay_a)
    pnl -= at.q_h * at.price_h + order_fee(at.price_h, at.q_h, schedule)
    pnl -= at.q_a * at.price_a + order_fee(at.price_a, at.q_a, schedule)
    if at.excess > 0:
        if at.unwind_price == at.unwind_price:
            pnl += at.excess * at.unwind_price - order_fee(at.unwind_price, at.excess, schedule)
        else:                                                  # no later quote: excess held to settlement
            pnl += at.excess * (pay_h if at.excess_leg == "home" else pay_a)
    return float(pnl)


def simulate_game(h, a, lo, hi, ko_ns, L, schedule):
    """Returns (runs table, attempts list). At most one executed position per game."""
    sig = signal_table(h, a, lo, hi, ko_ns, schedule)
    ry, rn = runs(sig, "yes", hi), runs(sig, "no", hi)
    rr = pd.concat([ry, rn], ignore_index=True)
    starts = rr.sort_values(["start", "dir"], key=lambda c: c if c.name == "start" else (c != "yes"))
    attempts, done, last_t = [], False, None
    for r in starts.itertuples():
        if done:
            break
        if last_t == r.start:          # YES and NO start at the same update: YES only
            continue
        last_t = r.start
        at = attempt(h, a, int(r.start), r.dir, L, hi, schedule)
        attempts.append(at)
        done = at.executed
    return rr, attempts


# ---------------------------------------------------------------- real data

def load_games():
    w = pd.read_csv("data/live/holdout_windows.csv")          # windows only (feadc99)
    ok = (w["qualifying"] == True) & ~w["excluded_outage"].astype(bool) & \
        ~w["excluded_no_rows"].astype(bool) & ~w["excluded_no_instrument"].astype(bool)
    w = w[ok].copy()
    nonv = w[w["machine"] != "vultr"]
    print(f"usable rows: {len(w)}; skipped (machine not vultr): {len(nonv)} rows, "
          f"{nonv['game_id'].nunique()} games", flush=True)
    w = w[w["machine"] == "vultr"]
    w["pref"] = (w["venue"] != "polymarket").astype(int)      # dedupe by game_id: polymarket row first
    pg = w.sort_values(["game_id", "pref"]).drop_duplicates("game_id").copy()
    cands = pd.read_csv(SRC / "data/live/holdout_candidates.csv").set_index("game_id")
    pg["kickoff_utc"] = cands.loc[pg["game_id"], "kickoff_utc"].to_numpy()
    ev = json.loads((SRC / "data/vultr/data/live/kalshi_events.json").read_text())
    st = pd.read_csv(SRC / "data/holdout_raw/settlements.csv")
    games = []
    for r in pg.itertuples():
        tk = cands.loc[r.game_id, "kalshi_ticker"]
        if tk not in ev:               # mechanical fix after crash (KeyError): event never seen by the Vultr collector
            print(f"skip {r.game_id}: {tk} not in Vultr kalshi_events.json (no Vultr Kalshi data)", flush=True)
            continue
        away, home, _ = ev[tk]
        assert home == r.game_id.split("_")[-1].upper(), r.game_id
        s = st[(st.game_id == r.game_id) & (st.status == "finalized")]
        sv = {row.ticker: float(row.settlement_value_dollars) for row in s.itertuples()}
        games.append(dict(game_id=r.game_id, home_tk=f"{tk}-{home}", away_tk=f"{tk}-{away}",
                          lo=int(r.window_start_ns), hi=int(r.window_end_ns),
                          ko=pd.Timestamp(r.kickoff_utc).value,
                          sv_h=sv.get(f"{tk}-{home}"), sv_a=sv.get(f"{tk}-{away}")))
    return games


def load_rows(games):
    import pyarrow.dataset as ds
    fs = sorted(glob.glob(str(SRC / "data/vultr/data/live/kalshi/*/*.parquet")))
    tks = sorted({g["home_tk"] for g in games} | {g["away_tk"] for g in games})
    lo = min(g["lo"] for g in games) - SEED_S * NS
    hi = max(g["hi"] for g in games) + TAIL_S * NS
    d = ds.dataset(fs, format="parquet")
    f = ds.field("market_id").isin(tks) & ds.field("kind").isin(["bid", "ask"]) & \
        (ds.field("recv_ns") >= lo) & (ds.field("recv_ns") <= hi)
    t = d.to_table(filter=f, columns=["recv_ns", "market_id", "kind", "price", "size"]).to_pandas()
    t["market_id"] = t["market_id"].astype("category")
    return {k: v for k, v in t.groupby("market_id", observed=True)}


def boot(per_game_pnl: np.ndarray, per_game_trades: list, rng) -> tuple:
    n = len(per_game_pnl)
    tot, mean = np.empty(N_BOOT), np.empty(N_BOOT)
    for b in range(N_BOOT):
        idx = rng.integers(0, n, n)
        tot[b] = per_game_pnl[idx].sum()
        tr = np.concatenate([per_game_trades[i] for i in idx]) if n else np.array([])
        mean[b] = tr.mean() if len(tr) else np.nan
    q = lambda x: (np.nanpercentile(x, 2.5), np.nanpercentile(x, 97.5)) if np.isfinite(x).any() else (np.nan, np.nan)
    return q(tot), q(mean)


def qs(x, ps=(0, 25, 50, 75, 90, 100)):
    x = np.asarray(x, dtype=float)
    return "/".join(f"{np.percentile(x, p):.3g}" for p in ps) if len(x) else ""


def main():
    games = load_games()
    print(f"{LABEL}\ngames (vultr, polymarket.com lead-test windows): {len(games)}", flush=True)
    rows = load_rows(games)
    print(f"loaded {sum(len(v) for v in rows.values())} book rows for {len(rows)} markets", flush=True)
    snaps = {}
    for g in games:
        e = pd.DataFrame(columns=["recv_ns", "kind", "price", "size"])
        snaps[g["game_id"]] = (snapshots(rows.get(g["home_tk"], e), away=False),
                               snapshots(rows.get(g["away_tk"], e), away=True))
    games = [g for g in games if not (snaps[g["game_id"]][0].empty or snaps[g["game_id"]][1].empty)]
    print(f"games with Vultr book rows on both team markets: {len(games)}", flush=True)
    out, trades = [], []
    for sched in SCHEDULES:
        for L in LATENCIES:
            all_runs, pg_pnl, pg_tr, n_att, n_miss, miss_reasons = [], [], [], 0, 0, {}
            ex_rows, unsettled = [], 0
            for g in games:
                h, a = snaps[g["game_id"]]
                if h.empty or a.empty:
                    pg_pnl.append(0.0); pg_tr.append(np.array([])); continue
                rr, ats = simulate_game(h, a, g["lo"], g["hi"], g["ko"], L, sched)
                all_runs.append(rr)
                n_att += len(ats)
                gp, gt = 0.0, []
                for at in ats:
                    if not at.executed:
                        n_miss += 1
                        miss_reasons[at.reason] = miss_reasons.get(at.reason, 0) + 1
                        continue
                    pnl = position_pnl(at, g["sv_h"], g["sv_a"], sched)
                    if pnl == pnl:
                        gp += pnl; gt.append(pnl)
                    else:
                        unsettled += 1
                    ex_rows.append(at)
                    trades.append(dict(label="POST-HOC EXPLORATORY", schedule=sched, latency_s=L,
                                       game_id=g["game_id"], t_signal_ns=at.t, direction=at.direction,
                                       fill_home_ns=at.fill_h_ns, fill_away_ns=at.fill_a_ns,
                                       fill_delay_home_s=(at.fill_h_ns - at.t) / NS - L,
                                       fill_delay_away_s=(at.fill_a_ns - at.t) / NS - L,
                                       price_home=at.price_h, price_away=at.price_a, q_home=at.q_h,
                                       q_away=at.q_a, q_paired=at.q, excess_leg=at.excess_leg,
                                       excess=at.excess, unwind_price=at.unwind_price, net_pnl=pnl))
                pg_pnl.append(gp); pg_tr.append(np.array(gt))
            rr = pd.concat(all_runs, ignore_index=True) if all_runs else pd.DataFrame(columns=["dir", "dur_s"])
            tr = np.concatenate(pg_tr) if pg_tr else np.array([])
            (tlo, thi), (mlo, mhi) = boot(np.array(pg_pnl), pg_tr, np.random.default_rng(BOOT_SEED))
            sd = tr.std(ddof=1) if len(tr) > 1 else np.nan
            delays = [d for at in ex_rows for d in ((at.fill_h_ns - at.t) / NS - L, (at.fill_a_ns - at.t) / NS - L)]
            out.append(dict(label="POST-HOC EXPLORATORY", schedule=sched, latency_s=L, games=len(games),
                            opps_yes=int((rr["dir"] == "yes").sum()), opps_no=int((rr["dir"] == "no").sum()),
                            opps_total=len(rr), attempts=n_att, executed=len(ex_rows), missed=n_miss,
                            missed_reasons="; ".join(f"{k}: {v}" for k, v in sorted(miss_reasons.items())),
                            unsettled_excluded=unsettled,
                            contracts=float(sum(at.q for at in ex_rows)),
                            net_pnl=float(tr.sum()), pnl_ci_lo=tlo, pnl_ci_hi=thi,
                            trade_mean=float(tr.mean()) if len(tr) else np.nan, trade_mean_ci_lo=mlo,
                            trade_mean_ci_hi=mhi, trade_sd=sd,
                            trade_sharpe=float(tr.mean() / sd) if len(tr) > 1 and sd > 0 else np.nan,
                            games_with_trade=int(sum(len(x) > 0 for x in pg_tr)),
                            size_q_min_25_50_75_90_max=qs([at.q for at in ex_rows]),
                            dur_s_min_25_50_75_90_max=qs(rr["dur_s"]) if len(rr) else "",
                            dur_censored=int(rr["censored"].sum()) if len(rr) else 0,
                            fill_delay_s_min_25_50_75_90_max=qs(delays)))
            print(out[-1], flush=True)
    res = pd.DataFrame(out)
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT / "idea1_results.csv", index=False)
    pd.DataFrame(trades).to_csv(OUT / "idea1_trades.csv", index=False)
    write_md(res, len(games))
    print(res.to_string())


def write_md(res: pd.DataFrame, n_games: int):
    def f(x, d=2):
        return "" if x != x else f"{x:.{d}f}"
    lines = ["# IDEA 1 results, Kalshi complement lag. POST-HOC, EXPLORATORY (formed after seeing the holdout)", "",
             "Spec: results/posthoc_latency/SPEC_idea1.md. One run on real data, no changes after output. "
             f"Games: {n_games} (vultr, polymarket.com lead-test windows). Dollars; size cap 10 contracts per leg. "
             "CI: game-level bootstrap, 2,000 draws, seed 20261003, percentile 95%. No interpretation.", ""]
    for sched in SCHEDULES:
        name = "Kalshi direct taker (primary)" if sched == "direct" else "Webull $0.02/contract/leg"
        r = res[res.schedule == sched]
        lines += [f"## {name}", "",
                  "| L (s) | opps YES | opps NO | attempts | executed | missed | contracts | net P&L | P&L 95% CI | "
                  "trade mean | mean 95% CI | trade sd | Sharpe/trade | games w/ trade |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for x in r.itertuples():
            lines.append(f"| {x.latency_s} | {x.opps_yes} | {x.opps_no} | {x.attempts} | {x.executed} | {x.missed} | "
                         f"{f(x.contracts)} | {f(x.net_pnl)} | [{f(x.pnl_ci_lo)}, {f(x.pnl_ci_hi)}] | "
                         f"{f(x.trade_mean, 3)} | [{f(x.trade_mean_ci_lo, 3)}, {f(x.trade_mean_ci_hi, 3)}] | "
                         f"{f(x.trade_sd, 3)} | {f(x.trade_sharpe, 3)} | {x.games_with_trade} |")
        lines += ["", "| L (s) | paired size min/25/50/75/90/max | opp duration s min/25/50/75/90/max (censored) | "
                  "fill delay s min/25/50/75/90/max | missed reasons | unsettled excluded |", "|---|---|---|---|---|---|"]
        for x in r.itertuples():
            lines.append(f"| {x.latency_s} | {x.size_q_min_25_50_75_90_max} | {x.dur_s_min_25_50_75_90_max} "
                         f"({x.dur_censored}) | {x.fill_delay_s_min_25_50_75_90_max} | {x.missed_reasons} | "
                         f"{x.unsettled_excluded} |")
        lines.append("")
    lines += ["Variant count: 3 (one per L) added to the DSR total. Per-trade rows (our simulated trades only): "
              "results/posthoc_latency/idea1_trades.csv.", ""]
    (OUT / "idea1_RESULTS.md").write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
