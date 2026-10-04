"""Build results/holdout_diag/numbers_diag.json (exploratory, post-run) from the diagnostic CSVs.

Every value is computed from a file; none is typed. Diagnostic CSVs are read read-only from git commit 5c24dbe
(t17-extras) via `git show 5c24dbe:<path>`, never checked out; the receipt diagnostic is read from
results/holdout/receipt_diagnostic.csv on this branch (main 5ef528f). Each key records its source file and column.

Usage: python scripts/numbers_diag.py
"""
from __future__ import annotations

import io
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

DIAG_COMMIT = "5c24dbe"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "holdout_diag" / "numbers_diag.json"


def show(path: str, skip_banner: bool = False) -> pd.DataFrame:
    raw = subprocess.run(["git", "-C", str(ROOT), "show", f"{DIAG_COMMIT}:{path}"], check=True,
                         capture_output=True).stdout
    return pd.read_csv(io.BytesIO(raw), skiprows=1 if skip_banner else 0)


def main() -> None:
    num: dict[str, dict] = {}

    def put(key, value, source, column):
        if isinstance(value, (np.floating, np.integer)):
            value = value.item()
        num[key] = {"value": value, "source": source, "column": column}

    d = "results/holdout_diag/"
    src_c = f"git show {DIAG_COMMIT}:"
    # h1: live cache check
    p = show(d + "h1_poll.csv")
    ok = p[p["status"] == 200]
    ages = pd.to_numeric(ok["h_age"], errors="coerce").dropna()
    cc = ok["h_cache-control"].dropna().unique()
    m = [int(re.search(r"max-age=(\d+)", c).group(1)) for c in cc if re.search(r"max-age=(\d+)", c)]
    put("pmus_cache_max_age_s", max(m), src_c + d + "h1_poll.csv", "h_cache-control (max-age)")
    put("pmus_age_header_min_s", int(ages.min()), src_c + d + "h1_poll.csv", "h_age")
    put("pmus_age_header_max_s", int(ages.max()), src_c + d + "h1_poll.csv", "h_age")
    put("pmus_live_poll_requests", int(len(p)), src_c + d + "h1_poll.csv", "rows")
    put("pmus_live_poll_body_changes", int(ok["body_changed"].astype(bool).sum()), src_c + d + "h1_poll.csv", "body_changed")
    # h0: recorded quote change interval and snapshot ages
    g = show(d + "h0_snapshot_gaps_per_game.csv")
    put("pmus_quote_change_interval_median_of_game_medians_s", float(g["gap_median_s"].median()),
        src_c + d + "h0_snapshot_gaps_per_game.csv", "gap_median_s (median over games)")
    put("pmus_quote_change_interval_n_games", int(len(g)), src_c + d + "h0_snapshot_gaps_per_game.csv", "rows")
    a = show(d + "h0_fill_snapshot_ages.csv")
    put("pmus_laggard_1s_entry_snapshot_age_median_s", float(a["entry_snapshot_age_s"].median()),
        src_c + d + "h0_fill_snapshot_ages.csv", "entry_snapshot_age_s")
    put("pmus_laggard_1s_exit_snapshot_age_median_s", float(a["exit_snapshot_age_s"].median()),
        src_c + d + "h0_fill_snapshot_ages.csv", "exit_snapshot_age_s")
    put("pmus_laggard_1s_share_entries_snapshot_older_5s", float((a["entry_snapshot_age_s"] > 5).mean()),
        src_c + d + "h0_fill_snapshot_ages.csv", "entry_snapshot_age_s > 5")
    put("pmus_laggard_1s_n_fills", int(len(a)), src_c + d + "h0_fill_snapshot_ages.csv", "rows")
    # h3: receipt minus venue trade time
    h3 = show(d + "h3_summary.csv", skip_banner=True).iloc[0]
    for k in ("delay_median_s", "delay_p10_s", "delay_p90_s"):
        put(f"pmus_receipt_minus_venue_{k}", float(h3[k]), src_c + d + "h3_summary.csv", k)
    put("pmus_receipt_minus_venue_n_matched", int(h3["n_matched"]), src_c + d + "h3_summary.csv", "n_matched")
    put("pmus_receipt_minus_venue_n_ambiguous", int(h3["n_ambiguous"]), src_c + d + "h3_summary.csv", "n_ambiguous")
    # g: run curve at 1 s (Polymarket US)
    c = show(d + "g_latency_curves.csv")
    r = c[(c["venue"] == "polymarket_us") & (c["latency_s"] == 1.0)].iloc[0]
    for k, col in (("mean_c", "edge_cents_mean"), ("ci_lo", "edge_ci_low"), ("ci_hi", "edge_ci_high"), ("n_trades", "n_trades")):
        put(f"pmus_laggard_run_1s_{k}", r[col] if k != "n_trades" else int(r[col]), src_c + d + "g_latency_curves.csv",
            f"{col} (venue polymarket_us, latency_s 1.0)")
    # h4: confirmed fills (partial: before 17:00 ET Oct 3)
    for f, tag in (("h4_run_summary.csv", "run"), ("h4_delay_adjusted_summary.csv", "delay19s")):
        s = show(d + f, skip_banner=True)
        for lat in sorted(s["latency_s"].unique()):
            for st, sk in (("all subset fills", "all"), ("both legs confirmed", "confirmed")):
                x = s[(s["latency_s"] == lat) & (s["set"] == st)]
                if x.empty:
                    continue
                x = x.iloc[0]
                pre = f"pmus_partial_{tag}_{str(lat).replace('.', 'p')}s_{sk}"
                for k, col in (("mean_c", "mean_net_c_per_contract"), ("ci_lo", "ci95_low"), ("ci_hi", "ci95_high"),
                               ("n_fills", "n_fills"), ("n_games", "n_games"), ("share_games_pos", "share_games_pnl_pos")):
                    v = x[col]
                    put(f"{pre}_{k}", int(v) if k.startswith("n_") else float(v), src_c + d + f,
                        f"{col} (latency_s {lat}, set '{st}')")
            put(f"pmus_partial_{tag}_{str(lat).replace('.', 'p')}s_share_both_confirmed",
                float(s[s["latency_s"] == lat]["share_both_confirmed"].iloc[0]), src_c + d + f,
                f"share_both_confirmed (latency_s {lat})")
    # receipt delay, polymarket.com and Kalshi (run output, this branch)
    rd = pd.read_csv(ROOT / "results" / "holdout" / "receipt_diagnostic.csv")
    for v in ("kalshi", "polymarket"):
        x = rd[(rd["machine"] == "vultr") & (rd["venue"] == v)].iloc[0]
        put(f"receipt_delay_{v}_median_s", float(x["median_s"]), "results/holdout/receipt_diagnostic.csv", f"median_s (vultr, {v})")
        put(f"receipt_delay_{v}_p90_s", float(x["p90_s"]), "results/holdout/receipt_diagnostic.csv", f"p90_s (vultr, {v})")
    # B outlier breakdown
    b = show(d + "d_b_big_diff_games.csv")
    cls = b["class"].str.replace(r" \(.*\)", "", regex=True).value_counts()
    put("b_big_diff_n_games", int(len(b)), src_c + d + "d_b_big_diff_games.csv", "rows")
    for k in ("mismatch", "stale venue", "real disagreement"):
        put(f"b_big_diff_n_{k.replace(' ', '_')}", int(cls.get(k, 0)), src_c + d + "d_b_big_diff_games.csv", "class")
    e = show(d + "d_b_excluding.csv")
    x = e[e["sample"].str.startswith("excluding")].iloc[0]
    for k, col in (("mean_c", "edge_webull_cents"), ("ci_lo", "edge_webull_ci_lo"), ("ci_hi", "edge_webull_ci_hi"),
                   ("n_trades", "n_trades")):
        put(f"b_excl_big_diff_webull_{k}", int(x[col]) if k == "n_trades" else float(x[col]), src_c + d + "d_b_excluding.csv",
            f"{col} (sample excluding)")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"status": "exploratory, post-run", "diag_commit": DIAG_COMMIT, "numbers": num}, indent=1) + "\n")
    w = max(len(k) for k in num)
    for k, v in num.items():
        val = v["value"]
        print(f"{k:<{w}}  {val:.6g}" if isinstance(val, float) else f"{k:<{w}}  {val}", f"  [{v['source']} : {v['column']}]")


if __name__ == "__main__":
    main()
