"""Kalshi leads, CME maker variant (Amendment 1, f1b2677): descriptive, post-hoc, 14 games; queue position unknown,
trade-through fill is a lower bound on fills.

Usage (cwd = repo root, PYTHONPATH=.:scripts): python scripts/kalshi_cme_maker.py
Writes results/posthoc_kalshi_cme/maker_cells.csv and data/kalshi_cme_cache/maker_trades.parquet (gitignored).
"""
from __future__ import annotations

import sys

import databento as db
import numpy as np
import pandas as pd

import kalshi_cme_stage1 as S

NS = S.NS
J = 0.05
WS = (5, 30)
EXITS = ("t60", "settle")
LABEL = "descriptive, post-hoc, 14 games; queue position unknown, trade-through fill is a lower bound on fills"


def first_through(tts: np.ndarray, tpx: np.ndarray, t: int, W: int, limit: float, d: int):
    """First CME trade print in (t, t + W] strictly through the limit: below it for a buy, above it for a sell."""
    i = np.searchsorted(tts, t, side="right")
    j = np.searchsorted(tts, t + W * NS, side="right")
    seg = tpx[i:j]
    hit = np.flatnonzero(seg < limit - S.EPS) if d > 0 else np.flatnonzero(seg > limit + S.EPS)
    return int(tts[i + hit[0]]) if len(hit) else None


def attempt(book: S.Book, tts, tpx, t: int, d: int, W: int, payout: float) -> list[dict]:
    b, a, bs, as_ = book.at(t)
    limit, sz = (b, bs) if d > 0 else (a, as_)
    base = {"limit": limit, "attempted": limit == limit and sz >= 1}
    rows = []
    for ex in EXITS:
        r = dict(base, exit_mode=ex, filled=False)
        if base["attempted"]:
            ft = first_through(tts, tpx, t, W, limit, d)
            if ft is not None:
                r.update(filled=True, fill_ts=ft, qty=10.0)
                if ex == "t60":
                    b6, a6, _, _ = book.at(ft + 60 * NS)
                    xp = b6 if d > 0 else a6
                    if xp != xp:
                        r.update(no_exit=True)
                        rows.append(r)
                        continue
                    ntr = 2
                else:
                    xp, ntr = payout, 1
                gross = (xp - limit) * d
                r.update(no_exit=False, exit_px=xp, n_trades=ntr, gross_pc=gross, profit_pc=gross - S.FEE * ntr,
                         pnl=(gross - S.FEE * ntr) * 10.0)
        rows.append(r)
    return rows


