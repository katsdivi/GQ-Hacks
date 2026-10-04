"""Post-hoc Idea 11, post-run correction of the (b) execution model.

Post-run correction: original execution model conditioned on the second leg clearing in the future (the run
counted a trade only if both legs cleared at their fill times, and the polymarket.com leg fills 1 s after the Kalshi
leg). This script re-prices every attempt from the committed detection output (results/posthoc_idea11/
opportunities.csv, the run committed in 9d06979; settlements as fixed in fc95b81). Detection is unchanged; no new
opportunities. SPEC.md is unchanged. Model (Divi, 2026-10-04):

- At detection t, two independent IOC limit orders at the observed best asks: Kalshi YES X at a_K, polymarket.com
  token of the other team at a_P (the k_px, pm_px columns of opportunities.csv).
- Book state at a fill time T = the latest snapshot whose VENUE timestamp (src_ts_ns) is <= T (ties: last
  received). Snapshots without a venue timestamp are not used.
- Kalshi leg fills at t + L if its best ask <= a_K then; polymarket.com leg fills at t + L + that market's delay if
  its best ask <= a_P then. Fill price = best ask at the fill time; size = min(10, displayed ask size then).
- Hedged quantity = min of the two leg fills. Any excess, or a one-leg fill, is NAKED:
  primary: hold to settlement; secondary: unwind at that venue's best bid at failure time + 1 s, with the fee.
  Failure time = the naked leg's own fill time.
- Fees per order at executed size: Kalshi 0.07 x C x P(1-P) rounded up to the cent; polymarket.com
  0.05 x C x P(1-P) rounded half-up to 5 decimals. Unwind orders pay the same fee at the unwind price and size.
- Each leg's order fee is split between its hedged and naked contracts in proportion to quantity.

post-hoc, exploratory; market-efficiency measurement; polymarket.com is not available to US persons; not a strategy
available to the authors.

Usage (cwd = repo root): PYTHONPATH=.:scripts nice -n 19 python scripts/posthoc_idea11_corrected.py
"""
from __future__ import annotations

import sys
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd

import holdout_mid as H
import posthoc_idea11 as P

NS = P.NS
QTY = P.QTY
TOL = 1e-9
UNWIND_S = 1.0
SEED, N_BOOT = 20261004, 2000
OUT = P.OUT
HEADER = "Post-run correction: original execution model conditioned on the second leg clearing in the future."


