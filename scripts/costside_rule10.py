"""Rule 10 (research pass): early-season vs later kickoff-price calibration, DESCRIPTIVE only (no trial).

post-hoc, exploratory; training only. Usage: PYTHONPATH=.:scripts python scripts/costside_rule10.py
"""
import numpy as np
import pandas as pd

import costside_common as C
import costside_espn as E

games = C.load_games()
wk, _ = C.week_index(games)
rows = []
for g in games:
    K = E.kickoff_price(g)
    pay = g["pay"][g["home"]]
    if K != K or pay != pay:
        continue
    for p, y in ((K, pay), (1 - K, 1 - pay)):
        rows.append({"early": wk[g["game_id"]] < 4, "p": p, "y": y})
d = pd.DataFrame(rows)
d["bin"] = pd.cut(d.p, [0.15, 0.35, 0.65, 0.85], labels=["15-35c", "35-65c", "65-85c"])
t = d.dropna(subset=["bin"]).groupby(["early", "bin"], observed=True).agg(n=("y", "size"), price=("p", "mean"),
                                                                        win=("y", "mean")).reset_index()
t["win_minus_price"] = t.win - t.price
t["period"] = np.where(t.early, "weeks 1-4", "weeks 5+")
t = t[["period", "bin", "n", "price", "win", "win_minus_price"]].round(4)
t.to_csv(C.OUT / "rule10_calibration.csv", index=False)
print(C.md(t))