def main() -> None:
    m = pd.read_csv(S.DATA / "cme_train_v2" / "map.csv")
    m = m[m["cme_mbp10_rows_in_window"] > 0]
    mbp = db.DBNStore.from_file(S.DATA / "cme_train_v2" / "jan_mbp1.dbn.zst").to_df().reset_index()
    mbp["ts_event"] = mbp["ts_event"].dt.as_unit("ns").astype("int64")
    tr = pd.read_parquet(S.DATA / "fg_cg_train_trades.parquet").reset_index()
    tr["ts_event"] = tr["ts_event"].dt.as_unit("ns").astype("int64")
    ko = pd.concat([pd.read_csv(S.DATA / "kalshi_only_games.csv"),
                    pd.read_csv(S.DATA / "cme_train_v2" / "kalshi_games.csv")]).drop_duplicates("game_id")
    ko = ko.set_index("game_id")
    games = {}
    for gid, grp in m.groupby("game_id"):
        r = ko.loc[gid]
        k0 = pd.Timestamp(r.kickoff_utc_espn).value
        assert k0 < S.SEAL.value, "training only"
        kp = S.DATA / ("kalshi_only" if grp["kalshi_dir"].iloc[0] == "kalshi_only" else "cme_train_v2/kalshi") \
            / f"{gid}.parquet"
        kts, kpx = S.kalshi_phome(kp)
        res = float(r.settlement_result)
        con = {}
        for row in grp.itertuples():
            side = "home" if row.team == r.home else ("away" if row.team == r.away else None)
            if side is None:
                continue
            bk = S.Book(mbp[mbp["symbol"] == row.symbol])
            x = tr[tr["symbol"] == row.symbol].sort_values("ts_event", kind="stable")
            if len(bk.ts) == 0:
                continue
            con[row.symbol] = (side, bk, x["ts_event"].to_numpy(np.int64), x["price"].to_numpy(float),
                               res if side == "home" else 1 - res)
        games[gid] = {"k0": k0, "kts": kts, "kpx": kpx, "con": con}
    sig = {g: S.signals(v["kts"], v["kpx"], v["k0"] - 2 * 3600 * NS, v["k0"] + 5 * 3600 * NS, J)
           for g, v in games.items()}
    rows = []
    for kind in ("real", "placebo"):
        for A, ga in games.items():
            for B in ([A] if kind == "real" else [b for b in games if b != A]):
                for tb, d in sig[B]:
                    t = tb if kind == "real" else ga["k0"] + (tb - games[B]["k0"])
                    for sym, (side, bk, tts, tpx, payout) in ga["con"].items():
                        if t < bk.ts[0]:
                            continue
                        dd = d if side == "home" else -d
                        for W in WS:
                            for r in attempt(bk, tts, tpx, t, dd, W, payout):
                                rows.append({"kind": kind, "game": A, "src": B, "sym": sym, "t": t, "dir": dd,
                                             "W": W, **r})
    T = pd.DataFrame(rows)
    S.CACHE.mkdir(parents=True, exist_ok=True)
    T.to_parquet(S.CACHE / "maker_trades.parquet", index=False)
    cells = []
    for (W, ex), g in T.groupby(["W", "exit_mode"]):
        re, pl = g[g.kind == "real"], g[g.kind == "placebo"]
        rf = re[re.filled & (re.no_exit != True)]
        pf = pl[pl.filled & (pl.no_exit != True)]
        est, lo, hi = S.boot(rf)
        pe, plo, phi = S.boot(pf)
        de, dlo, dhi = S.boot_diff(rf, pf) if len(rf) and len(pf) else (np.nan,) * 3
        gp = rf.groupby("game")["pnl"].sum().sort_values(ascending=False)
        keep = rf[~rf.game.isin(gp.index[:5])]
        ntr = 2 if ex == "t60" else 1
        cells.append({"W_s": W, "exit": ex, "attempts": int(re.attempted.sum()),
                      "not_attempted_no_quote": int((~re.attempted).sum()),
                      "fills": int(re.filled.sum()), "fill_rate": float(re.filled.sum() / max(re.attempted.sum(), 1)),
                      "no_exit_quote": int((re.filled & (re.no_exit == True)).sum()), "traded": len(rf),
                      "games": int(rf.game.nunique()),
                      "gross_pc": float(rf.gross_pc.mean()) if len(rf) else np.nan,
                      "profit_pc": est, "ci_lo": lo, "ci_hi": hi, "pnl_total": float(rf.pnl.sum()),
                      "excl_top5_profit_pc": float(keep.pnl.sum() / keep.qty.sum()) if len(keep) else np.nan,
                      "breakeven_commission_per_contract_per_trade": est / ntr if est == est else np.nan,
                      "placebo_attempts": int(pl.attempted.sum()),
                      "placebo_fill_rate": float(pl.filled.sum() / max(pl.attempted.sum(), 1)),
                      "placebo_profit_pc": pe, "placebo_ci_lo": plo, "placebo_ci_hi": phi,
                      "real_minus_placebo": de, "diff_ci_lo": dlo, "diff_ci_hi": dhi, "label": LABEL})
    C = pd.DataFrame(cells)
    C.to_csv(S.OUT / "maker_cells.csv", index=False)
    pd.set_option("display.width", 300, "display.max_columns", 40)
    print(f"real J=5c signals: {sum(len(v) for v in sig.values())}")
    print(C.drop(columns=["label"]).round(4).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
