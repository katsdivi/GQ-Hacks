"""Step 2 / Decision A: does Databento carry CME's sports event contracts, and do they trade?

Every request prints its cost first and asks before spending (pass --yes to skip the prompt).

Usage:
  # 1. List every FG (NFL) / CG (college) instrument defined on a day
  python -m ingest.databento_cme list --date 2026-09-27

  # 2. Pull trades + bbo-1s for one contract over a window, count trades, save shared-format parquet
  python -m ingest.databento_cme pull --symbol <raw_symbol> \
      --start 2026-09-27T15:00 --end 2026-09-27T21:00 --game-id <game_id> [--away]

Verdict printed at the end of `pull`: PASS (>= 50 trades), THIN (< 50), NO DATA (0).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATASET = "GLBX.MDP3"
PREFIXES = ("FG", "CG")
PASS_MIN_TRADES = 50

load_dotenv(ROOT / ".env")


def client():
    import databento as db
    key = os.getenv("DATABENTO_API_KEY")
    if not key:
        sys.exit("DATABENTO_API_KEY missing from .env")
    return db.Historical(key)


def confirm_cost(c, yes: bool, **params) -> None:
    cost = c.metadata.get_cost(dataset=DATASET, **params)
    print(f"  cost of {params.get('schema')} {params.get('symbols')!s:.60}: ${cost:.4f}")
    if not yes and input("  run it? [y/N] ").strip().lower() != "y":
        sys.exit("aborted")


def cmd_list(args) -> None:
    c = client()
    start = pd.Timestamp(args.date).strftime("%Y-%m-%d")
    end = (pd.Timestamp(args.date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    params = dict(schema="definition", symbols="ALL_SYMBOLS", stype_in="raw_symbol", start=start, end=end)
    confirm_cost(c, args.yes, **params)
    defs = c.timeseries.get_range(dataset=DATASET, **params).to_df()
    print(f"  {len(defs):,} definition rows; columns: {list(defs.columns)[:12]}...")

    sym_col = "raw_symbol" if "raw_symbol" in defs.columns else "symbol"
    mask = defs[sym_col].astype(str).str.startswith(PREFIXES)
    if "asset" in defs.columns:
        mask |= defs["asset"].astype(str).str.startswith(PREFIXES)
    hits = defs[mask].drop_duplicates(sym_col)

    keep = [col for col in [sym_col, "instrument_id", "asset", "security_type", "instrument_class",
                            "expiration", "min_price_increment", "unit_of_measure"] if col in hits.columns]
    out = ROOT / "out" / f"cme_sports_defs_{start}.csv"
    out.parent.mkdir(exist_ok=True)
    hits[keep].to_csv(out, index=False)
    print(f"\n{len(hits)} FG/CG instruments on {start}. Saved {out.relative_to(ROOT)}")
    with pd.option_context("display.max_rows", 60, "display.width", 200):
        print(hits[keep].head(60).to_string(index=False))
    if hits.empty:
        print("\nNO DATA: no FG/CG symbols. Check the asset/description columns by hand, "
              "then ask the Databento rep what root the sports contracts use.")


def cmd_pull(args) -> None:
    c = client()
    base = dict(symbols=[args.symbol], stype_in="raw_symbol", start=args.start, end=args.end)

    confirm_cost(c, args.yes, schema="trades", **base)
    trades = c.timeseries.get_range(dataset=DATASET, schema="trades", **base).to_df()
    confirm_cost(c, args.yes, schema="bbo-1s", **base)
    bbo = c.timeseries.get_range(dataset=DATASET, schema="bbo-1s", **base).to_df()

    n = len(trades)
    print(f"\n{args.symbol}: {n} trades, {len(bbo)} bbo-1s rows between {args.start} and {args.end}")
    if n:
        px = trades["price"]
        print(f"  price range {px.min()} to {px.max()} (raw units; check scale before trusting the 0-1 conversion)")
        print(f"  distinct prices: {px.nunique()}, price changes: {(px.diff() != 0).sum() - 1}")
        per_min = trades.resample("1min").size()
        print(f"  trades/min: median {per_min.median():.1f}, max {per_min.max()}, "
              f"minutes with 0 trades: {(per_min == 0).sum()} of {len(per_min)}")

    verdict = "NO DATA" if n == 0 else ("PASS" if n >= PASS_MIN_TRADES else "THIN")
    print(f"\nDecision A verdict: {verdict}")

    if n and args.game_id:
        df = to_shared(trades, bbo, args.symbol, args.away, args.price_scale)
        path = ROOT / "data" / "ticks" / f"{args.game_id}_cme.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        print(f"saved {len(df):,} shared-format rows to {path.relative_to(ROOT)} (gitignored)")


def to_shared(trades: pd.DataFrame, bbo: pd.DataFrame, symbol: str, away: bool, scale: float) -> pd.DataFrame:
    """Databento frames -> shared format. Price scale is a flag on purpose: verify it on real data."""
    def conv(p: pd.Series) -> pd.Series:
        p = p.astype(float) / scale
        return (1.0 - p) if away else p

    def ts_ns(frame: pd.DataFrame) -> pd.Series:
        # to_df() indexes by ts_recv; prefer exchange time ts_event when present.
        s = frame["ts_event"] if "ts_event" in frame.columns else frame.index.to_series()
        return pd.to_datetime(s, utc=True).dt.as_unit("ns").astype("int64").to_numpy()

    # Databento side = aggressor. Buying the away contract is selling the home one.
    side_map = {"A": "buy", "B": "sell", "N": "unknown"} if away else {"A": "sell", "B": "buy", "N": "unknown"}
    rows = [pd.DataFrame({
        "ts": ts_ns(trades), "venue": "cme", "market_id": symbol, "kind": "trade",
        "price": conv(trades["price"]).to_numpy(), "size": trades["size"].astype("int64").to_numpy(),
        "side": trades["side"].map(side_map).fillna("unknown").to_numpy(),
    })]
    if len(bbo):
        bid_col, ask_col = "bid_px_00", "ask_px_00"
        bid_sz, ask_sz = "bid_sz_00", "ask_sz_00"
        b = pd.DataFrame({"ts": ts_ns(bbo), "price": conv(bbo[bid_col]).to_numpy(),
                          "size": bbo[bid_sz].astype("int64").to_numpy()})
        a = pd.DataFrame({"ts": ts_ns(bbo), "price": conv(bbo[ask_col]).to_numpy(),
                          "size": bbo[ask_sz].astype("int64").to_numpy()})
        # An away contract's bid becomes the home ask and vice versa.
        bid_kind, ask_kind = ("ask", "bid") if away else ("bid", "ask")
        rows.append(b.assign(venue="cme", market_id=symbol, kind=bid_kind, side="buy" if not away else "sell"))
        rows.append(a.assign(venue="cme", market_id=symbol, kind=ask_kind, side="sell" if not away else "buy"))
    df = pd.concat(rows, ignore_index=True)[["ts", "venue", "market_id", "kind", "price", "size", "side"]]
    df = df.dropna(subset=["price"])
    return df.sort_values("ts", kind="stable").reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", action="store_true", help="skip cost confirmation prompts")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("--date", default="2026-09-27", help="a recent Sunday")
    p_list.set_defaults(func=cmd_list)

    p_pull = sub.add_parser("pull")
    p_pull.add_argument("--symbol", required=True, help="raw_symbol from `list`")
    p_pull.add_argument("--start", required=True, help="UTC, 2h before kickoff")
    p_pull.add_argument("--end", required=True, help="UTC, 30 min after the end")
    p_pull.add_argument("--game-id", help="if set, save data/ticks/<game_id>_cme.parquet")
    p_pull.add_argument("--away", action="store_true", help="contract pays on the AWAY team: flip with 1 - p")
    p_pull.add_argument("--price-scale", type=float, default=1.0,
                        help="divide raw price by this to get 0-1 (check `list` min_price_increment)")
    p_pull.set_defaults(func=cmd_pull)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
