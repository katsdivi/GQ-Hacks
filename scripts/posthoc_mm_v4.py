"""HYPOTHESIS_v4 maker: copy of scripts/posthoc_mm_signal.py at 38da93d (posthoc-mm-signal) plus the Arm B min_spread
parameter in simulate(); nothing else changed.

Original docstring: Post-hoc: Kalshi-signal market making on the slow venue (polymarket.com Oct 3 Vultr; CME 14 training games).

Spec: results/posthoc_mm_signal/SPEC.md (6098d5c, committed before any real-data run). Historical local files only:
no API calls, no keys, no orders.

Reused (cited): snapshots() and windows() logic from scripts/posthoc_idea11.py (posthoc-idea11 0487ebf);
kalshi_phome(), signals() and the mbp-1 Book from scripts/kalshi_cme_stage1.py (posthoc-kalshi-cme e05f28c).

Usage (cwd = repo root, PYTHONPATH=.:scripts): python scripts/posthoc_mm_signal.py
"""
from __future__ import annotations

import glob
import io
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

NS = 1_000_000_000
EPS = 1e-9
QTY = 10
INV_LIM = 50
J = 0.03
PULL_S = 10
LATS = (0.25, 1.0)
SEED, NBOOT = 20261004, 2000
CUT = (-2 * 60 * NS, 20 * 60 * NS)
RESIDUE = 0.01
ROOT = Path("/Users/divyamkataria/GQ HACKS/staleline")
OUT = Path("results/posthoc_mm_signal")
PM_RES = Path("/Users/divyamkataria/GQ HACKS/wt-idea11/data/pm_resolution")
CME_FEE = 0.01
PM_FEE = 0.0
LABEL = "post-hoc, exploratory; historical local files only"


# ---------------------------------------------------------------- Kalshi signal (Stage 1 rule, reused)
def signals(ts: np.ndarray, px: np.ndarray, lo: int, hi: int, j: float = J) -> list[tuple[int, int]]:
    """Move >= j within trailing 10 s (points in [t - 10 s, t]); 10 s refractory. From kalshi_cme_stage1.signals."""
    out, block, j0 = [], -1, 0
    for i in range(len(ts)):
        t = ts[i]
        if t < lo or t > hi or t < block:
            continue
        while ts[j0] < t - 10 * NS:
            j0 += 1
        w = px[j0:i + 1]
        up, dn = px[i] - w.min(), w.max() - px[i]
        if up >= j - EPS or dn >= j - EPS:
            out.append((int(t), 1 if up >= dn else -1))
            block = t + 10 * NS
    return out


# ---------------------------------------------------------------- slow-venue book (venue time)
class Book:
    """Top of book by venue time; state at T = latest update with venue ts <= T."""

    def __init__(self, ts, bid, ask, bsz, asz):
        o = np.argsort(ts, kind="stable")
        self.ts = np.asarray(ts, np.int64)[o]
        self.bid = np.asarray(bid, float)[o]
        self.ask = np.asarray(ask, float)[o]
        self.bsz = np.asarray(bsz, float)[o]
        self.asz = np.asarray(asz, float)[o]

    def idx(self, T):
        return np.searchsorted(self.ts, T, side="right") - 1

    def mid(self, T) -> np.ndarray:
        i = self.idx(np.asarray(T, np.int64))
        ok = i >= 0
        ii = np.maximum(i, 0)
        m = (self.bid[ii] + self.ask[ii]) / 2
        return np.where(ok, m, np.nan)


def in_cut(t, ko):
    return (t >= ko + CUT[0]) & (t < ko + CUT[1])


