"""Post-hoc maker / spread-capture search (SPEC: results/posthoc_costside_maker/SPEC.md). Training only."""
from __future__ import annotations

import math
import sys
from decimal import ROUND_CEILING, Decimal

import numpy as np
import pandas as pd

import strategy_a as A

NS = 1_000_000_000
EPS = 1e-9
MAKER_RATE = 0.0175
TAKER_RATE = 0.07
ORDER_SIZE = 5
STALE_S = 600
EXIT_WAIT_S = 120
MIN_PRICE, MAX_PRICE = 0.01, 0.98


def fee_rate(price: float, qty: int, rate: float) -> float:
    """rate x C x P x (1-P), exact decimal, rounded up to the cent per order."""
    if rate == 0:
        return 0.0
    p = Decimal(str(round(float(price), 4)))
    raw = Decimal(str(rate)) * Decimal(int(qty)) * p * (1 - p)
    return float(raw.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def fee_maker(price, qty, line):          # line in {"m0","m175"}
    return fee_rate(price, qty, 0.0 if line == "m0" else MAKER_RATE)


def fee_taker(price, qty):
    return fee_rate(price, qty, TAKER_RATE)


def ref_price(ts, px, t_ns):
    """Last trade with ts <= t_ns, None if none or older than STALE_S."""
    j = int(np.searchsorted(ts, t_ns, side="right")) - 1
    if j < 0 or ts[j] < t_ns - STALE_S * NS:
        return None
    return float(px[j])


def limit_price(ref, h, tick):
    L = round(round((ref - h * 0.01) / tick) * tick, 4)
    if L < MIN_PRICE - EPS or L > MAX_PRICE + EPS:
        return None
    return L


def strict_fill(ts, px, t_ns, w_ns, L, tick):
    """ts of the first trade in (t+1s, t+W] with price <= L - tick (strictly through L), else None."""
    lo = int(np.searchsorted(ts, t_ns + NS, side="right"))
    hi = int(np.searchsorted(ts, t_ns + w_ns, side="right"))
    if hi <= lo:
        return None
    m = np.nonzero(px[lo:hi] <= L - tick + EPS)[0]
    return int(ts[lo + m[0]]) if len(m) else None


def exit_sale(ts, px, t_exit_ns):
    """Taker sale: first trade ts >= exit+1s within EXIT_WAIT_S, price - 1 cent (floor 0.01); None if none."""
    lo = int(np.searchsorted(ts, t_exit_ns + NS, side="left"))
    if lo >= len(ts) or ts[lo] > t_exit_ns + EXIT_WAIT_S * NS:
        return None
    return max(0.01, round(float(px[lo]) - 0.01, 4))


def windows(k_ns, name):
    m = 60 * NS
    return {"pre": (k_ns - 60 * m, k_ns - 5 * m), "in": (k_ns + 20 * m, k_ns + 180 * m),
            "late": (k_ns + 90 * m, k_ns + 180 * m)}[name]


def simulate(arrs, teams, k_ns, result_home, home, p):
    """arrs: team -> (ts int64, px float own-YES). p: dict(window,h,cap,W_min,thr,end).
    Returns list of fill dicts + orders posted count. No lookahead: reference uses ts <= t_k, fills (t_k+1s, t_k+W]."""
    w0, w1 = windows(k_ns, p["window"])
    W = int(p["W_min"] * 60 * NS)
    inv = {t: 0 for t in teams}
    fills, orders = [], 0
    t_k, cyc = w0, 0
    while t_k + W <= w1:
        for t in teams:
            ts, px = arrs[t]
            tick = p["tick"].get(t, 0.01)
            ref = ref_price(ts, px, t_k)
            if ref is None or ref < p.get("thr", 0.0) - EPS:
                continue
            q = min(ORDER_SIZE, p["cap"] - inv[t])
            if q <= 0:
                continue
            L = limit_price(ref, p["h"], tick)
            if L is None:
                continue
            orders += 1
            f = strict_fill(ts, px, t_k, W, L, tick)
            if f is not None:
                inv[t] += q
                fills.append({"team": t, "cycle": cyc, "ts": f, "L": L, "qty": q})
        t_k += W
        cyc += 1
    for f in fills:
        f["payout"] = result_home if f["team"] == home else 1.0 - result_home
    return fills, orders


def game_pnl(fills, arrs, k_ns, p, line):
    """Net pnl, entry capital (cost + maker fee) and exit info for one fee line. Exit is taker."""
    pnl = cap = 0.0
    n_exit = 0
    by_team = {}
    for f in fills:
        mf = fee_maker(f["L"], f["qty"], line)
        cap += f["L"] * f["qty"] + mf
        by_team.setdefault(f["team"], []).append((f, mf))
    t_exit = windows(k_ns, p["window"])[1]
    for t, lst in by_team.items():
        Q = sum(f["qty"] for f, _ in lst)
        sp = exit_sale(*arrs[t], t_exit) if p["end"] == "exit" else None
        for f, mf in lst:
            pnl -= f["L"] * f["qty"] + mf
        if sp is not None:
            pnl += sp * Q - fee_taker(sp, Q)
            n_exit += 1
        else:
            pnl += lst[0][0]["payout"] * Q
    return pnl, cap, n_exit


def game_row(fills, orders, arrs, k_ns, p):
    r = {"orders": orders, "fills": len(fills), "contracts": sum(f["qty"] for f in fills)}
    for line in ("m0", "m175"):
        pnl, cap, ne = game_pnl(fills, arrs, k_ns, p, line)
        r["pnl_" + line], r["cap_" + line] = pnl, cap
    r["exits"] = ne
    r["out_q"] = sum(f["payout"] * f["qty"] for f in fills)
    r["px_q"] = sum(f["L"] * f["qty"] for f in fills)
    # pairs (M4): cycles with both teams filled
    cyc = {}
    for f in fills:
        cyc.setdefault(f["cycle"], []).append(f)
    pairs = [c for c in cyc.values() if len({f["team"] for f in c}) == 2]
    r["pairs"] = len(pairs)
    r["pair_cost"] = sum(sum(f["L"] for f in c) for c in pairs)
    pp = 0.0
    for c in pairs:
        for f in c:
            pp += (f["payout"] - f["L"]) * f["qty"] - fee_maker(f["L"], f["qty"], "m175")
    r["pair_pnl_m175"] = pp
    return r


# ---------- stats ----------
def boot_roc(pnl, cap, n_rep=2000, seed=20261004):
    rng = np.random.default_rng(seed)
    n = len(pnl)
    idx = rng.integers(0, n, size=(n_rep, n))
    s_p, s_c = pnl[idx].sum(1), cap[idx].sum(1)
    ok = s_c > 0
    roc = s_p[ok] / s_c[ok]
    return float(np.percentile(roc, 2.5)), float(np.percentile(roc, 97.5))


def sharpe_dd(daily):
    d = np.asarray(daily, float)
    sd = d.std(ddof=1) if len(d) > 1 else 0.0
    sh = float(d.mean() / sd * math.sqrt(365)) if sd > 0 else float("nan")
    cum = np.cumsum(d)
    dd = float((np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:] - cum).max()) if len(d) else 0.0
    return sh, dd


