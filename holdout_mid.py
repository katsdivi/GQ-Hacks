"""Amendment 2 confirmatory runner (HYPOTHESIS_v2.md, committed 8a509ff): book-mid lead test on recorded games.

Per candidate game (data/live/holdout_candidates.csv) and per test (Kalshi vs polymarket.com, Kalshi vs
Polymarket US):
  1. Instruments: Kalshi home-team market f"{event}-{HOME}", polymarket.com home token (collector_home_token in
     holdout_maps/polymarket_com_map.json), Polymarket US slug (holdout_maps/polymarket_us_map.json). One
     instrument per venue; the two books of a game are never merged. [Clarification needed: Amendment 2 does
     not name the instrument; home is the default here.]
  2. Window: kickoff - 90 min to the earlier of kickoff + 4.5 h or the first second from which either venue's
     defined mid stays >= 0.98 or <= 0.02 for 60 s (the window ends at the start of that run).
  3. Machines: Vultr if neither venue has an outage longer than 60 s inside the window, else the Mac if it has
     none, else excluded. One machine per game, never spliced. Outages: GAPS table rows for the venue (and
     "all"), plus the span before a feed's start (first heartbeat with a delivered message; the first recorded
     file only on a machine with no heartbeat log). For Kalshi every kalshi_ws gap is an outage, and so is any
     time the REST fallback was connected (REST polling degrades timing and biases Kalshi late).
  4. Qualifying: >= 50 mid changes (xcorr_lead.n_mid_changes) on each venue inside the window.
  5. Lag: xcorr_lead.game_lag_mid on the window.
  6. Placebo: Kalshi from game A vs the other venue from game B = the next qualifying game in kickoff order
     with kickoff within 30 min of A, recorded on the same machine as A; both series cut to A's window.
  7. Decision: xcorr_lead.decide, min_lead_s 1.0 (polymarket.com) or 1.5 (Polymarket US).
  8. Book-wipe exclusion (Amendment 3 draft): polymarket.com sports books cancel all resting limit orders at
     the official game start. Per game, on the test's other venue: the first second at or after kickoff -
     30 min whose book has neither side; excluded for BOTH venues from 2 min before it to 5 min after that
     book is two-sided again (to the window end if it never is). No such second -> excluded [kickoff - 2 min,
     kickoff + 10 min]. A both-sides-empty book writes no row in the 2026-10-03 recordings (only a
     "book_empty" marker row would show it), so on those recordings the fallback applies to every game.
     Mid changes never span an excluded interval; the qualifying count and the lag use the rest.
No prices are printed: outputs are counts, lags and decisions. Refuses games with kickoff >= 2026-08-01 unless
holdout_run=True (the run is once, after Saturday's last game, when Divi says go).
"""
from __future__ import annotations

import glob
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

import xcorr_lead as X

NS = 1_000_000_000
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
PRE_S, POST_S = 90 * 60, int(4.5 * 3600)       # window: kickoff - 90 min (Amendment 3 draft) to + 4.5 h
PIN_HI, PIN_LO, PIN_S = 0.98, 0.02, 60
MAX_OUTAGE_S = 60
MIN_CHANGES = 50
PLACEBO_KICKOFF_S = 30 * 60
WIPE_SEARCH_S = 30 * 60              # look for a full clear from kickoff - 30 min
WIPE_PRE_S, WIPE_POST_S = 2 * 60, 5 * 60
WIPE_FALLBACK = (-2 * 60, 10 * 60)   # no clear found: [kickoff - 2 min, kickoff + 10 min]
REST_HEARTBEAT_COVER_S = 15          # one connected kalshi_rest heartbeat covers this many seconds
HB_FEED = {"kalshi": "kalshi_ws", "polymarket": "polymarket", "polymarket_us": "polymarket_us"}
TESTS = {"polymarket.com": ("polymarket", 1.0), "Polymarket US": ("polymarket_us", 1.5)}


