"""The ONE holdout run (HYPOTHESIS_v2 + Amendments 1 to 4; HYPOTHESIS_v3 + Amendments 1 to 3), one command.

  python scripts/final_test_run.py --i-am-the-one-run    the real run; refuses if results/holdout/ exists
  python scripts/final_test_run.py --dry-run             the same pipeline on synthetic fixtures -> results/dryrun/

Order: pre-run checklist; v2 lead test on both venues with Holm (holdout_mid.run_all, Amendment 4 cutoff);
trade-the-laggard on the qualifying games (laggard.py: per-market delay, breaks = kickoff cut + every gap of either
venue, latency curve, capacity); Strategy A at theta 0.80 (final_test=True); Strategy B at the selected setting
k = 5c, m = 10 s, T = 300 s (final_test=True) with its placebo and costs x2; the combined book and report_book on
the test (capital bases and trial Sharpes from training, v3 Amendment 1). Writes everything to results/holdout/
(results/dryrun/ for --dry-run), OOS keys to results/numbers.json (results/dryrun/numbers.json), and the git hash
and start/end ET times to RUN_LOG.md there. No prices are printed; the console shows counts, decisions and paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

# The run's numbers were validated under these versions (requirements.txt, .venv-run). pandas 3 changes the default
# datetime unit; any mismatch aborts before anything is read.
PINNED = {"pandas": "2.3.2", "numpy": "1.26.4"}
_have = {"pandas": pd.__version__, "numpy": np.__version__}
if _have != PINNED:
    raise SystemExit(f"version mismatch: running {_have}, pinned {PINNED}; use .venv-run (requirements.txt)")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import holdout_mid as H  # noqa: E402
import laggard as L  # noqa: E402
import report_book as RB  # noqa: E402
import run_strategy_a as RA  # noqa: E402
import run_strategy_b as RBB  # noqa: E402
import strategy_a as A  # noqa: E402
import strategy_b as B  # noqa: E402

NS = 1_000_000_000
ET = "America/New_York"
SEL_B = (0.05, 10, 300)
EXPECT = {"seconds_delay": "24a5d41af0ba7f34", "polymarket_com_map.json": "202f819d1bd885dd",
          "polymarket_us_map.json": "4225d018acb3024e", "amendment4_games": 106}
FEEDS = ("kalshi", "polymarket", "polymarket_us")
REQUIRED = ["RUN_LOG.md", "checklist.json", "lead_decisions.json", "lead_polymarket.com_per_game.csv",
            "lead_polymarket.com_placebo.csv", "lead_Polymarket US_per_game.csv", "lead_Polymarket US_placebo.csv",
            "receipt_diagnostic.csv", "laggard_trades.csv", "laggard_latency_curve.csv", "laggard_capacity.csv",
            "strategy_a_rows.parquet", "strategy_a_summary.csv", "strategy_a_checks.csv",
            "strategy_b_trades.parquet", "strategy_b_summary.csv", "strategy_b_placebo_summary.csv",
            "strategy_b_costs_x2.csv", "equity_oos.png", "numbers.json"]
REQUIRED_KEYS = ["OOS.lead.polymarket.com.decision", "OOS.lead.Polymarket US.decision", "OOS.lead.n_candidates",
                 "OOS.laggard.n_trades", "OOS.A.n_games", "OOS.A.roc_webull", "OOS.A.roc_webull_ci",
                 "OOS.B.n_trades", "OOS.B.edge_webull_cents", "OOS.B.edge_webull_ci", "OOS.season_first_day",
                 "OOS.season_last_day", "OOS.A.sharpe", "OOS.combined.pnl_total", "OOS.corr_A_B.days_either_traded"]


def sha16(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def git_info() -> dict:
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True,
                                text=True, cwd=ROOT).stdout.strip())
    return {"git_sha": sha, "dirty": dirty}


def now_et() -> str:
    return pd.Timestamp.now(tz=ET).strftime("%Y-%m-%d %H:%M:%S ET")


class Ctx:
    """Paths for one run (real or dry)."""

    def __init__(self, out: Path, machines: list, cands: pd.DataFrame, maps: dict, delays_csv: Path,
                 a_games: pd.DataFrame, a_meta: pd.DataFrame, a_ticks: Path, b_games: pd.DataFrame, b_kalshi: Path,
                 b_pm: Path, training: tuple, fac: pd.DataFrame, dry: bool, map_files: dict):
        self.__dict__.update(locals())
        del self.__dict__["self"]


# ---------- checklist ----------

def checklist(c: Ctx) -> dict:
    out = {"feeds": {}, "checks": {}}
    for m in c.machines:
        out["feeds"][m.name] = {v: len(m.files(v)) for v in FEEDS}
    h = sha16(c.delays_csv)
    out["checks"]["holdout_seconds_delay.csv sha256"] = {"value": h, "expected": EXPECT["seconds_delay"],
                                                          "ok": c.dry or h == EXPECT["seconds_delay"]}
    for name, p in c.map_files.items():
        h = sha16(p)
        out["checks"][f"{name} sha256"] = {"value": h, "expected": EXPECT[name], "ok": c.dry or h == EXPECT[name]}
    kept = H.amendment4(c.cands)
    out["checks"]["Amendment 4 games kept"] = {"value": len(kept), "expected": EXPECT["amendment4_games"],
                                              "ok": c.dry or len(kept) == EXPECT["amendment4_games"]}
    out["checks"]["Vultr copy present"] = {"value": out["feeds"].get("vultr", {}),
                                           "ok": all(n > 0 for n in out["feeds"].get("vultr", {"x": 0}).values())}
    for m in c.machines:
        g = m.gaps()
        out["checks"][f"{m.name} gaps parsed"] = {"value": int(len(g)), "ok": True}
    if not c.dry:
        out["checks"].update(manifest_checks(c.machines))
        out["checks"].update(holdout_files_complete(ROOT / "data" / "holdout_raw"))
    return out


AB_CUTOFF = pd.Timestamp("2026-10-03 20:00", tz="America/New_York")   # v3 Amendment 4 (= v2 Amendment 4 cutoff)
WINDOW_END = pd.Timedelta(hours=5)       # download window end, kickoff + 5 h (B's kickoff + 4.5 h is inside it)


def holdout_files_complete(hr: Path) -> dict:
    """v3 Amendment 4: every A and B holdout file of a kept game must have been written at or after its game's
    window end (file modification time >= ESPN kickoff + 5 h). Reads file times and ids only, never the files."""
    out = {}
    ev = pd.read_csv(hr / "events.csv") if (hr / "events.csv").exists() else pd.DataFrame(columns=["game_id", "espn_kickoff"])
    ko = pd.to_datetime(ev["espn_kickoff"], utc=True)
    kept = ev[ko.notna() & (ko <= AB_CUTOFF)].assign(ko=ko)
    pm = pd.read_csv(hr / "pm_map.csv") if (hr / "pm_map.csv").exists() else pd.DataFrame(columns=["game_id"])
    for venue, ids in (("kalshi", kept["game_id"]), ("polymarket", kept[kept["game_id"].isin(pm["game_id"])]["game_id"])):
        k = kept.set_index("game_id")["ko"]
        missing, early = [], []
        for g in ids:
            f = hr / venue / f"{g}.parquet"
            if not f.exists():
                missing.append(g)
            elif pd.Timestamp(f.stat().st_mtime, unit="s", tz="UTC") < k[g] + WINDOW_END:
                early.append(g)
        out[f"holdout {venue} files written after window end"] = {
            "value": f"{len(ids)} kept games; missing {len(missing)}; written before window end {len(early)}"
                     + (f" ({early[:5]}{'...' if len(early) > 5 else ''})" if early else ""),
            "ok": len(ids) > 0 and not missing and not early}
    return out


MANIFEST = ROOT / "results" / "holdout_inputs_manifest.txt"


def manifest_checks(machines, manifest: Path = MANIFEST, root: Path = ROOT) -> dict:
    """Every GAPS table and heartbeat log the runner's Machine objects read must be listed in the manifest with the
    same sha256, the manifest must list nothing in those places that is missing, and no machine may read the
    tracked GAPS.md."""
    out = {}
    if not manifest.exists():
        return {"inputs manifest present": {"value": str(manifest), "ok": False}}
    man = {}
    for line in manifest.read_text().splitlines():
        if line.strip():
            h, path = line.split(maxsplit=1)
            man[(root / path.strip()).resolve()] = h
    for m in machines:
        read = [Path(m.gaps_md).resolve()] + sorted(Path(x).resolve() for x in (m.heartbeat_dir or Path("/nonexistent")).glob("*.jsonl"))
        bad = [str(p.relative_to(root.resolve())) for p in read
               if p not in man or hashlib.sha256(p.read_bytes()).hexdigest() != man[p]]
        hb = (m.heartbeat_dir or Path("/nonexistent")).resolve()
        listed = [p for p in man if p.parent == hb]
        missing = [str(p.relative_to(root.resolve())) for p in listed if not p.exists()]
        out[f"{m.name} frozen inputs match manifest"] = {
            "value": f"{len(read)} files read ({len(read) - 1} heartbeat logs); mismatched {bad}; listed but missing {missing}",
            "ok": not bad and not missing and len(read) > 1}
        out[f"{m.name} does not read tracked GAPS.md"] = {"value": str(Path(m.gaps_md).resolve().relative_to(root.resolve())),
                                                       "ok": Path(m.gaps_md).resolve() != (root / "GAPS.md").resolve()}
    return out


# ---------- lead test and laggard ----------

def lead(c: Ctx, num: dict) -> dict:
    res = H.run_all(c.cands, c.maps, c.machines, holdout_run=True)
    for t in H.TESTS:
        res[t]["per_game"].to_csv(c.out / f"lead_{t}_per_game.csv", index=False)
        res[t]["placebo"].to_csv(c.out / f"lead_{t}_placebo.csv", index=False)
        d = res[t]["decision"]
        num[f"OOS.lead.{t}.decision"] = d.get("result", str(d))
        num[f"OOS.lead.{t}.detail"] = d
        pg = res[t]["per_game"]
        q = pg.get("qualifying", pd.Series(False, index=pg.index)).fillna(False).astype(bool)
        num[f"OOS.lead.{t}.n_qualifying"] = int(q.sum())
        num[f"OOS.lead.{t}.n_excluded_outage"] = int(pg["reason"].astype(str).str.contains("outage|not recording|never recorded").sum())
    res["receipt_diagnostic"].to_csv(c.out / "receipt_diagnostic.csv", index=False)
    num["OOS.lead.n_candidates"] = int(len(H.amendment4(c.cands)))
    (c.out / "lead_decisions.json").write_text(json.dumps({t: res[t]["decision"] for t in H.TESTS}, indent=1,
                                                          default=str))
    return res


def rows_with_size(m, venue: str, market: str, lo: int, hi: int) -> pd.DataFrame:
    fs = m.files(venue)
    if not fs:
        return pd.DataFrame(columns=["ts", "venue", "market_id", "kind", "price", "size"])
    d = ds.dataset(fs, format="parquet")
    cols = [x for x in ["ts", "venue", "market_id", "kind", "price", "size"] if x in d.schema.names]
    f = (ds.field("market_id") == market) & (ds.field("ts") >= lo) & (ds.field("ts") <= hi)
    return d.to_table(filter=f, columns=cols).to_pandas()


def laggard(c: Ctx, res: dict, num: dict) -> None:
    by = {m.name: m for m in c.machines}
    delays = L.load_seconds_delay(c.delays_csv)
    cand = c.cands.set_index("game_id")
    trades = []
    for t, (other, _) in H.TESTS.items():
        pg = res[t]["per_game"]
        q = pg[pg.get("qualifying", pd.Series(False, index=pg.index)).fillna(False).astype(bool)]
        for r in q.itertuples():
            m = by[r.machine]
            inst = H.instruments(cand.loc[[r.game_id]].reset_index().iloc[0], c.maps)
            lo = int(r.window_start_ns)
            # causal trading end (v2 Amendment 5 draft): min(kickoff + 4.5 h, pin_start + 60 s), not the pin start
            hi = L.trading_end_ns(pd.Timestamp(r.kickoff_utc).value, getattr(r, "pin_start_g", None))
            kt = rows_with_size(m, "kalshi", inst["kalshi"], lo - 3600 * NS, hi + 120 * NS)
            ot = rows_with_size(m, other, inst[other], lo - 3600 * NS, hi + 120 * NS)
            gaps = m.gaps()
            outs = [(int(g.start_ns), int(g.end_ns)) for g in gaps[gaps["venue"].isin(["kalshi", other, "all"])].itertuples()
                    if g.end_ns > lo and g.start_ns < hi]
            cond = (c.maps["polymarket_com"].get(cand.loc[r.game_id, "kalshi_ticker"]) or {}).get("condition")
            tr = L.evaluate_game(r.game_id, r.kickoff_utc, kt, ot, other, lo, hi,
                                 exclude=[(int(r.excl_lo_g), int(r.excl_hi_g))], outages=outs, holdout_run=True,
                                 condition=cond if other == "polymarket" else None, delays=delays)
            if len(tr):
                trades.append(tr.assign(test=t, machine=r.machine))
    tdf = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame(
        columns=["game_id", "venue", "latency_s", "filled", "skip", "test"])
    tdf.to_csv(c.out / "laggard_trades.csv", index=False)
    curves = [L.latency_curve(d).assign(venue=v) for v, d in tdf.groupby("venue")] if len(tdf) else []
    (pd.concat(curves, ignore_index=True) if curves else pd.DataFrame()).to_csv(c.out / "laggard_latency_curve.csv",
                                                                               index=False)
    L.capacity(tdf).to_csv(c.out / "laggard_capacity.csv", index=False)
    base = tdf[tdf["added_latency_s"] == 0] if len(tdf) else tdf      # at each market's own delay, no extra latency
    num["OOS.laggard.n_trades"] = int(base["filled"].astype(bool).sum()) if len(base) else 0
    num["OOS.laggard.n_trades_by_venue"] = base[base["filled"].astype(bool)].groupby("venue").size().to_dict() if len(base) else {}
    if len(tdf):
        num["OOS.laggard.delay_sources"] = tdf.drop_duplicates(["game_id", "venue"])["delay_source"].value_counts().to_dict()


# ---------- Strategy A and B ----------

def a_games_loaded(c: Ctx) -> list:
    gp, mp = c.out / "inputs_a_games.csv", c.out / "inputs_a_meta.csv"
    c.a_games.to_csv(gp, index=False)
    c.a_meta.to_csv(mp, index=False)
    return A.load_games(gp, mp, ticks_dir=c.a_ticks, expect_preseason=None)


def a_ticks(c: Ctx, g) -> pd.DataFrame:
    f = Path(c.a_ticks) / f"{g.game_id}.parquet"
    return pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=["ts", "venue", "market_id", "kind", "price"])


def orientation_gate(c: Ctx, games: list, num: dict) -> tuple[bool, str]:
    """Same gate as training: for holdout A games that reach the favorite decision (ESPN kickoff, both markets
    present, both fresh, both priced at t), home own-market price + away own-market price at t (the as-of medians
    decide() uses). PASS = median in [0.97, 1.05] and < 2% of games outside [0.90, 1.10]. Prints only the verdict
    and median, p5, p95, count, n outside; no single price."""
    s = []
    for g in games:
        if g.kickoff_source not in A.KICKOFF_SOURCES or g.exclude:
            continue
        tr = a_ticks(c, g)
        if not len(tr):
            continue
        d = A.decide(tr, g)
        if d["skip"] and not d["skip"].startswith("no favorite"):
            continue
        t = d["t_ns"]
        own = {x: A.own_market_trades(tr, g, x) for x in (g.home, g.away)}
        s.append(A.asof_median(own[g.home], t) + A.asof_median(own[g.away], t))
    x = np.array(s, float)
    if not len(x):
        return False, "orientation gate: no game reaches the decision"
    out = int(((x < 0.90) | (x > 1.10)).sum())
    ok = 0.97 <= float(np.median(x)) <= 1.05 and out / len(x) < 0.02
    msg = (f"orientation gate {'PASS' if ok else 'FAIL'}: n {len(x)}, median {np.median(x):.4f}, "
           f"p5 {np.percentile(x, 5):.4f}, p95 {np.percentile(x, 95):.4f}, outside [0.90, 1.10] {out}")
    num["OOS.orientation_gate"] = {"pass": bool(ok), "n": len(x), "median": float(np.median(x)),
                                   "p5": float(np.percentile(x, 5)), "p95": float(np.percentile(x, 95)),
                                   "n_outside": out}
    return ok, msg


def strategy_a(c: Ctx, num: dict, games: list) -> pd.DataFrame:
    rows = []
    for g in games:
        tr = a_ticks(c, g)
        for r in A.evaluate_game(tr, g, thetas=(RB.A_THETA,), final_test=True):
            r.update(kickoff=g.kickoff, date=g.kickoff.tz_convert(ET).date().isoformat())
            rows.append(r)
    rows = pd.DataFrame(rows)
    rows.drop(columns=[x for x in rows.columns if x.startswith("_")], errors="ignore").to_parquet(c.out / "strategy_a_rows.parquet")
    summ = pd.concat([RA.table(rows).assign(sample="primary"),
                      RA.table(rows[~rows["preseason"].astype(bool)]).assign(sample="no NFL preseason")],
                     ignore_index=True)
    summ.to_csv(c.out / "strategy_a_summary.csv", index=False)
    e = rows[rows["entered"].astype(bool) & ~rows["placebo"].astype(bool)]
    checks = []
    top5 = e.nlargest(5, "pnl_webull").index if len(e) else []
    for name, sub in [("all", e), ("NFL", e[e["league"] == "NFL"]), ("CFB", e[e["league"] == "CFB"]),
                      ("without top 5 games by P&L", e.drop(top5))]:
        x = sub["roc_webull"].to_numpy(float)
        lo, hi = RA.boot_ci(x, np.random.default_rng(RA.SEED))
        checks.append({"subset": name, "n": len(x), "roc_webull": x.mean() if len(x) else np.nan, "ci_lo": lo, "ci_hi": hi})
    ck = pd.DataFrame(checks)
    ck.to_csv(c.out / "strategy_a_checks.csv", index=False)
    fav = summ[(summ["sample"] == "primary") & (summ["leg"] == "favorite")].iloc[0]
    num["OOS.A.n_games"] = int(fav["games"])
    num["OOS.A.n_trades"] = int(fav["entered"])
    num["OOS.A.roc_webull"] = float(fav.get("roc_webull", np.nan))
    num["OOS.A.roc_webull_ci"] = [float(fav.get("roc_webull_ci_lo", np.nan)), float(fav.get("roc_webull_ci_hi", np.nan))]
    num["OOS.A.roc_direct"] = float(fav.get("roc_direct", np.nan))
    a = ck.set_index("subset")
    num["OOS.A.fail_1_ci_includes_0"] = bool(not (a.loc["all", "ci_lo"] > 0 or a.loc["all", "ci_hi"] < 0))
    num["OOS.A.fail_2_without_top5_ci_includes_0"] = bool(not (a.loc["without top 5 games by P&L", "ci_lo"] > 0))
    num["OOS.A.fail_3_league_roc"] = {"NFL": float(a.loc["NFL", "roc_webull"]), "CFB": float(a.loc["CFB", "roc_webull"])}
    return rows


def strategy_b(c: Ctx, num: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    out, info = [], []
    for r in c.b_games.itertuples():
        kt = pd.read_parquet(Path(c.b_kalshi) / f"{r.game_id}.parquet")
        pt = pd.read_parquet(Path(c.b_pm) / f"{r.game_id}.parquet")
        t, i = B.evaluate_game(r.game_id, r.espn_kickoff, kt, pt, settings=[SEL_B], final_test=True)
        out.append(t)
        info.append(i)
    pairs = B.placebo_pairs(c.b_games[["game_id", "espn_kickoff"]])
    ko = dict(zip(c.b_games["game_id"], c.b_games["espn_kickoff"]))
    pl = []
    for a_id, b_id in pairs:
        kt = pd.read_parquet(Path(c.b_kalshi) / f"{a_id}.parquet")
        pt = pd.read_parquet(Path(c.b_pm) / f"{b_id}.parquet")
        pl.append(B.evaluate_game(a_id, ko[a_id], kt, pt, settings=[SEL_B], final_test=True)[0].assign(game_b=b_id))
    x2 = []
    for r in c.b_games.itertuples():
        kt = pd.read_parquet(Path(c.b_kalshi) / f"{r.game_id}.parquet")
        pt = pd.read_parquet(Path(c.b_pm) / f"{r.game_id}.parquet")
        x2.append(B.evaluate_game(r.game_id, r.espn_kickoff, kt, pt, settings=[SEL_B], final_test=True,
                                  half_spread=2 * B.HALF_SPREAD, fee_mult=2.0)[0])
    cat = lambda xs: pd.concat([x for x in xs if len(x)], ignore_index=True) if any(len(x) for x in xs) else \
        pd.DataFrame(columns=["k", "m", "T", "filled", "skip", "game_id", "exit_reason"])
    t, p, t2 = cat(out), cat(pl), cat(x2)
    t.to_parquet(c.out / "strategy_b_trades.parquet")
    s = RBB.summarize(t, len(c.b_games)) if len(t) else pd.DataFrame()
    s.to_csv(c.out / "strategy_b_summary.csv", index=False)
    (RBB.summarize(p, len(pairs)) if len(p) else pd.DataFrame()).to_csv(c.out / "strategy_b_placebo_summary.csv", index=False)
    (RBB.summarize(t2, len(c.b_games)) if len(t2) else pd.DataFrame()).to_csv(c.out / "strategy_b_costs_x2.csv", index=False)
    num["OOS.B.n_games"] = len(c.b_games)
    num["OOS.B.valid_share_median"] = float(pd.DataFrame(info)["valid_share"].median()) if info else float("nan")
    if len(s):
        r = s.iloc[0]
        num["OOS.B.n_trades"] = int(r["n_trades"])
        num["OOS.B.edge_webull_cents"] = float(r["edge_webull_cents"])
        num["OOS.B.edge_webull_ci"] = [float(r["edge_webull_ci_lo"]), float(r["edge_webull_ci_hi"])]
        num["OOS.B.edge_direct_cents"] = float(r["edge_direct_cents"])
    else:
        num["OOS.B.n_trades"], num["OOS.B.edge_webull_cents"], num["OOS.B.edge_webull_ci"] = 0, float("nan"), [np.nan, np.nan]
    return t, t2


# ---------- main ----------

def run(c: Ctx) -> dict:
    t0 = time.monotonic()
    start = now_et()
    gi = git_info()
    num: dict = {}
    ck = checklist(c)
    print("PRE-RUN CHECKLIST")
    for m, f in ck["feeds"].items():
        print(f"  {m} files per feed: {f}")
    for k, v in ck["checks"].items():
        tag = "SKIP(dry: fixture)" if c.dry and "expected" in v else ("OK " if v["ok"] else "BAD")
        print(f"  {tag} {k}: {v['value']}" + (f" (expected {v['expected']})" if "expected" in v else ""))
    if not c.dry and not all(v["ok"] for v in ck["checks"].values()):
        raise SystemExit("checklist failed; nothing run")
    c.out.mkdir(parents=True, exist_ok=c.dry)   # the lock: a second real run fails here (FileExistsError)
    (c.out / "checklist.json").write_text(json.dumps(ck, indent=1, default=str))
    games = a_games_loaded(c)
    gate_ok, gate_msg = orientation_gate(c, games, num)
    print(gate_msg)
    res = lead(c, num)
    for t in H.TESTS:
        print(f"lead test {t}: qualifying {num[f'OOS.lead.{t}.n_qualifying']}, decision {num[f'OOS.lead.{t}.decision']}")
    laggard(c, res, num)
    print(f"laggard: filled round trips {num['OOS.laggard.n_trades']}")
    if not gate_ok:
        print("Strategy A and B NOT run: orientation gate failed (lead test and laggard above stand)")
        return finish(c, num, start, t0, gi, gate_msg)
    rows = strategy_a(c, num, games)
    print(f"Strategy A: games {num['OOS.A.n_games']}, trades {num['OOS.A.n_trades']}")
    bt, b2 = strategy_b(c, num)
    print(f"Strategy B: games {num['OOS.B.n_games']}, trades {num['OOS.B.n_trades']}")
    t_rows, t_bt, t_b2, t_sel, t_kos = c.training
    _, bases, trial = RB.build(t_rows, t_bt, t_b2, t_sel, t_kos, c.fac, c.out / "training_tmp", prefix="TRAIN.")
    kos = pd.concat([pd.Series(pd.to_datetime(rows["kickoff"], utc=True)),
                     pd.to_datetime(c.b_games["espn_kickoff"], utc=True)], ignore_index=True)
    bnum, _, _ = RB.build(rows.assign(theta=RB.A_THETA), bt, b2, SEL_B, kos, c.fac, c.out, prefix="OOS.",
                          label="Out-of-sample", bases=bases, trial_srs=trial, png="equity_oos.png")
    num.update({k: v["value"] for k, v in bnum.items()})
    return finish(c, num, start, t0, gi, gate_msg)


def finish(c: Ctx, num: dict, start: str, t0: float, gi: dict, gate_msg: str) -> dict:
    numbers = {k: {"value": v, "source": "scripts/final_test_run.py"} for k, v in num.items()}
    (c.out / "numbers.json").write_text(json.dumps(numbers, indent=1, default=str))
    end = now_et()
    aborted = "FAIL" in gate_msg or "no game" in gate_msg
    (c.out / "RUN_LOG.md").write_text(
        f"# {'DRY RUN (synthetic fixtures)' if c.dry else 'THE holdout run'}\n\n- git sha: {gi['git_sha']}"
        f"{' (working tree had uncommitted changes)' if gi['dirty'] else ''}\n- start: {start}\n- end: {end}\n"
        f"- runtime: {time.monotonic() - t0:.1f} s\n- outputs: {c.out}\n- {gate_msg}\n"
        + ("- Strategy A and B ABORTED: the orientation gate failed; the lead test and laggard ran.\n" if aborted else ""))
    return numbers


def real_ctx(checklist_only: bool = False) -> Ctx:
    out = ROOT / "results" / "holdout"          # created (the lock) only after the checklist passes, in run()
    live = ROOT / "data" / "live"
    vroot, mroot = ROOT / "data" / "vultr", ROOT / "data" / "mac"
    # FROZEN inputs (scripts/stop_and_sync.sh step 3): GAPS tables and heartbeat logs copied after the recorders
    # stopped and hashed into results/holdout_inputs_manifest.txt; never the tracked, auto-logged GAPS.md.
    machines = [H.Machine("vultr", vroot, vroot / "GAPS_vultr.md", vroot / "heartbeats"),
                H.Machine("mac", ROOT, mroot / "GAPS_mac.md", mroot / "heartbeats")]
    md = live / "holdout_maps"
    maps_files = {"polymarket_com_map.json": md / "polymarket_com_map.json",
                  "polymarket_us_map.json": md / "polymarket_us_map.json"}
    if checklist_only:        # the checklist needs no holdout trades, settlements or training outputs
        return Ctx(out, machines, pd.read_csv(live / "holdout_candidates.csv"), H.load_maps(md),
                   live / "holdout_seconds_delay.csv", None, None, None, None, None, None, None, None, False, maps_files)
    hr = ROOT / "data" / "holdout_raw"
    ev = pd.read_csv(hr / "events.csv")
    st = pd.read_csv(hr / "settlements.csv")
    home = st[st["side"] == "home"].set_index("game_id")["result"]
    ev = ev[ev["espn_kickoff"].notna()]
    a_games = pd.DataFrame({"game_id": ev["game_id"], "league": ev["league"], "home": ev["k_home_code"],
                            "away": ev["k_away_code"], "kalshi_event": ev["k_event"], "kalshi_ticker": ev["k_home_ticker"],
                            "kickoff_utc_espn": ev["espn_kickoff"], "kickoff_source": "espn",
                            "settlement_result": ev["game_id"].map(home).map({"yes": 1.0, "no": 0.0})})
    a_meta = st.assign(price_ranges=None)
    pm = pd.read_csv(hr / "pm_map.csv")
    b_games = pd.DataFrame({"game_id": pm["game_id"], "espn_kickoff": pm["kickoff"]})
    b_games = b_games[[(hr / "kalshi" / f"{g}.parquet").exists() and (hr / "polymarket" / f"{g}.parquet").exists()
                       for g in b_games["game_id"]]]
    fac = pd.read_csv(ROOT / "data" / "raw" / "french" / "factors_daily.csv", parse_dates=["date"])
    return Ctx(out, machines, pd.read_csv(live / "holdout_candidates.csv"), H.load_maps(md),
               live / "holdout_seconds_delay.csv", a_games, a_meta, hr / "kalshi", b_games, hr / "kalshi",
               hr / "polymarket", RB.training_inputs(), fac, False,
               {"polymarket_com_map.json": md / "polymarket_com_map.json",
                "polymarket_us_map.json": md / "polymarket_us_map.json"})


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--i-am-the-one-run", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--checklist-only", action="store_true", help="real inputs, checklist only; no lock, nothing run")
    ap.add_argument("--dry-run-flip-away", action="store_true", help=argparse.SUPPRESS)  # dry run: force a FAIL gate
    a = ap.parse_args()
    if a.dry_run:
        import scripts.final_test_fixtures as FX
        c = FX.dry_ctx(ROOT / "results" / ("dryrun_gatefail" if a.dry_run_flip_away else "dryrun"),
                       flip_away=a.dry_run_flip_away)
    elif a.checklist_only:
        c = real_ctx(checklist_only=True)
        ck = checklist(c)
        print("PRE-RUN CHECKLIST (checklist only; nothing evaluated, no lock)")
        for m, f in ck["feeds"].items():
            print(f"  {m} files per feed: {f}")
        for k, v in ck["checks"].items():
            print(f"  {'OK ' if v['ok'] else 'BAD'} {k}: {v['value']}" + (f" (expected {v['expected']})" if "expected" in v else ""))
        ok = all(v["ok"] for v in ck["checks"].values())
        print("checklist", "PASS" if ok else "FAIL")
        if not ok:
            raise SystemExit(1)       # stop_and_sync.sh step 6 must fail loudly
        return
    else:
        if (ROOT / "results" / "holdout").exists():
            raise SystemExit("results/holdout/ exists: the one run has already happened")
        c = real_ctx()
    t = time.monotonic()
    numbers = run(c)
    gate_failed = not numbers.get("OOS.orientation_gate", {}).get("value", {}).get("pass", False)
    req = [f for f in REQUIRED if not (gate_failed and f.startswith(("strategy_", "equity_oos")))]
    req_keys = [k for k in REQUIRED_KEYS if not (gate_failed and k.split(".")[1] in ("A", "B", "season_first_day",
                                                                                      "season_last_day", "combined", "corr_A_B"))]
    missing = [f for f in req if not (c.out / f).exists()]
    missing_keys = [k for k in req_keys + ["OOS.orientation_gate"] if k not in numbers]
    if not c.dry:
        RB.write_numbers({k: v for k, v in numbers.items() if k.startswith("OOS.")}, ROOT / "results" / "numbers.json",
                         replace_prefix="OOS.")
    print(f"done in {time.monotonic() - t:.1f} s; outputs in {c.out}; missing files {missing}; missing keys {missing_keys}")


if __name__ == "__main__":
    main()
