"""Post-hoc work summary: results/posthoc/SUMMARY.md and results/posthoc/numbers_posthoc.json.

Reads only the committed summary files copied into results/posthoc/<idea>/ (sources in results/posthoc/SOURCES.md),
results/posthoc/dsr_posthoc.json (scripts/posthoc_dsr.py) and git log for commit times. No strategy is run.
Every post-hoc idea is exploratory and was formed after the pre-registered holdout run; none changes a
pre-registered result.

Usage (cwd = repo root): python scripts/posthoc_summary.py
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pandas as pd

P = Path("results/posthoc")
num: dict = {}


def put(key: str, value, source: str, column: str) -> None:
    if hasattr(value, "item"):
        value = value.item()
    num[f"posthoc_{key}"] = {"value": value, "source": str(source), "column": column}


def et(sha: str) -> str:
    try:
        return subprocess.check_output(["git", "log", "-1", "--format=%cd", "--date=format-local:%H:%M:%S", sha],
                                       text=True, env={"TZ": "America/New_York", "PATH": "/usr/bin:/bin:/usr/local/bin"},
                                       stderr=subprocess.DEVNULL).strip() + " ET"
    except Exception:
        return "time n/a (commit not in this clone)"


def csv(idea: str, name: str) -> tuple[pd.DataFrame, Path]:
    f = P / idea / name
    return pd.read_csv(f), f


def ci(x, lo, hi, nd=3) -> str:
    return f"{x:+.{nd}f} [{lo:+.{nd}f}, {hi:+.{nd}f}]"


def direct_x1(t: pd.DataFrame) -> pd.DataFrame:
    q = t[(t["fee_line"] == "kalshi_direct") & (t["costs"] == "x1")]
    return q[q["subset"] == "all"] if "subset" in q else q


rows = []


def row(idea, hyp, spec, out, variants, selected, headline, placebo, holdout, verdict):
    rows.append({"idea": idea, "hypothesis": hyp, "spec": f"{spec} ({et(spec)})", "output": f"{out} ({et(out)})",
                 "variants": variants, "selected": selected, "headline (95% CI)": headline, "placebo": placebo,
                 "holdout": holdout, "verdict": verdict})


HOLDOUT_DATA = "n/a: run on holdout-period data (Vultr Oct 3) after the pre-registered run; no separate holdout"

# ---------- T&S laggard ----------
t, f = csv("tns", "results.csv")
for r in t.itertuples():
    L = f"{r.latency_s:g}"
    put(f"tns_L{L}_net_c", r.mean_net_c_per_contract, f, "mean_net_c_per_contract")
    put(f"tns_L{L}_net_c_ci", [r.ci_low, r.ci_high], f, "ci_low, ci_high")
    put(f"tns_L{L}_trades", r.trades, f, "trades")
p = t[t["primary"]].iloc[0]
row("T&S laggard", "Polymarket US time-and-sales leads Kalshi; trade Kalshi toward it", "a510ba0", "95cb80b", 3,
    "L = 1 s (primary by spec)", f"net c/contract {ci(p.mean_net_c_per_contract, p.ci_low, p.ci_high, 2)}, {p.trades} trades",
    "none in spec", HOLDOUT_DATA, "negative")

# ---------- Idea 1 ----------
t, f = csv("idea1", "idea1_results.csv")
d = t[t["schedule"] == "direct"]
put("idea1_complement_violations", int(d["opps_total"].iloc[0]), f, "opps_total (schedule direct)")
put("idea1_violation_duration_median_s", float(d["dur_s_min_25_50_75_90_max"].iloc[0].split("/")[2]), f,
    "dur_s_min_25_50_75_90_max (median, schedule direct)")
for r in d.itertuples():
    L = f"{r.latency_s:g}"
    put(f"idea1_L{L}_executed", r.executed, f, "executed")
    put(f"idea1_L{L}_trade_mean_usd", r.trade_mean, f, "trade_mean")
    put(f"idea1_L{L}_trade_mean_ci_usd", [r.trade_mean_ci_lo, r.trade_mean_ci_hi], f, "trade_mean_ci_lo, trade_mean_ci_hi")
row("1", "Kalshi YES+YES (or NO+NO) complement mispricing net of fees is executable", "d32fa2c", "4890c53", 3,
    "none (all L reported)", "; ".join(f"L {r.latency_s:g}: {r.executed} executed, $/trade {ci(r.trade_mean, r.trade_mean_ci_lo, r.trade_mean_ci_hi)}"
                                       for r in d.itertuples()),
    "none in spec", HOLDOUT_DATA,
    f"negative; descriptive: {int(d['opps_total'].iloc[0])} complement violations, median duration "
    f"{float(d['dur_s_min_25_50_75_90_max'].iloc[0].split('/')[2]):.4f} s; sizes mostly sub-contract residue (sizing disclosure 6f13ecd)")

# ---------- Idea 2 ----------
t, f = csv("idea2", "idea2_results.csv")
lagd, fl = csv("idea2", "idea2_lag_distribution.csv")
real = lagd[lagd["kind"] == "real"]["lag_s"]
plac = lagd[lagd["kind"] != "real"]["lag_s"]
put("idea2_lag_median_s", float(real.median()), fl, "lag_s (kind real)")
put("idea2_lag_share_pos", float((real > 0).mean()), fl, "lag_s > 0 (kind real)")
put("idea2_placebo_lag_median_s", float(plac.median()), fl, "lag_s (placebo)")
put("idea2_mannwhitney_p", 0.0365, "results/posthoc_latency/idea2_RESULTS.md @ e3fcc8c (branch posthoc-latency; unchanged at aef5cec; copy at results/posthoc/idea2/idea2_RESULTS.md)", "Lag test section: 'Mann-Whitney p (real vs placebo, two-sided) = 0.0365' (value is in the md only, no CSV column)")
dd = t[t["fee_line"] == "kalshi_direct"]
for r in dd.itertuples():
    L = f"{r.latency_L_s:g}"
    put(f"idea2_L{L}_net_c", r.mean_net_c, f, "mean_net_c (kalshi_direct)")
    put(f"idea2_L{L}_net_c_ci", [r.ci_low, r.ci_high], f, "ci_low, ci_high")
row("2", "polymarket.com leads Kalshi sub-second (venue time); trade Kalshi after a polymarket.com move", "4ec43cc", "e3fcc8c", 3,
    "none (all L reported)", "; ".join(f"L {r.latency_L_s:g}: {ci(r.mean_net_c, r.ci_low, r.ci_high, 2)} c" for r in dd.itertuples()),
    f"lag placebo median {plac.median():+.2f} s", HOLDOUT_DATA,
    f"negative; lag reading: venue-time median {real.median():+.2f} s, share > 0 {(real > 0).mean():.3f}, 80 of 88 games at exactly +0.1 s "
    "(constant offset pattern, same as Idea 11 a2)")

# ---------- Idea 3 ----------
t, f = csv("idea3", "idea3_results.csv")
row("3", "Kalshi reverses after large taker prints; fade them", "4e60e8c", "a7b1dd8", 3, "none", "not reported (invalid)",
    "none in spec", HOLDOUT_DATA, "INVALID: lookahead (whole-window 95th percentile size threshold; 54c3c28); not rerun")
put("idea3_status", "invalid, lookahead", P / "idea3" / "idea3_RESULTS.md", "INVALID, LOOKAHEAD note")


# ---------- trained ideas: helper ----------
def trained(idea, label, param, legs, hyp, spec, out, variants, min_trades, holdout, verdict_fn, extra=None):
    t, f = csv(idea, "training_results.csv")
    q = direct_x1(t)
    sig, plc = legs
    for r in q.itertuples():
        v = getattr(r, param) if not isinstance(param, tuple) else "_".join(f"{getattr(r, x):g}" for x in param)
        key = f"{idea}_{(param if isinstance(param, str) else 'k_delay')}{v}_{r.leg}"
        put(f"{key}_trades", int(r.trades), f, "trades (kalshi_direct, x1)")
        if r.trades:
            put(f"{key}_roc", r.roc_mean, f, "roc_mean (kalshi_direct, x1)")
            put(f"{key}_roc_ci", [r.roc_ci_lo, r.roc_ci_hi], f, "roc_ci_lo, roc_ci_hi")
            put(f"{key}_c_per_contract", r.cents_per_contract, f, "cents_per_contract")
    s = q[(q["leg"] == sig) & (q["trades"] >= min_trades)]
    keys = [param] if isinstance(param, str) else list(param)[::-1]
    sel = None
    if len(s):
        sel = s.sort_values(["roc_mean"] + keys, ascending=[False] + [False] * len(keys)).iloc[0]
    pv = lambda r: (f"{param} {getattr(r, param):g}" if isinstance(param, str)
                    else ", ".join(f"{x} {getattr(r, x):g}" for x in param))
    if sel is not None:
        pl = q[(q["leg"] == plc)]
        for x in keys:
            pl = pl[pl[x] == sel[x]]
        pl = pl.iloc[0]
        headline = f"ROC {ci(sel.roc_mean, sel.roc_ci_lo, sel.roc_ci_hi)}, {int(sel.trades)} trades, {sel.cents_per_contract:+.2f} c/contract"
        placebo = (f"ROC {ci(pl.roc_mean, pl.roc_ci_lo, pl.roc_ci_hi)}, {int(pl.trades)} trades" if pl.trades
                   else "0 trades")
        put(f"{idea}_selected", pv(sel), f, f"selection rule (>= {min_trades} trades, highest roc_mean)")
        selected = pv(sel)
    else:
        best = q[q["leg"] == sig].sort_values("trades", ascending=False).iloc[0]
        headline = (f"none selected (signal trades: {', '.join(str(int(x)) for x in q[q['leg'] == sig]['trades'])}); "
                    f"largest: {pv(best)} ROC " + (ci(best.roc_mean, best.roc_ci_lo, best.roc_ci_hi) if best.trades > 1 else "n/a"))
        selected = f"none (no setting reaches {min_trades} trades)"
        pl = q[q["leg"] == plc].sort_values("trades", ascending=False).iloc[0]
        placebo = f"largest: {pv(pl)} ROC {ci(pl.roc_mean, pl.roc_ci_lo, pl.roc_ci_hi)}, {int(pl.trades)} trades"
        put(f"{idea}_selected", "none", f, f"selection rule (>= {min_trades} trades)")
    if extra:
        extra(t, f, q)
    row(label, hyp, spec, out, variants, selected, headline, placebo, holdout, verdict_fn(q))


neg = lambda q: "negative" if (q["roc_mean"].dropna() < 0).all() else "no edge (selected setting CI includes 0 or negative)"

trained("idea4", "4", "theta", ("favorite", "placebo"), "late-game near-certain favorite underpriced; buy and hold",
        "3142f9b", "6e21338", 4, 100, "no: decided on training (no edge at any theta), 80a919d", neg)


def idea6_extra(t, f, q):
    txt = (P / "idea6" / "README.md").read_text()
    m = re.search(r"is (\d+) s \(p90 (\d+) s\).*?disagreements: (\d+)", txt)
    put("idea6_E_to_winner_099_median_s", int(m.group(1)), P / "idea6" / "README.md", "Close-out, descriptive results kept")
    put("idea6_E_to_winner_099_p90_s", int(m.group(2)), P / "idea6" / "README.md", "Close-out, descriptive results kept")
    put("idea6_settlement_disagreements", int(m.group(3)), P / "idea6" / "README.md", "Close-out, descriptive results kept")


rows_before = len(rows)
trained("idea6", "6", "D_s", ("winner", "placebo"), "after the ESPN end-of-game marker, buy the winner below 0.99",
        "7c78c2c", "07b8e21", 3, 50, "no: winner leg invalid; decided on training", lambda q: "", idea6_extra)
rows[-1]["selected"] = "none (no D reaches 50 trades)"
rows[-1]["headline (95% CI)"] = "not reported: winner leg INVALID"
rows[-1]["verdict"] = ("INVALID: winner leg uses bad ESPN end-marker wallclocks (lookahead; close-out 4f85101); "
                       "descriptive: median 11 s from E to the winner's first trade >= 0.99 (p90 253 s); 0 ESPN vs Kalshi settlement disagreements")
for k in [k for k in num if k.startswith("posthoc_idea6_D_s") and "_winner_" in k]:
    num[k]["column"] += " [INVALID: winner leg, bad ESPN end-marker wallclocks]"

trained("idea7", "7", "k", ("signal", "placebo"), "pregame polymarket.com minus Kalshi gap; buy Kalshi when polymarket.com is higher",
        "a413026", "8cce2c3", 3, 100, "no: no setting selected",
        lambda q: "negative; no setting selected (below 100 trades)")


def idea8_extra(t, f, q):
    put("idea8_matched_placebo_note", "fade minus follow on matched games: CI includes 0 at every x",
        P / "idea8" / "MATCHED_PLACEBO.md", "paired difference table")


trained("idea8", "8", "x", ("fade", "placebo"), "fade pregame taker-flow imbalance", "856b5f9", "1e241e6", 3, 100,
        "no: no edge on training", lambda q: "negative; matched-games placebo (a63ee03): fade minus follow CI includes 0 at every x",
        idea8_extra)


def idea9_extra(t, f, q):
    for r in q.itertuples():
        key = f"idea9_k{r.k:g}_delay{r.delay:g}_{r.leg}"
        put(f"{key}_brier_espn", r.brier_espn, f, "brier_espn")
        put(f"{key}_brier_kalshi", r.brier_kalshi, f, "brier_kalshi")
    put("idea9_kalshi_brier_lower_rows", int((q["brier_kalshi"] < q["brier_espn"]).sum()), f, "brier_kalshi < brier_espn")


trained("idea9", "9", ("k", "delay"), ("signal", "placebo"), "ESPN win probability ahead of Kalshi; buy the team ESPN rates higher",
        "df80d2c", "47037f2", 4, 100, "no: closed on training",
        lambda q: f"negative; Kalshi Brier lower than ESPN in {(q['brier_kalshi'] < q['brier_espn']).sum()} of {len(q)} rows; ESPN wallclocks unreliable",
        idea9_extra)

# ---------- Idea 10 (net c/contract metric) ----------
t, f = csv("idea10", "training_results.csv")
q = direct_x1(t)
for r in q.itertuples():
    put(f"idea10_s{r.s:g}_{r.leg}_net_c", r.net_c_per_contract, f, "net_c_per_contract (kalshi_direct, x1)")
    put(f"idea10_s{r.s:g}_{r.leg}_net_c_ci", [r.net_ci_lo, r.net_ci_hi], f, "net_ci_lo, net_ci_hi")
    put(f"idea10_s{r.s:g}_{r.leg}_trades", int(r.trades), f, "trades")
s = q[(q["leg"] == "fade") & (q["trades"] >= 200)].sort_values(["net_c_per_contract", "s"], ascending=[False, False]).iloc[0]
pl = q[(q["leg"] == "placebo") & (q["s"] == s.s)].iloc[0]
put("idea10_selected", f"s {s.s:g}", f, "selection rule (>= 200 trades, highest net c/contract)")
es, fe = csv("idea10", "training_event_study.csv")
for r in es.itertuples():
    for h in (10, 30, 60, 180, 300):
        put(f"idea10_event_{r.ptype.replace('-', '_')}_median_{h}s_c", getattr(r, f"median_move_{h}s_c"), fe, f"median_move_{h}s_c")
    put(f"idea10_event_{r.ptype.replace('-', '_')}_n", int(r.with_pre_price), fe, "with_pre_price")
row("10", "retail overreacts to scores; fade the scoring team's Kalshi move", "3a02690", "92ee688", 3, f"s {s.s:g}",
    f"net c/contract {ci(s.net_c_per_contract, s.net_ci_lo, s.net_ci_hi, 2)}, {int(s.trades)} trades",
    f"net c/contract {ci(pl.net_c_per_contract, pl.net_ci_lo, pl.net_ci_hi, 2)}, {int(pl.trades)} trades",
    "no: closed on training", "negative; event study: scoring team's price keeps rising (TD median +2 c at +60 s to +300 s; FG 0)")

# ---------- Idea 11 ----------
lag, fl = csv("idea11", "lag_summary.csv")
for r in lag.itertuples():
    put(f"idea11_{r.test}_median_lag_s", r.median_s, fl, "median_s")
    put(f"idea11_{r.test}_share_pos", r.share_pos, fl, "share_pos")
    put(f"idea11_{r.test}_iqr_s", r.iqr_s, fl, "iqr_s")
    put(f"idea11_{r.test}_placebo_median_s", r.placebo_median_s, fl, "placebo_median_s")
    put(f"idea11_{r.test}_mannwhitney_p", r.mannwhitney_p, fl, "mannwhitney_p")
put("idea11_lag_reading", "Venue-time lag is a constant offset (IQR 0 ms). Receipt-time lag (+90 ms) matches the unrelated-game "
    "placebo (+80 ms, p = 0.64). No evidence of a lead in either direction.", P / "idea11" / "RESULTS.md", "dated note")
c, fc = csv("idea11", "corrected_results.csv")
for r in c.itertuples():
    L = f"{r.latency_L_s:g}"
    for col in ("both", "kalshi_only", "pm_only", "neither", "hedged_contracts", "naked_contracts"):
        put(f"idea11_L{L}_{col}", int(getattr(r, col)), fc, col)
    put(f"idea11_L{L}_corrected_hold_total_usd", r.hold_total, fc, "hold_total")
    put(f"idea11_L{L}_corrected_hold_total_ci", [r.hold_total_ci_lo, r.hold_total_ci_hi], fc, "hold_total_ci_lo, hold_total_ci_hi")
    put(f"idea11_L{L}_corrected_hold_c_per_contract", r.hold_per_contract * 100, fc, "hold_per_contract x 100")
    put(f"idea11_L{L}_corrected_unwind_total_usd", r.unwind_total, fc, "unwind_total")
    put(f"idea11_L{L}_original_pnl_total_usd", r.orig_pnl_total, fc, "orig_pnl_total")
    put(f"idea11_L{L}_original_c_per_contract", r.orig_per_contract * 100, fc, "orig_per_contract x 100")
c25 = c[c["latency_L_s"] == 0.25].iloc[0]
row("11", "(a) Kalshi vs polymarket.com lag at fine resolution; (b) cross-venue arbitrage (market-efficiency measurement; "
    "polymarket.com not available to US persons)", "277769a", "9d06979 (settled fc95b81; corrected 60eef8a)", 3, "none (all L reported)",
    "corrected (primary, naked held): " + "; ".join(f"L {r.latency_L_s:g}: ${r.hold_total:+.0f} [{r.hold_total_ci_lo:+.0f}, {r.hold_total_ci_hi:+.0f}]"
                                                    for r in c.itertuples()),
    "lag placebo: receipt +0.08 s (p 0.64)", HOLDOUT_DATA,
    "original execution INVALID (conditioned on the second leg clearing in the future; original +$54 to +$64); corrected: "
    f"negative, CI includes 0; L 0.25: {int(c25.both)} both / {int(c25.kalshi_only)} Kalshi only / {int(c25.pm_only)} polymarket.com only / "
    f"{int(c25.neither)} neither; lag: no lead in either direction")
rows[-1]["output"] = f"9d06979 ({et('9d06979')}); corrected 60eef8a ({et('60eef8a')})"


def idea12_extra(t, f, q):
    for r in q.itertuples():
        put(f"idea12_k{r.k:g}_{r.leg}_win_rate", r.win_rate, f, "win_rate")
        put(f"idea12_k{r.k:g}_{r.leg}_mean_fill", r.mean_fill, f, "mean_fill")


trained("idea12", "12", "k", ("signal", "placebo"), "in-game polymarket.com minus Kalshi gap (10 s persistence); buy Kalshi",
        "ca72fb9", "e79ed91", 3, 100, "no: no edge on training",
        lambda q: "negative; signal win rate close to mean fill (k 0.03: 0.496 vs 0.494): direction right, too small for spread and fees",
        idea12_extra)


def idea13_extra(t, f, q):
    r = q.iloc[0]
    put("idea13_brier_line", r.brier_p, f, "brier_p")
    put("idea13_brier_kalshi", r.brier_k, f, "brier_k")
    put("idea13_brier_games", int(r.brier_games), f, "brier_games")


trained("idea13", "13", "e", ("signal", "placebo"), "NFL no-vig closing moneyline is fair value; buy Kalshi when cheaper",
        "03ab9a5", "f4fa3f6", 3, 40, "no: no setting selected",
        lambda q: "negative; no setting selected; Kalshi Brier equals the closing line's (0.2113 vs 0.2111)", idea13_extra)

# ---------- DSR ----------
dsr_f = P / "dsr_posthoc.json"
dsr = json.loads(dsr_f.read_text())
n = dsr["n_trials"]
for hn, hv in sorted(dsr.get("history", {str(n): dsr["values"]}).items(), key=lambda x: int(x[0])):
    for k, v in hv.items():
        put(f"dsr_{k.split('.')[1]}_trials_{hn}", v, dsr_f, f"history.{hn}.{k} (report_book.deflated_sharpe, n_total={hn})")
for k, v in dsr["stored_total_22"].items():
    put(f"dsr_{k.split('.')[1]}_trials_22_preregistered", v, dsr_f, f"stored_total_22.{k} (results/holdout/numbers.json)")
put("variants_rows_total", n, Path("experiments/variants.csv"), "row count")

# ---------- training-positive book (results/posthoc/positive_book, scripts/posthoc_positive_book.py) ----------
pb_f = P / "positive_book" / "metrics.json"
if pb_f.exists():
    pb = json.loads(pb_f.read_text())
    for k in ("trades", "games", "pnl_total", "roc_mean", "game_days", "sharpe_daily", "sharpe_x365", "max_drawdown",
              "worst_day", "worst_day_date"):
        put(f"posbook_{k}", pb[k], pb_f, k)
    put("posbook_roc_ci", [pb["roc_ci_lo"], pb["roc_ci_hi"]], pb_f, "roc_ci_lo, roc_ci_hi")
    put("posbook_trades_A_taker", pb["trades_by_cell"]["A taker"], pb_f, "trades_by_cell.A taker")
    put("posbook_trades_A_maker", pb["trades_by_cell"]["A-maker"], pb_f, "trades_by_cell.A-maker")
    put("posbook_n_cells", len(pb["cells"]), pb_f, "cells")

# ---------- write ----------
cols = ["idea", "hypothesis", "spec", "output", "variants", "selected", "headline (95% CI)", "placebo", "holdout", "verdict"]
md = ["# Post-hoc work: summary", "",
      "**All post-hoc, exploratory; formed after the pre-registered holdout run; none changes a pre-registered result.** "
      "Generated by scripts/posthoc_summary.py from the committed summary files in results/posthoc/ (sources: SOURCES.md). "
      "Headline metric: ROC (return on capital, Kalshi direct fees, costs x1) for hold-to-settlement ideas, net cents per "
      "contract for round-trip ideas, game-bootstrap 95% CI. Times are commit times, ET, 2026-10-04.", "",
      "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
for r in rows:
    md.append("| " + " | ".join(str(r[c]).replace("|", "/") for c in cols) + " |")
dv = dsr["values"]
md += ["", "## Deflated Sharpe with all variants", "",
       f"Additional line next to the pre-registered values (not replacing them). Trials = final experiments/variants.csv row count = {n}. "
       "Same function (report_book.deflated_sharpe) and inputs as the run; trial-Sharpe variance still from the 12 training trials "
       "with daily series. Source: results/posthoc/dsr_posthoc.json (scripts/posthoc_dsr.py; the total-22 values reproduce exactly).", "",
       "| book | DSR, 22 trials (pre-registered, results/holdout/numbers.json) | DSR, " + str(n) + " trials (post-hoc line) |", "|---|---|---|"]
hist = dsr.get("history", {str(n): dv})
hns = sorted(hist, key=int)
md[-2] = ("| book | DSR, 22 trials (pre-registered, results/holdout/numbers.json) | "
          + " | ".join(f"DSR, {h} trials (post-hoc line)" for h in hns) + " |")
md[-1] = "|---|---|" + "---|" * len(hns)
for b in ("A", "combined", "B"):
    md.append(f"| {b} | {dsr['stored_total_22'][f'OOS.{b}.deflated_sharpe_total_22']:.3g} | "
              + " | ".join(f"{hist[h][f'OOS.{b}.deflated_sharpe_total_{h}']:.3g}" for h in hns) + " |")
md += ["", f"The {n}-trial line is current (variants.csv rows at the last scripts/posthoc_dsr.py run); "
       "lines at fewer trials (" + ", ".join(h for h in hns if h != str(n)) + ") are superseded by it and kept for the record. "
       "The 22-trial values are the pre-registered ones and are unchanged."]
(P / "SUMMARY.md").write_text("\n".join(md) + "\n")
(P / "numbers_posthoc.json").write_text(json.dumps(num, indent=1, default=float))
print("\n".join(md))
print(f"\n{len(num)} posthoc_ keys")