# ---------------------------------------------------------------- fees
def fee_k(p: float, q: float) -> float:
    if q <= 0:
        return 0.0
    Pp, Q = Decimal(str(round(float(p), 4))), Decimal(str(round(float(q), 4)))
    return float((Decimal("0.07") * Q * Pp * (1 - Pp)).quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def fee_pm(p: float, q: float) -> float:
    if q <= 0:
        return 0.0
    Pp, Q = Decimal(str(round(float(p), 6))), Decimal(str(round(float(q), 6)))
    return float((Decimal("0.05") * Q * Pp * (1 - Pp)).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------- book state on the venue clock
def by_venue_time(snap: pd.DataFrame) -> pd.DataFrame:
    s = snap[snap["src"].notna()].copy()
    s["src"] = s["src"].astype("int64")
    return s.sort_values(["src", "recv"], kind="stable").reset_index(drop=True)


def state_at(sv: pd.DataFrame, T: int) -> dict | None:
    """Latest snapshot with venue time <= T (sv sorted by src, recv). None if there is none."""
    i = int(np.searchsorted(sv["src"].to_numpy("int64"), T, side="right")) - 1
    if i < 0:
        return None
    r = sv.iloc[i]
    return {"src": int(r["src"]), "bid": r["bid"], "ask": r["ask"], "bid_size": r["bid_size"], "ask_size": r["ask_size"]}


def quote(st: dict | None, flip: bool, side: str) -> tuple[float, float]:
    """Best ask (side='ask') or best bid (side='bid') of the instrument held, with its size. Books are stored as
    P(home); flip=True means the instrument is the complement (away YES on Kalshi, away token on polymarket.com):
    its ask = 1 - stored bid (size bid_size), its bid = 1 - stored ask (size ask_size)."""
    if st is None:
        return np.nan, np.nan
    if not flip:
        return float(st[side]), float(st[f"{side}_size"])
    o = "bid" if side == "ask" else "ask"
    px = st[o]
    return (1.0 - float(px) if px == px else np.nan), float(st[f"{o}_size"])


def leg_fill(sv: pd.DataFrame, T: int, limit: float, flip: bool) -> dict:
    """IOC buy at limit, evaluated at fill time T on the venue clock."""
    st = state_at(sv, T)
    ask, sz = quote(st, flip, "ask")
    out = {"fill_time": T, "state_src": st["src"] if st else None, "ask": ask, "q": 0.0, "px": np.nan}
    if ask == ask and sz == sz and sz > 0 and round(ask, 4) <= round(float(limit), 4) + TOL:
        out.update(q=float(min(QTY, sz)), px=float(round(ask, 4)))
    return out


def unwind(sv: pd.DataFrame, T: int, flip: bool) -> tuple[float, float]:
    """Best bid and its size at T (venue clock) for selling the instrument held."""
    return quote(state_at(sv, T), flip, "bid")


# ---------------------------------------------------------------- one attempt
def reprice(op: dict, ksv: pd.DataFrame, psv: pd.DataFrame, L: float, delay_s: float,
            pay_k: float, pay_pm: float) -> dict:
    """op: team ('home'/'away'), t (ns), k_px (a_K), pm_px (a_P). ksv: Kalshi X market book (P(home), sorted by venue
    time); psv: polymarket.com book (home token, P(home)). pay_k, pay_pm: settlement of the held instruments."""
    t = int(op["t"])
    k_flip = op["team"] == "away"          # Kalshi away market is stored as P(home): YES away = complement
    p_flip = op["team"] == "home"          # polymarket.com leg holds the OTHER team's token
    kT, pT = t + int(round(L * NS)), t + int(round((L + delay_s) * NS))
    k = leg_fill(ksv, kT, op["k_px"], k_flip)
    p = leg_fill(psv, pT, op["pm_px"], p_flip)
    qk, qp = k["q"], p["q"]
    status = ("both" if qk > 0 and qp > 0 else "kalshi_only" if qk > 0 else "pm_only" if qp > 0 else "neither")
    qh = min(qk, qp)
    fk, fp = fee_k(k["px"], qk) if qk > 0 else 0.0, fee_pm(p["px"], qp) if qp > 0 else 0.0
    r = {"latency_s": L, "status": status, "k_fill_time": kT, "pm_fill_time": pT, "k_state_src": k["state_src"],
         "pm_state_src": p["state_src"], "k_ask": k["ask"], "pm_ask": p["ask"], "q_k": qk, "q_pm": qp,
         "k_px": k["px"], "pm_px": p["px"], "fee_k": fk, "fee_pm": fp, "q_hedged": qh,
         "naked_venue": "kalshi" if qk > qh else ("pm" if qp > qh else ""), "q_naked": max(qk, qp) - qh,
         "pay_k": pay_k, "pay_pm": pay_pm}
    settled = pay_k == pay_k and pay_pm == pay_pm
    r["settled"] = settled
    # hedged part
    if qh > 0:
        h = qh * (pay_k - k["px"]) + qh * (pay_pm - p["px"]) - fk * qh / qk - fp * qh / qp
    else:
        h = 0.0
    # naked part
    qn = r["q_naked"]
    hold, unw, unw_info = 0.0, 0.0, {"unwind_px": np.nan, "unwind_bid_size": np.nan, "unwind_fee": 0.0,
                                     "unwind_fallback_hold": False}
    if qn > 0:
        if r["naked_venue"] == "kalshi":
            px, pay, f_alloc, sv, flip, T0, ffun = k["px"], pay_k, fk * qn / qk, ksv, k_flip, kT, fee_k
        else:
            px, pay, f_alloc, sv, flip, T0, ffun = p["px"], pay_pm, fp * qn / qp, psv, p_flip, pT, fee_pm
        hold = qn * (pay - px) - f_alloc
        b, bsz = unwind(sv, T0 + int(round(UNWIND_S * NS)), flip)
        if b == b and bsz == bsz and bsz > 0:
            b = float(round(b, 4))
            uf = ffun(b, qn)
            unw = qn * (b - px) - f_alloc - uf
            unw_info = {"unwind_px": b, "unwind_bid_size": bsz, "unwind_fee": uf, "unwind_fallback_hold": False}
        else:
            unw = hold
            unw_info["unwind_fallback_hold"] = True
    r.update(unw_info)
    # Attempts on a game without a usable settlement on both venues are excluded from both treatments (counted).
    nan = np.nan
    r["pnl_hedged"] = h if settled else nan
    r["pnl_naked_hold"] = hold if settled else nan
    r["pnl_naked_unwind"] = unw if settled else nan
    r["pnl_hold"] = h + hold if settled else nan
    r["pnl_unwind"] = h + unw if settled else nan
    r["contracts"] = max(qk, qp)
    return r


# ---------------------------------------------------------------- stats
def boot3(g: pd.DataFrame, col: str) -> dict:
    """Game bootstrap of total, per attempt and per contract (contracts = larger leg fill per attempt)."""
    x, a, c = (g[col].to_numpy(float), g["attempts"].to_numpy(float), g["contracts"].to_numpy(float))
    if len(x) < 2:
        return {k: (np.nan, np.nan) for k in ("tot", "pa", "pc")}
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(x), size=(N_BOOT, len(x)))
    tot = x[idx].sum(1)
    pa = tot / a[idx].sum(1)
    pc = tot / np.maximum(c[idx].sum(1), 1e-12)
    return {"tot": tuple(np.percentile(tot, [2.5, 97.5])), "pa": tuple(np.percentile(pa, [2.5, 97.5])),
            "pc": tuple(np.percentile(pc, [2.5, 97.5]))}


# ---------------------------------------------------------------- main
def settlements(game_ids) -> tuple[dict, dict]:
    q = P.windows()
    maps = H.load_maps(P.DATA / "data/live/holdout_maps")
    sett = pd.read_csv(P.DATA / "data/holdout_raw/settlements.csv")
    rk, rp = {}, {}
    for a in q.itertuples():
        if a.game_id not in game_ids:
            continue
        pc = maps["polymarket_com"][a.kalshi_ticker]
        ks = sett[sett.game_id == a.game_id].set_index("side")["settlement_value_dollars"].astype(float)
        rk[a.game_id] = {"home": float(ks.get("home", np.nan)), "away": float(ks.get("away", np.nan))}
        pr = P.pm_resolution(pc["condition"])
        other = [t for t in pc["token_ids"] if t != pc["collector_home_token"]][0]
        rp[a.game_id] = ({"home": pr["tokens"].get(pc["collector_home_token"], np.nan), "away": pr["tokens"].get(other, np.nan)}
                         if pr else {"home": np.nan, "away": np.nan})
    return rk, rp


def main() -> None:
    ops = pd.read_csv(OUT / "opportunities.csv")
    exd = pd.read_csv(OUT / "executions.csv")
    delay = exd.groupby("game_id")["delay_s"].first()
    q = P.windows()
    q = q[q.game_id.isin(set(ops.game_id))]
    maps = H.load_maps(P.DATA / "data/live/holdout_maps")
    rk, rp = settlements(set(ops.game_id))
    ld = P.Loader(P.DATA / "data" / "vultr")
    rows = []
    print(f"{HEADER}\nre-pricing {len(ops)} detected opportunities in {ops.game_id.nunique()} games", flush=True)
    for i, a in enumerate(q.itertuples()):
        lo, hi = int(a.window_start_ns), int(a.window_end_ns)
        ev, home = a.kalshi_ticker, a.game_id.split("_")[-1].upper()
        away = a.game_id.split("_")[-2].upper()
        inst = H.instruments(pd.Series(a._asdict()), maps)
        # extend the load window so fill and unwind times near the window end still see the book
        hi2 = hi + 5 * NS
        sv = {"home": by_venue_time(ld.snap("kalshi", f"{ev}-{home}", lo, hi2)),
              "away": by_venue_time(ld.snap("kalshi", f"{ev}-{away}", lo, hi2))}
        psv = by_venue_time(ld.snap("polymarket", inst["polymarket"], lo, hi2))
        g_ops = ops[ops.game_id == a.game_id]
        other = {"home": "away", "away": "home"}
        for o in g_ops.to_dict("records"):
            pay_k, pay_pm = rk[a.game_id][o["team"]], rp[a.game_id][other[o["team"]]]
            for L in P.LATS:
                r = reprice(o, sv[o["team"]], psv, L, float(delay[a.game_id]), pay_k, pay_pm)
                rows.append({"game_id": a.game_id, "team": o["team"], "t": o["t"], "a_K": o["k_px"], "a_P": o["pm_px"], **r})
        print(f"  {i + 1}/{len(q)} {a.game_id} ops={len(g_ops)}", flush=True)
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "corrected_attempts.csv", index=False)
    report(d)


