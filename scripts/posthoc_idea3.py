"""IDEA 3, Kalshi reversal after large taker trades. POST-HOC, EXPLORATORY (formed after seeing the holdout).

Spec: results/posthoc_latency/SPEC_idea3.md (commit 4e60e8c, before this script ran on real data).
A Kalshi trade print with size >= the market's 95th percentile of in-window trade sizes (whole-window
percentile: a lookahead in the threshold, kept as a property of the given rule) that moved the mid >= 2 c in
its direction is faded at the first snapshot received at or after t + L (t = print receipt time), and exited
at the quote in the first snapshot received at or after fill + 10 s. Kalshi direct fees both legs.

All prices are in stored P(home) terms (away markets flipped at ingest), so: buy home = stored ask (stored ask
size), sell home = stored bid (stored bid size), in either team market.

Usage: python scripts/posthoc_idea3.py   (writes results/posthoc_latency/idea3_results.csv and idea3_RESULTS.md)
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import costs
import laggard

NS = 1_000_000_000
MS = 1_000_000
SIZE = 10
LATENCIES = (0.25, 0.5, 1.0)
HOLD_S = 10
PCTL = 95
MIN_PRINTS = 20
MOVE = 0.02
TOL = 1e-9
KO_PRE_S, KO_POST_S = 2 * 60, 20 * 60
EXIT_TAIL_S = 60
PAD_S = 15 * 60                 # rows loaded around each window (pre-print books, exit quotes)
LABEL = "POST-HOC, EXPLORATORY (formed after seeing the holdout)"

SRC = Path("/Users/divyamkataria/GQ HACKS/staleline")
OUT = Path("results/posthoc_latency")


# ---------------------------------------------------------------- pure pieces (unit tested)

def book_snapshots(rows: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Top-of-book snapshots (rows sharing recv_ns) in stored P(home) terms. Returns (snapshots sorted by
    recv_ns with columns recv_ns, bms, bid, bsz, ask, asz, mid; number of book rows dropped for null src)."""
    cols = ["recv_ns", "bms", "bid", "bsz", "ask", "asz", "mid"]
    r = rows[rows["kind"].isin(["bid", "ask"])]
    n_null = int(r["src_ts_ns"].isna().sum())
    r = r.dropna(subset=["src_ts_ns"])
    if r.empty:
        return pd.DataFrame(columns=cols), n_null
    r = r.drop_duplicates(["recv_ns", "kind"], keep="last")
    src = r.groupby("recv_ns")["src_ts_ns"].first()
    w = r.pivot_table(index="recv_ns", columns="kind", values=["price", "size"], aggfunc="last")
    w.columns = [f"{a}_{b}" for a, b in w.columns]
    for c in ("price_bid", "price_ask", "size_bid", "size_ask"):
        if c not in w:
            w[c] = np.nan
    out = pd.DataFrame({"bms": np.rint(src.loc[w.index].to_numpy(dtype="float64") / MS).astype(np.int64),
                        "bid": w["price_bid"].to_numpy(), "bsz": w["size_bid"].to_numpy(),
                        "ask": w["price_ask"].to_numpy(), "asz": w["size_ask"].to_numpy()}, index=w.index)
    out["mid"] = (out["bid"] + out["ask"]) / 2          # NaN unless both sides present
    out.index.name = "recv_ns"
    return out.sort_index().reset_index()[cols], n_null


def dedupe_trades(tr: pd.DataFrame) -> pd.DataFrame:
    tr = tr[tr["kind"] == "trade"].sort_values("recv_ns", kind="stable")
    return tr.drop_duplicates(["ts", "price", "size", "side"], keep="first").sort_values("ts", kind="stable")


def in_cut(t_ns, ko_ns: int):
    return (t_ns >= ko_ns - KO_PRE_S * NS) & (t_ns <= ko_ns + KO_POST_S * NS)