@dataclass
class Machine:
    name: str                      # "vultr" or "mac"
    root: Path                     # contains data/live/<venue>/<YYYYMMDD>/<unix>_<pid>.parquet
    gaps_md: Path
    heartbeat_dir: Path | None = None
    year: int = 2026               # GAPS tables carry no year
    _gaps: pd.DataFrame | None = field(default=None, repr=False)
    _start: dict = field(default_factory=dict, repr=False)

    def files(self, venue: str) -> list[str]:
        return sorted(glob.glob(str(self.root / "data" / "live" / venue / "*" / "*.parquet")))

    def feed_start_ns(self, venue: str) -> int | None:
        """First heartbeat of the feed with a delivered message (last_ok set). Only a machine without a
        heartbeat log falls back to the first recorded file's unix-second prefix. No rows are read."""
        if venue not in self._start:
            hb = self.heartbeat_first_ok(HB_FEED[venue]) if self.heartbeat_dir else None
            if hb is not None or self.heartbeat_dir:
                self._start[venue] = hb
            else:
                fs = [int(Path(f).name.split("_")[0]) for f in self.files(venue)]
                self._start[venue] = min(fs) * NS if fs else None
        return self._start[venue]

    def heartbeat_first_ok(self, feed: str) -> int | None:
        for f in sorted(glob.glob(str(self.heartbeat_dir / "*.jsonl"))):
            for line in open(f):
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("venue") == feed and r.get("last_ok_utc"):
                    return pd.Timestamp(r["last_ok_utc"]).value
        return None

    def rows(self, venue: str, market: str, lo_ns: int, hi_ns: int) -> pd.DataFrame:
        fs = self.files(venue)
        if not fs:
            return pd.DataFrame(columns=["ts", "venue", "market_id", "kind", "price"])
        d = ds.dataset(fs, format="parquet")
        f = (ds.field("market_id") == market) & (ds.field("ts") >= lo_ns) & (ds.field("ts") <= hi_ns)
        return d.to_table(filter=f, columns=["ts", "venue", "market_id", "kind", "price"]).to_pandas()

    def gaps(self) -> pd.DataFrame:
        if self._gaps is None:
            self._gaps = parse_gaps(self.gaps_md, self.rest_intervals(), self.year)
        return self._gaps

    def rest_intervals(self) -> list[tuple[int, int]]:
        if not self.heartbeat_dir:
            return []
        out = []
        for f in sorted(glob.glob(str(self.heartbeat_dir / "*.jsonl"))):
            for line in open(f):
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("venue") == "kalshi_rest" and r.get("connected"):
                    t = pd.Timestamp(r["recv_utc"]).value
                    out.append((t, t + REST_HEARTBEAT_COVER_S * NS))
        return out


ROW = re.compile(r"^\|\s*(\w{3} \w{3} \d{2} \d{2}:\d{2}:\d{2})\s*\|\s*(\w{3} \w{3} \d{2} \d{2}:\d{2}:\d{2})\s*\|\s*([\w.]+)\s*\|")


def _et(s: str, year: int = 2026) -> int:
    """'Sat Oct 03 09:19:06' (ET, as written in the GAPS tables) -> UTC ns."""
    return pd.to_datetime(f"{s} {year}", format="%a %b %d %H:%M:%S %Y").tz_localize("America/New_York").value


def parse_gaps(md: Path, rest: list[tuple[int, int]], year: int = 2026) -> pd.DataFrame:
    """GAPS table rows -> (venue, start_ns, end_ns). Times are ET (GAPS rows carry no year). For the lead test
    Kalshi is out whenever the websocket is: every kalshi_ws gap is a Kalshi outage, and every span where the
    REST fallback was connected (heartbeat) is one too. Reported as venue "kalshi"."""
    rows = []
    if md and Path(md).exists():
        for line in open(md):
            m = ROW.match(line)
            if not m:
                continue
            a, b, v = _et(m.group(1), year), _et(m.group(2), year), m.group(3)
            if v == "kalshi_ws":
                rows.append(("kalshi", a, b))
            elif v == "kalshi_rest":
                continue          # REST being down is not an outage while the websocket delivers
            else:
                rows.append((v, a, b))
    rows += [("kalshi", lo, hi) for lo, hi in _merge(rest)]
    return pd.DataFrame(rows, columns=["venue", "start_ns", "end_ns"])


