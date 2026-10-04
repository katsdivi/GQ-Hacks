"""Book report on TRAINING (v3 Amendment 1 sections 1 and 2): Strategy A (theta 0.80), Strategy B (selected
setting) and the combined Kalshi book, 10 contracts per trade each. Holdout never loaded.

Inputs (from run_strategy_a.py / run_strategy_b.py, gitignored): out/strategy_a/rows.parquet,
out/strategy_b/trades.parquet, trades_costs_x2.parquet, summary.csv; Ken French daily factors
(data/raw/french/factors_daily.csv, ingest/french_factors.py).

Daily P&L (ET calendar day): A books each trade on its settlement date, approximated as the ET date of ESPN
kickoff + 4 h (Kalshi settlement times are not stored); B books each trade on the ET date of its exit fill.
Season days only: every calendar day from the first to the last day with a training game (A or B), zeros kept.
Capital base (v3 A1, PROPOSED): the maximum capital committed at once (entry price x 10 + entry fee, over all
open positions; A held from fill to kickoff + 4 h, B from entry fill to exit fill; a P(home) sell costs
1 - P per contract). Each book uses its own base; returns = daily P&L / base.
Metrics: annualized return (mean x 365), vol (sd x sqrt 365), Sharpe (ratio; also with Newey-West 5-lag
long-run sd), max drawdown, turnover, skew, worst month, by year, costs x2, Ken French regression (Mkt-RF, HML,
UMD, intercept, Newey-West 5 lags; P&L on a non-factor day moves to the next factor day), A vs B correlation
on days where at least one traded, deflated Sharpe (own grid and the 21-variant total). Every number goes to
results/numbers.json as key -> {value, source}. Equity curve: results/equity_training.png.

Usage: python report_book.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import run_strategy_a as RA  # noqa: E402

ET = "America/New_York"
A_THETA = 0.80
NW_LAGS = 5
SRC = "report_book.py"
RES = Path("results")
QTY = 10


def a_trades(rows: pd.DataFrame, theta: float, placebo: bool = False) -> pd.DataFrame:
    e = rows[rows["entered"].astype(bool) & (rows["theta"] == theta) & (rows["placebo"].astype(bool) == placebo)]
    e = e.copy()
    rel = pd.to_datetime(e["kickoff"], utc=True) + pd.Timedelta(hours=4)
    e["day"] = rel.dt.tz_convert(ET).dt.date
    e["open_ns"] = e["fill_ts"].astype("int64")
    e["close_ns"] = rel.dt.as_unit("ns").astype("int64")      # ns under pandas 2 and 3 (pandas 3 defaults to us)
    e["capital"] = e["fill_price"] * QTY + e["fee_webull"]
    e["contracts"] = QTY
    e["notional"] = e["fill_price"] * QTY
    return e


def b_trades(t: pd.DataFrame, setting) -> pd.DataFrame:
    k, m, T = setting
    f = t[t["filled"].astype(bool) & (t["k"] == k) & (t["m"] == m) & (t["T"] == T)].copy()
    f["day"] = pd.to_datetime(f["exit_fill_ts"].astype("int64"), utc=True).dt.tz_convert(ET).dt.date
    cost_in = np.where(f["direction"] == 1, f["entry_px"], 1 - f["entry_px"])
    f["capital"] = cost_in * QTY + f["fee_webull"] / 2
    f["open_ns"], f["close_ns"] = f["entry_fill_ts"].astype("int64"), f["exit_fill_ts"].astype("int64")
    f["contracts"] = 2 * QTY
    f["notional"] = (f["entry_px"] + f["exit_px"]) * QTY
    return f


def max_capital(*books: pd.DataFrame) -> float:
    ev = pd.concat([pd.DataFrame({"t": b["open_ns"], "c": b["capital"]}) for b in books] +
                   [pd.DataFrame({"t": b["close_ns"], "c": -b["capital"]}) for b in books])
    ev = ev.sort_values(["t", "c"])                       # releases before openings at the same instant
    return float(ev["c"].cumsum().max())


def daily(book: pd.DataFrame, days: pd.DatetimeIndex, col: str = "pnl_webull") -> pd.Series:
    return book.groupby("day")[col].sum().reindex(days.date, fill_value=0.0).astype(float)


def nw_sd(x: np.ndarray, lags: int = NW_LAGS) -> float:
    x = x - x.mean()
    n = len(x)
    v = (x @ x) / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (x[l:] @ x[:-l]) / n
    return float(np.sqrt(max(v, 0.0)))


def metrics(pnl: pd.Series, base: float, book: pd.DataFrame) -> dict:
    r = pnl / base
    eq = pnl.cumsum()
    dd = float((eq.cummax() - eq).max())
    month = pnl.groupby(pd.to_datetime(pd.Series(pnl.index)).dt.to_period("M").values).sum()
    year = pnl.groupby(pd.to_datetime(pd.Series(pnl.index)).dt.year.values).sum()
    sd = r.std(ddof=1)
    out = {"days": len(r), "capital_base": base, "pnl_total": float(pnl.sum()),
           "ann_return": float(r.mean() * 365), "ann_vol": float(sd * np.sqrt(365)),
           "sharpe": float(r.mean() / sd * np.sqrt(365)) if sd > 0 else float("nan"),
           "sharpe_nw5": float(r.mean() / nw_sd(r.to_numpy()) * np.sqrt(365)) if sd > 0 else float("nan"),
           "max_drawdown_dollars": dd, "max_drawdown_of_base": dd / base,
           "turnover_contracts_per_day": float(book["contracts"].sum() / len(r)),
           "turnover_notional_per_day": float(book["notional"].sum() / len(r)),
           "skew_daily": float(skew(r, bias=False)), "worst_month": str(month.idxmin()),
           "worst_month_pnl": float(month.min()), "n_trades": len(book)}
    for y, v in year.items():
        out[f"pnl_{y}"] = float(v)
    return out


def ols_nw(y: np.ndarray, X: np.ndarray, lags: int = NW_LAGS):
    """OLS with Newey-West (Bartlett) HAC standard errors. Returns (params, tvalues, r_squared)."""
    n = len(y)
    xtx_inv = np.linalg.inv(X.T @ X)
    b = xtx_inv @ X.T @ y
    u = y - X @ b
    xu = X * u[:, None]
    S = xu.T @ xu
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1)
        g = xu[l:].T @ xu[:-l]
        S += w * (g + g.T)
    cov = xtx_inv @ S @ xtx_inv
    r2 = 1 - (u @ u) / ((y - y.mean()) @ (y - y.mean()))
    return b, b / np.sqrt(np.diag(cov)), float(r2)


def french(pnl: pd.Series, base: float, fac: pd.DataFrame) -> dict:
    """Regress daily returns on Mkt-RF, HML, UMD with NW(5) errors; non-factor days roll to the next factor day."""
    f = fac.set_index("date").sort_index()
    days = pd.to_datetime(pd.Series(pnl.index))
    pos = f.index.searchsorted(days, side="left")
    ok = pos < len(f)
    mapped = pd.Series(pnl.to_numpy()[ok], index=f.index[pos[ok]]).groupby(level=0).sum()
    span = f.loc[mapped.index.min():mapped.index.max()]
    y = mapped.reindex(span.index, fill_value=0.0) / base
    X = np.column_stack([np.ones(len(span)), span[["mkt_rf", "hml", "umd"]].to_numpy()])
    params, tvals, r2 = ols_nw(y.to_numpy(float), X)
    names = ["alpha_daily", "beta_mkt_rf", "beta_hml", "beta_umd"]
    out = {n: float(v) for n, v in zip(names, params)}
    out.update({f"t_{n}": float(v) for n, v in zip(names, tvals)})
    out.update(r_squared=r2, n_factor_days=int(len(y)),
               last_factor_date=str(f.index.max().date()))
    return out


def deflated_sharpe(r: np.ndarray, trial_srs: list[float], n_trials: int) -> float:
    """Bailey and Lopez de Prado (2014), daily (non-annualized) Sharpe."""
    sr = r.mean() / r.std(ddof=1)
    if n_trials > 1:
        v = float(np.var(trial_srs, ddof=1)) if len(trial_srs) > 1 else 0.0
        g = 0.5772156649
        sr0 = np.sqrt(v) * ((1 - g) * norm.ppf(1 - 1 / n_trials) + g * norm.ppf(1 - 1 / (n_trials * np.e)))
    else:
        sr0 = 0.0
    g3, g4 = skew(r, bias=False), kurtosis(r, fisher=False, bias=False)
    den = np.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2, 1e-12))
    return float(norm.cdf((sr - sr0) * np.sqrt(len(r) - 1) / den))


def build(rows: pd.DataFrame, bt: pd.DataFrame, b2: pd.DataFrame, sel, game_kickoffs: pd.Series, fac: pd.DataFrame,
          res_dir: Path, prefix: str = "", label: str = "Training", bases: dict | None = None,
          trial_srs: dict | None = None, png: str = "equity_training.png") -> tuple[dict, dict, dict]:
    """All book numbers for one sample. prefix "" = training keys, "OOS." = test keys. bases: the training
    capital bases (v3 A1: fixed from training and reused on the test); None = compute here (training).
    trial_srs: {"A": [...], "B": [...], "all": [...]} training trial Sharpes for the deflated Sharpe; None =
    compute here (training). Returns (numbers, bases, trial_srs)."""
    import strategy_b as B
    res_dir.mkdir(parents=True, exist_ok=True)
    A = a_trades(rows, A_THETA)
    Bk = b_trades(bt, sel)
    gd = pd.to_datetime(game_kickoffs, utc=True).dt.tz_convert(ET).dt.date
    first = min([gd.min()] + ([A["day"].min()] if len(A) else []) + ([Bk["day"].min()] if len(Bk) else []))
    last = max([gd.max()] + ([A["day"].max()] if len(A) else []) + ([Bk["day"].max()] if len(Bk) else []))
    days = pd.date_range(first, last, freq="D")
    a_p, b_p = daily(A, days), daily(Bk, days)
    c_p = a_p + b_p
    C = pd.concat([A[["open_ns", "close_ns", "capital", "contracts", "notional"]],
                   Bk[["open_ns", "close_ns", "capital", "contracts", "notional"]]])
    if bases is None:
        bases = {"A": max_capital(A), "B": max_capital(Bk), "combined": max_capital(A, Bk)}
    num: dict = {}

    def put(key, val):
        num[prefix + key] = {"value": val, "source": SRC}

    put("season_first_day", str(first))
    put("season_last_day", str(last))
    put("A.theta", A_THETA)
    put("B.selected_setting", {"k": sel[0], "m": sel[1], "T": sel[2]})
    put("capital_bases_from_training", bases)
    B_DROP = {"capital_base", "ann_return", "ann_vol", "max_drawdown_of_base"}   # meaningless under B's $43 base
    fac_last = pd.Timestamp(fac["date"].max()).date()
    for name, p, bk in (("A", a_p, A), ("B", b_p, Bk), ("combined", c_p, C)):
        if len(bk) == 0 or p.std(ddof=1) == 0:
            put(f"{name}.n_trades", len(bk))
            continue
        for k, v in metrics(p, bases[name], bk).items():
            if name == "B" and k in B_DROP:
                continue
            put(f"{name}.{k}", v)
        if last > fac_last:      # v3 A1: not estimated on partial factor data
            put(f"{name}.french", f"not available (French files end {fac_last}, sample ends {last})")
            continue
        for k, v in french(p, bases[name], fac).items():
            if name == "B" and k in ("alpha_daily", "beta_mkt_rf", "beta_hml", "beta_umd"):
                continue                       # levels scale with B's $43 base; t-stats and R^2 do not
            put(f"{name}.french.{k}", v)
    for line in ("webull", "direct"):
        if len(Bk):
            put(f"B.edge_{line}_cents_per_contract", float(Bk[f"pnl_{line}"].sum() / (QTY * len(Bk)) * 100))
    put("B.note", "B is reported per contract (cents/contract) and by Sharpe only: under the PROPOSED capital base "
                  "(max capital committed at once, $43 for B on training) its return levels are meaningless")
    # costs x2
    A2 = RA.costs_x2(A).assign(day=A["day"]) if len(A) else A
    B2 = b_trades(b2, sel)
    for name, p, bk in (("A", daily(A2, days), A), ("B", daily(B2, days), Bk),
                        ("combined", daily(A2, days) + daily(B2, days), C)):
        if len(bk) == 0 or p.std(ddof=1) == 0:
            continue
        m2 = metrics(p, bases[name], bk)
        keys = ("pnl_total", "sharpe", "sharpe_nw5", "max_drawdown_dollars") if name == "B" else \
            ("pnl_total", "ann_return", "ann_vol", "sharpe", "sharpe_nw5", "max_drawdown_dollars")
        for k in keys:
            put(f"{name}.costs_x2.{k}", m2[k])
    for line in ("webull", "direct"):
        if len(B2):
            put(f"B.costs_x2.edge_{line}_cents_per_contract", float(B2[f"pnl_{line}"].sum() / (QTY * len(B2)) * 100))
    # A vs B correlation on days where at least one traded
    traded = pd.Series(days.date).isin(set(A["day"]) | set(Bk["day"])).to_numpy()
    put("corr_A_B.days_either_traded", int(traded.sum()))
    if traded.sum() > 2 and a_p[traded].std() > 0 and b_p[traded].std() > 0:
        put("corr_A_B.pearson", float(np.corrcoef(a_p.to_numpy()[traded], b_p.to_numpy()[traded])[0, 1]))
    # deflated Sharpe: trial Sharpes of A's 3 thetas, B's 8 settings, the combined book (training trials)
    sr = lambda p: float(p.mean() / p.std(ddof=1)) if p.std(ddof=1) > 0 else 0.0
    if trial_srs is None:
        a_srs = [sr(daily(a_trades(rows, th), days)) for th in (0.70, 0.80, 0.90)]
        b_srs = [sr(daily(b_trades(bt, s), days)) for s in B.SETTINGS]
        trial_srs = {"A": a_srs, "B": b_srs, "all": a_srs + b_srs + [sr(c_p)]}
    for name, p, own, n_own in (("A", a_p, trial_srs["A"], 3), ("B", b_p, trial_srs["B"], 8),
                                ("combined", c_p, [0.0], 1)):
        if p.std(ddof=1) == 0:
            continue
        r = (p / bases[name]).to_numpy()
        put(f"{name}.sharpe_daily", sr(p))
        put(f"{name}.deflated_sharpe_own_grid", deflated_sharpe(r, own, n_own))
        put(f"{name}.deflated_sharpe_total_21", deflated_sharpe(r, trial_srs["all"], 21))
    put("deflated_sharpe.note", "total-21 deflated Sharpe: trial-Sharpe variance from the 12 TRAINING trials with "
                                "daily series (A 3, B 8, combined 1; the other 9 of the 21 have no daily series); "
                                "B's 8 trials, all strongly negative, dominate that variance")
    # equity curve
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for name, p in (("A (theta 0.80)", a_p), (f"B {sel}", b_p), ("combined", c_p)):
        ax.plot(pd.to_datetime(pd.Series(p.index)), p.cumsum().to_numpy(), label=name)
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_title(f"{label} equity curves, 10 contracts per trade, Webull costs")
    ax.set_ylabel("cumulative P&L ($)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(res_dir / png, dpi=130)
    put("equity_curve_png", str(res_dir / png))
    return num, bases, trial_srs


def write_numbers(num: dict, path: Path = RES / "numbers.json", replace_prefix: str | None = None) -> None:
    """Merge into numbers.json; replace_prefix drops existing keys that start with it (or all non-OOS keys if "")."""
    old = json.loads(path.read_text()) if path.exists() else {}
    if replace_prefix == "":
        old = {k: v for k, v in old.items() if k.startswith("OOS.")}
    elif replace_prefix:
        old = {k: v for k, v in old.items() if not k.startswith(replace_prefix)}
    old.update(num)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(old, indent=1, default=str))


def training_inputs():
    import strategy_b as B
    rows = pd.read_parquet("out/strategy_a/rows.parquet")
    bt = pd.read_parquet("out/strategy_b/trades.parquet")
    b2 = pd.read_parquet("out/strategy_b/trades_costs_x2.parquet")
    sel = B.select_setting(pd.read_csv("out/strategy_b/summary.csv"))
    kos = pd.concat([pd.Series(pd.to_datetime(rows["kickoff"], utc=True)),
                     pd.to_datetime(pd.read_csv("out/strategy_b/b_games_espn.csv")["espn_kickoff"], utc=True)],
                    ignore_index=True)
    return rows, bt, b2, sel, kos


def main() -> None:
    rows, bt, b2, sel, kos = training_inputs()
    fac = pd.read_csv("data/raw/french/factors_daily.csv", parse_dates=["date"])
    num, _, _ = build(rows, bt, b2, sel, kos, fac, RES)
    num = {("training." + k if k.startswith("season_") else k): v for k, v in num.items()}
    write_numbers(num, replace_prefix="")
    for k, v in num.items():
        print(f"{k}: {v['value']}")


if __name__ == "__main__":
    main()