# ---------------------------------------------------------------- simulator
def simulate(book: Book, tr_ts, tr_px, tr_sz, lo: int, hi: int, ko: int, sigs: list[tuple[int, int]] | None,
             L: float | None, rule: str, min_spread: float = 0.0) -> list[dict]:
    """One maker on one contract. sigs = Kalshi signals in this contract's YES terms (None = N maker).
    rule 'F1' strict trade-through, 'F2' queue. Returns fills.
    min_spread (HYPOTHESIS_v4 Arm B): quote only while best ask - best bid >= min_spread; 0.0 = Arm A (always quote)."""
    ev = []  # (time, order, kind, payload); order: 0 trade, 1 pull change, 2 book
    for k in range(len(tr_ts)):
        ev.append((int(tr_ts[k]), 0, "T", k))
    if sigs:
        for t, d in sigs:
            side = "ask" if d > 0 else "bid"
            ev.append((t + int(L * NS), 1, "P+", side))
            ev.append((t + PULL_S * NS, 1, "P-", side))
    for k in range(len(book.ts)):
        ev.append((int(book.ts[k]), 2, "B", k))
    ev.sort(key=lambda e: (e[0], e[1]))
    pulled = {"bid": 0, "ask": 0}
    order = {"bid": None, "ask": None}   # dict(price, rem, queue, placed)
    bi = -1
    inv = 0
    fills = []

    def best(side):
        if bi < 0:
            return np.nan, 0.0
        if side == "bid":
            return book.bid[bi], book.bsz[bi]
        return book.ask[bi], book.asz[bi]

    def refresh(t):
        live = lo <= t < hi and not in_cut(t, ko)
        if min_spread > 0 and bi >= 0:
            spr = book.ask[bi] - book.bid[bi]
            live = live and spr == spr and spr >= min_spread - EPS
        elif min_spread > 0:
            live = False
        for side, sg in (("bid", 1), ("ask", -1)):
            px, sz = best(side)
            want = (live and pulled[side] == 0 and px == px and sz > 0 and abs(inv + sg * QTY) <= INV_LIM)
            o = order[side]
            if not want:
                order[side] = None
            elif o is None or abs(o["price"] - px) > EPS:
                order[side] = {"price": float(px), "rem": QTY, "queue": float(sz), "placed": t}

    for t, _, kind, p in ev:
        if kind == "B":
            bi = p
            refresh(t)
        elif kind == "P+":
            pulled[p] += 1
            refresh(t)
        elif kind == "P-":
            pulled[p] = max(0, pulled[p] - 1)
            refresh(t)
        else:
            if not (lo <= t < hi) or in_cut(t, ko):
                refresh(t)
                continue
            px, sz = float(tr_px[p]), float(tr_sz[p])
            for side, sg in (("bid", 1), ("ask", -1)):
                o = order[side]
                if o is None or o["placed"] >= t:
                    continue
                through = px < o["price"] - EPS if side == "bid" else px > o["price"] + EPS
                at = abs(px - o["price"]) <= EPS
                q = 0
                if through:
                    q = o["rem"]
                elif at and rule == "F2":
                    o["queue"] -= sz
                    if o["queue"] < 0:
                        q = min(o["rem"], -o["queue"])
                        o["queue"] = 0.0
                if q > 0:
                    q = int(q) if q >= 1 else q
                    fills.append({"t": t, "side": sg, "price": o["price"], "qty": float(q)})
                    o["rem"] -= q
                    inv += sg * q
                    if o["rem"] <= EPS:
                        order[side] = None
            refresh(t)
    return fills


def score(fills: list[dict], book: Book, payout: float, fee: float) -> pd.DataFrame:
    if not fills:
        return pd.DataFrame(columns=["t", "side", "price", "qty", "pnl60", "pnlset", "as10", "as60"])
    f = pd.DataFrame(fills)
    t = f["t"].to_numpy(np.int64)
    m0 = book.mid(t - 1)
    m10, m60 = book.mid(t + 10 * NS), book.mid(t + 60 * NS)
    s, p, q = f["side"].to_numpy(float), f["price"].to_numpy(float), f["qty"].to_numpy(float)
    f["pnl60"] = s * (m60 - p) * q - fee * q
    f["pnlset"] = s * (payout - p) * q - fee * q
    f["as10"] = s * (m10 - m0)
    f["as60"] = s * (m60 - m0)
    return f


def boot_diff(gs: pd.Series, gn: pd.Series) -> tuple[float, float, float]:
    games = sorted(set(gs.index) | set(gn.index))
    d = (gs.reindex(games, fill_value=0.0) - gn.reindex(games, fill_value=0.0)).to_numpy(float)
    if len(d) == 0:
        return np.nan, np.nan, np.nan
    est = float(d.sum())
    if len(d) < 2:
        return est, np.nan, np.nan
    rng = np.random.default_rng(SEED)
    bs = d[rng.integers(0, len(d), (NBOOT, len(d)))].sum(1)
    return est, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


