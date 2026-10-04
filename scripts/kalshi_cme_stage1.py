"""Post-hoc Kalshi leads, trade CME: Stage 1 (descriptive, post-hoc, 14 training games).

Spec: results/posthoc_kalshi_cme/SPEC.md (657c5b6, committed before any Stage 1 computation).
Usage (cwd = repo root): python scripts/kalshi_cme_stage1.py
Writes results/posthoc_kalshi_cme/stage1_cells.csv, stage1_games.csv and data/kalshi_cme_cache/stage1_trades.parquet
(gitignored; contains CME prices).
"""
from __future__ import annotations

import sys
from pathlib import Path

import databento as db
import numpy as np
import pandas as pd

DATA = Path("/Users/divyamkataria/GQ HACKS/staleline/data/raw")
OUT = Path("results/posthoc_kalshi_cme")
CACHE = Path("data/kalshi_cme_cache")
NS = 1_000_000_000
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
FEE = 0.01                      # CME 25-466 Appendix D, per contract per Globex trade
SEED, NBOOT = 20261004, 2000
JS, LS, EXITS = (0.03, 0.04, 0.05), (1, 2, 5), ("t60", "settle")
EPS = 1e-9


def kalshi_phome(path: Path) -> tuple[np.ndarray, np.ndarray]:
    t = pd.read_parquet(path, columns=["ts", "kind", "price"])
    t = t[t["kind"] == "trade"].sort_values("ts", kind="stable")
    return t["ts"].to_numpy(np.int64), np.round(t["price"].to_numpy(float), 4)


def signals(ts: np.ndarray, px: np.ndarray, lo: int, hi: int, J: float) -> list[tuple[int, int]]:
    """Kalshi P(home) move >= J within trailing 10 s (trades in [t - 10 s, t]); 10 s refractory after a signal."""
    out, block = [], -1
    j0 = 0
    for i in range(len(ts)):
        t = ts[i]
        if t < lo or t > hi or t < block:
            continue
        while ts[j0] < t - 10 * NS:
            j0 += 1
        w = px[j0:i + 1]
        up, dn = px[i] - w.min(), w.max() - px[i]
        if up >= J - EPS or dn >= J - EPS:
            out.append((int(t), 1 if up >= dn else -1))
            block = t + 10 * NS
    return out


class Book:
    """CME top of book by venue time: state at T = latest update with ts_event <= T."""

    def __init__(self, d: pd.DataFrame):
        d = d.sort_values(["ts_event", "sequence"], kind="stable")
        self.ts = d["ts_event"].to_numpy(np.int64)
        bid, ask = d["bid_px_00"].to_numpy(float), d["ask_px_00"].to_numpy(float)
        bsz, asz = d["bid_sz_00"].to_numpy(float), d["ask_sz_00"].to_numpy(float)
        self.bid = np.where((bsz > 0) & np.isfinite(bid) & (bid > 0), bid, np.nan)
        self.ask = np.where((asz > 0) & np.isfinite(ask) & (ask > 0) & (ask < 1.5), ask, np.nan)
        self.bsz, self.asz = bsz, asz

    def at(self, T: int):
        i = np.searchsorted(self.ts, T, side="right") - 1
        if i < 0:
            return np.nan, np.nan, 0.0, 0.0
        return self.bid[i], self.ask[i], self.bsz[i], self.asz[i]

    def mid(self, T: int) -> float:
        b, a, _, _ = self.at(T)
        return (b + a) / 2 if b == b and a == a else np.nan