def find_signals(tr: pd.DataFrame, snaps: pd.DataFrame, lo: int, hi: int, ko_ns: int, market: str,
                 counts: dict) -> list[dict]:
    """Signals of one market. tr: deduped trade rows (ts, recv_ns, size, side). The percentile uses all in-window
    prints of the market (whole window: stated lookahead of the given rule). Everything else uses only snapshots
    received at or before the print's receipt time t."""
    tr = tr[(tr["ts"] >= lo) & (tr["ts"] < hi) & ~in_cut(tr["ts"], ko_ns)]
    if len(tr) < MIN_PRINTS:
        counts["market_lt_min_prints"] = counts.get("market_lt_min_prints", 0) + 1
        return []
    thr = float(np.percentile(tr["size"].to_numpy(dtype=float), PCTL))
    big = tr[tr["size"] >= thr - TOL]
    counts["big_prints"] = counts.get("big_prints", 0) + len(big)
    s = snaps.sort_values(["bms", "recv_ns"], kind="stable")
    bms, rcv, mid = s["bms"].to_numpy(), s["recv_ns"].to_numpy(), s["mid"].to_numpy()
    out = []
    for p in big.itertuples():
        if p.side not in ("buy", "sell"):
            counts["unknown_side"] = counts.get("unknown_side", 0) + 1
            continue
        d = 1 if p.side == "buy" else -1
        t, pms = int(p.recv_ns), int(p.ts) // MS
        k = int(np.searchsorted(bms, pms, side="left"))
        ib, ia = k - 1, k                        # last with bms < print_ms; first with bms >= print_ms
        if ib < 0 or rcv[ib] > t:
            counts["no_pre_book"] = counts.get("no_pre_book", 0) + 1
            continue
        if ia >= len(bms) or rcv[ia] > t:
            counts["post_book_not_received"] = counts.get("post_book_not_received", 0) + 1
            continue
        mb, ma = mid[ib], mid[ia]
        if not (mb == mb and ma == ma):
            counts["mid_undefined"] = counts.get("mid_undefined", 0) + 1
            continue
        move = d * (ma - mb)
        if move < MOVE - TOL:
            counts["move_lt_2c"] = counts.get("move_lt_2c", 0) + 1
            continue
        out.append(dict(market=market, t=t, ts=int(p.ts), d=d, size=float(p.size), thr=thr, move=float(move),
                        pre_recv=int(rcv[ib]), post_recv=int(rcv[ia])))
    return out


def fee_c(price: float, qty: float) -> float:
    """Kalshi direct fee for one order, in cents per contract."""
    return costs.fee(price, qty, "buy", "kalshi", route="direct") * 100 / qty


def simulate(signals: list[dict], snaps: dict, L: float, ko_ns: int, hi: int, counts: dict) -> list[dict]:
    """One position at a time per game. signals: from all markets of the game. snaps: market -> snapshots."""
    trades, busy_until = [], -1
    for sg in sorted(signals, key=lambda x: (x["t"], x["market"])):
        if sg["t"] < busy_until:
            counts["busy"] = counts.get("busy", 0) + 1
            continue
        s = snaps[sg["market"]]
        rcv = s["recv_ns"].to_numpy()
        order = sg["t"] + int(round(L * NS))
        i = int(np.searchsorted(rcv, order, side="left"))
        if i >= len(rcv):
            counts["no_fill_snapshot"] = counts.get("no_fill_snapshot", 0) + 1
            continue
        short = sg["d"] == 1                     # fade a buy print: sell home at bid
        px, sz = (s["bid"].iat[i], s["bsz"].iat[i]) if short else (s["ask"].iat[i], s["asz"].iat[i])
        if not (px == px and sz == sz and sz > 0):
            counts["no_quote"] = counts.get("no_quote", 0) + 1
            continue
        q = float(min(SIZE, sz))
        fill_recv = int(rcv[i])
        xcol = "ask" if short else "bid"
        j = int(np.searchsorted(rcv, fill_recv + HOLD_S * NS, side="left"))
        xv = s[xcol].to_numpy()
        while j < len(rcv) and xv[j] != xv[j]:
            j += 1
        if j >= len(rcv):
            counts["no_exit_snapshot"] = counts.get("no_exit_snapshot", 0) + 1
            continue
        exit_recv, xpx = int(rcv[j]), float(xv[j])
        if in_cut(fill_recv, ko_ns) or in_cut(exit_recv, ko_ns):
            counts["fill_or_exit_in_cut"] = counts.get("fill_or_exit_in_cut", 0) + 1
            continue
        if exit_recv > hi + EXIT_TAIL_S * NS:
            counts["exit_after_window"] = counts.get("exit_after_window", 0) + 1
            continue
        gross = (px - xpx) * 100 if short else (xpx - px) * 100
        fe, fx = fee_c(px, q), fee_c(xpx, q)
        trades.append(dict(sg, L=L, side="short_home" if short else "long_home", fill_recv=fill_recv,
                           fill_delay_s=(fill_recv - order) / NS, entry=float(px), exit_recv=exit_recv,
                           exit=xpx, qty=q, gross_c=float(gross), fee_entry_c=fe, fee_exit_c=fx,
                           net_c=float(gross - fe - fx), print_recv_lag_s=(sg["t"] - sg["ts"]) / NS))
        busy_until = exit_recv
    return trades


