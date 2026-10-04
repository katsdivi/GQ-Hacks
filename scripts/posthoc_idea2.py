"""IDEA 2, polymarket.com sub-second lead. POST-HOC, EXPLORATORY (formed after seeing the holdout).

Spec: results/posthoc_latency/SPEC_idea2.md (committed before this ran). Venue-time (src_ts_ns) 100 ms grid
lag test with placebo, and a Kalshi taker rule triggered by fast polymarket.com mid moves, for L in
{0.25, 0.5, 1.0} s. Vultr recordings only. Paper only.

Run once:  PYTHONPATH=.:scripts python scripts/posthoc_idea2.py
"""
from __future__ import annotations

import bisect
import glob
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

import costs
import holdout_mid as H
import laggard as LG
import xcorr_lead as X

NS = 1_000_000_000
BIN = 100_000_000                 # 100 ms in ns
MAX_LAG_BINS = 30                 # -3.0 .. +3.0 s
SIG_WINDOW = 500_000_000          # 500 ms
SIG_MOVE = 0.03                   # polymarket.com mid move, dollars
KAL_MAX = 0.01                    # Kalshi same-direction move must be below this
TOL = 1e-9
HOLD = 30 * NS
QTY = 10
LATS = (0.25, 0.5, 1.0)
CUT = (-2 * 60 * NS, 20 * 60 * NS)
EXIT_AFTER_END = 60 * NS
LOAD_MARGIN = 120 * NS
_EMPTY = -1.0

DATA = Path("/Users/divyamkataria/GQ HACKS/staleline")
OUT = Path("results/posthoc_latency")
LABEL = "POST-HOC, EXPLORATORY (formed after seeing the holdout)"