def legs(book: Book, t: int, d: int, L: int, payout: float) -> list[dict]:
    """d = +1 buy (signal favours this team), -1 sell. Returns one row per exit."""
    m0, mL = book.mid(t), book.mid(t + L * NS)
    b, a, bs, as_ = book.at(t + L * NS)
    moved = (mL - m0) * d >= 0.01 - EPS if (m0 == m0 and mL == mL) else True
    side_px, side_sz = (a, as_) if d > 0 else (b, bs)
    base = {"m0": m0, "mL": mL, "not_moved": (not moved) and m0 == m0 and mL == mL,
            "side_ok": side_px == side_px and side_sz >= 1, "disp_size": side_sz, "entry": side_px}
    base["executable"] = base["not_moved"] and base["side_ok"]
    rows = []
    for ex in EXITS:
        r = dict(base, exit_mode=ex)
        if base["executable"]:
            q = min(10.0, float(side_sz))
            if ex == "t60":
                b6, a6, _, _ = book.at(t + 60 * NS)
                xp = b6 if d > 0 else a6
                if xp != xp:
                    r.update(no_exit=True)
                    rows.append(r)
                    continue
                fees = 2 * FEE
            else:
                xp, fees = payout, FEE
            ppc = (xp - side_px) * d - fees
            r.update(no_exit=False, qty=q, exit_px=xp, profit_pc=ppc, pnl=ppc * q)
        rows.append(r)
    return rows


