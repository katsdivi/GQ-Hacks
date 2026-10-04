"""Collect sportsbook line data for training games -> data/raw/lines/moves.parquet.

Free sources only (no paid APIs, no logins):
  1. ESPN core odds API (open/close/current per provider; NO timestamps, movement sub-resource empty)
  2. ESPN summary pickcenter cache (DraftKings current line, 208 games)
  3. nflverse games.csv closing lines (NFL only, baseline)
Usage: python scripts/fetch_lines.py [--root <staleline main dir>] [--espn-cache <espn_raw dir>] [--skip-fetch]
Rate limit: <= 2 req/s per host. Raw JSON cached under data/raw/lines/espn_core/.
"""
import argparse, json, os, time, glob
import pandas as pd, numpy as np, requests

MAIN = "/Users/divyamkataria/GQ HACKS/staleline"
ESPN_RAW = "/Users/divyamkataria/GQ HACKS/wt-idea6/data/espn_raw"
LG = {"NFL": "nfl", "CFB": "college-football"}
NFLV = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"


def am(s):
    try:
        return float(str(s).replace("+", ""))
    except Exception:
        return np.nan


def pt(s):
    return am(s)


def ml_prob(a):
    return -a / (-a + 100) if a < 0 else 100 / (a + 100)


def novig(h, a):
    if np.isnan(h) or np.isnan(a):
        return np.nan
    ph, pa = ml_prob(h), ml_prob(a)
    return ph / (ph + pa)


def fetch(games, cache, skip):
    os.makedirs(cache, exist_ok=True)
    s = requests.Session()
    for r in games.itertuples():
        f = f"{cache}/{r.game_id}.json"
        if os.path.exists(f) or skip:
            continue
        i = r.espn_id
        B = f"https://sports.core.api.espn.com/v2/sports/football/leagues/{LG[r.league]}/events/{i}/competitions/{i}"
        out = {"odds": None, "movement": {}}
        try:
            out["odds"] = s.get(B + "/odds", timeout=20).json()
            time.sleep(0.5)
            for it in out["odds"].get("items", []):
                p = it["provider"]["id"]
                out["movement"][p] = s.get(f"{B}/odds/{p}/history/0/movement", timeout=20).json()
                time.sleep(0.5)
        except Exception as e:
            out["err"] = str(e)
        json.dump(out, open(f, "w"))


def rows_from_core(games, cache):
    R = []
    for r in games.itertuples():
        f = f"{cache}/{r.game_id}.json"
        if not os.path.exists(f):
            continue
        d = json.load(open(f))
        kick = pd.Timestamp(r.kickoff_utc_espn)
        for it in (d.get("odds") or {}).get("items", []):
            prov = it["provider"]["name"]
            if prov == "ESPN Bet - Live Odds":
                continue
            ho, ao = it.get("homeTeamOdds", {}), it.get("awayTeamOdds", {})
            for ph in ("open", "close"):
                h, a = ho.get(ph, {}) or {}, ao.get(ph, {}) or {}
                ts = kick if ph == "close" else pd.NaT
                prec = "assumed_at_kickoff" if ph == "close" else "none_untimed_open"
                hp = pt(h.get("pointSpread", {}).get("american"))
                ap = pt(a.get("pointSpread", {}).get("american"))
                if ph == "close" and not np.isnan(hp):
                    R.append(dict(ts_utc=ts, source="espn_core", book=prov, game_id=r.game_id, market="spread",
                                  home_value=hp, away_value=ap, implied_home_prob_novig=np.nan, ts_precision=prec, phase=ph))
                hm, am_ = am(h.get("moneyLine", {}).get("american")), am(a.get("moneyLine", {}).get("american"))
                if ph == "close" and not np.isnan(hm):  # ESPN 'open' moneyLine duplicates the spread price, so not emitted
                    R.append(dict(ts_utc=ts, source="espn_core", book=prov, game_id=r.game_id, market="moneyline",
                                  home_value=hm, away_value=am_, implied_home_prob_novig=novig(hm, am_), ts_precision=prec, phase=ph))
                if ph == "open" and not np.isnan(hp):
                    R.append(dict(ts_utc=ts, source="espn_core", book=prov, game_id=r.game_id, market="spread",
                                  home_value=hp, away_value=ap, implied_home_prob_novig=np.nan, ts_precision=prec, phase=ph))
    return R