# ---------------------------------------------------------------- snapshots
def snapshots(rows: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Book rows -> one row per snapshot (same receipt ts): recv, src, bid, ask, bid_size, ask_size.
    Rows with null src_ts_ns are dropped (count returned). Trade rows are ignored."""
    b = rows[rows["kind"].isin(["bid", "ask"])]
    n_null = int(b["src_ts_ns"].isna().sum())
    b = b[b["src_ts_ns"].notna()]
    cols = ["recv", "src", "bid", "ask", "bid_size", "ask_size"]
    if b.empty:
        return pd.DataFrame(columns=cols), n_null
    p = b.pivot_table(index="ts", columns="kind", values=["price", "size"], aggfunc="last")
    out = pd.DataFrame(index=p.index)
    for k in ("bid", "ask"):
        out[k] = p[("price", k)] if ("price", k) in p.columns else np.nan
        out[f"{k}_size"] = p[("size", k)] if ("size", k) in p.columns else np.nan
    src = b.groupby("ts")["src_ts_ns"].max().astype("int64")
    recv = b.groupby("ts")["recv_ns"].max().astype("int64")
    out["src"], out["recv"] = src, recv
    out = out.reset_index(drop=True)
    return out[cols].sort_values(["recv", "src"], kind="stable").reset_index(drop=True), n_null


def mid_of(snap: pd.DataFrame) -> np.ndarray:
    return ((snap["bid"] + snap["ask"]) / 2).to_numpy(float)   # NaN when a side is missing


# ---------------------------------------------------------------- 100 ms venue-time grid and lag
def grid100(snap: pd.DataFrame) -> pd.Series:
    """Bin b = src // 100 ms -> mid of the last snapshot (venue time, ties by receipt) in or before bin b.
    One-sided snapshot -> undefined until the next two-sided one."""
    if snap.empty:
        return pd.Series(dtype="float64")
    s = snap.assign(mid=mid_of(snap)).sort_values(["src", "recv"], kind="stable")
    b = s["src"].to_numpy("int64") // BIN
    last = pd.Series(s["mid"].fillna(_EMPTY).to_numpy(), index=b).groupby(level=0).last()
    full = np.arange(last.index.min(), last.index.max() + 1, dtype="int64")
    return last.reindex(full).ffill().replace(_EMPTY, np.nan)


def cut_bins(ko_ns: int) -> tuple[int, int]:
    return ((ko_ns + CUT[0]) // BIN, (ko_ns + CUT[1]) // BIN)


def lag_100ms(snap_k: pd.DataFrame, snap_p: pd.DataFrame, lo: int, hi: int, ko_ns: int) -> float:
    """xcorr_lead.game_lag_mid on the 100 ms venue-time grid, lags -30..+30 bins; seconds, + = Kalshi first."""
    sk = snap_k[(snap_k["src"] >= lo) & (snap_k["src"] < hi)]
    sp = snap_p[(snap_p["src"] >= lo) & (snap_p["src"] < hi)]
    gx, gy = grid100(sk), grid100(sp)
    if gx.empty or gy.empty:
        return float("nan")
    a, z = max(gx.index.min(), gy.index.min()), min(gx.index.max(), gy.index.max())
    if z - a + 1 < 2 * MAX_LAG_BINS + 2:
        return float("nan")
    idx = np.arange(a, z + 1, dtype="int64")
    exc = [cut_bins(ko_ns)]
    rx, ry = X.mid_changes(gx, exc).reindex(idx), X.mid_changes(gy, exc).reindex(idx)
    corr = {lag: float(rx.corr(ry.shift(-lag))) for lag in range(-MAX_LAG_BINS, MAX_LAG_BINS + 1)}
    corr = {k: (v if v == v else -np.inf) for k, v in corr.items()}
    lag = max(corr, key=corr.get)          # first maximal key from -30 upward
    return float(lag) / 10 if np.isfinite(corr[lag]) else float("nan")


# ---------------------------------------------------------------- causal as-of on venue time
class CausalAsOf:
    """Snapshots are added in receipt order; query(t) = mid of the last added snapshot with src <= t
    (ties by receipt order). Only snapshots already added (received) are visible."""

    def __init__(self):
        self.keys: list[tuple[int, int]] = []
        self.vals: list[float] = []
        self.seq = 0

    def add(self, src: int, mid: float) -> None:
        k = (int(src), self.seq)
        self.seq += 1
        i = bisect.bisect_right(self.keys, k)
        self.keys.insert(i, k)
        self.vals.insert(i, mid)

    def query(self, t: int) -> float:
        i = bisect.bisect_right(self.keys, (int(t), math.inf)) - 1
        return self.vals[i] if i >= 0 else float("nan")


def in_cut(t0: int, t1: int, ko_ns: int) -> bool:
    """Does [t0, t1] intersect the kickoff cut [T - 2 min, T + 20 min]?"""
    return t1 >= ko_ns + CUT[0] and t0 <= ko_ns + CUT[1]


def signals(snap_p: pd.DataFrame, snap_k: pd.DataFrame, lo: int, hi: int, ko_ns: int) -> pd.DataFrame:
    """One row per polymarket.com snapshot that fires: trig_recv, trig_src, dP, dK, direction (+1 buy, -1 sell).
    Inputs use only snapshots with venue time <= as-of time and receipt <= the trigger's receipt."""
    pa, ka = CausalAsOf(), CausalAsOf()
    p_src, p_recv, p_mid = snap_p["src"].to_numpy("int64"), snap_p["recv"].to_numpy("int64"), mid_of(snap_p)
    k_src, k_recv, k_mid = snap_k["src"].to_numpy("int64"), snap_k["recv"].to_numpy("int64"), mid_of(snap_k)
    j, nk = 0, len(k_recv)
    out = []
    i, n = 0, len(p_recv)
    while i < n:
        # add every polymarket.com snapshot with this same receipt time first (one message)
        r = p_recv[i]
        e = i
        while e < n and p_recv[e] == r:
            pa.add(p_src[e], p_mid[e])
            e += 1
        while j < nk and k_recv[j] <= r:
            ka.add(k_src[j], k_mid[j])
            j += 1
        for q in range(i, e):
            s = int(p_src[q])
            if not (lo <= s < hi) or in_cut(s - SIG_WINDOW, s, ko_ns):
                continue
            dp = pa.query(s) - pa.query(s - SIG_WINDOW)
            if not (abs(dp) >= SIG_MOVE - TOL):
                continue
            dk = ka.query(s) - ka.query(s - SIG_WINDOW)
            if dk != dk:
                continue
            d = 1 if dp > 0 else -1
            if dk * d < KAL_MAX - TOL:
                out.append({"trig_recv": int(r), "trig_src": s, "dP": dp, "dK": dk, "direction": d})
        i = e
    return pd.DataFrame(out, columns=["trig_recv", "trig_src", "dP", "dK", "direction"])


# ---------------------------------------------------------------- execution
def leg_fee_cents(price: float, qty: float, route: str) -> float:
    return costs.fee(price, qty, "buy", "kalshi", route=route) * 100 / qty


def simulate(sig: pd.DataFrame, snap_k: pd.DataFrame, lat_s: float, ko_ns: int, hi: int) -> tuple[list, dict]:
    """Taker rule for one game and one L. Returns trades and skip counts."""
    kr = snap_k["recv"].to_numpy("int64")
    kb, ka = snap_k["bid"].to_numpy(float), snap_k["ask"].to_numpy(float)
    kbs, kas = snap_k["bid_size"].to_numpy(float), snap_k["ask_size"].to_numpy(float)
    trades, skip = [], {"no_quote": 0, "no_exit": 0, "in_cut": 0, "after_end": 0, "held": 0}
    busy_until = -1
    lat = int(round(lat_s * NS))
    for s in sig.itertuples():
        if s.trig_recv < busy_until:
            skip["held"] += 1
            continue
        order = s.trig_recv + lat
        f = int(np.searchsorted(kr, order, side="left"))
        if f >= len(kr):
            skip["no_quote"] += 1
            continue
        d = s.direction
        px, sz = (ka[f], kas[f]) if d > 0 else (kb[f], kbs[f])
        if not (px == px) or not (sz == sz) or sz <= 0:
            skip["no_quote"] += 1
            continue
        qty = float(min(QTY, sz))
        x0 = int(np.searchsorted(kr, kr[f] + HOLD, side="left"))
        side = kb if d > 0 else ka
        x = next((k for k in range(x0, len(kr)) if side[k] == side[k]), None)
        if x is None:
            skip["no_exit"] += 1
            continue
        if in_cut(kr[f], kr[f], ko_ns) or in_cut(kr[x], kr[x], ko_ns):
            skip["in_cut"] += 1
            continue
        if kr[x] > hi + EXIT_AFTER_END:
            skip["after_end"] += 1
            continue
        xp = side[x]
        gross = (xp - px) * 100 if d > 0 else (px - xp) * 100
        fd = leg_fee_cents(px, qty, "direct") + leg_fee_cents(xp, qty, "direct")
        fw = leg_fee_cents(px, qty, "webull") + leg_fee_cents(xp, qty, "webull")
        trades.append({"latency_s": lat_s, "trig_src": s.trig_src, "trig_recv": s.trig_recv, "dP": s.dP,
                       "dK": s.dK, "direction": d, "fill_recv": int(kr[f]), "entry_px": px, "qty": qty,
                       "exit_recv": int(kr[x]), "exit_px": xp, "gross_c": gross,
                       "net_direct_c": gross - fd, "net_webull_c": gross - fw})
        busy_until = int(kr[x])
    return trades, skip


def summarize(tr: pd.DataFrame, col: str) -> dict:
    if tr.empty:
        return {"trades": 0, "games_with_trades": 0}
    pg = tr.groupby("game_id")[col]
    s, n = pg.sum(), pg.size()
    lo, hi = LG.game_bootstrap_ci(s.to_numpy(), n.to_numpy())
    e = tr[col].to_numpy(float)
    top5 = s.sort_values(ascending=False).index[:5]
    ex = tr[~tr["game_id"].isin(top5)][col].to_numpy(float)
    sh = lambda v: float(v.mean() / v.std(ddof=1)) if len(v) > 1 and v.std(ddof=1) > 0 else float("nan")
    return {"trades": len(e), "games_with_trades": int(len(s)), "mean_net_c": float(e.mean()),
            "ci_low": lo, "ci_high": hi, "share_games_positive": float((s > 0).mean()),
            "sharpe_per_trade": sh(e), "mean_gross_c": float(tr["gross_c"].mean()),
            "ex_top5_trades": len(ex), "ex_top5_mean_net_c": float(ex.mean()) if len(ex) else float("nan"),
            "ex_top5_sharpe_per_trade": sh(ex)}


# ---------------------------------------------------------------- data
class Loader:
    def __init__(self, root: Path):
        self.d = {v: ds.dataset(sorted(glob.glob(str(root / "data" / "live" / v / "*" / "*.parquet"))), format="parquet")
                  for v in ("kalshi", "polymarket")}
        self.nulls = {"kalshi": [0, 0], "polymarket": [0, 0]}   # [null src book rows, book rows]

    def snap(self, venue: str, market: str, lo: int, hi: int) -> pd.DataFrame:
        f = (ds.field("market_id") == market) & (ds.field("ts") >= lo - LOAD_MARGIN) & (ds.field("ts") <= hi + LOAD_MARGIN)
        t = self.d[venue].to_table(filter=f, columns=["ts", "kind", "price", "size", "recv_ns", "src_ts_ns"]).to_pandas()
        s, nn = snapshots(t)
        self.nulls[venue][0] += nn
        self.nulls[venue][1] += int(t["kind"].isin(["bid", "ask"]).sum())
        return s


def main() -> None:
    per = pd.read_csv(DATA / "results/holdout/lead_polymarket.com_per_game.csv")
    q = per[per["qualifying"].fillna(False).astype(bool) & (per["machine"] == "vultr")].copy()
    q["ko"] = pd.to_datetime(q["kickoff_utc"], utc=True)
    q = q.sort_values("ko").reset_index(drop=True)
    cands = pd.read_csv(DATA / "data/live/holdout_candidates.csv")
    maps = H.load_maps(DATA / "data/live/holdout_maps")
    ld = Loader(DATA / "data" / "vultr")
    print(f"{LABEL}\nqualifying vultr games: {len(q)}", flush=True)
    inst = {g: H.instruments(cands[cands.game_id == g].iloc[0], maps) for g in q["game_id"]}

    lag_rows, trades, skips, nsig = [], [], [], 0
    for i, a in q.iterrows():
        lo, hi, ko = int(a.window_start_ns), int(a.window_end_ns), int(a.ko.value)
        sk = ld.snap("kalshi", inst[a.game_id]["kalshi"], lo, hi)
        sp = ld.snap("polymarket", inst[a.game_id]["polymarket"], lo, hi)
        lag_rows.append({"kind": "real", "game_id": a.game_id, "game_b": "", "lag_s": lag_100ms(sk, sp, lo, hi, ko)})
        sig = signals(sp, sk, lo, hi, ko)
        nsig += len(sig)
        for L in LATS:
            tr, sc = simulate(sig, sk, L, ko, hi)
            trades += [{"game_id": a.game_id, **t} for t in tr]
            skips.append({"game_id": a.game_id, "latency_s": L, "signals": len(sig), **sc})
        # placebo: next qualifying game on the same machine within PLACEBO_KICKOFF_S (holdout_mid.run_test)
        nxt = q[(q.index > i) & (q["machine"] == a["machine"]) &
                ((q["ko"] - a["ko"]).dt.total_seconds() <= H.PLACEBO_KICKOFF_S)]
        if len(nxt):
            b = nxt.iloc[0]
            spb = ld.snap("polymarket", inst[b.game_id]["polymarket"], lo, hi)
            lag_rows.append({"kind": "placebo", "game_id": a.game_id, "game_b": b.game_id,
                             "lag_s": lag_100ms(sk, spb, lo, hi, ko) if len(sk) and len(spb) else float("nan")})
        print(f"{i + 1}/{len(q)} {a.game_id} signals={len(sig)}", flush=True)
        # per-game flush (robustness against the hard stop; final files are rewritten below)
        pd.DataFrame(lag_rows).to_csv(OUT / "idea2_lag_distribution.csv", index=False)
        pd.DataFrame(trades).to_csv(OUT / "idea2_trades.csv", index=False)
        pd.DataFrame(skips).to_csv(OUT / "idea2_skips.csv", index=False)

    lags = pd.DataFrame(lag_rows)
    lags.to_csv(OUT / "idea2_lag_distribution.csv", index=False)
    real, pl = lags[lags.kind == "real"]["lag_s"].to_numpy(float), lags[lags.kind == "placebo"]["lag_s"].to_numpy(float)
    dec = X.decide(real, pl, 0.0, "kalshi", "polymarket.com", min_lead_s=1.0)
    tdf = pd.DataFrame(trades)
    tdf.to_csv(OUT / "idea2_trades.csv", index=False)
    sdf = pd.DataFrame(skips)
    sdf.to_csv(OUT / "idea2_skips.csv", index=False)
    res = []
    for L in LATS:
        t = tdf[tdf["latency_s"] == L] if len(tdf) else tdf
        for route, col in (("kalshi_direct", "net_direct_c"), ("webull", "net_webull_c")):
            res.append({"label": LABEL, "latency_L_s": L, "fee_line": route, **summarize(t, col)})
    rdf = pd.DataFrame(res)
    rdf.to_csv(OUT / "idea2_results.csv", index=False)
    print("lag decide-style stats:", dec)
    print("src_ts_ns null book rows [null, total]:", ld.nulls)
    print("signals total:", nsig)
    print(sdf.groupby("latency_s")[["no_quote", "no_exit", "in_cut", "after_end", "held"]].sum())
    pd.set_option("display.width", 250)
    print(rdf.drop(columns="label").to_string())
    print("real lag distribution (s):", lags[lags.kind == "real"]["lag_s"].value_counts(dropna=False).sort_index().to_dict())
    print("placebo lag distribution (s):", lags[lags.kind == "placebo"]["lag_s"].value_counts(dropna=False).sort_index().to_dict())


if __name__ == "__main__":
    sys.exit(main())