def summarize(tr: pd.DataFrame, L: float) -> dict:
    """Per-L report row. tr: trades of this L with game_id and net_c."""
    if tr.empty:
        return dict(latency_s=L, trades=0, games_with_trades=0)
    pg = tr.groupby("game_id")["net_c"].agg(["sum", "count"])
    lo, hi = laggard.game_bootstrap_ci(pg["sum"].to_numpy(), pg["count"].to_numpy())
    x = tr["net_c"].to_numpy()
    sd = x.std(ddof=1) if len(x) > 1 else np.nan
    top5 = pg["sum"].sort_values(ascending=False).index[:5]
    y = tr.loc[~tr["game_id"].isin(top5), "net_c"].to_numpy()
    sdy = y.std(ddof=1) if len(y) > 1 else np.nan
    lag = tr["print_recv_lag_s"].to_numpy()
    return dict(latency_s=L, trades=len(x), games_with_trades=len(pg), contracts=float(tr["qty"].sum()),
                mean_gross_c=float(tr["gross_c"].mean()), mean_fees_c=float((tr.fee_entry_c + tr.fee_exit_c).mean()),
                mean_net_c=float(x.mean()), ci_lo=lo, ci_hi=hi,
                share_games_positive=float((pg["sum"] > 0).mean()),
                sharpe_per_trade=float(x.mean() / sd) if sd == sd and sd > 0 else np.nan,
                ex_top5_trades=len(y), ex_top5_mean_net_c=float(y.mean()) if len(y) else np.nan,
                ex_top5_sharpe=float(y.mean() / sdy) if sdy == sdy and sdy > 0 else np.nan,
                print_recv_lag_s_p50=float(np.median(lag)), print_recv_lag_s_p90=float(np.percentile(lag, 90)),
                print_recv_lag_s_max=float(lag.max()), prints_lag_gt_5s=int((lag > 5).sum()))


# ---------------------------------------------------------------- real data

def load_games():
    import posthoc_idea1
    return posthoc_idea1.load_games()


def load_rows(games):
    import pyarrow.dataset as ds
    fs = sorted(glob.glob(str(SRC / "data/vultr/data/live/kalshi/*/*.parquet")))
    tks = sorted({g["home_tk"] for g in games} | {g["away_tk"] for g in games})
    lo = min(g["lo"] for g in games) - PAD_S * NS
    hi = max(g["hi"] for g in games) + PAD_S * NS
    d = ds.dataset(fs, format="parquet")
    f = ds.field("market_id").isin(tks) & (ds.field("recv_ns") >= lo) & (ds.field("recv_ns") <= hi)
    t = d.to_table(filter=f, columns=["ts", "market_id", "kind", "price", "size", "side", "src_ts_ns",
                                      "recv_ns"]).to_pandas()
    t["market_id"] = t["market_id"].astype("category")
    return {k: v for k, v in t.groupby("market_id", observed=True)}


