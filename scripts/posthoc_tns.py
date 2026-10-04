"""Post-hoc T&S laggard test (EXPLORATORY, selected after seeing the holdout).

Spec: results/posthoc_tns/SPEC.md (committed before this file existed). The pre-registered laggard signal code
(laggard.signals, unchanged) is fed a synthetic Polymarket US follower book built from Time & Sales prints:
bid = ask = home-oriented print price at each print's venue time, so the Amendment 2 mid is the last trade.
Fills: first print at or after decision + L (entry) / the exit decision time (exit), +1 c buy / -1 c sell,
capped to [0.01, 0.99]; no print within 60 s -> skip; costs.fee Polymarket US on each leg.
Kalshi: the run's recorded books on the run's machine, loaded with final_test_run.rows_with_size.

  PYTHONPATH=.:scripts python scripts/posthoc_tns.py --tns <csv> --staleline <dir> --spec-commit "<hash time>"
      [--pytest-summary "<line>"]

Writes results/posthoc_tns/{results.csv, trades.csv, RESULTS.md}. Never writes raw T&S prints.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import costs  # noqa: E402
import laggard as L  # noqa: E402

NS = 1_000_000_000
ET = "America/New_York"
VENUE = "polymarket_us"
LATENCIES = (1.0, 2.0, 5.0)
PRIMARY_L = 1.0
MAX_WAIT_NS = 60 * NS
COVER_END_NS = int(pd.Timestamp("2026-10-03 17:00", tz=ET).value)
QTY = L.SETTING["qty"]
OUT = ROOT / "results" / "posthoc_tns"
SEED = 20261003
SKIP_ENTRY = "no entry trade within 60 s"
SKIP_EXIT = "no exit trade within 60 s"
OUTSIDE = "outside coverage"

_TS = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?([+-])(\d{2}):(\d{2})$")


# ---------- parsing and price series ----------

def parse_venue_time(s: pd.Series) -> np.ndarray:
    """ISO 8601 venue time strings -> UTC ns (int64), integer arithmetic only. Only offset -04:00 is accepted."""
    p = s.astype(str).str.extract(_TS)
    if p.isna()[[0, 1, 3, 4, 5]].any().any():
        bad = s[p[0].isna()].head(3).tolist()
        raise ValueError(f"unparseable Transaction Time, e.g. {bad}")
    off = p[3] + p[4] + ":" + p[5]
    if (off != "-04:00").any():
        raise ValueError(f"unexpected offsets {sorted(off.unique())}")
    local = pd.to_datetime(p[0] + " " + p[1], format="%Y-%m-%d %H:%M:%S").to_numpy().astype("datetime64[ns]").astype("int64")
    frac = p[2].fillna("").str.ljust(9, "0").astype("int64").to_numpy()
    return local + frac + 4 * 3600 * NS            # local = UTC - 4 h


def home_price(last_price: np.ndarray, long_is_away: bool) -> np.ndarray:
    p = np.asarray(last_price, float)
    return np.round(1.0 - p, 4) if long_is_away else np.round(p, 4)


def load_tns(path: Path, slugs: set) -> dict:
    """slug -> (ts ns int64 sorted stably, raw Last Price float), file order kept at equal ns."""
    d = pd.read_csv(path, dtype=str, usecols=["Transaction Time", "Symbol", "Last Price"])
    d = d[d["Symbol"].isin(slugs)]
    out = {}
    for slug, g in d.groupby("Symbol", sort=False):
        ts = parse_venue_time(g["Transaction Time"])
        px = g["Last Price"].astype(float).to_numpy()
        o = np.argsort(ts, kind="stable")
        out[slug] = (ts[o], px[o])
    return out


def synthetic_ticks(ts: np.ndarray, home_px: np.ndarray, slug: str) -> pd.DataFrame:
    """Follower tick table for laggard.signals: per print, a bid row and an ask row at the print price."""
    n = len(ts)
    return pd.DataFrame({"ts": np.repeat(np.asarray(ts, "int64"), 2), "venue": VENUE, "market_id": slug,
                         "kind": np.tile(["bid", "ask"], n), "price": np.repeat(np.asarray(home_px, float), 2)})


def price_at(ts: np.ndarray, px: np.ndarray, t_ns: int) -> float:
    """Backward only: price of the last print with venue time <= t_ns (last in file order at equal ns)."""
    i = int(np.searchsorted(ts, t_ns, side="right")) - 1
    return float(px[i]) if i >= 0 else float("nan")


def first_trade(ts: np.ndarray, t_ns: int, cover_end_ns: int = COVER_END_NS, max_wait_ns: int = MAX_WAIT_NS):
    """(index, reason) of the first print with venue time in [t_ns, t_ns + max_wait] (first in file order at
    equal ns). reason "" when found; "outside coverage" when none is found before the coverage end and the
    window reaches it (or t_ns is already past it); "none" when no print in a window fully inside coverage."""
    if t_ns >= cover_end_ns:
        return None, OUTSIDE
    i = int(np.searchsorted(ts, t_ns, side="left"))
    if i < len(ts) and ts[i] <= t_ns + max_wait_ns and ts[i] < cover_end_ns:
        return i, ""
    if t_ns + max_wait_ns >= cover_end_ns:
        return None, OUTSIDE
    return None, "none"


def fill_price(p: float, buy: bool) -> float:
    """+1 c buying, -1 c selling, then capped to [0.01, 0.99]."""
    return round(min(p + 0.01, 0.99), 4) if buy else round(max(p - 0.01, 0.01), 4)


# ---------- round trips ----------

def simulate(sig: pd.DataFrame, ts: np.ndarray, px: np.ndarray, latency_s: float,
             cover_end_ns: int = COVER_END_NS, max_wait_ns: int = MAX_WAIT_NS) -> pd.DataFrame:
    """One row per signal at one latency. px = home-oriented print prices aligned with ts."""
    lat = int(round(latency_s * NS))
    rows = []
    for s in sig.itertuples():
        d_ns, x_ns = int(s.entry_decision_ns), int(s.exit_decision_ns)
        t_in = d_ns + lat
        row = {"latency_s": latency_s, "entry_g": int(s.entry_g), "direction": int(s.direction), "qty": int(s.qty),
               "exit_reason": s.exit_reason, "decision_ns": d_ns, "entry_time_ns": t_in, "exit_time_ns": x_ns,
               "tns_price_at_decision": price_at(ts, px, d_ns)}
        if d_ns >= cover_end_ns:
            rows.append({**row, "status": OUTSIDE})
            continue
        i, r_in = first_trade(ts, t_in, cover_end_ns, max_wait_ns)
        j, r_out = first_trade(ts, x_ns, cover_end_ns, max_wait_ns)
        if r_in or r_out:
            st = OUTSIDE if OUTSIDE in (r_in, r_out) else (SKIP_ENTRY if r_in else SKIP_EXIT)
            rows.append({**row, "status": st})
            continue
        buy_in = s.direction == 1
        p_in, p_out = float(px[i]), float(px[j])
        f_in, f_out = fill_price(p_in, buy_in), fill_price(p_out, not buy_in)
        e_ts, x_ts = int(ts[i]), int(ts[j])
        fee_in = costs.fee(f_in, s.qty, "buy" if buy_in else "sell", VENUE, ts=e_ts)
        fee_out = costs.fee(f_out, s.qty, "sell" if buy_in else "buy", VENUE, ts=x_ts)
        pnl = s.direction * (f_out - f_in) * s.qty - fee_in - fee_out
        rows.append({**row, "status": "filled", "entry_trade_ns": e_ts, "entry_trade_price": p_in, "entry_fill": f_in,
                     "exit_trade_ns": x_ts, "exit_trade_price": p_out, "exit_fill": f_out,
                     "fee_entry": fee_in, "fee_exit": fee_out, "pnl_usd": round(pnl, 6),
                     "net_c_per_contract": round(pnl * 100 / s.qty, 6)})
    df = pd.DataFrame(rows)
    for c in ("entry_trade_ns", "exit_trade_ns"):      # exact ns with gaps: nullable Int64, never float
        df[c] = pd.array([r.get(c) for r in rows], dtype="Int64")
    return df


def summarize(t: pd.DataFrame) -> dict:
    """Stats over filled rows of one latency (SPEC (g))."""
    f = t[t["status"] == "filled"]
    out = {"trades": len(f)}
    if not len(f):
        return {**out, "games_with_trades": 0}
    g = f.groupby("game_id").agg(pnl=("pnl_usd", "sum"), sumc=("net_c_per_contract", "sum"), n=("pnl_usd", "size"))
    lo, hi = L.game_bootstrap_ci(g["sumc"].to_numpy(), g["n"].to_numpy())
    sd = g["pnl"].std(ddof=1)
    top5 = g.nlargest(5, "pnl").index
    rest = f[~f["game_id"].isin(top5)]
    return {**out, "games_with_trades": len(g), "mean_net_c_per_contract": float(f["net_c_per_contract"].mean()),
            "ci_low": lo, "ci_high": hi, "share_games_positive": float((g["pnl"] > 0).mean()),
            "per_game_sharpe_not_annualized": float(g["pnl"].mean() / sd) if sd > 0 else float("nan"),
            "mean_net_c_excl_top5_games": float(rest["net_c_per_contract"].mean()) if len(rest) else float("nan"),
            "trades_excl_top5": len(rest), "pnl_total_usd": float(g["pnl"].sum())}


def et(ns) -> str:
    """UTC ns -> ET wall time with 9 fractional digits."""
    if ns is None or pd.isna(ns):
        return ""
    ns = int(ns)
    return pd.Timestamp(ns - ns % NS, tz="UTC").tz_convert(ET).strftime("%Y-%m-%d %H:%M:%S") + f".{ns % NS:09d} ET"


def md_table(d: pd.DataFrame) -> str:
    f = lambda v: f"{v:.4f}" if isinstance(v, float) else str(v)
    lines = ["| " + " | ".join(d.columns) + " |", "|" + "---|" * len(d.columns)]
    lines += ["| " + " | ".join(f(v) for v in r) + " |" for r in d.itertuples(index=False)]
    return "\n".join(lines)


# ---------- real-data driver ----------

def universe(sl: Path) -> pd.DataFrame:
    pg = pd.read_csv(sl / "results" / "holdout" / "lead_Polymarket US_per_game.csv")
    q = pg[pg["qualifying"].astype("boolean").fillna(False).astype(bool)]
    return q[q["window_start_ns"] < COVER_END_NS].reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tns", type=Path, required=True)
    ap.add_argument("--staleline", type=Path, required=True)
    ap.add_argument("--spec-commit", required=True)
    ap.add_argument("--pytest-summary", default="")
    a = ap.parse_args()
    sl = a.staleline.resolve()
    sys.path.insert(0, str(ROOT / "scripts"))
    import final_test_run as F                  # rows_with_size: the run's own loader
    import holdout_mid as H

    vroot, mroot = sl / "data" / "vultr", sl / "data" / "mac"
    machines = {"vultr": H.Machine("vultr", vroot, vroot / "GAPS_vultr.md", vroot / "heartbeats"),
                "mac": H.Machine("mac", sl, mroot / "GAPS_mac.md", mroot / "heartbeats")}
    cands = pd.read_csv(sl / "data" / "live" / "holdout_candidates.csv").set_index("game_id")
    maps = H.load_maps(sl / "data" / "live" / "holdout_maps")
    pmus = json.loads((sl / "data" / "live" / "holdout_maps" / "polymarket_us_map.json").read_text())

    q = universe(sl)
    games = []
    for r in q.itertuples():
        i = H.instruments(cands.loc[[r.game_id]].reset_index().iloc[0], maps)
        slug = i["polymarket_us"]
        lia = (pmus.get(slug) or {}).get("long_is_away")
        if lia is None:
            raise SystemExit(f"{r.game_id}: long_is_away missing for {slug}")
        games.append((r, i, slug, bool(lia)))
    print(f"universe: {len(games)} games; long_is_away True for {sum(g[3] for g in games)}", flush=True)
    tns = load_tns(a.tns, {g[2] for g in games})
    missing = [g[2] for g in games if g[2] not in tns]
    if missing:
        raise SystemExit(f"slugs with no T&S prints: {missing}")

    rows = []
    for r, i, slug, lia in games:
        m = machines[r.machine]
        lo = int(r.window_start_ns)
        pin = None if pd.isna(r.pin_start_g) else int(r.pin_start_g)
        hi = L.trading_end_ns(pd.Timestamp(r.kickoff_utc).value, pin)
        kt = F.rows_with_size(m, "kalshi", i["kalshi"], lo - 3600 * NS, hi + 120 * NS)
        gaps = m.gaps()
        outs = [(int(g.start_ns), int(g.end_ns)) for g in gaps[gaps["venue"].isin(["kalshi", "all"])].itertuples()
                if g.end_ns > lo and g.start_ns < hi]
        ts, raw = tns[slug]
        hp = home_price(raw, lia)
        syn = synthetic_ticks(ts, hp, slug)
        exclude = [(int(r.excl_lo_g), int(r.excl_hi_g))]
        sig = L.signals(kt, syn, VENUE, lo, hi, exclude=exclude, outages=outs)
        if not len(sig):
            continue
        lo_g, hi_g = lo // NS, hi // NS - 1
        br = L._breaks_g(exclude, outs)
        gk = L._grid(kt, "kalshi", lo_g, hi_g, br)
        go = L._grid(syn, VENUE, lo_g, hi_g, br)
        for lat in LATENCIES:
            t = simulate(sig, ts, hp, lat)
            t["kalshi_mid_at_decision"] = [float(gk.get(g, np.nan)) for g in t["entry_g"]]
            t["tns_grid_price_at_decision"] = [float(go.get(g, np.nan)) for g in t["entry_g"]]
            rows.append(t.assign(game_id=r.game_id, slug=slug, machine=r.machine))
        print(f"{r.game_id}: {len(sig)} signals", flush=True)
    t = pd.concat(rows, ignore_index=True)

    res = []
    for lat in LATENCIES:
        d = t[t["latency_s"] == lat]
        s = summarize(d)
        res.append({"latency_s": lat, "primary": lat == PRIMARY_L, "signals": len(d), **s,
                    "skips_no_entry_trade": int((d["status"] == SKIP_ENTRY).sum()),
                    "skips_no_exit_trade": int((d["status"] == SKIP_EXIT).sum()),
                    "outside_coverage_not_skips": int((d["status"] == OUTSIDE).sum())})
    res = pd.DataFrame(res)
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT / "results.csv", index=False)
    for c in ("decision_ns", "entry_time_ns", "exit_time_ns", "entry_trade_ns", "exit_trade_ns"):
        t[c.replace("_ns", "_et")] = t[c].map(et)
    cols = ["latency_s", "game_id", "slug", "machine", "status", "entry_g", "decision_ns", "decision_et", "direction",
            "exit_reason", "kalshi_mid_at_decision", "tns_grid_price_at_decision", "tns_price_at_decision",
            "entry_time_ns", "entry_time_et", "entry_trade_ns", "entry_trade_et", "entry_trade_price", "entry_fill",
            "exit_time_ns", "exit_time_et", "exit_trade_ns", "exit_trade_et", "exit_trade_price", "exit_fill",
            "fee_entry", "fee_exit", "pnl_usd", "net_c_per_contract", "qty"]
    t[cols].to_csv(OUT / "trades.csv", index=False)

    # comparison: the run's own Polymarket US laggard fills, same games, exit fill before 17:00 ET, 1 s
    run = pd.read_csv(sl / "results" / "holdout" / "laggard_trades.csv")
    rf = run[(run["venue"] == VENUE) & (run["latency_s"] == 1.0) & run["filled"].astype(bool)
             & (run["exit_fill_ns"] < COVER_END_NS) & run["game_id"].isin(q["game_id"])]
    pgr = rf.groupby("game_id")["edge_cents_per_contract"]
    rlo, rhi = L.game_bootstrap_ci(pgr.sum().to_numpy(), pgr.size().to_numpy())
    comp = (f"run's own Polymarket US laggard (recorded polled quotes), total latency 1 s, same {len(q)} games, "
            f"exit fill before 17:00 ET: {len(rf)} fills, {rf['game_id'].nunique()} games, "
            f"{rf['edge_cents_per_contract'].mean():+.3f} c/contract [{rlo:+.3f}, {rhi:+.3f}]")
    print(comp, flush=True)

    samp = t[(t["latency_s"] == PRIMARY_L) & (t["status"] == "filled")].sample(5, random_state=SEED)
    md = ["# Post-hoc T&S laggard test results", "", "**EXPLORATORY, selected after seeing the holdout.** "
          "Does not change any pre-registered result. This adds 3 variants (L = 1, 2, 5 s) to the DSR total.", "",
          f"SPEC: results/posthoc_tns/SPEC.md, commit {a.spec_commit} (committed before any test code existed).", "",
          f"Universe: {len(q)} qualifying Polymarket US games with laggard window start before 17:00 ET Oct 3 "
          f"(SPEC note (a)); games with at least one signal: {t['game_id'].nunique()}.", "",
          "## Results (primary: L = 1 s)", "", md_table(res), "",
          "Skips by reason are the skips_* columns; outside_coverage_not_skips counts round trips whose decision or "
          "a needed fill print falls at or after 17:00 ET (excluded, not skips).", "",
          "## Comparison only (not the same fill model)", "", comp, "",
          "## 5 random filled trades at L = 1 s (random_state 20261003)", ""]
    for r in samp.itertuples():
        md += [f"- {r.game_id} ({r.slug}), direction {r.direction:+d}, exit reason {r.exit_reason}",
               f"  - decision {r.decision_et}; Kalshi mid at decision {r.kalshi_mid_at_decision:.4f}; "
               f"T&S home price at decision (last print <= decision) {r.tns_price_at_decision:.4f}; "
               f"T&S grid price used by the signal {r.tns_grid_price_at_decision:.4f}",
               f"  - entry time {r.entry_time_et}; entry print {r.entry_trade_et} at {r.entry_trade_price:.4f}; "
               f"entry fill {r.entry_fill:.4f}; fee {r.fee_entry:.2f}",
               f"  - exit time {r.exit_time_et}; exit print {r.exit_trade_et} at {r.exit_trade_price:.4f}; "
               f"exit fill {r.exit_fill:.4f}; fee {r.fee_exit:.2f}",
               f"  - P&L {r.pnl_usd:+.4f} USD, net {r.net_c_per_contract:+.4f} c/contract"]
    md += ["", "## Unit tests", "", a.pytest_summary or "(not given)", "",
           "Prices are home-oriented (home = 1 - T&S Last Price for long_is_away slugs). Times are venue time "
           "(T&S) and recorder receipt time (Kalshi), no clock correction.", ""]
    (OUT / "RESULTS.md").write_text("\n".join(md))
    pd.set_option("display.width", 250)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
