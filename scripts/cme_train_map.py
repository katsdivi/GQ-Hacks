"""Map CME football event contracts (FG = NFL, CG = college) to Kalshi TRAINING games and measure coverage.

Reads only files already on disk (no vendor requests):
  data/raw/fg_cg_defs.parquet, fg_cg_train_trades.parquet, fg_cg_train_bbo-1s.parquet (Databento GLBX.MDP3)
  data/raw/kalshi_only_games.csv, data/raw/kalshi_only/<game_id>.parquet
Writes data/raw/cme_train_v2/map.csv (gitignored) and prints a coverage summary.

Symbol layout (from fg_cg_defs.parquet): <FG|CG><team, 3 chars><month code><year digit><day> [C0001|P0001],
e.g. FGNEXF611 C0001 = NFL, New England, Jan (F) 2026, day 11. The day is the contract's listed game date
(expiration is 10:00 UTC the following morning). C0001 is the "team wins" contract.

Usage (cwd = repo root): python scripts/cme_train_map.py [--data ../staleline/data]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

MONTH = dict(zip("FGHJKMNQUVXZ", range(1, 13)))
# CME 3-char roots that differ from Kalshi codes (a trailing X pads 2-letter NFL codes).
FIX = {"JAX": "JAC", "LAR": "LA", "OLE": "MISS"}
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
PRE, POST = pd.Timedelta(hours=2), pd.Timedelta(hours=5)


def parse(sym: str):
    m = re.match(r"^(FG|CG)([A-Z]{3})([FGHJKMNQUVXZ])(\d)(\d{2})(?: ([CP])0001)?$", sym)
    if not m:
        return None
    lg, root, mon, yr, day, cp = m.groups()
    team = FIX.get(root, root[:-1] if root.endswith("X") else root)
    return {"league": "NFL" if lg == "FG" else "CFB", "root": root, "team": team,
            "date": pd.Timestamp(2020 + int(yr), MONTH[mon], int(day)).date(), "cp": cp or "F"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../staleline/data")
    a = ap.parse_args()
    raw = Path(a.data) / "raw"
    tr = pd.read_parquet(raw / "fg_cg_train_trades.parquet", columns=["ts_event", "symbol", "price", "size"])
    bbo = pd.read_parquet(raw / "fg_cg_train_bbo-1s.parquet", columns=["ts_event", "symbol"])
    print(f"CME trades on disk: {len(tr)} rows, {tr.ts_event.min()} to {tr.ts_event.max()}")
    print(f"CME bbo-1s on disk: {len(bbo)} rows, {bbo.ts_event.min()} to {bbo.ts_event.max()}")
    defs = pd.read_parquet(raw / "fg_cg_defs.parquet", columns=["raw_symbol", "expiration"])
    syms = pd.DataFrame([{"symbol": s, **p} for s in defs.raw_symbol.unique() if (p := parse(s))])
    syms = syms[(syms.cp == "C") & (pd.to_datetime(syms.date) < SEAL.tz_localize(None))]
    k = pd.read_csv(raw / "kalshi_only_games.csv")
    k["ko"] = pd.to_datetime(k.kickoff_utc_espn, utc=True)
    rows = []
    for s in syms.itertuples():
        et = k.ko.dt.tz_convert("America/New_York").dt.date
        c = k[(k.league == s.league) & ((k.home == s.team) | (k.away == s.team))
              & (et >= s.date - pd.Timedelta(days=1)) & (et <= s.date)]
        r = {"symbol": s.symbol, "league": s.league, "team": s.team, "cme_date": s.date,
             "game_id": c.game_id.iloc[0] if len(c) == 1 else None, "n_kalshi_match": len(c)}
        if len(c) == 1:
            ko = c.ko.iloc[0]
            lo, hi = ko - PRE, ko + POST
            st = tr[(tr.symbol == s.symbol) & (tr.ts_event >= lo) & (tr.ts_event <= hi)]
            sb = bbo[(bbo.symbol == s.symbol) & (bbo.ts_event >= lo) & (bbo.ts_event <= hi)]
            kf = raw / "kalshi_only" / f"{r['game_id']}.parquet"
            kt = pd.read_parquet(kf, columns=["ts", "kind"]) if kf.exists() else pd.DataFrame(columns=["ts", "kind"])
            kt = kt[kt.kind == "trade"]
            r.update(kickoff=ko, cme_trades_in_window=len(st), cme_bbo_rows_in_window=len(sb),
                     kalshi_trades_in_window=int(((kt.ts >= lo.value) & (kt.ts <= hi.value)).sum()))
        rows.append(r)
    m = pd.DataFrame(rows).sort_values(["cme_date", "symbol"])
    out = Path(a.data) / "raw" / "cme_train_v2"
    out.mkdir(parents=True, exist_ok=True)
    m.to_csv(out / "map.csv", index=False)
    both = m[(m.cme_trades_in_window.fillna(0) > 0) & (m.kalshi_trades_in_window.fillna(0) > 0)]
    print(f"CME 'win' contracts with game date before 2026-08-01: {len(m)}")
    print(f"  matched to exactly one Kalshi training game: {m.game_id.notna().sum()}")
    print(f"  with CME AND Kalshi trades in [kickoff - 2 h, + 5 h]: {len(both)} contracts, "
          f"{both.game_id.nunique()} games")
    print(m.to_string(index=False))


if __name__ == "__main__":
    main()