def rows_pickcenter(games, espn_raw):
    R = []
    for r in games.itertuples():
        f = f"{espn_raw}/{'nfl' if r.league=='NFL' else 'cfb'}_{r.espn_id}.json"
        if not os.path.exists(f):
            continue
        d = json.load(open(f))
        for p in d.get("pickcenter") or []:
            ho, ao = p.get("homeTeamOdds", {}), p.get("awayTeamOdds", {})
            hm, am_ = ho.get("moneyLine"), ao.get("moneyLine")
            kick = pd.Timestamp(r.kickoff_utc_espn)
            if hm is not None and am_ is not None:
                R.append(dict(ts_utc=kick, source="espn_pickcenter", book=p["provider"]["name"], game_id=r.game_id,
                              market="moneyline", home_value=float(hm), away_value=float(am_),
                              implied_home_prob_novig=novig(float(hm), float(am_)), ts_precision="assumed_at_kickoff", phase="current"))
            if p.get("spread") is not None:
                hs = p["spread"] if ho.get("favorite") else -p["spread"]
                R.append(dict(ts_utc=kick, source="espn_pickcenter", book=p["provider"]["name"], game_id=r.game_id,
                              market="spread", home_value=float(p["spread"]), away_value=-float(p["spread"]),
                              implied_home_prob_novig=np.nan, ts_precision="assumed_at_kickoff", phase="current"))
    return R


def rows_nflverse(games, raw):
    f = f"{raw}/nflverse_games.csv"
    if not os.path.exists(f):
        open(f, "wb").write(requests.get(NFLV, timeout=60).content)
    n = pd.read_csv(f)
    n = n[n.season == 2025]
    espn_map = {str(int(e)): g for e, g in zip(n.espn.dropna(), n.loc[n.espn.notna(), "game_id"])}
    R = []
    for r in games[games.league == "NFL"].itertuples():
        row = n[n.espn == float(r.espn_id)]
        if row.empty:
            continue
        x = row.iloc[0]
        kick = pd.Timestamp(r.kickoff_utc_espn)
        if pd.notna(x.home_moneyline):
            R.append(dict(ts_utc=kick, source="nflverse", book="close_consensus", game_id=r.game_id, market="moneyline",
                          home_value=x.home_moneyline, away_value=x.away_moneyline,
                          implied_home_prob_novig=novig(x.home_moneyline, x.away_moneyline), ts_precision="assumed_at_kickoff", phase="close"))
        if pd.notna(x.spread_line):  # nflverse spread_line is positive when home favored
            R.append(dict(ts_utc=kick, source="nflverse", book="close_consensus", game_id=r.game_id, market="spread",
                          home_value=-x.spread_line, away_value=x.spread_line, implied_home_prob_novig=np.nan,
                          ts_precision="assumed_at_kickoff", phase="close"))
    return R


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=MAIN)
    ap.add_argument("--espn-cache", default=ESPN_RAW)
    ap.add_argument("--skip-fetch", action="store_true")
    a = ap.parse_args()
    raw = f"{a.root}/data/raw"
    out = f"{raw}/lines"
    os.makedirs(out, exist_ok=True)
    kg = pd.read_csv(f"{raw}/kalshi_only_games.csv")
    ids = pd.read_csv(f"{a.espn_cache}/ids_training.csv", dtype={"espn_id": str})
    games = kg.merge(ids[["game_id", "espn_id"]], on="game_id", how="left")
    print("games", len(games), "with espn id", games.espn_id.notna().sum())
    games = games[games.espn_id.notna()]
    fetch(games, f"{out}/espn_core", a.skip_fetch)
    R = rows_from_core(games, f"{out}/espn_core") + rows_pickcenter(games, a.espn_cache) + rows_nflverse(games, out)
    df = pd.DataFrame(R)
    df["ts_utc"] = pd.to_datetime(df.ts_utc, utc=True).astype("datetime64[ns, UTC]")
    df["league"] = df.game_id.str.split("_").str[0].str.upper()
    cols = ["ts_utc", "source", "book", "league", "game_id", "market", "home_value", "away_value",
            "implied_home_prob_novig", "ts_precision", "phase"]
    df = df[cols].sort_values(["game_id", "source", "book", "market", "ts_utc"])
    df.to_parquet(f"{out}/moves.parquet", index=False)
    mv = json_n = 0
    for f in glob.glob(f"{out}/espn_core/*.json"):
        d = json.load(open(f))
        mv += sum(m.get("count", 0) for m in d.get("movement", {}).values())
    print("rows", len(df), "games covered", df.game_id.nunique(), "of", len(kg), "| ESPN movement items total:", mv)
    print(df.groupby(["source", "book", "market", "phase"]).game_id.nunique())