# ---------------------------------------------------------------- polymarket.com loaders (idea11 logic)
def pm_windows() -> pd.DataFrame:
    txt = subprocess.run(["git", "-C", str(ROOT), "show", "feadc99:data/live/holdout_windows.csv"],
                         capture_output=True, text=True, check=True).stdout
    w = pd.read_csv(io.StringIO(txt))
    w = w[w["venue"] == "polymarket"]
    fl = lambda c: w[c].fillna(False).astype(bool)
    q = w[fl("qualifying") & ~fl("excluded_outage") & ~fl("excluded_no_rows") & ~fl("excluded_no_instrument")
          & ~fl("not_qualifying_mid_changes") & (w["machine"] == "vultr")].copy()
    c = pd.read_csv(ROOT / "data/live/holdout_candidates.csv")
    q = q.merge(c, on="game_id", how="left")
    q["ko"] = pd.to_datetime(q["kickoff_utc"], utc=True)
    return q.sort_values("ko", kind="stable").reset_index(drop=True)


class Loader:
    def __init__(self):
        import pyarrow.dataset as ds
        self.ds = ds
        root = ROOT / "data/vultr/data/live"
        self.d = {v: ds.dataset(sorted(glob.glob(str(root / v / "*" / "*.parquet"))), format="parquet")
                  for v in ("kalshi", "polymarket")}
        self.residue = {"kalshi": 0, "polymarket": 0}

    def rows(self, venue, market, lo, hi):
        f = (self.ds.field("market_id") == market) & (self.ds.field("ts") >= lo - 600 * NS) & (self.ds.field("ts") < hi)
        return self.d[venue].to_table(filter=f, columns=["ts", "kind", "price", "size", "recv_ns", "src_ts_ns"]).to_pandas()

    def book(self, venue, t: pd.DataFrame) -> Book:
        """Snapshots (same receipt ts) -> top of book at venue time; residue removed (side empty)."""
        b = t[t["kind"].isin(["bid", "ask"])]
        res = (b["size"] > 0) & (b["size"] < RESIDUE)
        self.residue[venue] += int(res.sum())
        keep = b[~res]
        g = b.groupby("ts")
        src = g["src_ts_ns"].max().astype("float64")
        out = pd.DataFrame({"src": src})
        for k in ("bid", "ask"):
            s = keep[keep["kind"] == k].groupby("ts").last()
            out[k] = s["price"].reindex(out.index)
            out[f"{k}_sz"] = s["size"].reindex(out.index)
        out = out[out["src"].notna()]
        return Book(out["src"].astype("int64").to_numpy(), out["bid"].to_numpy(float), out["ask"].to_numpy(float),
                    out["bid_sz"].fillna(0).to_numpy(float), out["ask_sz"].fillna(0).to_numpy(float))


def run_pm(rows_out: list, notes: dict) -> None:
    import holdout_mid as H
    q = pm_windows()
    maps = H.load_maps(ROOT / "data/live/holdout_maps")
    sett = pd.read_csv(ROOT / "data/holdout_raw/settlements.csv")
    ld = Loader()
    notes["pm_games"] = len(q)
    for i, a in q.iterrows():
        lo, hi, ko = int(a.window_start_ns), int(a.window_end_ns), int(a.ko.value)
        inst = H.instruments(a, maps)
        pc = maps["polymarket_com"][a.kalshi_ticker]
        home = a.game_id.split("_")[-1].upper()
        kt = ld.rows("kalshi", f"{a.kalshi_ticker}-{home}", lo, hi)
        kb = ld.book("kalshi", kt)
        km = (kb.bid + kb.ask) / 2
        ok = ~np.isnan(km)
        sig = signals(kb.ts[ok], km[ok], lo, hi)
        pt = ld.rows("polymarket", inst["polymarket"], lo, hi)
        pb = ld.book("polymarket", pt)
        tr = pt[(pt["kind"] == "trade") & pt["src_ts_ns"].notna()].sort_values("src_ts_ns", kind="stable")
        tts, tpx, tsz = (tr["src_ts_ns"].astype("int64").to_numpy(), tr["price"].to_numpy(float),
                         tr["size"].to_numpy(float))
        payout = np.nan
        f = PM_RES / f"{pc['condition']}.json"
        if f.exists() and f.read_text().strip() not in ("", "[]"):
            m = json.loads(f.read_text())[0]
            toks = dict(zip(json.loads(m["clobTokenIds"]), [float(x) for x in json.loads(m["outcomePrices"])]))
            payout = toks.get(pc["collector_home_token"], np.nan)
        if payout != payout:
            ks = sett[(sett.game_id == a.game_id) & (sett.side == "home")]["settlement_value_dollars"].astype(float)
            payout = float(ks.iloc[0]) if len(ks) else np.nan
            notes["pm_settle_fallback"] = notes.get("pm_settle_fallback", 0) + 1
        for maker, L in (("N", None), ("S", 0.25), ("S", 1.0)):
            fl = simulate(pb, tts, tpx, tsz, lo, hi, ko, None if maker == "N" else sig, L, "F1")
            sc = score(fl, pb, payout, PM_FEE)
            sc["venue"], sc["game"], sc["maker"], sc["L"], sc["rule"], sc["contract"] = \
                "polymarket.com", a.game_id, maker, L if L else 0.0, "F1", "home"
            rows_out.append(sc)
        notes.setdefault("pm_signals", 0)
        notes["pm_signals"] += len(sig)
        print(f"pm {i + 1}/{len(q)} {a.game_id} sig={len(sig)} trades={len(tts)}", flush=True)


