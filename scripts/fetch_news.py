#!/usr/bin/env python3
"""Build data/raw/news/events.parquet: timestamped news events for training games.

Sources (free only): Google News RSS (per team per game, date-filtered), nflverse
injury reports (week level), plus ESPN probes (summary news, team news depth).
Usage: python3 scripts/fetch_news.py [--stage probe|gnews|gdelt|reddit|bsky|build (run fetch stages in parallel, then build)] [--root DIR]
Raw cache (resumable) lives in <root>/data/raw/news/. Max 2 req/s per host.
"""
import argparse, json, os, re, time, urllib.parse, urllib.request, email.utils, html
from datetime import datetime, timedelta, timezone
import pandas as pd

ROOT = "/Users/divyamkataria/GQ HACKS/staleline"
ESPN_CACHE = "/Users/divyamkataria/GQ HACKS/wt-idea6/data/espn_raw"
UA = {"User-Agent": "Mozilla/5.0 (StaleLine research)"}
_last = {}

def get(url, tries=3):
    host = urllib.parse.urlparse(url).netloc
    for i in range(tries):
        w = 0.55 - (time.time() - _last.get(host, 0))
        if w > 0: time.sleep(w)
        _last[host] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read()
        except Exception as e:
            err = e; time.sleep(2 * (i + 1))
    raise err

def load_games(root):
    g = pd.read_csv(f"{root}/data/raw/kalshi_only_games.csv")
    g["kick"] = pd.to_datetime(g.kickoff_utc_espn, utc=True)
    ids = pd.read_csv(f"{ESPN_CACHE}/ids_training.csv")[["game_id", "espn_id"]]
    g = g.merge(ids, on="game_id", how="left")
    names = {}
    for r in g.itertuples():
        p = f"{ESPN_CACHE}/{r.league.lower()}_{r.espn_id}.json"
        if pd.notna(r.espn_id) and os.path.exists(p):
            try:
                c = json.load(open(p))["header"]["competitions"][0]["competitors"]
                for t in c:
                    names[(r.game_id, t["homeAway"])] = (t["team"].get("location"), t["team"].get("name"))
            except Exception:
                pass
    g["home_loc"] = [names.get((i, "home"), (None, None))[0] for i in g.game_id]
    g["home_nick"] = [names.get((i, "home"), (None, None))[1] for i in g.game_id]
    g["away_loc"] = [names.get((i, "away"), (None, None))[0] for i in g.game_id]
    g["away_nick"] = [names.get((i, "away"), (None, None))[1] for i in g.game_id]
    return g

KW = '(inactive OR "ruled out" OR questionable OR doubtful OR injury OR "starting quarterback" OR "will start")'

def gnews_url(loc, nick, league, d0, d1):
    nm = f'"{loc} {nick}"' if league == "NFL" else f'"{loc}" football'
    q = f"{nm} {KW} after:{d0} before:{d1}"
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})

def fetch_gnews(root, games):
    d = f"{root}/data/raw/news/gnews"; os.makedirs(d, exist_ok=True)
    todo = []
    for r in games.itertuples():
        for side in ("home", "away"):
            loc, nick = getattr(r, f"{side}_loc"), getattr(r, f"{side}_nick")
            if not loc: continue
            k = r.kick - timedelta(hours=6)
            d0 = (k - timedelta(days=4)).strftime("%Y-%m-%d"); d1 = (k + timedelta(days=2)).strftime("%Y-%m-%d")
            todo.append((f"{d}/{r.game_id}_{side}.xml", gnews_url(loc, nick, r.league, d0, d1)))
    n = 0
    for path, url in todo:
        if os.path.exists(path): continue
        try:
            open(path, "wb").write(get(url))
        except Exception as e:
            print("fail", path, e); continue
        n += 1
        if n % 100 == 0: print("gnews fetched", n, "of", len(todo), flush=True)

def classify(t):
    s = t.lower()
    if re.search(r"inactive|inactives|\bin and out\b", s): return "inactive"
    if re.search(r"ruled out|will not play|won't play|out for|\bout vs|\bout against|placed on (ir|injured)|season-ending|sidelined", s): return "injury_out"
    if re.search(r"starting quarterback|start at qb|named (the )?starter|to start at quarterback|benched|will start|qb change|backup qb|turns to", s): return "qb_change"
    if re.search(r"questionable|doubtful|game-time decision|game-time|downgraded|injury report|limited in practice", s): return "questionable"
    return "other"