def _merge(iv: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Union of intervals (consecutive REST heartbeats become one span)."""
    out = []
    for lo, hi in sorted(iv):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def outage_reason(m: Machine, venues: tuple[str, str], lo: int, hi: int) -> str:
    """Empty string if no outage > 60 s inside [lo, hi] on either venue, else the reason."""
    g = m.gaps()
    for v in venues:
        st = m.feed_start_ns(v)
        if st is None:
            return f"{m.name}: {v} never recorded"
        if st - lo > MAX_OUTAGE_S * NS:
            return f"{m.name}: {v} not recording for {(min(st, hi) - lo) / NS:.0f} s of the window"
        for r in g[g["venue"].isin([v, "all"])].itertuples():
            ov = min(r.end_ns, hi) - max(r.start_ns, lo)
            if ov > MAX_OUTAGE_S * NS:
                return f"{m.name}: {v} outage {ov / NS:.0f} s in window"
    return ""


def pinned_end(gx: pd.Series, gy: pd.Series, lo_g: int, hi_g: int) -> int:
    """First grid second from which either defined mid stays >= 0.98 or <= 0.02 for 60 s; else hi_g."""
    idx = np.arange(lo_g, hi_g + 1)
    best = hi_g
    for g in (gx, gy):
        s = g.reindex(idx)
        pin = ((s >= PIN_HI) | (s <= PIN_LO)).astype(int).to_numpy()
        run = np.convolve(pin, np.ones(PIN_S, dtype=int), mode="valid")       # run[i] = pins in [i, i + 60)
        hits = np.flatnonzero(run == PIN_S)
        if len(hits):
            best = min(best, int(idx[hits[0]]))
    return best


def wipe_exclusion(to: pd.DataFrame, other: str, ko_ns: int, end_g: int) -> tuple[tuple[int, int], str]:
    """Excluded grid seconds (lo_g, hi_g inclusive) and the source ("clear" or "fallback")."""
    ko_g = ko_ns // NS
    sides = X.sides_snapshots(to, other)
    if len(sides):
        g = pd.Series(sides.to_numpy(), index=sides.index.to_numpy() // NS).groupby(level=0).last()
        empty = g[(g.index >= ko_g - WIPE_SEARCH_S) & (g == 0)]
        if len(empty):
            c = int(empty.index[0])
            back = g[(g.index > c) & (g == 2)]
            hi = int(back.index[0]) + WIPE_POST_S if len(back) else end_g
            return (c - WIPE_PRE_S, min(hi, end_g)), "clear"
    return (ko_g + WIPE_FALLBACK[0], ko_g + WIPE_FALLBACK[1]), "fallback"


def instruments(c, maps: dict) -> dict:
    home = c.game_id.split("_")[-1].upper()
    pc = maps["polymarket_com"].get(c.kalshi_ticker)
    pu = [s for s, r in maps["polymarket_us"].items() if r.get("kalshi_event") == c.kalshi_ticker]
    return {"kalshi": f"{c.kalshi_ticker}-{home}", "polymarket": pc["collector_home_token"] if pc else None,
            "polymarket_us": pu[0] if pu else None}


def game_on_machine(m: Machine, c, inst: dict, other: str) -> dict:
    ko = pd.Timestamp(c.kickoff_utc).value
    lo, hi = ko - PRE_S * NS, ko + POST_S * NS
    tk = m.rows("kalshi", inst["kalshi"], lo, hi)
    to = m.rows(other, inst[other], lo, hi)
    out = {"machine": m.name, "kalshi_rows": len(tk), "other_rows": len(to)}
    if tk.empty or to.empty:
        out["reason"] = f"{m.name}: no rows ({'kalshi' if tk.empty else other})"
        return out
    gx, gy = X.mid_grid(X.mid_snapshots(tk, "kalshi")), X.mid_grid(X.mid_snapshots(to, other))
    end_g = pinned_end(gx, gy, lo // NS, hi // NS - 1)
    end = (end_g + 1) * NS if end_g < hi // NS - 1 else hi
    out.update(window_start_ns=lo, window_end_ns=end)
    r = outage_reason(m, ("kalshi", other), lo, end)
    if r:
        out["reason"] = r
        return out
    lo_g, hi_g = lo // NS, end // NS - 1
    ex, src = wipe_exclusion(to, other, ko, hi_g)
    exc = [ex]
    out.update(excl_lo_g=ex[0], excl_hi_g=ex[1], excl_source=src,
               excluded_s=max(0, min(ex[1], hi_g) - max(ex[0], lo_g) + 1))
    nx, ny = X.n_mid_changes(gx.loc[lo_g:hi_g], exc), X.n_mid_changes(gy.loc[lo_g:hi_g], exc)
    out.update(n_changes_kalshi=nx, n_changes_other=ny)
    if nx < MIN_CHANGES or ny < MIN_CHANGES:
        out["reason"] = f"not qualifying ({nx} / {ny} mid changes, need {MIN_CHANGES})"
        out["qualifying"] = False
        return out
    tkw, tow = tk[(tk.ts >= lo) & (tk.ts < end)], to[(to.ts >= lo) & (to.ts < end)]
    out.update(qualifying=True, reason="", lag_s=X.game_lag_mid(tkw, "kalshi", tow, other, exclude=exc))
    return out


def run_test(cands: pd.DataFrame, maps: dict, machines: list[Machine], test: str,
             holdout_run: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    other, min_lead = TESTS[test]
    if not holdout_run and (pd.to_datetime(cands["kickoff_utc"], utc=True) >= SEAL).any():
        raise ValueError("holdout games (kickoff >= 2026-08-01) need holdout_run=True; run once, when Divi says go")
    per = []
    for c in cands.sort_values("kickoff_utc").itertuples():
        inst = instruments(c, maps)
        row = {"game_id": c.game_id, "kickoff_utc": c.kickoff_utc, "test": test}
        if inst[other] is None:
            per.append({**row, "machine": "", "reason": f"no {other} instrument mapped"})
            continue
        reasons = []
        for m in machines:                    # order = preference (Vultr first)
            r = game_on_machine(m, c, inst, other)
            if not r.get("reason") or r.get("qualifying") is False:
                per.append({**row, **r})
                break
            reasons.append(r["reason"])
        else:
            per.append({**row, "machine": "", "reason": "excluded: " + "; ".join(reasons)})
    per = pd.DataFrame(per)
    q = per[per.get("qualifying", pd.Series(False, index=per.index)).fillna(False).astype(bool)].copy()
    q["ko"] = pd.to_datetime(q["kickoff_utc"], utc=True)
    q = q.sort_values("ko").reset_index(drop=True)
    by = {m.name: m for m in machines}
    pl = []
    for i, a in q.iterrows():
        nxt = q[(q.index > i) & (q["machine"] == a["machine"]) &
                ((q["ko"] - a["ko"]).dt.total_seconds() <= PLACEBO_KICKOFF_S)]
        if nxt.empty:
            continue
        b = nxt.iloc[0]
        m = by[a["machine"]]
        ca = cands[cands.game_id == a["game_id"]].iloc[0]
        cb = cands[cands.game_id == b["game_id"]].iloc[0]
        lo, end = int(a["window_start_ns"]), int(a["window_end_ns"])
        tk = m.rows("kalshi", instruments(ca, maps)["kalshi"], lo, end - 1)
        to = m.rows(other, instruments(cb, maps)[other], lo, end - 1)
        exc = [(int(a["excl_lo_g"]), int(a["excl_hi_g"]))]      # A's window, A's exclusion
        pl.append({"game_a": a["game_id"], "game_b": b["game_id"], "machine": a["machine"],
                   "lag_s": X.game_lag_mid(tk, "kalshi", to, other, exclude=exc) if len(tk) and len(to)
                   else float("nan")})
    pl = pd.DataFrame(pl, columns=["game_a", "game_b", "machine", "lag_s"])
    dec = X.decide(q["lag_s"].to_numpy(float), pl["lag_s"].to_numpy(float), 0.0, "kalshi", other, min_lead_s=min_lead)
    return per, pl, dec


def load_maps(d: Path) -> dict:
    return {"polymarket_com": json.loads((d / "polymarket_com_map.json").read_text()),
            "polymarket_us": json.loads((d / "polymarket_us_map.json").read_text())}


def run_all(cands: pd.DataFrame, maps: dict, machines: list[Machine], holdout_run: bool = False) -> dict:
    """Both venue tests, then Holm across them (Amendment 3 draft). Returns per-test tables and final decisions."""
    res = {t: run_test(cands, maps, machines, t, holdout_run) for t in TESTS}
    inputs = {}
    for t, (per, pl, _dec) in res.items():
        q = per[per.get("qualifying", pd.Series(False, index=per.index)).fillna(False).astype(bool)]
        inputs[t] = (q["lag_s"].to_numpy(float), pl["lag_s"].to_numpy(float), TESTS[t][0], TESTS[t][1])
    final = X.decide_holm(inputs)
    return {t: {"per_game": res[t][0], "placebo": res[t][1], "decision": final[t]} for t in TESTS}