def run_cme(rows_out: list, notes: dict) -> None:
    import databento as db
    raw = ROOT / "data/raw"
    m = pd.read_csv(raw / "cme_train_v2" / "map.csv")
    m = m[m["cme_mbp10_rows_in_window"] > 0]
    mbp = db.DBNStore.from_file(raw / "cme_train_v2" / "jan_mbp1.dbn.zst").to_df().reset_index()
    mbp["ts_event"] = mbp["ts_event"].dt.as_unit("ns").astype("int64")
    trd = pd.read_parquet(raw / "fg_cg_train_trades.parquet").reset_index()
    trd["ts_event"] = pd.to_datetime(trd["ts_event"], utc=True).dt.as_unit("ns").astype("int64")
    ko = pd.concat([pd.read_csv(raw / "kalshi_only_games.csv"),
                    pd.read_csv(raw / "cme_train_v2" / "kalshi_games.csv")]).drop_duplicates("game_id").set_index("game_id")
    notes["cme_games"] = m["game_id"].nunique()
    for gid, grp in m.groupby("game_id"):
        r = ko.loc[gid]
        k0 = pd.Timestamp(r.kickoff_utc_espn).value
        assert k0 < pd.Timestamp("2026-08-01", tz="UTC").value, "training only"
        kp = raw / ("kalshi_only" if grp["kalshi_dir"].iloc[0] == "kalshi_only" else "cme_train_v2/kalshi") / f"{gid}.parquet"
        kt = pd.read_parquet(kp, columns=["ts", "kind", "price"])
        kt = kt[kt["kind"] == "trade"].sort_values("ts", kind="stable")
        lo, hi = k0 - 2 * 3600 * NS, k0 + 5 * 3600 * NS
        sig = signals(kt["ts"].to_numpy(np.int64), np.round(kt["price"].to_numpy(float), 4), lo, hi)
        notes.setdefault("cme_signals", 0)
        notes["cme_signals"] += len(sig)
        res = float(r.settlement_result)
        for row in grp.itertuples():
            side = "home" if row.team == r.home else ("away" if row.team == r.away else None)
            if side is None:
                continue
            d = mbp[mbp["symbol"] == row.symbol].sort_values(["ts_event", "sequence"], kind="stable")
            if d.empty:
                continue
            bsz, asz = d["bid_sz_00"].to_numpy(float), d["ask_sz_00"].to_numpy(float)
            bid = np.where(bsz > 0, d["bid_px_00"].to_numpy(float), np.nan)
            ask = np.where((asz > 0) & (d["ask_px_00"].to_numpy(float) < 1.5), d["ask_px_00"].to_numpy(float), np.nan)
            bk = Book(d["ts_event"].to_numpy(np.int64), bid, ask, bsz, asz)
            t = trd[trd["symbol"] == row.symbol].sort_values(["ts_event"], kind="stable")
            tts, tpx, tsz = t["ts_event"].to_numpy(np.int64), t["price"].to_numpy(float), t["size"].to_numpy(float)
            payout = res if side == "home" else 1 - res
            csig = [(tt, dd if side == "home" else -dd) for tt, dd in sig]
            for rule in ("F1", "F2"):
                for maker, L in (("N", None), ("S", 0.25), ("S", 1.0)):
                    fl = simulate(bk, tts, tpx, tsz, lo, hi, k0, None if maker == "N" else csig, L, rule)
                    sc = score(fl, bk, payout, CME_FEE)
                    sc["venue"], sc["game"], sc["maker"], sc["L"], sc["rule"], sc["contract"] = \
                        "CME", gid, maker, L if L else 0.0, rule, row.symbol
                    rows_out.append(sc)
        print(f"cme {gid} sig={len(sig)}", flush=True)