def boot(df: pd.DataFrame) -> tuple[float, float, float]:
    """Profit per contract = sum pnl / sum qty, game-level bootstrap."""
    if df.empty:
        return np.nan, np.nan, np.nan
    g = df.groupby("game")[["pnl", "qty"]].sum()
    p, q = g["pnl"].to_numpy(), g["qty"].to_numpy()
    est = p.sum() / q.sum()
    if len(p) < 2:
        return est, np.nan, np.nan
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(p), (NBOOT, len(p)))
    bs = p[idx].sum(1) / q[idx].sum(1)
    return float(est), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def boot_diff(real: pd.DataFrame, plc: pd.DataFrame) -> tuple[float, float, float]:
    """(real - placebo) profit per contract, resampling games (the CME game is the cluster in both)."""
    gr = real.groupby("game")[["pnl", "qty"]].sum()
    gp = plc.groupby("game")[["pnl", "qty"]].sum()
    games = sorted(set(gr.index) | set(gp.index))
    gr, gp = gr.reindex(games, fill_value=0.0), gp.reindex(games, fill_value=0.0)
    f = lambda R, P: R["pnl"].sum() / max(R["qty"].sum(), EPS) - P["pnl"].sum() / max(P["qty"].sum(), EPS)
    est = f(gr, gp)
    rng = np.random.default_rng(SEED)
    rp, rq, pp, pq = (gr["pnl"].to_numpy(), gr["qty"].to_numpy(), gp["pnl"].to_numpy(), gp["qty"].to_numpy())
    idx = rng.integers(0, len(games), (NBOOT, len(games)))
    bs = rp[idx].sum(1) / np.maximum(rq[idx].sum(1), EPS) - pp[idx].sum(1) / np.maximum(pq[idx].sum(1), EPS)
    return float(est), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def main() -> None:
    m = pd.read_csv(DATA / "cme_train_v2" / "map.csv")
    m = m[m["cme_mbp10_rows_in_window"] > 0]
    mbp = db.DBNStore.from_file(DATA / "cme_train_v2" / "jan_mbp1.dbn.zst").to_df().reset_index()
    mbp["ts_event"] = mbp["ts_event"].dt.as_unit("ns").astype("int64")
    ko = pd.concat([pd.read_csv(DATA / "kalshi_only_games.csv"),
                    pd.read_csv(DATA / "cme_train_v2" / "kalshi_games.csv")]).drop_duplicates("game_id")
    ko = ko.set_index("game_id")
    games = {}
    for gid, grp in m.groupby("game_id"):
        r = ko.loc[gid]
        k0 = pd.Timestamp(r.kickoff_utc_espn).value
        assert k0 < SEAL.value, "training only"
        kp = DATA / ("kalshi_only" if grp["kalshi_dir"].iloc[0] == "kalshi_only" else "cme_train_v2/kalshi") \
            / f"{gid}.parquet"
        kts, kpx = kalshi_phome(kp)
        res = float(r.settlement_result)
        contracts = {}
        for row in grp.itertuples():
            side = "home" if row.team == r.home else ("away" if row.team == r.away else None)
            if side is None:
                continue
            bk = Book(mbp[mbp["symbol"] == row.symbol])
            if len(bk.ts) == 0:
                continue
            payout = res if side == "home" else 1 - res
            contracts[row.symbol] = (side, bk, payout)
        games[gid] = {"k0": k0, "kts": kts, "kpx": kpx, "contracts": contracts,
                      "lo": k0 - 2 * 3600 * NS, "hi": k0 + 5 * 3600 * NS}
    print(f"games {len(games)}; contracts {sum(len(g['contracts']) for g in games.values())}", flush=True)

    rows = []
    for J in JS:
        sig = {gid: signals(g["kts"], g["kpx"], g["lo"], g["hi"], J) for gid, g in games.items()}
        for kind in ("real", "placebo"):
            for A, ga in games.items():
                srcs = [A] if kind == "real" else [B for B in games if B != A]
                for B in srcs:
                    for t_b, d in sig[B]:
                        t = t_b if kind == "real" else ga["k0"] + (t_b - games[B]["k0"])
                        for sym, (side, bk, payout) in ga["contracts"].items():
                            if t < bk.ts[0]:
                                continue
                            dd = d if side == "home" else -d
                            for L in LS:
                                for r in legs(bk, t, dd, L, payout):
                                    rows.append({"J": J, "L": L, "kind": kind, "game": A, "src": B, "sym": sym,
                                                 "t": t, "dir": dd, **r})
        print(f"J {J}: real signals {sum(len(v) for v in sig.values())}", flush=True)
    T = pd.DataFrame(rows)
    CACHE.mkdir(parents=True, exist_ok=True)
    T.to_parquet(CACHE / "stage1_trades.parquet", index=False)

    cells = []
    for (J, L, ex), g in T.groupby(["J", "L", "exit_mode"]):
        re, pl = g[g.kind == "real"], g[g.kind == "placebo"]
        rx = re[re.executable & (re.no_exit == False)]
        px = pl[pl.executable & (pl.no_exit == False)]
        est, lo, hi = boot(rx)
        pe, plo, phi = boot(px)
        de, dlo, dhi = boot_diff(rx, px) if len(rx) and len(px) else (np.nan,) * 3
        gp = rx.groupby("game")["pnl"].sum().sort_values(ascending=False)
        keep = rx[~rx.game.isin(gp.index[:5])]
        cells.append({"J": J, "L": L, "exit": ex,
                      "signals_real": int(re[["game", "t"]].drop_duplicates().shape[0]),
                      "contract_signals_real": len(re), "share_not_moved": float(re.not_moved.mean()),
                      "share_side_ok": float(re.side_ok.mean()), "executable_share": float(re.executable.mean()),
                      "executable_n": int(re.executable.sum()), "no_exit_quote": int((re.executable & re.no_exit.fillna(False)).sum()),
                      "traded_n": len(rx), "games": int(rx.game.nunique()), "mean_disp_size": float(rx.disp_size.mean()) if len(rx) else np.nan,
                      "profit_pc": est, "ci_lo": lo, "ci_hi": hi, "pnl_total": float(rx.pnl.sum()),
                      "excl_top5_profit_pc": float(keep.pnl.sum() / keep.qty.sum()) if len(keep) else np.nan,
                      "placebo_traded_n": len(px), "placebo_profit_pc": pe, "placebo_ci_lo": plo, "placebo_ci_hi": phi,
                      "real_minus_placebo": de, "diff_ci_lo": dlo, "diff_ci_hi": dhi,
                      "label": "descriptive, post-hoc, 14 games; profit after CME exchange fee $0.01/contract/trade, before broker commissions"})
    C = pd.DataFrame(cells)
    OUT.mkdir(parents=True, exist_ok=True)
    C.to_csv(OUT / "stage1_cells.csv", index=False)
    G = T[(T.kind == "real")].groupby(["J", "L", "exit_mode", "game"]).agg(
        signals=("t", "nunique"), executable=("executable", "sum"), pnl=("pnl", "sum"), qty=("qty", "sum")).reset_index()
    G.to_csv(OUT / "stage1_games.csv", index=False)
    pd.set_option("display.width", 300, "display.max_columns", 40)
    print(C.drop(columns=["label"]).round(4).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
