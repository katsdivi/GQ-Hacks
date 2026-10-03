"""Who leads: the primary test of HYPOTHESIS_v2.md, exactly as frozen in docs/stats_plan.md.

  python who_leads.py                 # every training game in out/download_manifest.csv
  python who_leads.py --games sample  # mechanics check on the fake game

Per game: 1 s grids from the trailing 3 s median of raw trades (no shift), jumps detected on
each venue with the other's response (leadlag.py, both directions). Signed lead per matched
(covered) jump, positive = Kalshi first. Per-game L = median signed lead; qualifies with >= 5
matched jumps. Across qualifying games: >= 30 needed (else "inconclusive"), two-sided exact
sign test (ties excluded), leader needs majority + p < 0.05 + median L >= 1 s in its favour, and
Kalshi additionally needs median L >= 1 s + median D.

Placebo: Kalshi from game A vs polymarket.com from game B (kickoff within 30 min, next in
kickoff order, cyclic within the slot), same steps.

Writes out/who_leads_games.csv, out/who_leads_placebo.csv, out/who_leads_summary.json.
Training games only (kickoff before 2026-08-01); the fake game is allowed for checks.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import align
import leadlag

ROOT = Path(__file__).resolve().parent
TICKS = ROOT / "data" / "ticks"
OUT = ROOT / "out"
TEST_START = pd.Timestamp("2026-08-01", tz="UTC")
PRICE_WINDOW_S = 3.0
MIN_MATCHED = 5
MIN_GAMES = 30
MIN_LEAD_S = 1.0
MIN_TRADES = 50
PAIR_WINDOW = pd.Timedelta(minutes=30)
BOOT_N, BOOT_SEED = 2000, 20261003


def grid(ticks: pd.DataFrame, venue: str) -> pd.Series:
    return align.to_grid(align.trade_median_events(ticks, venue, PRICE_WINDOW_S))


def game_lead(gx: pd.Series, gy: pd.Series) -> dict:
    """gx = the 'first-positive' venue (Kalshi), gy = the other. Returns per-game stats."""
    gx, gy = align.common_grid(gx, gy)
    p = leadlag.PROVISIONAL
    rx, _ = leadlag.leadlag(gx, gy, p["jump_cents"], p["window_s"], p["cover"], p["max_wait_s"], p["max_lag_s"])
    ry, _ = leadlag.leadlag(gy, gx, p["jump_cents"], p["window_s"], p["cover"], p["max_wait_s"], p["max_lag_s"])
    signed = np.concatenate([rx.loc[rx["covered"], "response_s"].to_numpy(),
                             -ry.loc[ry["covered"], "response_s"].to_numpy()])
    lag, _ = leadlag.xcorr_lag(gx, gy, p["max_lag_s"])
    return {"n_jumps_x": len(rx), "n_jumps_y": len(ry), "n_matched": int(len(signed)),
            "L_s": float(np.median(signed)) if len(signed) else float("nan"), "xcorr_lag_s": int(lag)}


def sign_test(n_pos: int, n_neg: int) -> float:
    n, k = n_pos + n_neg, min(n_pos, n_neg)
    if n == 0:
        return float("nan")
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def summarise(df: pd.DataFrame, d_median: float, label_x: str, label_y: str) -> dict:
    q = df[df["n_matched"] >= MIN_MATCHED]
    n_pos, n_neg = int((q["L_s"] > 0).sum()), int((q["L_s"] < 0).sum())
    out = {"n_games": int(len(df)), "n_qualifying": int(len(q)), f"{label_x}_first": n_pos,
           f"{label_y}_first": n_neg, "ties": int((q["L_s"] == 0).sum())}
    if len(q):
        med = float(q["L_s"].median())
        rng = np.random.default_rng(BOOT_SEED)
        vals = q["L_s"].to_numpy()
        boots = [np.median(rng.choice(vals, size=len(vals), replace=True)) for _ in range(BOOT_N)]
        out.update({"median_L_s": med, "median_L_ci95": [float(np.percentile(boots, 2.5)),
                                                         float(np.percentile(boots, 97.5))]})
    p = sign_test(n_pos, n_neg)
    out["sign_test_p"] = p
    if len(q) < MIN_GAMES:
        out["result"] = f"inconclusive ({len(q)} qualifying games < {MIN_GAMES})"
        return out
    med = out["median_L_s"]
    x_rule = n_pos > n_neg and p < 0.05 and med >= MIN_LEAD_S + d_median
    y_rule = n_neg > n_pos and p < 0.05 and -med >= MIN_LEAD_S
    out["thresholds"] = {f"{label_x}_needs_median_L_s_at_least": MIN_LEAD_S + d_median,
                         f"{label_y}_needs_median_L_s_at_most": -MIN_LEAD_S}
    out["result"] = (f"{label_x} leads" if x_rule else f"{label_y} leads" if y_rule
                     else "neither venue leads consistently")
    return out


def load_games(games: list[str] | None) -> pd.DataFrame:
    if games:
        g = pd.read_csv(ROOT / "data" / "games.csv", dtype=str)
        g = g[g["game_id"].isin(games)].copy()
        g["dropped"] = ""
        return g
    m = pd.read_csv(OUT / "download_manifest.csv").drop_duplicates("game_id", keep="last")
    m["kickoff_utc"] = pd.to_datetime(m["kickoff_utc"], utc=True)
    m = m[m["kickoff_utc"] < TEST_START].copy()
    m["dropped"] = np.where(m["polymarket_truncated"].astype(str) == "True", "polymarket truncated",
                   np.where((m["n_kalshi_trades"] < MIN_TRADES) | (m["n_polymarket_trades"] < MIN_TRADES),
                            f"< {MIN_TRADES} trades on a venue", ""))
    return m.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", help="comma list of game_ids (default: all training games in the manifest)")
    a = ap.parse_args()
    games = load_games(a.games.split(",") if a.games else None)
    d = json.loads((ROOT / "experiments" / "d_estimate.json").read_text())
    print(f"D median {d['D_median_s']:+.3f} s ({d['n_trades']} trades); games listed {len(games)}, "
          f"dropped {int((games['dropped'] != '').sum())}")

    rows, grids = [], {}
    for g in games.itertuples():
        if g.game_id != "sample" and pd.Timestamp(g.kickoff_utc) >= TEST_START:
            continue
        if g.dropped:
            rows.append({"game_id": g.game_id, "dropped": g.dropped})
            continue
        t = pd.read_parquet(TICKS / f"{g.game_id}.parquet")
        vx = "kalshi"
        vy = "polymarket" if "polymarket" in set(t["venue"]) else sorted(set(t["venue"]) - {vx})[0]
        gx, gy = grid(t, vx), grid(t, vy)
        grids[g.game_id] = (gx, gy, pd.Timestamp(g.kickoff_utc))
        rows.append({"game_id": g.game_id, "league": getattr(g, "league", ""), "dropped": "",
                     "x": vx, "y": vy, **game_lead(gx, gy)})
    df = pd.DataFrame(rows)
    OUT.mkdir(exist_ok=True)
    df.to_csv(OUT / "who_leads_games.csv", index=False)
    kept = df[df["dropped"] == ""] if "dropped" in df else df
    vx, vy = (kept["x"].iloc[0], kept["y"].iloc[0]) if len(kept) else ("kalshi", "polymarket")
    summ = summarise(kept, d["D_median_s"] if vy == "polymarket" else 0.0, vx, vy)

    # Placebo: Kalshi from game A vs the other venue from game B (kickoff within 30 min).
    ids = list(grids)
    prow = []
    for i, gid in enumerate(ids):
        k = grids[gid][2]
        cands = [j for j in ids if j != gid and abs(grids[j][2] - k) <= PAIR_WINDOW]
        if not cands:
            continue
        order = sorted(ids, key=lambda x: (grids[x][2], x))
        after = [j for j in order[order.index(gid) + 1:] + order[:order.index(gid)] if j in cands]
        partner = after[0]
        prow.append({"game_a": gid, "game_b": partner, **game_lead(grids[gid][0], grids[partner][1])})
    pdf = pd.DataFrame(prow)
    pdf.to_csv(OUT / "who_leads_placebo.csv", index=False)
    psumm = summarise(pdf, 0.0, vx, vy) if len(pdf) else {"n_games": 0, "result": "no placebo pairs"}
    if len(pdf):
        q = pdf[pdf["n_matched"] >= MIN_MATCHED]
        psumm["share_abs_L_ge_1s"] = float((q["L_s"].abs() >= MIN_LEAD_S).mean()) if len(q) else float("nan")

    by_league = {}
    if "league" in kept and kept["league"].astype(str).str.len().gt(0).any():
        for lg, part in kept.groupby("league"):
            by_league[str(lg)] = summarise(part, d["D_median_s"], vx, vy)
    result = {"main": summ, "placebo_unrelated_games": psumm, "by_league_descriptive": by_league,
              "dropped": df.loc[df.get("dropped", "") != "", "dropped"].value_counts().to_dict() if "dropped" in df else {}}
    (OUT / "who_leads_summary.json").write_text(json.dumps(result, indent=1, default=str) + "\n")
    print(json.dumps(result, indent=1, default=str))


if __name__ == "__main__":
    main()