def summarise(F: pd.DataFrame, games: dict) -> pd.DataFrame:
    out = []
    for (venue, rule), g in F.groupby(["venue", "rule"]):
        allg = games[venue]
        for L in LATS:
            n = g[(g.maker == "N")]
            s = g[(g.maker == "S") & (np.isclose(g.L, L))]
            row = {"venue": venue, "rule": rule, "L": L}
            for name, x in (("N", n), ("S", s)):
                q = x["qty"].sum()
                row.update({f"{name}_fills": len(x), f"{name}_contracts": q,
                            f"{name}_pnl60": x["pnl60"].sum(), f"{name}_pnlset": x["pnlset"].sum(),
                            f"{name}_pnl60_pc": x["pnl60"].sum() / q if q else np.nan,
                            f"{name}_pnlset_pc": x["pnlset"].sum() / q if q else np.nan,
                            f"{name}_as10": x["as10"].mean(), f"{name}_as60": x["as60"].mean()})
            for pn in ("pnl60", "pnlset"):
                gs = s.groupby("game")[pn].sum().reindex(allg, fill_value=0.0)
                gn = n.groupby("game")[pn].sum().reindex(allg, fill_value=0.0)
                e, lo_, hi_ = boot_diff(gs, gn)
                row.update({f"SminusN_{pn}": e, f"SminusN_{pn}_lo": lo_, f"SminusN_{pn}_hi": hi_})
            out.append(row)
    return pd.DataFrame(out)


def verdict(tab: pd.DataFrame, venue: str, L: float, pn: str = "pnl60") -> str:
    f1 = tab[(tab.venue == venue) & (tab.rule == "F1") & np.isclose(tab.L, L)]
    if f1.empty:
        return "does not make sense on this data (no F1 result)"
    f1 = f1.iloc[0]
    ok = f1[f"SminusN_{pn}"] > 0 and f1[f"SminusN_{pn}_lo"] > 0 and f1[f"S_{pn}"] > 0
    if venue == "CME":
        f2 = tab[(tab.venue == venue) & (tab.rule == "F2") & np.isclose(tab.L, L)]
        ok = ok and (not f2.empty) and np.sign(f2.iloc[0][f"SminusN_{pn}"]) == np.sign(f1[f"SminusN_{pn}"])
    return "makes sense" if ok else "does not make sense on this data"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, notes = [], {}
    run_cme(rows, notes)
    run_pm(rows, notes)
    F = pd.concat([r for r in rows if len(r)], ignore_index=True)
    Path("data/mm_cache").mkdir(parents=True, exist_ok=True)
    F.to_parquet("data/mm_cache/fills.parquet", index=False)
    games = {"CME": sorted(F[F.venue == "CME"]["game"].unique()) if (F.venue == "CME").any() else [],
             "polymarket.com": sorted(F[F.venue == "polymarket.com"]["game"].unique()) if (F.venue == "polymarket.com").any() else []}
    tab = summarise(F, games)
    tab.to_csv(OUT / "results.csv", index=False)
    lines = [f"# Kalshi-signal market making on the slow venue: results ({LABEL})", "",
             "Spec 6098d5c. One run, unedited. P&L in dollars (10-contract quotes); pnl60 = marked to slow-venue mid at "
             "fill + 60 s (primary), pnlset = held to settlement. S minus N = sum over games, game-bootstrap 95% CI "
             "(2,000, seed 20261004). Adverse selection as10/as60 = mean side x mid move after fill (negative = against us).",
             "", f"Notes: {json.dumps(notes)}", "", "| " + " | ".join(tab.columns) + " |", "|" + "---|" * len(tab.columns)]
    for r in tab.itertuples(index=False):
        lines.append("| " + " | ".join(f"{v:.4g}" if isinstance(v, float) else str(v) for v in r) + " |")
    lines += ["", "## Verdicts (pre-fixed reading rule, primary +60 s mark; settlement shown for reference)", ""]
    for venue in ("polymarket.com", "CME"):
        for L in LATS:
            lines.append(f"- {venue}, L {L} s: {verdict(tab, venue, L, 'pnl60')} (settlement mark: "
                         f"{verdict(tab, venue, L, 'pnlset')})")
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
