"""Post-hoc Idea 11: (a) Kalshi vs polymarket.com lag diagnostics at fine resolution; (b) cross-venue arbitrage
measurement. POST-HOC, EXPLORATORY (formed after the holdout was seen).

Spec: results/posthoc_idea11/SPEC.md (committed 277769a before any real-data run). Vultr Oct 3 books only, windows
only from data/live/holdout_windows.csv at feadc99. Paper only; (b) is a market-efficiency measurement:
polymarket.com is not available to US persons; not a strategy available to the authors.

Reused: snapshot pivot and venue-time grid from scripts/posthoc_idea2.py (posthoc-latency, 2b73091), Loader from
the same file, xcorr_lead.mid_changes, holdout_mid.instruments / load_maps / PLACEBO_KICKOFF_S (Design 1 pairs as
holdout_mid.run_test).

Run once:  PYTHONPATH=.:scripts nice -n 19 python scripts/posthoc_idea11.py
"""
from __future__ import annotations

import glob
import io
import json
import subprocess
import sys
import time
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import requests
from scipy.stats import mannwhitneyu

import holdout_mid as H
import strategy_a as A
import xcorr_lead as X

NS = 1_000_000_000
BIN = 10_000_000                  # 10 ms
MAX_LAG_BINS = 100                # -1.0 .. +1.0 s
CUT = (-2 * 60 * NS, 20 * 60 * NS)
RESIDUE = 0.01
LATS = (0.25, 0.5, 1.0)
QTY = 10
TOL = 1e-9
SEED, N_BOOT = 20261004, 2000
WINDOWS_COMMIT = "feadc99"

DATA = Path("/Users/divyamkataria/GQ HACKS/staleline")
OUT = Path("results/posthoc_idea11")
PM_CACHE = Path("data/pm_resolution")
LABEL = "POST-HOC, EXPLORATORY (formed after the holdout was seen)"
ARB_LABEL = ("market-efficiency measurement; polymarket.com is not available to US persons; "
             "not a strategy available to the authors")
SNAP_COLS = ["recv", "src", "bid", "ask", "bid_size", "ask_size"]