def summarize(df):
    """df: game rows (all test games, zeros included) with date, pnl_*, cap_*, contracts, orders, fills."""
    out = {"games": len(df), "games_filled": int((df["fills"] > 0).sum()), "orders": int(df["orders"].sum()),
           "fills": int(df["fills"].sum()), "contracts": int(df["contracts"].sum())}
    out["fill_rate"] = out["fills"] / out["orders"] if out["orders"] else float("nan")
    c = df["contracts"].sum()
    out["adverse_sel"] = float((df["out_q"].sum() - df["px_q"].sum()) / c) if c else float("nan")
    out["win_rate"] = float(df["out_q"].sum() / c) if c else float("nan")
    out["mean_fill_px"] = float(df["px_q"].sum() / c) if c else float("nan")
    for line in ("m0", "m175"):
        P, C = df["pnl_" + line].to_numpy(), df["cap_" + line].to_numpy()
        out["pnl_" + line] = float(P.sum())
        out["roc_" + line] = float(P.sum() / C.sum()) if C.sum() > 0 else float("nan")
        out["c_per_contract_" + line] = float(P.sum() / c * 100) if c else float("nan")
        if line == "m175":
            out["roc_ci_lo"], out["roc_ci_hi"] = boot_roc(P, C) if C.sum() > 0 else (float("nan"),) * 2
            top = np.argsort(-P)[5:]
            out["excl_top5_roc"] = float(P[top].sum() / C[top].sum()) if C[top].sum() > 0 else float("nan")
        daily = df.groupby("date")["pnl_" + line].sum()
        out["sharpe_" + line], out["maxdd_" + line] = sharpe_dd(daily.to_numpy())
    out["pairs"] = int(df["pairs"].sum())
    out["pair_mean_cost"] = float(df["pair_cost"].sum() / out["pairs"]) if out["pairs"] else float("nan")
    out["pair_pnl_m175"] = float(df["pair_pnl_m175"].sum())
    return out