def parse_gnews(root, games):
    rows = []
    d = f"{root}/data/raw/news/gnews"
    for r in games.itertuples():
        for side in ("home", "away"):
            p = f"{d}/{r.game_id}_{side}.xml"
            if not os.path.exists(p): continue
            x = open(p, encoding="utf-8", errors="ignore").read()
            code = r.home if side == "home" else r.away
            loc, nick = getattr(r, f"{side}_loc"), getattr(r, f"{side}_nick")
            for it in re.findall(r"<item>(.*?)</item>", x, re.S):
                title = html.unescape(re.search(r"<title>(.*?)</title>", it, re.S).group(1))
                link = html.unescape(re.search(r"<link>(.*?)</link>", it, re.S).group(1))
                pd_ = re.search(r"<pubDate>(.*?)</pubDate>", it)
                if not pd_: continue
                ts = pd.Timestamp(email.utils.parsedate_to_datetime(pd_.group(1))).tz_convert("UTC")
                tl = title.lower()
                if loc.lower() not in tl and (nick or "").lower() not in tl: continue
                src = title.rsplit(" - ", 1)[-1] if " - " in title else ""
                # Google truncates historical pubDates to the day (07:00:00 or 08:00:00 GMT = 00:00 Pacific)
                prec = "day" if (ts.minute == 0 and ts.second == 0 and ts.hour in (7, 8)) else "second"
                rows.append(dict(ts_utc=ts, source="gnews_rss", league=r.league, team=code, game_id=r.game_id,
                                 event_type=classify(title), headline=title, url=link, ts_precision=prec, publisher=src,
                                 kick=r.kick))
    df = pd.DataFrame(rows)
    return df.drop_duplicates(["url", "team", "game_id"])

def parse_nflverse(root, games):
    nf = games[games.league == "NFL"]
    sched = pd.read_csv("https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv")
    sched = sched[sched.season == 2025]
    inj = []
    for yr in (2025,):
        p = f"{root}/data/raw/news/injuries_{yr}.parquet"
        if not os.path.exists(p):
            open(p, "wb").write(get(f"https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{yr}.parquet"))
        inj.append(pd.read_parquet(p))
    inj = pd.concat(inj)
    fix = {"JAC": "JAX"}
    rows = []
    for r in nf.itertuples():
        kd = (r.kick - timedelta(hours=6)).strftime("%Y-%m-%d")
        h, a = fix.get(r.home, r.home), fix.get(r.away, r.away)
        m = sched[(sched.home_team == h) & (sched.away_team == a) & (sched.gameday.between((r.kick - timedelta(days=2)).strftime("%Y-%m-%d"), (r.kick + timedelta(days=1)).strftime("%Y-%m-%d")))]
        if m.empty: continue
        wk, gt = int(m.week.iloc[0]), m.game_type.iloc[0]
        for side, code, nv in (("home", r.home, h), ("away", r.away, a)):
            sub = inj[(inj.team == nv) & (inj.week == wk) & (inj.game_type == gt) & inj.report_status.notna()]
            for q in sub.itertuples():
                et = "injury_out" if q.report_status == "Out" else "questionable"
                rows.append(dict(ts_utc=r.kick.floor("D"), source="nflverse_injuries", league="NFL", team=code, game_id=r.game_id,
                                 event_type=et, headline=f"{q.full_name} ({q.position}) {q.report_status}: {q.report_primary_injury}",
                                 url="https://github.com/nflverse/nflverse-data/releases/tag/injuries", ts_precision="day",
                                 publisher="NFL official report", kick=r.kick))
    return pd.DataFrame(rows)

