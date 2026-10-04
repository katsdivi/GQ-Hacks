"""Synthetic fixtures for scripts/final_test_run.py --dry-run. No real data is read.

Builds, under results/dryrun/fixtures/:
  - two fake recorder machines (vultr, mac) with GAPS tables and heartbeat-free roots, 20 candidate games dated
    2026-10-03 (holdout dates, so every seal guard runs with final_test / holdout_run), books from the synthetic
    quote model of tests/test_activity_bias.py (polymarket.com 5 s behind Kalshi), frozen-map stand-ins with a
    condition id per game and a seconds_delay file (1 s, one market missing to exercise the 3 s fallback);
  - Strategy A: 60 fake Kalshi games (both team markets as P(home) trades) with settlements;
  - Strategy B: 40 fake games with Kalshi and polymarket.com trades (polymarket.com moves first);
  - a "training" sample (same generators, 2025 dates) for the capital bases and trial Sharpes;
  - synthetic daily factors (ending 2026-08-31 like the real files, so the out-of-sample regression is
    "not available", as on the real run).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd

import holdout_mid as H
import run_strategy_b as RBB
import strategy_a as A
import strategy_b as B
from tests.test_activity_bias import hidden_path, quotes

NS = 1_000_000_000
SEED = 20261003


def _et(ns):
    return pd.Timestamp(ns, tz="UTC").tz_convert("America/New_York").strftime("%a %b %d %H:%M:%S")


def lead_world(root: Path, rng) -> tuple:
    n_games, ko0 = 20, pd.Timestamp("2026-10-03 14:00", tz="UTC")
    cands, pc, pu, frames = [], {}, {}, {"kalshi": [], "polymarket": [], "polymarket_us": []}
    for i in range(n_games):
        ko = ko0 + pd.Timedelta(minutes=10 * i)
        ev, gid = f"KXNCAAFGAME-26OCT03A{i:02d}H{i:02d}", f"cfb_20261003_a{i:02d}_h{i:02d}"
        lo = ko.value - H.PRE_S * NS
        cands.append({"game_id": gid, "league": "CFB", "kickoff_utc": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "kalshi_ticker": ev, "polymarket_com_mapped": "y", "polymarket_us_mapped": "y",
                      "window_start_utc": ""})
        pc[ev] = {"collector_home_token": f"tok{i}", "condition": f"cond{i}", "game_start": ko.isoformat()}
        pu[f"aec-cfb-a{i}-h{i}"] = {"kalshi_event": ev}
        p = hidden_path(rng)
        for venue, mid, kw in (("kalshi", f"{ev}-H{i:02d}", dict(lag_s=0.0, flicker_per_min=6)),
                               ("polymarket", f"tok{i}", dict(lag_s=5.0, flicker_per_min=2)),
                               ("polymarket_us", f"aec-cfb-a{i}-h{i}", dict(lag_s=5.0, flicker_per_min=1, poll_s=1))):
            q = quotes(rng, p, venue=venue, **kw).assign(market_id=mid)
            q = q[q["price"].between(0.001, 0.999)].copy()
            q["ts"] = q["ts"] + lo
            if "size" not in q or q["size"].isna().all():
                q["size"] = 100.0 if venue == "polymarket" else np.nan
            frames[venue].append(q)
    machines = []
    for name in ("vultr", "mac"):
        mroot = root / name
        for venue, fs in frames.items():
            d = mroot / "data" / "live" / venue / "20261003"
            d.mkdir(parents=True, exist_ok=True)
            for j, f in enumerate(fs):
                f.to_parquet(d / f"{int(f['ts'].min() // NS)}_{j}.parquet", index=False)
        lines = ["| Start (ET) | End (ET) | Venue | Cause | Fixed by |", "|---|---|---|---|---|"]
        a = (ko0 + pd.Timedelta(minutes=40)).value
        lines.append(f"| {_et(a)} | {_et(a + 20 * NS)} | polymarket | short test gap | fixture |")   # < 60 s
        if name == "vultr":
            b = (ko0 + pd.Timedelta(minutes=60 + 30)).value
            lines.append(f"| {_et(b)} | {_et(b + 120 * NS)} | polymarket_us | long test gap | fixture |")
        md = mroot / "GAPS.md"
        md.write_text("\n".join(lines) + "\n")
        machines.append(H.Machine(name, mroot, md, year=2026))
    maps = {"polymarket_com": pc, "polymarket_us": pu}
    mf = {}
    for k, v in (("polymarket_com_map.json", pc), ("polymarket_us_map.json", pu)):
        mf[k] = root / k
        mf[k].write_text(pd.Series(v).to_json())
    delays = root / "holdout_seconds_delay.csv"
    pd.DataFrame({"market_id": [f"cond{i}" for i in range(n_games - 1)], "seconds_delay": 1,
                  "fetched_at_utc": "fixture"}).to_csv(delays, index=False)        # cond19 missing -> 3 s, counted
    return machines, pd.DataFrame(cands), maps, delays, mf


def a_games(root: Path, rng, n: int, start: str, prefix: str, flip_away: bool = False
            ) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    d = root / f"{prefix}_a_ticks"
    d.mkdir(parents=True, exist_ok=True)
    games, meta = [], []
    for i in range(n):
        ko = pd.Timestamp(start, tz="UTC") + pd.Timedelta(days=i // 10, hours=i % 10)
        ev, home, away = f"KXNCAAFGAME-X{prefix}{i:03d}", f"H{i}", f"A{i}"
        gid = f"cfb_{ko:%Y%m%d}_{away.lower()}_{home.lower()}"
        p0 = float(rng.uniform(0.15, 0.95))
        ts = np.arange((ko - pd.Timedelta(hours=2)).value, (ko + pd.Timedelta(hours=5)).value, 15 * NS)
        rows = []
        for mk in (home, away):
            px = np.clip(np.round(p0 + rng.normal(0, 0.01, len(ts)), 2), 0.01, 0.99)
            if flip_away and mk == away:
                px = np.round(1 - px, 2)          # away rows NOT flipped to P(home): the gate must FAIL
            rows.append(pd.DataFrame({"ts": ts + rng.integers(0, 10 * NS, len(ts)), "venue": "kalshi",
                                      "market_id": f"{ev}-{mk}", "kind": "trade", "price": px, "size": 1.0,
                                      "side": "buy"}))
        pd.concat(rows).sort_values("ts").to_parquet(d / f"{gid}.parquet", index=False)
        res = float(rng.random() < p0)
        games.append({"game_id": gid, "league": "NFL" if i % 4 == 0 else "CFB", "home": home, "away": away,
                      "kalshi_event": ev, "kalshi_ticker": f"{ev}-{home}", "kickoff_utc_espn": ko.isoformat(),
                      "kickoff_source": "espn", "settlement_result": res})
        for side, mk, r in (("home", home, res), ("away", away, 1 - res)):
            meta.append({"game_id": gid, "side": side, "ticker": f"{ev}-{mk}", "status": "finalized",
                         "result": "yes" if r == 1 else "no", "settlement_value_dollars": r,
                         "price_ranges": '[{"end": "1.0000", "start": "0.0000", "step": "0.0100"}]'})
    return pd.DataFrame(games), pd.DataFrame(meta), d


def b_games(root: Path, rng, n: int, start: str, prefix: str) -> tuple[pd.DataFrame, Path, Path]:
    dk, dp = root / f"{prefix}_b_kalshi", root / f"{prefix}_b_pm"
    dk.mkdir(parents=True, exist_ok=True)
    dp.mkdir(parents=True, exist_ok=True)
    out = []
    for i in range(n):
        ko = pd.Timestamp(start, tz="UTC") + pd.Timedelta(days=i // 8, hours=i % 8)
        gid = f"cfb_{ko:%Y%m%d}_b{prefix}{i}_h{i}"
        secs = np.arange(-2 * 3600, 5 * 3600)
        walk = np.clip(0.5 + np.cumsum(rng.choice([0, 0, 0, 0.01, -0.01], len(secs))) * 0.5, 0.05, 0.95)
        base = ko.value
        for venue, lag, every, d in (("polymarket", 0, 7, dp), ("kalshi", 20, 3, dk)):
            idx = np.arange(0, len(secs), every)
            src = np.clip(idx - lag, 0, len(secs) - 1)
            pd.DataFrame({"ts": base + secs[idx] * NS + 300_000_000, "venue": venue, "market_id": f"{venue}{i}",
                          "kind": "trade", "price": np.round(walk[src], 2), "size": 1.0, "side": "buy"}
                         ).to_parquet(d / f"{gid}.parquet", index=False)
        out.append({"game_id": gid, "espn_kickoff": ko.isoformat()})
    return pd.DataFrame(out), dk, dp


def training(root: Path, rng):
    g, m, d = a_games(root, rng, 40, "2025-10-04", "train")
    gp, mp = root / "train_a_games.csv", root / "train_a_meta.csv"
    g.to_csv(gp, index=False)
    m.to_csv(mp, index=False)
    rows = []
    for gm in A.load_games(gp, mp, ticks_dir=d, expect_preseason=None):
        tr = pd.read_parquet(d / f"{gm.game_id}.parquet")
        for r in A.evaluate_game(tr, gm):
            r.update(kickoff=gm.kickoff)
            rows.append(r)
    rows = pd.DataFrame(rows).drop(columns=["_tr"], errors="ignore")
    bg, dk, dp = b_games(root, rng, 24, "2025-10-04", "train")
    bt, b2 = [], []
    for r in bg.itertuples():
        kt, pt = pd.read_parquet(dk / f"{r.game_id}.parquet"), pd.read_parquet(dp / f"{r.game_id}.parquet")
        bt.append(B.evaluate_game(r.game_id, r.espn_kickoff, kt, pt)[0])
        b2.append(B.evaluate_game(r.game_id, r.espn_kickoff, kt, pt, settings=[(0.05, 10, 300)], half_spread=0.01,
                                  fee_mult=2.0)[0])
    bt = pd.concat([x for x in bt if len(x)], ignore_index=True)
    b2 = pd.concat([x for x in b2 if len(x)], ignore_index=True)
    sel = B.select_setting(RBB.summarize(bt, len(bg))) or (0.05, 10, 300)
    kos = pd.concat([pd.to_datetime(g["kickoff_utc_espn"], utc=True), pd.to_datetime(bg["espn_kickoff"], utc=True)],
                    ignore_index=True)
    return rows, bt, b2, sel, kos


def factors() -> pd.DataFrame:
    days = pd.bdate_range("2025-07-01", "2026-08-31")
    r = np.random.default_rng(SEED)
    return pd.DataFrame({"date": days, "mkt_rf": r.normal(0, 0.01, len(days)), "smb": r.normal(0, 0.005, len(days)),
                         "hml": r.normal(0, 0.005, len(days)), "rf": 0.0002, "umd": r.normal(0, 0.007, len(days))})


def dry_ctx(out: Path, flip_away: bool = False):
    from scripts.final_test_run import Ctx
    if out.exists():
        shutil.rmtree(out)
    fx = out / "fixtures"
    fx.mkdir(parents=True)
    rng = np.random.default_rng(SEED)
    machines, cands, maps, delays, mf = lead_world(fx / "lead", rng)
    ag, am, ad = a_games(fx, rng, 60, "2026-09-05", "oos", flip_away)
    bg, bk, bp = b_games(fx, rng, 40, "2026-09-05", "oos")
    return Ctx(out, machines, cands, maps, delays, ag, am, ad, bg, bk, bp, training(fx, rng), factors(), True, mf)