def report(d: pd.DataFrame) -> None:
    orig = pd.read_csv(OUT / "arb_results.csv").set_index("latency_L_s")
    res, lines = [], [f"# Idea 11 (b): corrected execution ({pd.Timestamp.now(tz='America/New_York'):%Y-%m-%d %H:%M} ET)", "",
                      f"**{HEADER}**", "",
                      "post-hoc, exploratory; market-efficiency measurement; polymarket.com is not available to US "
                      "persons; not a strategy available to the authors.", "",
                      "Re-priced from the committed detection output (opportunities.csv of the run in 9d06979; "
                      "settlements as fixed in fc95b81). Detection unchanged, SPEC.md unchanged. Script: "
                      "scripts/posthoc_idea11_corrected.py. Model: independent IOC limit orders at the detected best asks "
                      "a_K, a_P; book state at a fill time = latest snapshot with venue timestamp <= that time; Kalshi leg "
                      "at t + L, polymarket.com leg at t + L + delay (1 s for every game); fill price = best ask then, size = "
                      "min(10, displayed size); hedged = min of the two fills; the rest is naked. Primary: naked held to "
                      "settlement. Secondary: naked unwound at that venue's best bid at failure time + 1 s with its fee, "
                      "failure time = the naked leg's own fill time (if that bid side is empty, held to settlement and "
                      "counted). Fees per order at executed size (Kalshi rounded up to the cent; polymarket.com rounded "
                      "half-up to 5 decimals); each order's fee is split between hedged and naked contracts by quantity.",
                      "", "Per contract = P&L / sum over attempts of the larger leg fill. Game bootstrap 95% CI, 2,000 "
                      "reps, seed 20261004. Excluding top 5 = the 5 games with the highest P&L under that treatment.", ""]
    for L in P.LATS:
        e = d[d.latency_s == L]
        st = e[e.settled]
        cnt = e["status"].value_counts()
        row = {"latency_L_s": L, "attempts": len(e), "both": int(cnt.get("both", 0)), "kalshi_only": int(cnt.get("kalshi_only", 0)),
               "pm_only": int(cnt.get("pm_only", 0)), "neither": int(cnt.get("neither", 0)),
               "unsettled_excluded": int((~e.settled).sum()), "unwind_fallback_hold": int(e["unwind_fallback_hold"].sum()),
               "unwind_bid_size_below_naked": int(((e.q_naked > 0) & (e.unwind_bid_size < e.q_naked)).sum()),
               "hedged_contracts": float(st.q_hedged.sum()), "naked_contracts": float(st.q_naked.sum()),
               "contracts": float(st.contracts.sum())}
        g = st.groupby("game_id").agg(attempts=("t", "size"), contracts=("contracts", "sum"), hold=("pnl_hold", "sum"),
                                      unwind=("pnl_unwind", "sum"), hedged=("pnl_hedged", "sum"),
                                      naked_hold=("pnl_naked_hold", "sum"), naked_unwind=("pnl_naked_unwind", "sum"))
        for tr in ("hold", "unwind"):
            b = boot3(g, tr)
            g5 = g.drop(g[tr].sort_values(ascending=False).index[:5])
            row.update({f"{tr}_total": float(g[tr].sum()), f"{tr}_total_ci_lo": b["tot"][0], f"{tr}_total_ci_hi": b["tot"][1],
                        f"{tr}_per_attempt": float(g[tr].sum() / g.attempts.sum()), f"{tr}_pa_ci_lo": b["pa"][0],
                        f"{tr}_pa_ci_hi": b["pa"][1], f"{tr}_per_contract": float(g[tr].sum() / g.contracts.sum()),
                        f"{tr}_pc_ci_lo": b["pc"][0], f"{tr}_pc_ci_hi": b["pc"][1],
                        f"{tr}_ex_top5_total": float(g5[tr].sum()),
                        f"{tr}_ex_top5_per_contract": float(g5[tr].sum() / g5.contracts.sum()) if g5.contracts.sum() else np.nan})
        row.update(hedged_pnl=float(g.hedged.sum()), naked_hold_pnl=float(g.naked_hold.sum()),
                   naked_unwind_pnl=float(g.naked_unwind.sum()), games=len(g),
                   orig_executed=int(orig.loc[L, "executed"]), orig_pnl_total=float(orig.loc[L, "pnl_total"]),
                   orig_per_contract=float(orig.loc[L, "pnl_per_contract"]))
        res.append(row)
    r = pd.DataFrame(res)
    r.insert(0, "label", "post-run correction; post-hoc, exploratory; market-efficiency measurement")
    r.to_csv(OUT / "corrected_results.csv", index=False)
    lines += ["## Fill outcomes per L (all detected attempts)", "",
              "| L (s) | attempts | both filled | Kalshi only | polymarket.com only | neither | unsettled excluded | hedged contracts | naked contracts |",
              "|---|---|---|---|---|---|---|---|---|"]
    for x in res:
        lines.append(f"| {x['latency_L_s']} | {x['attempts']} | {x['both']} | {x['kalshi_only']} | {x['pm_only']} | {x['neither']} | "
                     f"{x['unsettled_excluded']} | {x['hedged_contracts']:.2f} | {x['naked_contracts']:.2f} |")
    for tr, name in (("hold", "Primary: naked held to settlement"), ("unwind", "Secondary: naked unwound at best bid, failure time + 1 s")):
        lines += ["", f"## P&L, {name}", "",
                  "| L (s) | total $ | 95% CI | per attempt $ | 95% CI | per contract $ | 95% CI | ex top 5 total $ | ex top 5 per contract $ |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for x in res:
            lines.append(f"| {x['latency_L_s']} | {x[f'{tr}_total']:.2f} | [{x[f'{tr}_total_ci_lo']:.2f}, {x[f'{tr}_total_ci_hi']:.2f}] | "
                         f"{x[f'{tr}_per_attempt']:.4f} | [{x[f'{tr}_pa_ci_lo']:.4f}, {x[f'{tr}_pa_ci_hi']:.4f}] | "
                         f"{x[f'{tr}_per_contract']:.4f} | [{x[f'{tr}_pc_ci_lo']:.4f}, {x[f'{tr}_pc_ci_hi']:.4f}] | "
                         f"{x[f'{tr}_ex_top5_total']:.2f} | {x[f'{tr}_ex_top5_per_contract']:.4f} |")
    lines += ["", "## Hedged vs naked split ($)", "", "| L (s) | hedged | naked, held | naked, unwound | unwind bid side empty (held instead) | unwind bid size < naked qty |",
              "|---|---|---|---|---|---|"]
    for x in res:
        lines.append(f"| {x['latency_L_s']} | {x['hedged_pnl']:.2f} | {x['naked_hold_pnl']:.2f} | {x['naked_unwind_pnl']:.2f} | "
                     f"{x['unwind_fallback_hold']} | {x['unwind_bid_size_below_naked']} |")
    lines += ["", "## Original model (fc95b81, for comparison; conditioned on the second leg clearing)", "",
              "| L (s) | executed | total $ | per contract $ |", "|---|---|---|---|"]
    for x in res:
        lines.append(f"| {x['latency_L_s']} | {x['orig_executed']} | {x['orig_pnl_total']:.2f} | {x['orig_per_contract']:.4f} |")
    lines += ["", "Per-attempt rows: corrected_attempts.csv (untracked; regenerate with the command in README.md)."]
    (OUT / "CORRECTED_EXECUTION.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