def probe(root):
    out = {}
    for lg, sp in (("nfl", "nfl"), ("cfb", "college-football")):
        for lim in (50,):
            try:
                a = json.loads(get(f"https://site.api.espn.com/apis/site/v2/sports/football/{sp}/news?limit={lim}"))["articles"]
                out[f"{lg}_league_news"] = (len(a), min(x["published"] for x in a), max(x["published"] for x in a))
            except Exception as e:
                out[f"{lg}_league_news"] = str(e)
    try:
        a = json.loads(get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/8/news?limit=100"))["articles"]
        out["nfl_team8_news"] = (len(a), min(x["published"] for x in a), max(x["published"] for x in a))
    except Exception as e:
        out["nfl_team8_news"] = str(e)
    c = {}; inj = 0
    for f in os.listdir(ESPN_CACHE):
        if not f.endswith(".json"): continue
        d = json.load(open(f"{ESPN_CACHE}/{f}"))
        if d.get("injuries"): inj += 1
        for a in (d.get("news") or {}).get("articles", []): c[a["published"][:7]] = c.get(a["published"][:7], 0) + 1
    out["espn_summary_news_by_month"] = c; out["espn_summary_with_injuries"] = inj
    json.dump(out, open(f"{root}/data/raw/news/probe_espn.json", "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


KEYS = re.compile(r"inactive|ruled out|\bout\b|questionable|doubtful|injur|will not play|won't play|expected to play|starting|\bstart(s|ed)?\b|benched|suspend|placed on|\bIR\b|activated|game-time|downgraded|sidelined|surgery|torn|limited|DNP|lineup|concussion|return", re.I)
INSIDERS = re.compile(r"^\[(schefter|rapoport|pelissero|garafolo|fowler|thamel|dellenger|russini|yates|mortensen|palmer|breer|auman|volin|cabot|mcafee|graziano|wickersham|[a-z .'-]{3,25})\]", re.I)

def sleep_get(url, wait):
    time.sleep(wait); return get(url)

def fetch_gdelt(root, games):
    d = f"{root}/data/raw/news/gdelt"; os.makedirs(d, exist_ok=True)
    order = games[games.league == "NFL"].sample(frac=1, random_state=0)  # random order: any partial run is a random sample (GDELT is slow, ~35 s/query)
    n = 0
    for r in order.itertuples():
        p = f"{d}/{r.game_id}.json"
        if os.path.exists(p) or not r.home_loc: continue
        if r.league == "NFL":
            t = f'("{r.home_loc} {r.home_nick}" OR "{r.away_loc} {r.away_nick}")'
        else:
            t = f'("{r.home_loc}" OR "{r.away_loc}") football'
        q = t + ' (injury OR inactive OR "ruled out" OR questionable OR doubtful OR "starting quarterback" OR suspended)'
        s0 = (r.kick - timedelta(hours=30)).strftime("%Y%m%d%H%M%S"); s1 = (r.kick + timedelta(hours=1)).strftime("%Y%m%d%H%M%S")
        url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(
            {"query": q, "mode": "artlist", "format": "json", "startdatetime": s0, "enddatetime": s1, "maxrecords": 250, "sort": "datedesc"})
        for _ in range(8):
            try:
                b = sleep_get(url, 6)
                json.loads(b); open(p, "wb").write(b); break
            except Exception as e:
                time.sleep(4)
        n += 1
        if n % 50 == 0: print("gdelt", n, flush=True)

def fetch_reddit(root):
    d = f"{root}/data/raw/news/reddit"; os.makedirs(d, exist_ok=True)
    for sub in ("nfl", "CFB"):
        p = f"{d}/{sub}.jsonl"
        last = 1754006400  # 2025-08-01
        if os.path.exists(p):
            for line in open(p): last = max(last, json.loads(line)["created_utc"])
        end = 1769990400  # 2026-02-02
        f = open(p, "a"); fails = 0
        while last < end:
            a = datetime.fromtimestamp(last, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            url = f"https://arctic-shift.photon-reddit.com/api/posts/search?subreddit={sub}&after={a}&before=2026-02-02T00:00:00Z&limit=100&sort=asc"
            try:
                data = json.loads(sleep_get(url, 0.6)).get("data") or []
            except Exception:
                data = None
            if not data:
                fails += 1
                if fails > 8: print("reddit stop", sub, a); break
                time.sleep(5); continue
            fails = 0
            for x in data: f.write(json.dumps({k: x.get(k) for k in ("id", "created_utc", "title", "permalink", "score")}) + "\n")
            f.flush()
            nl = max(x["created_utc"] for x in data)
            last = nl + 1 if nl == last else nl
            print("reddit", sub, a, len(data), flush=True)

BSKY = ["tompelissero", "rapsheet", "mortreport", "adamschefter", "ianrapoport", "jordanschultz", "nfl", "pfrumors", "espn", "nflnetwork", "petethamel", "heismanwatch", "ncaafootball", "dpbrugler", "danorlovsky7", "joshnorris"]

def fetch_bsky(root):
    d = f"{root}/data/raw/news/bsky"; os.makedirs(d, exist_ok=True)
    for h in BSKY:
        p = f"{d}/{h}.jsonl"
        if os.path.exists(p): continue
        rows, cur = [], None
        while True:
            url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor={h}.bsky.social&limit=100&filter=posts_no_replies" + (f"&cursor={cur}" if cur else "")
            try: j = json.loads(sleep_get(url, 0.6))
            except Exception as e: print("bsky skip", h, e); break
            fe = j.get("feed", [])
            if not fe: break
            old = False
            for it in fe:
                po = it["post"]
                if it.get("reason") or po["author"]["handle"].lower() != f"{h}.bsky.social": continue
                ts = po["record"]["createdAt"]
                if ts < "2025-08-01": old = True; continue
                rows.append(dict(ts=ts, text=po["record"].get("text", ""), uri=po["uri"], handle=h))
            cur = j.get("cursor")
            if old or not cur: break
        open(p, "w").write("\n".join(json.dumps(r) for r in rows)); print("bsky", h, len(rows), flush=True)

def aliases(games):
    """Per (league, code): list of (regex, label). NFL by nickname; CFB by location."""
    al = {}
    for r in games.itertuples():
        for code, loc, nick in ((r.home, r.home_loc, r.home_nick), (r.away, r.away_loc, r.away_nick)):
            if not loc: continue
            names = [nick] if r.league == "NFL" else [loc]
            al[(r.league, code)] = [re.compile(r"\b" + re.escape(x) + r"\b", re.I) for x in names if x]
    return al

def attribute(games, al, ts, text, hours_before=48, after=4):
    """Return list of (game_id, code, league, kick) the text refers to, games kicking off in [ts-after, ts+hours_before]."""
    out = []
    cand = games[(games.kick >= ts - timedelta(hours=after)) & (games.kick <= ts + timedelta(hours=hours_before))]
    for r in cand.itertuples():
        for code in (r.home, r.away):
            if any(rx.search(text) for rx in al.get((r.league, code), [])):
                out.append((r.game_id, code, r.league, r.kick))
    return out

def mk(ts, source, league, team, gid, headline, url, prec, pub, kick):
    return dict(ts_utc=ts, source=source, league=league, team=team, game_id=gid, event_type=classify(headline),
                headline=headline, url=url, ts_precision=prec, publisher=pub, kick=kick)

def parse_social(root, games):
    al = aliases(games); rows = []
    g = games.sort_values("kick")
    # reddit
    for sub in ("nfl", "CFB"):
        p = f"{root}/data/raw/news/reddit/{sub}.jsonl"
        if not os.path.exists(p): continue
        for line in open(p):
            x = json.loads(line); t = x["title"]
            if not KEYS.search(t): continue
            ts = pd.Timestamp(x["created_utc"], unit="s", tz="UTC")
            m = INSIDERS.match(t); pub = f"r/{sub}" + (f" {m.group(1)}" if m else "")
            for gid, code, lg, kick in attribute(g, al, ts, t):
                if (lg == "NFL") != (sub == "nfl"): continue
                rows.append(mk(ts, "reddit_arctic_shift", lg, code, gid, t, "https://reddit.com" + x["permalink"], "second", pub, kick))
    # bluesky
    for f in os.listdir(f"{root}/data/raw/news/bsky") if os.path.isdir(f"{root}/data/raw/news/bsky") else []:
        for line in open(f"{root}/data/raw/news/bsky/{f}"):
            x = json.loads(line); t = x["text"]
            if not KEYS.search(t): continue
            ts = pd.Timestamp(x["ts"]).tz_convert("UTC")
            for gid, code, lg, kick in attribute(g, al, ts, t):
                rows.append(mk(ts, "bluesky", lg, code, gid, t, "https://bsky.app/profile/" + x["handle"] + ".bsky.social/post/" + x["uri"].rsplit("/", 1)[-1], "second", "@" + x["handle"], kick))
    # gdelt (per-game cache; seendate is first-seen by GDELT, 15 min grid)
    d = f"{root}/data/raw/news/gdelt"
    gi = games.set_index("game_id")
    for f in os.listdir(d) if os.path.isdir(d) else []:
        gid = f[:-5]
        try: arts = json.load(open(f"{d}/{f}")).get("articles", [])
        except Exception: continue
        r = gi.loc[gid]
        for a in arts:
            t = a["title"]
            ts = pd.Timestamp(datetime.strptime(a["seendate"], "%Y%m%dT%H%M%SZ"), tz="UTC")
            for code in (r.home, r.away):
                if any(rx.search(t) for rx in al.get((r.league, code), [])):
                    rows.append(mk(ts, "gdelt_doc", r.league, code, gid, t, a["url"], "minute", a.get("domain", ""), r.kick))
    # apify X
    p = f"{root}/data/raw/news/apify_x.json"
    if os.path.exists(p):
        for x in json.load(open(p)):
            ts = pd.Timestamp(datetime.strptime(x["createdAt"], "%a %b %d %H:%M:%S %z %Y")).tz_convert("UTC")
            for gid, code, lg, kick in attribute(g, al, ts, x["fullText"], 48, 6):
                rows.append(mk(ts, "apify_x", lg, code, gid, x["fullText"], x["url"], "second", "@" + x["author.userName"], kick))
    return pd.DataFrame(rows).drop_duplicates(["url", "team", "game_id"])

def build(root, games):
    parts = [parse_gnews(root, games), parse_nflverse(root, games), parse_social(root, games)]
    extra = f"{root}/data/raw/news/events_extra.parquet"   # optional Apify rows
    if os.path.exists(extra): parts.append(pd.read_parquet(extra))
    ev = pd.concat(parts, ignore_index=True)
    ev["ts_utc"] = pd.to_datetime(ev.ts_utc, utc=True).astype("datetime64[ns, UTC]")
    ev["hrs_before_kick"] = (ev.kick - ev.ts_utc).dt.total_seconds() / 3600
    ev["in_6h_pre_kick"] = ev.hrs_before_kick.between(0, 6) & (ev.ts_precision != "day")  # day-precision rows cannot be placed within 6h
    cols = ["ts_utc", "source", "league", "team", "game_id", "event_type", "headline", "url", "ts_precision", "publisher", "hrs_before_kick", "in_6h_pre_kick"]
    ev = ev.sort_values("ts_utc")[cols].reset_index(drop=True)
    ev.to_parquet(f"{root}/data/raw/news/events.parquet", index=False)
    print(len(ev), "events")
    print(ev.groupby(["source", "league", "event_type"]).size())
    print(ev.groupby(["source", "ts_precision"]).size())
    intr = ev[ev.ts_precision != "day"]
    print("intraday rows", len(intr), "in 6h pre-kick", int(intr.in_6h_pre_kick.sum()),
          "games covered by intraday 6h:", intr[intr.in_6h_pre_kick].game_id.nunique(), "of", games.game_id.nunique())
    print("games with any event", ev.game_id.nunique())
    print("minute-or-better share", round(float((ev.ts_precision != "day").mean()), 4), "of", len(ev))
    print(intr.groupby(["source", "league"]).agg(n=("ts_utc", "size"), n_6h=("in_6h_pre_kick", "sum")))
    print(intr[intr.in_6h_pre_kick].groupby("league").game_id.nunique(), games.groupby("league").game_id.nunique())
    print(intr[intr.in_6h_pre_kick].groupby("event_type").size())
    print(intr[(intr.event_type != "other")].groupby(["source", "event_type"]).size())

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--stage", default="all"); ap.add_argument("--root", default=ROOT)
    a = ap.parse_args()
    os.makedirs(f"{a.root}/data/raw/news", exist_ok=True)
    g = load_games(a.root)
    if a.stage in ("probe",): probe(a.root)
    if a.stage in ("fetch", "gnews"): fetch_gnews(a.root, g)
    if a.stage == "gdelt": fetch_gdelt(a.root, g)
    if a.stage == "reddit": fetch_reddit(a.root)
    if a.stage == "bsky": fetch_bsky(a.root)
    if a.stage == "build": build(a.root, g)
