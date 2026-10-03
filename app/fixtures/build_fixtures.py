"""Create tiny, explicitly synthetic UI fixtures without running a strategy.

Run from the repository root: python app/fixtures/build_fixtures.py.
Only writes into this directory. Marker prices copy the sample quote midpoint
so the fixture demonstrates alignment, not strategy quality or profitability.
"""
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    """Choose a few sample timestamps and attach hand-authored display values."""
    ticks = pd.read_parquet(ROOT / "data/ticks/sample.parquet")
    quotes = ticks[(ticks.venue == "kalshi") & ticks.kind.isin(["bid", "ask"])]
    book = quotes.pivot_table(index="ts", columns="kind", values="price", aggfunc="last").ffill()
    midpoints = (book.bid + book.ask) / 2
    # These are fictional actions and dollar balances, never calculated returns.
    actions = ["enter_long", "exit", "enter_short", "exit"]
    balances = [0.0, 0.02, 0.02, -0.01]
    rows = []
    for position, action, balance in zip([60, 90, 120, 150], actions, balances):
        rows.append(dict(ts=int(midpoints.index[position]), action=action, venue="kalshi",
                         price=float(midpoints.iloc[position]), qty=1, fee=0.02, pnl_cum=balance))
    pd.DataFrame(rows).to_parquet(HERE / "sample_signals.parquet", index=False)


if __name__ == "__main__":
    main()