# ---------------------------------------------------------------- snapshots and residue
def snapshots(rows: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Book rows -> one row per snapshot (same receipt ts). Residue levels (0 < size < 0.01) are removed first,
    leaving that side EMPTY at that snapshot (top of book only is recorded). Returns (snapshots, n_removed)."""
    b = rows[rows["kind"].isin(["bid", "ask"])]
    if b.empty:
        return pd.DataFrame(columns=SNAP_COLS), 0
    res = (b["size"] > 0) & (b["size"] < RESIDUE)
    n_res = int(res.sum())
    keep = b[~res]
    g = b.groupby("ts")
    out = pd.DataFrame({"recv": g["recv_ns"].max().astype("int64"),
                        "src": g["src_ts_ns"].max()})          # nullable; NaN when all src are null
    for k in ("bid", "ask"):
        s = keep[keep["kind"] == k].groupby("ts").last()
        out[k] = s["price"].reindex(out.index)
        out[f"{k}_size"] = s["size"].reindex(out.index)
    out = out.reset_index(drop=True)
    out["src"] = out["src"].astype("float64")
    return out[SNAP_COLS].sort_values(["recv"], kind="stable").reset_index(drop=True), n_res


def mid_of(snap: pd.DataFrame) -> np.ndarray:
    return ((snap["bid"] + snap["ask"]) / 2).to_numpy(float)   # NaN when a side is empty


# ---------------------------------------------------------------- 10 ms grid and lag
def grid(snap: pd.DataFrame, clock: str, lo: int, hi: int) -> pd.Series:
    """Bin = clock // 10 ms -> mid of the last snapshot in or before the bin (ties by receipt order), forward
    filled; a one-sided snapshot makes the mid undefined until the next two-sided one. Only clock in [lo, hi)."""
    s = snap[snap[clock].notna()]
    c = s[clock].to_numpy("float64")
    s = s[(c >= lo) & (c < hi)]
    if s.empty:
        return pd.Series(dtype="float64")
    s = s.assign(mid=mid_of(s), _c=s[clock].astype("int64")).sort_values(["_c", "recv"], kind="stable")
    b = s["_c"].to_numpy("int64") // BIN
    last = pd.Series(s["mid"].fillna(-1.0).to_numpy(), index=b).groupby(level=0).last()
    full = np.arange(last.index.min(), last.index.max() + 1, dtype="int64")
    return last.reindex(full).ffill().replace(-1.0, np.nan)


def xcorr_lag(rx: np.ndarray, ry: np.ndarray, max_lag: int = MAX_LAG_BINS) -> float:
    """Exact pairwise Pearson of rx[t] and ry[t + lag] over pairs where both are defined, lags -max..+max bins;
    returns the first maximal lag scanning upward from -max, in seconds (+ = x first). NaN if undefined."""
    vx, vy = ~np.isnan(rx), ~np.isnan(ry)
    x0, y0 = np.where(vx, rx, 0.0), np.where(vy, ry, 0.0)
    fx, fy = vx.astype(float), vy.astype(float)
    n_all = len(rx)
    best, best_c = None, -np.inf
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            a, b = slice(0, n_all - lag), slice(lag, n_all)
        else:
            a, b = slice(-lag, n_all), slice(0, n_all + lag)
        n = fx[a] @ fy[b]
        if n < 3:
            continue
        sx, sy = x0[a] @ fy[b], fx[a] @ y0[b]
        sxx, syy, sxy = (x0[a] ** 2) @ fy[b], fx[a] @ (y0[b] ** 2), x0[a] @ y0[b]
        vxx, vyy = sxx - sx * sx / n, syy - sy * sy / n
        if vxx <= 1e-15 or vyy <= 1e-15:
            continue
        c = (sxy - sx * sy / n) / np.sqrt(vxx * vyy)
        if c > best_c + 1e-12:
            best, best_c = lag, c
    return float(best) * BIN / NS if best is not None else float("nan")


def game_lag(sk: pd.DataFrame, sp: pd.DataFrame, clock: str, lo: int, hi: int, ko: int) -> float:
    gx, gy = grid(sk, clock, lo, hi), grid(sp, clock, lo, hi)
    if gx.empty or gy.empty:
        return float("nan")
    a, z = max(gx.index.min(), gy.index.min()), min(gx.index.max(), gy.index.max())
    if z - a + 1 < 2 * MAX_LAG_BINS + 2:
        return float("nan")
    idx = np.arange(a, z + 1, dtype="int64")
    exc = [((ko + CUT[0]) // BIN, (ko + CUT[1]) // BIN)]
    rx = X.mid_changes(gx.reindex(idx), exc).to_numpy(float)
    ry = X.mid_changes(gy.reindex(idx), exc).to_numpy(float)
    return xcorr_lag(rx, ry)


# ---------------------------------------------------------------- fees
def fee_k(p: float, q: float) -> float:
    """Kalshi direct taker fee for one order of q contracts: 0.07 x q x P x (1 - P), rounded up to the cent."""
    P, Q = Decimal(str(round(float(p), 4))), Decimal(str(round(float(q), 4)))
    return float((Decimal("0.07") * Q * P * (1 - P)).quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def fee_k_pc10(p: float) -> float:
    """Detection fee per contract: strategy_a.fee_kalshi_direct for a 10-contract order, divided by 10."""
    return A.fee_kalshi_direct(float(p), QTY) / QTY


def fee_pm(p: float, q: float = 1.0) -> float:
    return 0.05 * q * p * (1 - p)


# ---------------------------------------------------------------- arbitrage
def in_cut(t, ko: int):
    return (t >= ko + CUT[0]) & (t <= ko + CUT[1])


def legs_at(snaps: dict, T: np.ndarray, lo: int, hi: int, ko: int) -> dict:
    """As-of state at receipt times T (only snapshots received at or before T). For X in (home, away):
    Kalshi YES-X ask and size, polymarket.com other-token ask and size, live flag."""
    st = {}
    for k, s in snaps.items():
        r = s["recv"].to_numpy("int64")
        i = np.searchsorted(r, T, side="right") - 1
        ok = i >= 0
        ii = np.maximum(i, 0)
        rr = np.where(ok, r[ii], -1)
        fresh = ok & (rr >= lo) & (rr < hi) & ~in_cut(rr, ko)
        st[k] = {c: np.where(ok, s[c].to_numpy(float)[ii], np.nan) for c in ("bid", "ask", "bid_size", "ask_size")}
        st[k]["fresh"] = fresh
    base = (T >= lo) & (T < hi) & ~in_cut(T, ko)
    kh, ka, pm = st["k_home"], st["k_away"], st["pm"]
    out = {"home": {"k_px": kh["ask"], "k_sz": kh["ask_size"], "pm_px": 1 - pm["bid"], "pm_sz": pm["bid_size"],
                    "live": base & kh["fresh"] & pm["fresh"]},
           "away": {"k_px": 1 - ka["bid"], "k_sz": ka["bid_size"], "pm_px": pm["ask"], "pm_sz": pm["ask_size"],
                    "live": base & ka["fresh"] & pm["fresh"]}}
    for x in out.values():
        x["live"] = x["live"] & ~np.isnan(x["k_px"]) & ~np.isnan(x["pm_px"])
    return out


def clears(k_px, pm_px) -> np.ndarray:
    k_px, pm_px = np.asarray(k_px, float), np.asarray(pm_px, float)
    fk = np.array([fee_k_pc10(p) if p == p else np.nan for p in np.round(k_px, 4)])
    s = k_px + pm_px + fk + fee_pm(pm_px)
    return s < 1.0 - TOL


def opportunities(snaps: dict, lo: int, hi: int, ko: int) -> pd.DataFrame:
    T = np.unique(np.concatenate([s["recv"].to_numpy("int64") for s in snaps.values()]))
    T = T[(T >= lo) & (T < hi)]
    if len(T) == 0:
        return pd.DataFrame()
    st = legs_at(snaps, T, lo, hi, ko)
    rows = []
    for x, d in st.items():
        ok = d["live"].copy()
        ok[ok] = clears(d["k_px"][ok], d["pm_px"][ok])
        if not ok.any():
            continue
        e = np.diff(np.concatenate([[0], ok.astype(int), [0]]))
        starts, ends = np.flatnonzero(e == 1), np.flatnonzero(e == -1)     # ends = first index not ok
        for a, z in zip(starts, ends):
            t = int(T[a])
            cap = ko + CUT[0] if t < ko + CUT[0] else hi
            t_end = min(int(T[z]) if z < len(T) else hi, cap)
            rows.append({"team": x, "t": t, "duration_s": (t_end - t) / NS, "k_px": d["k_px"][a],
                         "pm_px": d["pm_px"][a], "k_sz": d["k_sz"][a], "pm_sz": d["pm_sz"][a],
                         "size": min(d["k_sz"][a], d["pm_sz"][a])})
    return pd.DataFrame(rows)


def execute(op: dict, snaps: dict, L: float, delay_s: float) -> dict:
    """Kalshi leg: first X-market snapshot received at or after t + L; polymarket.com leg: first snapshot received at
    or after t + L + delay. Same size q on both legs. Executed iff the sum (with fees for q) still clears."""
    t = int(op["t"])
    kk = "k_home" if op["team"] == "home" else "k_away"
    ks, ps = snaps[kk], snaps["pm"]
    kt, pt = t + int(round(L * NS)), t + int(round((L + delay_s) * NS))
    ki = int(np.searchsorted(ks["recv"].to_numpy("int64"), kt, side="left"))
    pi = int(np.searchsorted(ps["recv"].to_numpy("int64"), pt, side="left"))
    out = {"latency_s": L, "k_fill_recv": None, "pm_fill_recv": None, "executed": False, "why": ""}
    if ki >= len(ks) or pi >= len(ps):
        out["why"] = "no book after fill time"
        return out
    k, p = ks.iloc[ki], ps.iloc[pi]
    if op["team"] == "home":
        k_px, k_sz, pm_px, pm_sz = k["ask"], k["ask_size"], 1 - p["bid"], p["bid_size"]
    else:
        k_px, k_sz, pm_px, pm_sz = 1 - k["bid"], k["bid_size"], p["ask"], p["ask_size"]
    out.update(k_fill_recv=int(k["recv"]), pm_fill_recv=int(p["recv"]), k_px=k_px, pm_px=pm_px)
    if not (k_px == k_px and pm_px == pm_px and k_sz == k_sz and pm_sz == pm_sz):
        out["why"] = "side empty at fill"
        return out
    q = float(min(QTY, k_sz, pm_sz))
    fk, fp = fee_k(k_px, q), fee_pm(pm_px, q)
    out.update(q=q, fee_k=fk, fee_pm=fp, sum_pc=k_px + pm_px + fk / q + fp / q)
    if out["sum_pc"] < 1.0 - TOL:
        out["executed"] = True
    else:
        out["why"] = "missed"
    return out


def settle_pnl(ex: dict, team: str, k_res: dict, pm_res: dict) -> dict:
    """k_res: {'home': value, 'away': value} Kalshi settlement per team market; pm_res: same for the polymarket.com
    tokens. X leg pays k_res[X]; the polymarket.com leg (other team's token) pays pm_res[other]."""
    other = "away" if team == "home" else "home"
    pk, pp = k_res[team], pm_res[other]
    q = ex["q"]
    pnl = q * (pk + pp) - q * (ex["k_px"] + ex["pm_px"]) - ex["fee_k"] - ex["fee_pm"]
    return {"payout_k": pk, "payout_pm": pp, "pnl": pnl}


def settlement_agrees(k_res: dict, pm_res: dict) -> bool:
    return abs(k_res["home"] - pm_res["home"]) < 1e-9 and abs(k_res["away"] - pm_res["away"]) < 1e-9


# ---------------------------------------------------------------- stats
def boot(game_pnl: np.ndarray, game_q: np.ndarray) -> dict:
    if len(game_pnl) < 2:
        return {"total_ci": (np.nan, np.nan), "pc_ci": (np.nan, np.nan)}
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(game_pnl), size=(N_BOOT, len(game_pnl)))
    tot = game_pnl[idx].sum(axis=1)
    pc = tot / np.maximum(game_q[idx].sum(axis=1), 1e-12)
    return {"total_ci": tuple(np.percentile(tot, [2.5, 97.5])), "pc_ci": tuple(np.percentile(pc, [2.5, 97.5]))}


def iqr(x):
    x = x[~np.isnan(x)]
    return float(np.percentile(x, 75) - np.percentile(x, 25)) if len(x) else float("nan")


# ---------------------------------------------------------------- loading
class Loader:
    def __init__(self, root: Path):
        self.d = {v: ds.dataset(sorted(glob.glob(str(root / "data" / "live" / v / "*" / "*.parquet"))), format="parquet")
                  for v in ("kalshi", "polymarket")}
        self.residue = {"kalshi": 0, "polymarket": 0}
        self.book_rows = {"kalshi": 0, "polymarket": 0}

    def snap(self, venue: str, market: str, lo: int, hi: int) -> pd.DataFrame:
        f = (ds.field("market_id") == market) & (ds.field("ts") >= lo) & (ds.field("ts") < hi)
        t = self.d[venue].to_table(filter=f, columns=["ts", "kind", "price", "size", "recv_ns", "src_ts_ns"]).to_pandas()
        s, nr = snapshots(t)
        self.residue[venue] += nr
        self.book_rows[venue] += int(t["kind"].isin(["bid", "ask"]).sum())
        return s


def windows() -> pd.DataFrame:
    txt = subprocess.run(["git", "-C", str(DATA), "show", f"{WINDOWS_COMMIT}:data/live/holdout_windows.csv"],
                         capture_output=True, text=True, check=True).stdout
    w = pd.read_csv(io.StringIO(txt))
    w = w[w["venue"] == "polymarket"]
    fl = lambda c: w[c].fillna(False).astype(bool)
    q = w[fl("qualifying") & ~fl("excluded_outage") & ~fl("excluded_no_rows") & ~fl("excluded_no_instrument")
          & ~fl("not_qualifying_mid_changes") & (w["machine"] == "vultr")].copy()
    c = pd.read_csv(DATA / "data/live/holdout_candidates.csv")
    q = q.merge(c, on="game_id", how="left")
    q["ko"] = pd.to_datetime(q["kickoff_utc"], utc=True)
    return q.sort_values("ko", kind="stable").reset_index(drop=True)


def pm_resolution(cond: str) -> dict | None:
    """token id -> settlement value (outcomePrices) from the Gamma API, cached."""
    PM_CACHE.mkdir(parents=True, exist_ok=True)
    f = PM_CACHE / f"{cond}.json"
    if f.exists() and f.read_text().strip() == "[]":
        f.unlink()                    # first run cached empty answers (query lacked closed=true)
    if not f.exists():
        for i in range(4):
            try:
                r = requests.get("https://gamma-api.polymarket.com/markets", params={"condition_ids": cond, "closed": "true"}, timeout=30)
                if r.status_code == 200:
                    f.write_text(r.text)
                    break
            except requests.RequestException:
                pass
            time.sleep(2 ** i)
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    if not d:
        return None
    m = d[0]
    toks, px = json.loads(m["clobTokenIds"]), [float(x) for x in json.loads(m["outcomePrices"])]
    return {"tokens": dict(zip(toks, px)), "closed": m.get("closed"), "uma": m.get("umaResolutionStatus")}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    q = windows()
    maps = H.load_maps(DATA / "data/live/holdout_maps")
    delays = pd.read_csv(DATA / "data/live/holdout_seconds_delay.csv").set_index("market_id")["seconds_delay"]
    sett = pd.read_csv(DATA / "data/holdout_raw/settlements.csv")
    ld = Loader(DATA / "data" / "vultr")
    print(f"{LABEL}\nqualifying vultr polymarket.com windows: {len(q)}", flush=True)

    lag_rows, ops_rows, ex_rows, delay_rows, notes = [], [], [], [], {"delay_default": 0}
    for i, a in q.iterrows():
        lo, hi, ko = int(a.window_start_ns), int(a.window_end_ns), int(a.ko.value)
        inst = H.instruments(a, maps)
        pc = maps["polymarket_com"][a.kalshi_ticker]
        ev, home = a.kalshi_ticker, a.game_id.split("_")[-1].upper()
        away = a.game_id.split("_")[-2].upper()
        snaps = {"k_home": ld.snap("kalshi", f"{ev}-{home}", lo, hi), "k_away": ld.snap("kalshi", f"{ev}-{away}", lo, hi),
                 "pm": ld.snap("polymarket", inst["polymarket"], lo, hi)}
        sk, sp = snaps["k_home"], snaps["pm"]
        for clock, name in (("recv", "a1_receipt"), ("src", "a2_venue")):
            lag_rows.append({"test": name, "kind": "real", "game_id": a.game_id, "game_b": "",
                             "lag_s": game_lag(sk, sp, clock, lo, hi, ko)})
        nxt = q[(q.index > i) & ((q["ko"] - a["ko"]).dt.total_seconds() <= H.PLACEBO_KICKOFF_S)]
        if len(nxt):
            b = nxt.iloc[0]
            spb = ld.snap("polymarket", H.instruments(b, maps)["polymarket"], lo, hi)
            for clock, name in (("recv", "a1_receipt"), ("src", "a2_venue")):
                lag_rows.append({"test": name, "kind": "placebo", "game_id": a.game_id, "game_b": b.game_id,
                                 "lag_s": game_lag(sk, spb, clock, lo, hi, ko)})
        for v, s in (("kalshi", sk), ("kalshi", snaps["k_away"]), ("polymarket", sp)):
            s2 = s[s["src"].notna()]
            s2 = s2[(s2["recv"] >= lo) & (s2["recv"] < hi) & ~in_cut(s2["recv"].to_numpy("int64"), ko)]
            delay_rows.append(pd.DataFrame({"venue": v, "d_ms": (s2["recv"] - s2["src"]).to_numpy(float) / 1e6}))
        ops = opportunities(snaps, lo, hi, ko)
        cond = pc["condition"]
        dly = float(delays.get(cond, np.nan))
        if dly != dly:
            dly = 1.0
            notes["delay_default"] += 1
        if len(ops):
            ops.insert(0, "game_id", a.game_id)
            ops_rows.append(ops)
            ks = sett[sett.game_id == a.game_id].set_index("side")["settlement_value_dollars"].astype(float)
            pr = pm_resolution(cond)
            k_res = {"home": float(ks.get("home", np.nan)), "away": float(ks.get("away", np.nan))}
            other_tok = [t for t in pc["token_ids"] if t != pc["collector_home_token"]][0]
            pm_res = ({"home": pr["tokens"].get(pc["collector_home_token"], np.nan), "away": pr["tokens"].get(other_tok, np.nan)}
                      if pr else {"home": np.nan, "away": np.nan})
            for o in ops.to_dict("records"):
                for L in LATS:
                    e = execute(o, snaps, L, dly)
                    r = {"game_id": a.game_id, "team": o["team"], "t": o["t"], **e, "delay_s": dly,
                         "k_settle_home": k_res["home"], "pm_settle_home": pm_res["home"],
                         "settle_agree": settlement_agrees(k_res, pm_res)}
                    if e["executed"]:
                        r.update(settle_pnl(e, o["team"], k_res, pm_res))
                    ex_rows.append(r)
        print(f"{i + 1}/{len(q)} {a.game_id} ops={len(ops)}", flush=True)

    lags = pd.DataFrame(lag_rows)
    lags.to_csv(OUT / "lags.csv", index=False)
    ops = pd.concat(ops_rows, ignore_index=True) if ops_rows else pd.DataFrame()
    ops.to_csv(OUT / "opportunities.csv", index=False)
    exd = pd.DataFrame(ex_rows)
    exd.to_csv(OUT / "executions.csv", index=False)
    dl = pd.concat(delay_rows, ignore_index=True)

    lines = [f"# Idea 11 results. {LABEL}", "", f"Windows: {len(q)} (feadc99, polymarket.com rows, qualifying, no "
             "exclusion flags, vultr). Spec: SPEC.md (277769a).", "",
             f"Residue levels removed (0 < size < 0.01): Kalshi {ld.residue['kalshi']} of {ld.book_rows['kalshi']} "
             f"book rows; polymarket.com {ld.residue['polymarket']} of {ld.book_rows['polymarket']} (loaded rows, incl. "
             "placebo loads).", "", "## (a) Lag diagnostics (descriptive, not variants). + = Kalshi first", ""]
    summ = {}
    for test in ("a1_receipt", "a2_venue"):
        r = lags[(lags.test == test) & (lags.kind == "real")]["lag_s"].to_numpy(float)
        p = lags[(lags.test == test) & (lags.kind == "placebo")]["lag_s"].to_numpy(float)
        rr, pp = r[~np.isnan(r)], p[~np.isnan(p)]
        mw = mannwhitneyu(rr, pp, alternative="two-sided").pvalue if len(rr) and len(pp) else float("nan")
        s = {"n": len(rr), "n_nan": int(np.isnan(r).sum()), "median_s": float(np.median(rr)) if len(rr) else np.nan,
             "share_pos": float((rr > 0).mean()) if len(rr) else np.nan, "sd_s": float(np.std(rr, ddof=1)) if len(rr) > 1 else np.nan,
             "iqr_s": iqr(rr), "placebo_n": len(pp), "placebo_median_s": float(np.median(pp)) if len(pp) else np.nan,
             "placebo_iqr_s": iqr(pp), "mannwhitney_p": float(mw)}
        summ[test] = s
        hist = pd.Series(np.round(rr * 100).astype(int)).value_counts().sort_index()
        lines += [f"### {test}", "", "| " + " | ".join(s) + " |", "|" + "---|" * len(s),
                  "| " + " | ".join(f"{v:.4g}" if isinstance(v, float) else str(v) for v in s.values()) + " |", "",
                  "Real per-game lags, 10 ms bins (s: games): " +
                  ", ".join(f"{k / 100:+.2f}: {v}" for k, v in hist.items()), ""]
    a1, a2 = summ["a1_receipt"], summ["a2_venue"]
    if a2["iqr_s"] <= 0.010 + 1e-12 and not (a1["median_s"] > 0 and abs(a1["median_s"] - a2["median_s"]) < 0.0051):
        reading = "venue-time result read as a TIMESTAMP OFFSET (a2 IQR <= 10 ms and a1 does not show the same positive median)"
    elif a1["median_s"] >= 0.030 - 1e-12 and a1["share_pos"] >= 0.6:
        reading = f"read as a RECEIPT-SIDE LEAD of {a1['median_s'] * 1000:.0f} ms (Kalshi first)"
    else:
        reading = "INCONCLUSIVE"
    lines += ["### a3. Offset signature and pre-fixed reading", "",
              f"a1 per-game lag SD {a1['sd_s'] * 1000:.1f} ms, IQR {a1['iqr_s'] * 1000:.1f} ms; "
              f"a2 SD {a2['sd_s'] * 1000:.1f} ms, IQR {a2['iqr_s'] * 1000:.1f} ms.", "",
              "Rule (fixed in SPEC before the run): if a2 per-game lags have IQR <= 10 ms and a1 per-game lags do not "
              "show the same positive median, the venue-time result is read as a timestamp offset; if a1 median lag >= "
              "+30 ms with share > 0 >= 0.6, it is read as a receipt-side lead of that size; otherwise inconclusive.", "",
              f"Reading: {reading}.", "", "### a4. Receipt minus venue time (ms), book snapshots in windows, cut excluded", "",
              "| venue | n | median | p10 | p90 |", "|---|---|---|---|---|"]
    for v, g in dl.groupby("venue"):
        d = g["d_ms"].to_numpy(float)
        lines.append(f"| {v} | {len(d)} | {np.median(d):.1f} | {np.percentile(d, 10):.1f} | {np.percentile(d, 90):.1f} |")
    lines += ["", f"## (b) Cross-venue arbitrage: {ARB_LABEL}", ""]
    if len(ops):
        dur = ops["duration_s"].to_numpy(float)
        lines += [f"Opportunities: {len(ops)} in {ops.game_id.nunique()} games (home leg {int((ops.team == 'home').sum())}, "
                  f"away leg {int((ops.team == 'away').sum())}). Duration median {np.median(dur):.3f} s, p90 "
                  f"{np.percentile(dur, 90):.3f} s. Share lasting >= 0.25 / 0.5 / 1.0 / 2.0 s: "
                  + " / ".join(f"{(dur >= x).mean():.3f}" for x in (0.25, 0.5, 1.0, 2.0))
                  + f". Median executable size at t: {ops['size'].median():.2f}.", ""]
    else:
        lines += ["Opportunities: 0.", ""]
    lines += ["| L (s) | attempts | executed | missed | no book / side empty | games executed | contracts | total P&L $ "
              "| 95% CI | per contract $ | 95% CI | ex top 5 total $ | ex top 5 per contract $ |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    res = []
    for L in LATS:
        e = exd[exd["latency_s"] == L] if len(exd) else pd.DataFrame(columns=["executed", "why"])
        x = e[e["executed"].astype(bool)] if len(e) else e
        row = {"label": ARB_LABEL, "latency_L_s": L, "attempts": len(e), "executed": len(x),
               "missed": int((e["why"] == "missed").sum()) if len(e) else 0,
               "no_book_or_empty": int(e["why"].isin(["no book after fill time", "side empty at fill"]).sum()) if len(e) else 0}
        if len(x):
            gp = x.groupby("game_id").agg(pnl=("pnl", "sum"), q=("q", "sum"))
            bt = boot(gp["pnl"].to_numpy(float), gp["q"].to_numpy(float))
            top5 = gp["pnl"].sort_values(ascending=False).index[:5]
            g2 = gp.drop(top5)
            row.update(games=len(gp), contracts=float(gp.q.sum()), pnl_total=float(gp.pnl.sum()),
                       total_ci_lo=bt["total_ci"][0], total_ci_hi=bt["total_ci"][1],
                       pnl_per_contract=float(gp.pnl.sum() / gp.q.sum()), pc_ci_lo=bt["pc_ci"][0], pc_ci_hi=bt["pc_ci"][1],
                       ex_top5_total=float(g2.pnl.sum()),
                       ex_top5_pc=float(g2.pnl.sum() / g2.q.sum()) if g2.q.sum() > 0 else float("nan"))
            lines.append(f"| {L} | {row['attempts']} | {row['executed']} | {row['missed']} | {row['no_book_or_empty']} | "
                         f"{row['games']} | {row['contracts']:.2f} | {row['pnl_total']:.2f} | [{row['total_ci_lo']:.2f}, "
                         f"{row['total_ci_hi']:.2f}] | {row['pnl_per_contract']:.4f} | [{row['pc_ci_lo']:.4f}, "
                         f"{row['pc_ci_hi']:.4f}] | {row['ex_top5_total']:.2f} | {row['ex_top5_pc']:.4f} |")
        else:
            lines.append(f"| {L} | {row['attempts']} | 0 | {row['missed']} | {row['no_book_or_empty']} | 0 | | | | | | | |")
        res.append(row)
    pd.DataFrame(res).to_csv(OUT / "arb_results.csv", index=False)
    xg = exd[exd["executed"].astype(bool)] if len(exd) else exd
    dis = sorted(set(xg[~xg["settle_agree"].astype(bool)]["game_id"])) if len(xg) else []
    lines += ["", f"Settlement check (games with an executed opportunity at any L: {xg.game_id.nunique() if len(xg) else 0}): "
              f"disagreements {len(dis)}: {dis}. Kalshi: data/holdout_raw/settlements.csv; polymarket.com: Gamma API "
              "outcomePrices (cached data/pm_resolution/).",
              f"Taker delay defaulted to 1 s (condition missing from holdout_seconds_delay.csv): {notes['delay_default']} games."]
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n")
    pd.DataFrame([{"test": k, **v} for k, v in summ.items()]).to_csv(OUT / "lag_summary.csv", index=False)
    print("\n".join(lines))


def settle_only() -> None:
    """Settlement step only, after the 04:14 run cached empty polymarket.com resolutions. Reads the saved
    executions.csv (fills, sizes, prices and fees are unchanged; nothing is re-detected or re-filled), fetches the
    resolutions with closed=true, recomputes payouts, P&L and the settlement check, and writes RESULTS_b.md and
    arb_results.csv."""
    exd = pd.read_csv(OUT / "executions.csv")
    q = windows()
    maps = H.load_maps(DATA / "data/live/holdout_maps")
    sett = pd.read_csv(DATA / "data/holdout_raw/settlements.csv")
    res_k, res_pm = {}, {}
    for a in q.itertuples():
        pc = maps["polymarket_com"][a.kalshi_ticker]
        ks = sett[sett.game_id == a.game_id].set_index("side")["settlement_value_dollars"].astype(float)
        res_k[a.game_id] = {"home": float(ks.get("home", np.nan)), "away": float(ks.get("away", np.nan))}
        if a.game_id in set(exd.game_id):
            pr = pm_resolution(pc["condition"])
            other = [t for t in pc["token_ids"] if t != pc["collector_home_token"]][0]
            res_pm[a.game_id] = ({"home": pr["tokens"].get(pc["collector_home_token"], np.nan),
                                  "away": pr["tokens"].get(other, np.nan), "closed": pr["closed"], "uma": pr["uma"]}
                                 if pr else {"home": np.nan, "away": np.nan, "closed": None, "uma": None})
    exd["k_settle_home"] = exd.game_id.map(lambda g: res_k[g]["home"])
    exd["pm_settle_home"] = exd.game_id.map(lambda g: res_pm[g]["home"])
    exd["settle_agree"] = exd.game_id.map(lambda g: settlement_agrees(res_k[g], res_pm[g]))
    pnl = []
    for r in exd.to_dict("records"):
        pnl.append(settle_pnl(r, r["team"], res_k[r["game_id"]], res_pm[r["game_id"]])["pnl"] if r["executed"] else np.nan)
    exd["pnl"] = pnl
    exd.to_csv(OUT / "executions_settled.csv", index=False)
    ops = pd.read_csv(OUT / "opportunities.csv")
    lines = [f"# Idea 11 (b), settled. {ARB_LABEL}", "", "Settlement step only (settle_only), run after the one "
             "real-data run (9d06979): that run cached empty polymarket.com resolutions because the Gamma query lacked "
             "closed=true, so its P&L was all NaN (printed as 0) and every game showed as a disagreement. Opportunities, "
             "fills, sizes, prices and fees below are the run's saved executions.csv, unchanged.", ""]
    dur = ops["duration_s"].to_numpy(float)
    lines += [f"Opportunities: {len(ops)} in {ops.game_id.nunique()} games (home leg {int((ops.team == 'home').sum())}, "
              f"away leg {int((ops.team == 'away').sum())}). Duration median {np.median(dur):.3f} s, p90 "
              f"{np.percentile(dur, 90):.3f} s. Share lasting >= 0.25 / 0.5 / 1.0 / 2.0 s: "
              + " / ".join(f"{(dur >= x).mean():.3f}" for x in (0.25, 0.5, 1.0, 2.0))
              + f". Median executable size at t: {ops['size'].median():.2f}.", "",
              "| L (s) | attempts | executed | missed | no book / side empty | games executed | contracts | total P&L $ "
              "| 95% CI | per contract $ | 95% CI | ex top 5 total $ | ex top 5 per contract $ |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    res = []
    for L in LATS:
        e = exd[exd["latency_s"] == L]
        x = e[e["executed"].astype(bool) & e["pnl"].notna()]
        row = {"label": ARB_LABEL, "latency_L_s": L, "attempts": len(e), "executed": int(e["executed"].sum()),
               "executed_unsettled": int((e["executed"].astype(bool) & e["pnl"].isna()).sum()),
               "missed": int((e["why"] == "missed").sum()),
               "no_book_or_empty": int(e["why"].isin(["no book after fill time", "side empty at fill"]).sum())}
        gp = x.groupby("game_id").agg(pnl=("pnl", "sum"), q=("q", "sum"))
        bt = boot(gp["pnl"].to_numpy(float), gp["q"].to_numpy(float))
        g2 = gp.drop(gp["pnl"].sort_values(ascending=False).index[:5])
        row.update(games=len(gp), contracts=float(gp.q.sum()), pnl_total=float(gp.pnl.sum()),
                   total_ci_lo=bt["total_ci"][0], total_ci_hi=bt["total_ci"][1],
                   pnl_per_contract=float(gp.pnl.sum() / gp.q.sum()), pc_ci_lo=bt["pc_ci"][0], pc_ci_hi=bt["pc_ci"][1],
                   ex_top5_total=float(g2.pnl.sum()), ex_top5_pc=float(g2.pnl.sum() / g2.q.sum()) if g2.q.sum() > 0 else np.nan)
        lines.append(f"| {L} | {row['attempts']} | {row['executed']} | {row['missed']} | {row['no_book_or_empty']} | "
                     f"{row['games']} | {row['contracts']:.2f} | {row['pnl_total']:.2f} | [{row['total_ci_lo']:.2f}, "
                     f"{row['total_ci_hi']:.2f}] | {row['pnl_per_contract']:.4f} | [{row['pc_ci_lo']:.4f}, "
                     f"{row['pc_ci_hi']:.4f}] | {row['ex_top5_total']:.2f} | {row['ex_top5_pc']:.4f} |")
        res.append(row)
    pd.DataFrame(res).to_csv(OUT / "arb_results.csv", index=False)
    xg = exd[exd["executed"].astype(bool)]
    games = sorted(set(xg.game_id))
    dis = [g for g in games if not settlement_agrees(res_k[g], res_pm[g])]
    lines += ["", f"Settlement check: {len(games)} games with an executed opportunity at any L; disagreements "
              f"{len(dis)}: " + (", ".join(f"{g} (Kalshi home {res_k[g]['home']}, polymarket.com home token "
                                            f"{res_pm[g]['home']}, closed {res_pm[g]['closed']}, uma {res_pm[g]['uma']})"
                                            for g in dis) or "none") + ".",
              f"Executed rows without a usable settlement (excluded from P&L): "
              + ", ".join(f"L {r['latency_L_s']}: {r['executed_unsettled']}" for r in res) + ".",
              "Sources: Kalshi data/holdout_raw/settlements.csv (settlement_value_dollars); polymarket.com Gamma API "
              "markets?condition_ids=..&closed=true outcomePrices (cached data/pm_resolution/, gitignored)."]
    (OUT / "RESULTS_b.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(settle_only() if "--settle-only" in sys.argv else main())
