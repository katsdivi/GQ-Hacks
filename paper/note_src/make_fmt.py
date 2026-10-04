"""Write fmt.tex: display-formatted copies (prefix f_) of keys used in main.tex.

Reads only numbers.tex, extra.tex and phantom.tex (themselves generated from committed files),
so every formatted value traces to the same source as its raw key. Rounding only; no arithmetic
except unit changes stated per rule (share -> percent, dollars -> cents for B's k).
Missing raw keys are skipped and reported; main.tex then shows a red box for them.

Usage: python3 make_fmt.py
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = ("numbers.tex", "extra.tex", "phantom.tex")
DEF = re.compile(r"\\defval\{([^}]*)\}\{(.*)\}\s*(?:%.*)?$")


def load() -> dict[str, str]:
    out: dict[str, str] = {}
    for fn in SRC:
        p = HERE / fn
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            m = DEF.match(line.strip())
            if m:
                out[m.group(1)] = m.group(2)
    return out


def num(v: str) -> float:
    return float(v.replace("{,}", "").replace(",", "").replace("\\%", ""))


def minus(s: str) -> str:
    return "$-$" + s[1:] if s.startswith("-") else s


def thousands(x: float, d: int) -> str:
    s = f"{x:,.{d}f}".replace(",", "{,}")
    return minus(s)


RULES = {
    "lag1": lambda v: minus(f"{num(v):.1f}"),
    "r3": lambda v: minus(f"{num(v):.3f}"),
    "c2": lambda v: minus(f"{num(v):.2f}"),
    "sh2": lambda v: minus(f"{num(v):.2f}"),
    "pct1": lambda v: f"{100 * num(v):.1f}\\%",
    "theta": lambda v: f"{num(v):.2f}",
    "kcents": lambda v: f"{100 * num(v):.0f}",
    "usd0": lambda v: thousands(num(v), 0),
    "pct0": lambda v: thousands(100 * num(v), 0) + "\\%",
    "usd1": lambda v: thousands(num(v), 1),
    "int": lambda v: thousands(num(v), 0),
    "s2": lambda v: f"{num(v):.2f}",
    "s3": lambda v: f"{num(v):.3f}",
    "ms": lambda v: f"{1000 * num(v):.0f}",
    "dec": lambda v: v[:1].upper() + v[1:],
}

# key -> rule
KEYS = {
    # lead test
    "OOS_lead_polymarket_com_detail_median_corrected_lag_s": "lag1",
    "OOS_lead_polymarket_com_detail_placebo_median_s": "lag1",
    "OOS_lead_polymarket_com_detail_share_positive": "pct1",
    "OOS_lead_polymarket_com_decision": "dec",
    "OOS_lead_Polymarket_US_detail_median_corrected_lag_s": "lag1",
    "OOS_lead_Polymarket_US_detail_placebo_median_s": "lag1",
    "OOS_lead_Polymarket_US_detail_share_positive": "pct1",
    "OOS_lead_Polymarket_US_detail_holm_level": "s3",
    "OOS_lead_Polymarket_US_decision": "dec",
    "phantom_pmcom_robust_result": "dec",
    "phantom_pmus_robust_result": "dec",
    "diag_receipt_delay_kalshi_median_s": "ms",
    "diag_receipt_delay_polymarket_median_s": "ms",
    "diag_receipt_delay_polymarket_p90_s": "ms",
    "OOS_orientation_gate_median": "s2",
    # Polymarket US diagnostics
    "diag_pmus_quote_change_interval_median_of_game_medians_s": "lag1",
    "diag_pmus_receipt_minus_venue_delay_median_s": "lag1",
    "diag_pmus_partial_run_1p0s_share_both_confirmed": "pct1",
    "diag_pmus_partial_run_1p0s_confirmed_mean_c": "c2",
    "diag_pmus_partial_run_1p0s_confirmed_ci_lo": "c2",
    "diag_pmus_partial_run_1p0s_confirmed_ci_hi": "c2",
    "diag_b_excl_big_diff_webull_mean_c": "c2",
    # Strategy A
    "A_theta": "theta",
    "A_roc_webull": "r3",
    "A_roc_direct": "r3",
    "OOS_A_roc_webull": "r3",
    "OOS_A_roc_webull_ci_0": "r3",
    "OOS_A_roc_webull_ci_1": "r3",
    "OOS_A_roc_direct": "r3",
    "OOS_A_fail_3_league_roc_NFL": "r3",
    "A_placebo_roc_webull": "r3",
    "OOS_A_maker_win_minus_fill": "r3",
    "OOS_A_maker_roc_webull": "r3",
    "OOS_A_maker_roc_webull_ci_0": "r3",
    "OOS_A_maker_roc_webull_ci_1": "r3",
    "plateau_A_roc_webull_070": "r3",
    "plateau_A_roc_webull_090": "r3",
    "A_french_t_alpha_daily": "s2",
    "A_french_r_squared": "s2",
    # Strategy B
    "B_selected_setting_k": "kcents",
    "B_edge_webull_cents_per_contract": "c2",
    "OOS_B_edge_webull_cents": "c2",
    "OOS_B_edge_webull_ci_0": "c2",
    "OOS_B_edge_webull_ci_1": "c2",
    "OOS_B_edge_direct_cents": "c2",
    "OOS_B_costs_x2_edge_webull_cents_per_contract": "c2",
    # results table: training (no prefix) and holdout (OOS_)
    **{f"{p}{s}_{m}": r for p in ("", "OOS_") for s in ("A", "B", "combined") for m, r in (
        ("pnl_total", "usd0"), ("ann_vol", "pct0"), ("sharpe", "sh2"), ("max_drawdown_dollars", "usd0"),
        ("turnover_contracts_per_day", "usd0"), ("skew_daily", "sh2"), ("worst_month_pnl", "usd0"),
        ("ann_return", "pct0"), ("costs_x2_sharpe", "sh2"), ("capital_base", "usd0"))},
    "OOS_combined_max_drawdown_of_base": "s2",
    # deflated Sharpe at own grid (training, A)
    "A_deflated_sharpe_own_grid": "s2",
    # post-hoc
    "posthoc_posbook_roc_mean": "r3",
    "posthoc_posbook_roc_ci_0": "r3",
    "posthoc_posbook_roc_ci_1": "r3",
    "posthoc_idea1_violation_duration_median_s": "s3",
    "posthoc_idea11_L1_original_c_per_contract": "c2",
    "posthoc_idea11_L1_corrected_hold_c_per_contract": "c2",
    "posthoc_idea11_a2_venue_iqr_s": "ms",
    "posthoc_idea12_k0_03_signal_roc": "r3",
}


def main() -> None:
    raw = load()
    lines = ["% GENERATED by make_fmt.py from numbers.tex, extra.tex, phantom.tex; do not edit."]
    missing = []
    for k, rule in KEYS.items():
        if k not in raw:
            missing.append(k)
            continue
        v = raw[k]
        try:
            fv = RULES[rule](v)
        except ValueError:
            fv = v  # non-numeric (e.g. "n/a"): pass through unchanged
        lines.append(f"\\defval{{f_{k}}}{{{fv}}}  % {rule}({k} = {v})")
    (HERE / "fmt.tex").write_text("\n".join(lines) + "\n")
    print(f"fmt.tex: {len(lines) - 1} keys; raw keys missing: {len(missing)}")
    for k in missing:
        print("  missing raw key:", k)


if __name__ == "__main__":
    main()
