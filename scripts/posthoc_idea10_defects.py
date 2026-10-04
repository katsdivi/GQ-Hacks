"""Post-hoc Idea 10: ESPN wallclock defect diagnostic (report only; the committed rule is not changed).

post-hoc, exploratory; selected on training only.
Defective scoring event: wallclock outside [kickoff, kickoff + 6 h], or out of order with neighbouring plays
(earlier than the nearest preceding play with a wallclock, or later than the nearest following one).
Defect game: at least one defective scoring event. Reads the training trades written by posthoc_idea10.py.
"""
from __future__ import annotations

import json

import pandas as pd

import posthoc_idea10 as I
import strategy_a as A

NS = I.NS


def main() -> None:
    games, _ = I.training_games()
    ids = pd.read_csv(I.ESPN_CACHE / "ids_training.csv", dtype={"espn_id": str}).set_index("game_id")
    ev_rows = []
    for g in games:
        if g.game_id not in ids.index or pd.isna(ids.loc[g.game_id, "espn_id"]):
            continue
        p = I.ESPN_CACHE / f"{g.league.lower()}_{int(float(ids.loc[g.game_id, 'espn_id']))}.json"
        if not p.exists():
            continue
        s = json.loads(p.read_text())
        plays = [x for dr in (s.get("drives") or {}).get("previous", []) for x in dr.get("plays", [])]
        wcs = [pd.Timestamp(x["wallclock"]).value if x.get("wallclock") else None for x in plays]
        ko = g.kickoff.value
        prev = (0, 0)
        for i, x in enumerate(plays):
            cur = (x.get("homeScore", prev[0]), x.get("awayScore", prev[1]))
            st = (x.get("scoringType") or {}).get("name")
            if x.get("scoringPlay") and st in I.SCORING_TYPES and wcs[i] is not None and \
                    (cur[0] > prev[0]) != (cur[1] > prev[1]):
                w = wcs[i]
                before = next((wcs[j] for j in range(i - 1, -1, -1) if wcs[j] is not None), None)
                after = next((wcs[j] for j in range(i + 1, len(plays)) if wcs[j] is not None), None)
                out_range = not (ko <= w <= ko + 6 * 3600 * NS)
                out_order = (before is not None and w < before) or (after is not None and w > after)
                ev_rows.append({"game_id": g.game_id, "wc_ns": w, "out_range": out_range, "out_order": out_order})
            prev = cur
    ev = pd.DataFrame(ev_rows)
    ev["defect"] = ev["out_range"] | ev["out_order"]
    bad_games = set(ev.loc[ev["defect"], "game_id"])
    tr = pd.read_csv(I.OUT / "training_trades.csv")
    tr = tr[tr["entered"].astype(bool)]
    evk = ev.groupby(["game_id", "wc_ns"], as_index=False)["defect"].any()   # events sharing a wallclock
    tr = tr.merge(evk, on=["game_id", "wc_ns"], how="left")
    lines = [f"# Idea 10 training: ESPN wallclock defects (diagnostic, report only)", "",
             f"label: {I.LABEL}", "",
             f"scoring events with a wallclock and one scoring side: {len(ev)}",
             f"outside [kickoff, kickoff + 6 h]: {int(ev['out_range'].sum())}",
             f"out of order with neighbouring plays: {int(ev['out_order'].sum())}",
             f"either: {int(ev['defect'].sum())}; games with at least one: {len(bad_games)}", "",
             "| s | leg | trades | trades in defect games | trades on a defective event | P&L total (direct x1) | "
             "P&L in defect games | share |", "|---|---|---|---|---|---|---|---|"]
    for (s, leg), r in tr.groupby(["s", "leg"]):
        inb = r["game_id"].isin(bad_games)
        tot, sub = r["pnl_direct"].sum(), r.loc[inb, "pnl_direct"].sum()
        lines.append(f"| {s} | {leg} | {len(r)} | {int(inb.sum())} | {int(r['defect'].fillna(False).sum())} | "
                     f"{tot:.2f} | {sub:.2f} | {sub / tot:.3f} |")
    lines += ["", "Defect games: " + ", ".join(sorted(bad_games))]
    (I.OUT / "training_wallclock_defects.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