def main():
    games = load_games()
    print(f"{LABEL}\ngames: {len(games)}", flush=True)
    rows = load_rows(games)
    print(f"loaded {sum(len(v) for v in rows.values())} rows for {len(rows)} markets", flush=True)
    counts, sigs, snaps, n_null = {}, {}, {}, 0
    empty = pd.DataFrame(columns=["ts", "kind", "price", "size", "side", "src_ts_ns", "recv_ns"])
    for g in games:
        sigs[g["game_id"]], snaps[g["game_id"]] = [], {}
        for mk in (g["home_tk"], g["away_tk"]):
            r = rows.get(mk, empty)
            sn, nn = book_snapshots(r)
            n_null += nn
            snaps[g["game_id"]][mk] = sn
            if sn.empty:
                counts["market_no_book"] = counts.get("market_no_book", 0) + 1
                continue
            sigs[g["game_id"]] += find_signals(dedupe_trades(r), sn, g["lo"], g["hi"], g["ko"], mk, counts)
    counts["book_rows_null_src"] = n_null
    n_sig = sum(len(v) for v in sigs.values())
    print(f"signal counts: {counts}; signals: {n_sig}", flush=True)
    out, all_tr = [], []
    for L in LATENCIES:
        c = {}
        trs = []
        for g in games:
            for t in simulate(sigs[g["game_id"]], snaps[g["game_id"]], L, g["ko"], g["hi"], c):
                trs.append(dict(t, game_id=g["game_id"]))
        tr = pd.DataFrame(trs)
        row = dict(label="POST-HOC EXPLORATORY", games=len(games), signals=n_sig, **summarize(tr, L),
                   skips="; ".join(f"{k}: {v}" for k, v in sorted(c.items())))
        out.append(row)
        all_tr += trs
        print(row, flush=True)
    res = pd.DataFrame(out)
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT / "idea3_results.csv", index=False)
    pd.DataFrame(all_tr).to_csv(OUT / "idea3_trades.csv", index=False)
    write_md(res, len(games), counts)
    print(res.to_string())


def write_md(res: pd.DataFrame, n_games: int, counts: dict):
    def f(x, d=2):
        return "" if x != x else f"{x:.{d}f}"
    lines = ["# IDEA 3 results, Kalshi reversal after large taker trades. POST-HOC, EXPLORATORY (formed after "
             "seeing the holdout)", "",
             "Spec: results/posthoc_latency/SPEC_idea3.md (commit 4e60e8c). One run on real data, no changes after "
             f"output. Games: {n_games} (vultr). Net c/contract after Kalshi direct fees on both legs. CI: "
             "laggard.game_bootstrap_ci on per-game sums (2,000 draws, seed 20261003), games with >= 1 trade. "
             "The 95th percentile threshold uses the whole game window (lookahead in the threshold, a property "
             "of the given rule). No interpretation.", "",
             "| L (s) | trades | games w/ trades | mean gross c | mean fees c | mean net c | 95% CI | share games + | "
             "Sharpe/trade | ex top 5: trades | ex top 5: mean net c | ex top 5: Sharpe |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in res.itertuples():
        if x.trades == 0:
            lines.append(f"| {x.latency_s} | 0 | 0 | | | | | | | | | |")
            continue
        lines.append(f"| {x.latency_s} | {x.trades} | {x.games_with_trades} | {f(x.mean_gross_c)} | "
                     f"{f(x.mean_fees_c)} | {f(x.mean_net_c)} | [{f(x.ci_lo)}, {f(x.ci_hi)}] | "
                     f"{f(x.share_games_positive)} | {f(x.sharpe_per_trade, 3)} | {x.ex_top5_trades} | "
                     f"{f(x.ex_top5_mean_net_c)} | {f(x.ex_top5_sharpe, 3)} |")
    lines += ["", "Print receipt lag (recv_ns - ts) of traded prints, and skips:", "",
              "| L (s) | lag p50 s | lag p90 s | lag max s | traded prints lag > 5 s | execution skips |",
              "|---|---|---|---|---|---|"]
    for x in res.itertuples():
        if x.trades == 0:
            lines.append(f"| {x.latency_s} | | | | | {x.skips} |")
            continue
        lines.append(f"| {x.latency_s} | {f(x.print_recv_lag_s_p50)} | {f(x.print_recv_lag_s_p90)} | "
                     f"{f(x.print_recv_lag_s_max)} | {x.prints_lag_gt_5s} | {x.skips} |")
    lines += ["", f"Signal stage counts (all games): {', '.join(f'{k}: {v}' for k, v in sorted(counts.items()))}; "
              f"signals: {int(res['signals'].iat[0]) if len(res) else 0}.", "",
              "Variant count: 3 (one per L) added to the DSR total. Per-trade rows (our simulated trades only): "
              "results/posthoc_latency/idea3_trades.csv.", ""]
    (OUT / "idea3_RESULTS.md").write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
