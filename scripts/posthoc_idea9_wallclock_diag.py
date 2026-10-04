"""Post-hoc Idea 9 diagnostic (not a variant): traded games with suspect ESPN wallclocks, and their P&L share.

Suspect = some play's wallclock is more than 5 min earlier than the previous play's (ESPN play order), or lies
outside [kickoff, kickoff + 6 h]. Reads results/posthoc_idea9/training_trades.csv; writes training_wallclock_diag.csv.
"""
import pandas as pd

import posthoc_idea9 as P

tr = pd.read_csv(P.OUT / "training_trades.csv")
g = pd.read_csv(P.DATA / "raw" / "kalshi_only_games.csv").set_index("game_id")
ids = pd.read_csv(P.IDEA6_CACHE / "ids_training.csv").set_index("game_id")
flag = {}
for gid in tr["game_id"].unique():
    s = P.load_summary(g.loc[gid, "league"], ids.loc[gid, "espn_id"])
    ko = pd.Timestamp(g.loc[gid, "kickoff_utc_espn"]).value
    wc = [pd.Timestamp(p["wallclock"]).value for p in P.plays_of(s) if p.get("wallclock")]
    back = any(b < a - 300 * P.NS for a, b in zip(wc, wc[1:]))
    out = any(w < ko or w > ko + 6 * 3600 * P.NS for w in wc)
    flag[gid] = "backward>5min" if back and not out else ("outside window" if out and not back else ("both" if out else ""))
tr["wallclock_flag"] = tr["game_id"].map(flag)
rows = []
for (k, d, lg), r in tr.groupby(["k", "delay", "leg"]):
    bad = r[r["wallclock_flag"] != ""]
    rows.append({"k": k, "delay": d, "leg": lg, "trades": len(r), "flagged_trades": len(bad),
                 "pnl_direct_total": r["pnl_direct"].sum(), "pnl_direct_flagged": bad["pnl_direct"].sum(),
                 "pnl_direct_unflagged": r["pnl_direct"].sum() - bad["pnl_direct"].sum(),
                 "roc_direct_unflagged": r.loc[r["wallclock_flag"] == "", "roc_direct"].mean()})
d = pd.DataFrame(rows)
d.to_csv(P.OUT / "training_wallclock_diag.csv", index=False)
print("traded games:", tr["game_id"].nunique(), "flagged:", sum(v != "" for v in flag.values()),
      pd.Series([v for v in flag.values() if v]).value_counts().to_dict())
print(d.round(4).to_string(index=False))
