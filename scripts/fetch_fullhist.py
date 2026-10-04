"""Full-history trades for TRAINING games (kickoff < 2026-08-01): Kalshi and polymarket.com, market listing
to close, in the shared tick contract (ts ns UTC, venue, market_id, kind, price as P(home), size, side).

Data only, no strategy. Free public endpoints only.

Kalshi (1,267 games, data/raw/kalshi_only_games.csv):
  The existing files data/raw/kalshi_only/<game_id>.parquet already hold [kickoff - 2 h, kickoff + 5 h].
  This script fetches only the two missing pieces per team market, [open_time, kickoff - 2 h) and
  (kickoff + 5 h, close_time], and writes pre + existing middle + post to
  data/raw/fullhist/kalshi/<game_id>.parquet. The existing files are never modified.
  open_time/close_time come from data/raw/kalshi_kx{nfl,ncaaf}game_historical.parquet, else
  GET /historical/markets/{ticker} or /markets/{ticker}.
  Reused (read-only): ingest.kalshi.fetch_trades and trades_to_rows, with ingest.kalshi_only_train's
  throttled, backoff-aware _kget patched in at import (its own line 85), rate set to 2 req/s.
  --validate N: for N random games, also refetch the middle window and compare it with the existing file.

polymarket.com (977 games, data/raw/t8_game_plan.csv: pm_condition, pm_flipped, game_id):
  Full taker-trade history of the moneyline condition from the data API, paged BACKWARDS with the
  `end` parameter (the offset parameter is capped at 10,000), deduplicated as in ingest/download_all.py.
  Orientation exactly as ingest/download_all.py line 327: home_index = 0 if pm_flipped else 1; non-home
  outcome prices are flipped with 1 - p and buy/sell swapped. Written to
  data/raw/fullhist/polymarket/<game_id>.parquet.

Rate limits: 2 req/s per host. Resumable: existing output files are skipped. Training only: every game is
asserted to have kickoff < 2026-08-01.

Usage (cwd = staleline repo root, .venv-run):
  python <wt>/scripts/fetch_fullhist.py kalshi [--limit N] [--validate N]
  python <wt>/scripts/fetch_fullhist.py polymarket [--limit N]
  python <wt>/scripts/fetch_fullhist.py report
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from ingest import kalshi as K  # noqa: E402
from ingest import kalshi_only_train as T  # noqa: E402  (patches K._get with the throttled _kget)

RAW = ROOT / "data" / "raw"
OUT = RAW / "fullhist"
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
PRE, POST = pd.Timedelta(hours=2), pd.Timedelta(hours=5)
PMDATA = "https://data-api.polymarket.com/trades"
COLS = ["ts", "venue", "market_id", "kind", "price", "size", "side"]
NS = 1_000_000_000
T.K_RATE[0] = float(__import__("os").environ.get("KRATE", "2.0"))  # per process
_pm_next = [0.0]
_s = requests.Session()


def log(msg: str) -> None:
    print(f"{pd.Timestamp.now(tz='America/New_York'):%H:%M:%S} ET {msg}", flush=True)


def utc(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def empty() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in
                         zip(COLS, ["int64", "string", "string", "string", "float64", "float64", "string"])})


# ---------- Kalshi ----------

def market_times() -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    out = {}
    for f in ("kalshi_kxnflgame_historical.parquet", "kalshi_kxncaafgame_historical.parquet"):
        d = pd.read_parquet(RAW / f, columns=["ticker", "open_time", "close_time"])
        for r in d.itertuples():
            if r.open_time and r.close_time:
                out[r.ticker] = (utc(r.open_time), utc(r.close_time))
    return out


def market_time_api(ticker: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    for path in (f"/historical/markets/{ticker}", f"/markets/{ticker}"):
        try:
            d = K._get(path)
        except Exception:
            continue
        m = (d or {}).get("market")
        if m and m.get("open_time") and m.get("close_time"):
            return utc(m["open_time"]), utc(m["close_time"])
    return None


def kalshi_one(r, times: dict, validate: bool) -> dict:
    ko = utc(r.kickoff_utc_espn)
    assert ko < SEAL, f"sealed game {r.game_id}"
    mid_path = RAW / "kalshi_only" / f"{r.game_id}.parquet"
    mid = pd.read_parquet(mid_path) if mid_path.exists() else empty()
    pieces, info = [], {"game_id": r.game_id, "kickoff": ko}
    lo_all, hi_all = None, None
    home_tk = r.kalshi_ticker
    others = [m for m in mid["market_id"].dropna().unique() if m != home_tk] if len(mid) else []
    # Away ticker from the existing file when present: team codes such as OH can be M-OH in the ticker.
    away_tk = others[0] if len(others) == 1 else f"{r.kalshi_event}-{r.away}"
    for tk, away in ((home_tk, False), (away_tk, True)):
        ot = times.get(tk) or market_time_api(tk)
        if ot is None:
            info[f"{'away' if away else 'home'}_err"] = "no open/close time"
            continue
        o, c = ot
        lo_all = o if lo_all is None else min(lo_all, o)
        hi_all = c if hi_all is None else max(hi_all, c)
        if o < ko - PRE:
            p = K.fetch_trades(tk, o, ko - PRE, away=away)
            pieces.append(p[p["ts"] < (ko - PRE).value])
        if c > ko + POST:
            p = K.fetch_trades(tk, ko + POST, c, away=away)
            pieces.append(p[p["ts"] > (ko + POST).value])
        if validate:
            v = K.fetch_trades(tk, ko - PRE, ko + POST, away=away)
            e = mid[mid["market_id"] == tk]
            key = ["ts", "market_id", "price", "size"]
            m = v.merge(e, on=key, how="outer", indicator=True)
            side = "away" if away else "home"
            info.update({f"val_{side}_new": len(v), f"val_{side}_old": len(e),
                         f"val_{side}_only_new": int((m["_merge"] == "left_only").sum()),
                         f"val_{side}_only_old": int((m["_merge"] == "right_only").sum())})
    full = pd.concat(pieces + [mid], ignore_index=True)
    full = full.drop_duplicates(["ts", "market_id", "price", "size", "side"]).sort_values("ts", kind="stable")
    full = full.reset_index(drop=True)
    info.update({"open": lo_all, "close": hi_all, "n_mid": len(mid), "n_full": len(full),
                 "n_pre": int((full["ts"] < (ko - PRE).value).sum()) if len(full) else 0,
                 "n_post": int((full["ts"] > (ko + POST).value).sum()) if len(full) else 0,
                 "first_trade": pd.Timestamp(int(full["ts"].min()), tz="UTC") if len(full) else None})
    return info, full


def run_kalshi(limit: int | None, n_validate: int) -> None:
    out = OUT / "kalshi"
    out.mkdir(parents=True, exist_ok=True)
    g = pd.read_csv(RAW / "kalshi_only_games.csv")
    assert (pd.to_datetime(g["kickoff_utc_espn"], utc=True) < SEAL).all()
    rng = np.random.default_rng(20261004)
    val_ids = set(rng.choice(g["game_id"].to_numpy(), size=min(n_validate, len(g)), replace=False)) if n_validate else set()
    times = market_times()
    manifest = OUT / "kalshi_manifest.csv"
    todo = g if limit is None else g.head(limit)
    log(f"kalshi: {len(todo)} games, {len(val_ids)} validation games, open/close known for {len(times)} tickers")
    for i, r in enumerate(todo.itertuples(), 1):
        f = out / f"{r.game_id}.parquet"
        if f.exists():
            continue
        try:
            info, full = kalshi_one(r, times, r.game_id in val_ids)
        except Exception as e:  # keep going; failures are listed in the manifest
            info, full = {"game_id": r.game_id, "error": f"{type(e).__name__}: {str(e)[:160]}"}, None
        if full is not None:
            full.to_parquet(f, index=False)
        pd.DataFrame([info]).to_csv(manifest, mode="a", header=not manifest.exists(), index=False)
        if i % 25 == 0:
            log(f"kalshi {i}/{len(todo)} ({r.game_id})")
    log("kalshi done")


# ---------- polymarket.com ----------

def pm_get(params: dict):
    for attempt in range(8):
        w = _pm_next[0] - time.monotonic()
        if w > 0:
            time.sleep(w)
        _pm_next[0] = max(_pm_next[0], time.monotonic()) + 0.5
        try:
            r = _s.get(PMDATA, params=params, timeout=60)
        except requests.RequestException:
            time.sleep(min(2 ** attempt, 60))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(2 ** attempt, 60))
            continue
        if r.status_code == 400:
            return None
        r.raise_for_status()
        return r.json()
    raise RuntimeError("polymarket.com data API: giving up")


def pm_full(condition: str, taker_only: bool = True) -> tuple[list[dict], dict]:
    """All taker trades, paged backwards by `end` (inclusive seconds). Stops on an empty or short page."""
    raw, seen, end, pages, stuck = [], set(), None, 0, 0
    while True:
        p = {"market": condition, "limit": 10_000, "takerOnly": "true" if taker_only else "false"}
        if end is not None:
            p["end"] = end
        b = pm_get(p)
        pages += 1
        if not isinstance(b, list) or not b:
            break
        new = 0
        for x in b:
            k = (x.get("transactionHash"), x.get("asset"), x.get("size"), x.get("price"), x.get("side"),
                 x.get("outcomeIndex"), x.get("timestamp"))
            if k not in seen:
                seen.add(k)
                raw.append(x)
                new += 1
        mn = min(int(x["timestamp"]) for x in b)
        if len(b) < 10_000:
            break
        if new == 0:            # a full page of already-seen rows inside one second: step past it
            stuck += 1
            end = mn - 1
        else:
            end = mn
        if pages > 500:
            break
    return raw, {"pages": pages, "stuck_steps": stuck}


def pm_rows(raw: list[dict], condition: str, home_index: int) -> pd.DataFrame:
    if not raw:
        return empty()
    t = pd.DataFrame(raw)
    is_home = t["outcomeIndex"].astype(int) == home_index
    price = t["price"].astype(float).where(is_home, 1.0 - t["price"].astype(float))
    side = t["side"].str.lower().map({"buy": "buy", "sell": "sell"}).fillna("unknown")
    side = side.where(is_home, side.map({"buy": "sell", "sell": "buy", "unknown": "unknown"}))
    df = pd.DataFrame({"ts": t["timestamp"].astype("int64").to_numpy() * NS, "venue": "polymarket",
                       "market_id": condition, "kind": "trade", "price": price.round(4).to_numpy(),
                       "size": t["size"].astype(float).to_numpy(), "side": side.to_numpy()})
    return df.sort_values("ts", kind="stable").reset_index(drop=True)


def run_pm(limit: int | None) -> None:
    out = OUT / "polymarket"
    out.mkdir(parents=True, exist_ok=True)
    plan = pd.read_csv(RAW / "t8_game_plan.csv")
    plan = plan[plan["pm_condition"].notna()]
    assert (pd.to_datetime(plan["kickoff_utc"], utc=True) < SEAL).all()
    manifest = OUT / "polymarket_manifest.csv"
    todo = plan if limit is None else plan.head(limit)
    log(f"polymarket: {len(todo)} games")
    for i, r in enumerate(todo.itertuples(), 1):
        f = out / f"{r.game_id}.parquet"
        if f.exists():
            continue
        try:
            raw, meta = pm_full(r.pm_condition)
            df = pm_rows(raw, r.pm_condition, 0 if bool(r.pm_flipped) else 1)
            df.to_parquet(f, index=False)
            # Sidecar (not the tick contract): every fill record incl. maker fills, with the wallet fields.
            fraw, fmeta = pm_full(r.pm_condition, taker_only=False)
            side_cols = ["timestamp", "transactionHash", "proxyWallet", "side", "asset", "outcomeIndex", "price", "size"]
            fills = pd.DataFrame(fraw)
            if len(fills):
                fills = fills[[c for c in side_cols if c in fills.columns]].copy()
                tk = {(x.get("transactionHash"), x.get("proxyWallet"), x.get("size"), x.get("price")) for x in raw}
                fills["in_taker_feed"] = [(a, b, c, d) in tk for a, b, c, d in
                                          zip(fills["transactionHash"], fills["proxyWallet"], fills["size"], fills["price"])]
                fills["ts"] = fills["timestamp"].astype("int64") * NS
                fills["home_index"] = 0 if bool(r.pm_flipped) else 1
            (OUT / "polymarket_fills").mkdir(parents=True, exist_ok=True)
            fills.to_parquet(OUT / "polymarket_fills" / f"{r.game_id}.parquet", index=False)
            meta["fills_rows"], meta["fills_pages"] = len(fills), fmeta["pages"]
            ko = utc(r.kickoff_utc)
            info = {"game_id": r.game_id, "kickoff": ko, "n_full": len(df), **meta,
                    "first_trade": pd.Timestamp(int(df["ts"].min()), tz="UTC") if len(df) else None,
                    "last_trade": pd.Timestamp(int(df["ts"].max()), tz="UTC") if len(df) else None,
                    "n_pre": int((df["ts"] < (ko - PRE).value).sum()), "n_post": int((df["ts"] > (ko + POST).value).sum())}
        except Exception as e:
            info = {"game_id": r.game_id, "error": f"{type(e).__name__}: {str(e)[:160]}"}
        pd.DataFrame([info]).to_csv(manifest, mode="a", header=not manifest.exists(), index=False)
        if i % 25 == 0:
            log(f"polymarket {i}/{len(todo)} ({r.game_id})")
    log("polymarket done")


# ---------- Kalshi candlesticks (sidecar; not the tick contract) ----------
# GET /historical/markets/{ticker}/candlesticks, public, no auth. Max 5,000 candles per request.
# 1-min candles over [kickoff - 24 h, min(close, kickoff + 8 h)] and 60-min candles over [open, close].
# Each candle carries yes_bid and yes_ask OHLC (top of book at minute resolution), trade price OHLC,
# volume and open interest. Prices are the market's own YES price (NOT flipped to P(home)); the
# columns team and is_home say which team the market pays on.

def candles(ticker: str, a: pd.Timestamp, b: pd.Timestamp, period: int) -> list[dict]:
    out, step = [], 4_900 * 60 * period
    lo = int(a.timestamp())
    hi = int(b.timestamp())
    while lo < hi:
        up = min(hi, lo + step)
        d = None
        for path in (f"/historical/markets/{ticker}/candlesticks",):
            try:
                d = K._get(path, {"start_ts": lo, "end_ts": up, "period_interval": period})
            except Exception:
                d = None
        out += (d or {}).get("candlesticks", []) or []
        lo = up
    return out


def flat(cs: list[dict], ticker: str, team: str, is_home: bool, period: int) -> pd.DataFrame:
    rows = []
    for c in cs:
        r = {"end_ts": int(c["end_period_ts"]) * NS, "ticker": ticker, "team": team, "is_home": is_home,
             "period_min": period, "volume": c.get("volume"), "open_interest": c.get("open_interest")}
        for blk in ("price", "yes_bid", "yes_ask"):
            for k in ("open", "high", "low", "close"):
                r[f"{blk}_{k}"] = (c.get(blk) or {}).get(k)
        rows.append(r)
    df = pd.DataFrame(rows)
    for col in df.columns:
        if col.startswith(("price_", "yes_", "volume", "open_interest")):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def run_candles(limit: int | None) -> None:
    out = OUT / "kalshi_candles"
    out.mkdir(parents=True, exist_ok=True)
    g = pd.read_csv(RAW / "kalshi_only_games.csv")
    assert (pd.to_datetime(g["kickoff_utc_espn"], utc=True) < SEAL).all()
    times = market_times()
    manifest = OUT / "kalshi_candles_manifest.csv"
    todo = g if limit is None else g.head(limit)
    log(f"candles: {len(todo)} games")
    for i, r in enumerate(todo.itertuples(), 1):
        f = out / f"{r.game_id}.parquet"
        if f.exists():
            continue
        ko = utc(r.kickoff_utc_espn)
        parts, info = [], {"game_id": r.game_id}
        try:
            midf = RAW / "kalshi_only" / f"{r.game_id}.parquet"
            mids = pd.read_parquet(midf, columns=["market_id"])["market_id"].dropna().unique() if midf.exists() else []
            others = [m for m in mids if m != r.kalshi_ticker]
            away_tk = others[0] if len(others) == 1 else f"{r.kalshi_event}-{r.away}"
            for tk, team, is_home in ((r.kalshi_ticker, r.home, True), (away_tk, r.away, False)):
                ot = times.get(tk) or market_time_api(tk)
                if ot is None:
                    continue
                o, c = ot
                parts.append(flat(candles(tk, max(o, ko - pd.Timedelta(hours=24)), min(c, ko + pd.Timedelta(hours=8)), 1),
                                  tk, team, is_home, 1))
                parts.append(flat(candles(tk, o, c, 60), tk, team, is_home, 60))
            df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
            df.to_parquet(f, index=False)
            info.update({"rows_1m": int((df["period_min"] == 1).sum()) if len(df) else 0,
                         "rows_60m": int((df["period_min"] == 60).sum()) if len(df) else 0,
                         "bid_ask_1m_nonnull": int(df.loc[df["period_min"] == 1, "yes_bid_close"].notna().sum()) if len(df) else 0})
        except Exception as e:
            info["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        pd.DataFrame([info]).to_csv(manifest, mode="a", header=not manifest.exists(), index=False)
        if i % 25 == 0:
            log(f"candles {i}/{len(todo)} ({r.game_id})")
    log("candles done")


# ---------- report ----------

VAL_COLS = ["game_id", "kickoff", "val_home_new", "val_home_old", "val_home_only_new", "val_home_only_old",
            "val_away_new", "val_away_old", "val_away_only_new", "val_away_only_old", "open", "close", "n_mid",
            "n_full", "n_pre", "n_post", "first_trade"]


def read_manifest(mf: Path) -> pd.DataFrame:
    """Manifests are appended row by row and validation/error rows carry different columns (the header is
    the first row's), so rows are mapped by field count."""
    import csv
    with open(mf) as fh:
        rows = list(csv.reader(fh))
    head, out = rows[0], []
    for r in rows[1:]:
        if len(r) == len(head):
            out.append(dict(zip(head, r)))
        elif len(r) == len(VAL_COLS):
            out.append(dict(zip(VAL_COLS, r)))
        elif len(r) == len(head) + 1 and head[:2] == ["game_id", "kickoff"]:
            out.append({"game_id": r[0], "error": f"partial: {r[2]}"})
        elif len(r) == 2:
            out.append({"game_id": r[0], "error": r[1]})
        else:
            out.append({"game_id": r[0], "error": f"unparsed manifest row ({len(r)} fields)"})
    m = pd.DataFrame(out).replace("", np.nan)
    for c in m.columns:
        if c.startswith(("n_", "val_", "pages", "stuck", "fills_", "rows_", "bid_")):
            m[c] = pd.to_numeric(m[c], errors="coerce")
    if "error" not in m:
        m["error"] = np.nan
    return m


def report() -> None:
    res = {}
    for venue in ("kalshi", "polymarket"):
        mf = OUT / f"{venue}_manifest.csv"
        if not mf.exists():
            continue
        m = read_manifest(mf).drop_duplicates("game_id", keep="last")
        ok = m[m["error"].isna()]
        ko = pd.to_datetime(ok["kickoff"], utc=True)
        ft = pd.to_datetime(ok["first_trade"], utc=True)
        pre_h = ((ko - ft).dt.total_seconds() / 3600).dropna()
        r = {"games": int(len(m)), "ok": int(len(ok)), "errors": int(len(m) - len(ok)),
             "pre_hours_median": float(pre_h.median()), "pre_hours_p10": float(pre_h.quantile(0.10)),
             "pre_hours_p90": float(pre_h.quantile(0.90)),
             "trades_per_game_median": float(ok["n_full"].median()),
             "pre_trades_median": float(ok["n_pre"].median()), "post_trades_median": float(ok["n_post"].median())}
        if venue == "kalshi":
            r["mid_trades_median"] = float(ok["n_mid"].median())
            vcols = [c for c in ok.columns if c.startswith("val_")]
            if vcols:
                v = ok.dropna(subset=["val_home_new"]).fillna({c: 0 for c in vcols})
                r["validation_games"] = int(len(v))
                for s in ("home", "away"):
                    r[f"val_{s}_new_total"] = int(v[f"val_{s}_new"].sum())
                    r[f"val_{s}_old_total"] = int(v[f"val_{s}_old"].sum())
                    r[f"val_{s}_only_new_total"] = int(v[f"val_{s}_only_new"].sum())
                    r[f"val_{s}_only_old_total"] = int(v[f"val_{s}_only_old"].sum())
                r["validation_games_exact"] = int(((v["val_home_new"] == v["val_home_old"]) & (v["val_away_new"] == v["val_away_old"])
                                                   & (v["val_home_only_new"] + v["val_home_only_old"] + v["val_away_only_new"] + v["val_away_only_old"] == 0)).sum())
        else:
            r["stuck_steps_total"] = int(ok["stuck_steps"].sum())
            r["pages_max"] = int(ok["pages"].max())
            r["fills_rows_median"] = float(ok["fills_rows"].median())
            r["last_trade_after_kickoff_h_median"] = float(((pd.to_datetime(ok["last_trade"], utc=True) - ko).dt.total_seconds() / 3600).median())
        res[venue] = r
    cf = OUT / "kalshi_candles_manifest.csv"
    if cf.exists():
        c = read_manifest(cf).drop_duplicates("game_id", keep="last")
        okc = c[c["error"].isna()]
        res["kalshi_candles"] = {"games": int(len(c)), "ok": int(len(okc)), "errors": int(len(c) - len(okc)),
                                 "rows_1m_median": float(okc["rows_1m"].median()),
                                 "rows_60m_median": float(okc["rows_60m"].median()),
                                 "games_with_bid_ask_1m": int((okc["bid_ask_1m_nonnull"] > 0).sum())}
    print(json.dumps(res, indent=1, default=str))
    (OUT / "coverage.json").write_text(json.dumps(res, indent=1, default=str))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["kalshi", "polymarket", "candles", "report"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--validate", type=int, default=0)
    a = ap.parse_args()
    if a.what == "kalshi":
        run_kalshi(a.limit, a.validate)
    elif a.what == "polymarket":
        run_pm(a.limit)
    elif a.what == "candles":
        run_candles(a.limit)
    else:
        report()


if __name__ == "__main__":
    main()
