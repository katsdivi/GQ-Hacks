"""Post-hoc cost-side search, Round 7 (SPEC.md Round 7: ESPN non-scoring possession changes and halftime; 8 trials).

post-hoc, exploratory; training only. ESPN cache read-only from ../wt-idea6/data/espn_raw/. Usage:
  PYTHONPATH=.:scripts python scripts/costside_round7.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import costside_common as C
import costside_round1 as R1
import ingest.kalshi_only_train as T

ESPN = Path("/Users/divyamkataria/GQ HACKS/wt-idea6/data/espn_raw")
TO_RESULTS = {"INT", "FUMBLE", "DOWNS", "MISSED FG"}


def registry() -> list[dict]:
    r = [{"trial": f"R7.TO.{d}.{em}", "method": "ESPN non-scoring possession change, Kalshi reaction",
          "params": f"{d} m>=0.03 (fade) / 0<=m<0.03 (follow) exec={em}",
          "cost_line": "taker" if em == "taker" else "maker175 (alt maker0)"}
         for d in ("fade", "follow") for em in ("taker", "maker")]
    r += [{"trial": f"R7.HALF.{d}.{em}", "method": "2nd-quarter momentum into halftime",
           "params": f"{d} |c|>=0.10 exec={em}", "cost_line": "taker" if em == "taker" else "maker175 (alt maker0)"}
          for d in ("follow", "fade") for em in ("taker", "maker")]
    assert len(r) == 8
    return [{**x, "round": 7} for x in r]


def orient(comp, k_home, k_away):
    """Idea 6 rule (posthoc-idea6 0f57732 scripts/posthoc_idea6.py orient())."""
    t = {c["homeAway"]: c["team"] for c in comp["competitors"]}
    same = T._name_score(*k_home, t["home"]) + T._name_score(*k_away, t["away"])
    swap = T._name_score(*k_home, t["away"]) + T._name_score(*k_away, t["home"])
    if max(same, swap) < 1.6 or same == swap:
        return None
    return "same" if same > swap else "swapped"


def ns(w: str) -> int:
    return pd.Timestamp(w).value


def load_espn(g, idrow, stats):
    f = ESPN / f"{g['league'].lower()}_{idrow.espn_id}.json"
    if not f.exists():
        stats["no summary"] += 1
        return None
    d = json.loads(f.read_text())
    comp = d["header"]["competitions"][0]
    o = orient(comp, (idrow.k_home_name, g["home"]), (idrow.k_away_name, g["away"]))
    if o is None:
        stats["mapping"] += 1
        return None
    id2code = {}
    for c in comp["competitors"]:
        kal_home = (c["homeAway"] == "home") == (o == "same")
        id2code[str(c["team"]["id"])] = g["home"] if kal_home else g["away"]
    drives = (d.get("drives") or {}).get("previous", [])
    plays = [p for dr in drives for p in dr.get("plays", []) if p.get("wallclock")]
    w = np.array([ns(p["wallclock"]) for p in plays], dtype=np.int64)
    ko = g["kickoff_ns"]
    if len(w) == 0 or (w < ko).any() or (w > ko + 6 * 3600 * C.NS).any() or (np.diff(w) < -300 * C.NS).any():
        stats["defect"] += 1
        return None
    stats["ok"] += 1
    return {"drives": drives, "plays": plays, "id2code": id2code}


def price_at(g, team, t, maxage):
    ts, px = g["own"][team]
    i = np.searchsorted(ts, t, side="right") - 1
    return float(px[i]) if i >= 0 and t - ts[i] <= maxage * C.NS else np.nan


def events(g, e):
    ko = g["kickoff_ns"]
    lo, hi = ko + 20 * 60 * C.NS, ko + 4 * 3600 * C.NS
    out = {"TO.fade": [], "TO.follow": [], "HALF.follow": [], "HALF.fade": []}
    for dr in e["drives"]:
        if dr.get("result") not in TO_RESULTS or not dr.get("plays"):
            continue
        last = [p for p in dr["plays"] if p.get("wallclock")]
        if not last:
            continue
        wc = ns(last[-1]["wallclock"])
        t = wc + 60 * C.NS
        if not (lo <= t <= hi):
            continue
        lost = e["id2code"].get(str(dr.get("team", {}).get("id")))
        if lost is None:
            continue
        gain = g["away"] if lost == g["home"] else g["home"]
        pre, post = price_at(g, gain, wc, 120), price_at(g, gain, t, 30)
        if pre != pre or post != post:
            continue
        m = post - pre
        if m >= 0.03 - 1e-9 and not out["TO.fade"]:
            out["TO.fade"].append((t, lost))
        if 0 <= m < 0.03 - 1e-9 and not out["TO.follow"]:
            out["TO.follow"].append((t, gain))
    def marker(txt):
        for p in e["plays"]:
            if p.get("text", "").strip().rstrip(".").lower() == txt:
                return ns(p["wallclock"]) + 60 * C.NS
        return None
    t1, t2 = marker("end of 1st quarter"), marker("end of 2nd quarter")
    if t1 and t2 and lo <= t2 <= hi:
        a, b = price_at(g, g["home"], t1, 120), price_at(g, g["home"], t2, 120)
        if a == a and b == b and abs(b - a) >= 0.10 - 1e-9:
            up = g["home"] if b > a else g["away"]
            dn = g["away"] if up == g["home"] else g["home"]
            out["HALF.follow"].append((t2, up))
            out["HALF.fade"].append((t2, dn))
    return out


def main() -> None:
    games = C.load_games()
    wk, hist = C.week_index(games)
    pd.DataFrame(registry()).to_csv(C.CACHE / "registry_round7.csv", index=False)
    ids = pd.read_csv(ESPN / "ids_training.csv").set_index("game_id")
    stats = {"no summary": 0, "mapping": 0, "defect": 0, "ok": 0, "no id": 0}
    rows = []
    for g in games:
        if wk[g["game_id"]] < hist:
            continue
        if g["game_id"] not in ids.index or ids.loc[g["game_id"], "espn_id"] != ids.loc[g["game_id"], "espn_id"]:
            stats["no id"] += 1
            continue
        idrow = ids.loc[g["game_id"]]
        idrow = idrow.iloc[0] if isinstance(idrow, pd.DataFrame) else idrow
        idrow = idrow.copy()
        idrow["espn_id"] = int(float(idrow["espn_id"]))
        e = load_espn(g, idrow, stats)
        if e is None:
            continue
        for name, evs in events(g, e).items():
            for t, team in evs:
                for em in ("taker", "maker"):
                    rows += R1.run_sequential(g, [(t, 1)], lambda _d, team=team: team, f"R7.{name}.{em}", em, None,
                                              {"week": wk[g["game_id"]]})
    print("ESPN games:", stats, flush=True)
    pd.DataFrame(rows).to_parquet(C.CACHE / "trades_round7.parquet")
    (C.CACHE / "round7_espn_stats.json").write_text(json.dumps(stats))


if __name__ == "__main__":
    sys.exit(main())
