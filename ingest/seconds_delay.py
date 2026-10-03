"""Fetch the per-market sports taker delay for the frozen holdout polymarket.com markets.

v2 Amendment 3: the polymarket.com taker delay is a per-market value (read 2026-10-03 16:22 ET: all 112
holdout markets at 1 s; the help center's 3 s is not used). This reads ONLY the delay field from the public CLOB market endpoint
(GET clob.polymarket.com/markets/<condition_id>, field `seconds_delay`, the docs' market.trading.secondsDelay).

SEAL: the market metadata also carries prices, outcome prices, volume and resolution. Nothing but the
condition id and seconds_delay is kept; the response is dropped in memory before anything is written,
and nothing else is printed, logged, stored or hashed.

Output: data/live/holdout_seconds_delay.csv (market_id, seconds_delay, fetched_at_utc), gitignored.
Prints the sha256 prefix and value counts (3 / 1 / other / missing).

Usage: python -m ingest.seconds_delay
"""
from __future__ import annotations

import csv
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

MAP = Path("data/live/holdout_maps/polymarket_com_map.json")
OUT = Path("data/live/holdout_seconds_delay.csv")
URL = "https://clob.polymarket.com/markets/{}"


def fetch_delay(cond: str) -> int | None:
    for attempt in range(3):
        try:
            r = requests.get(URL.format(cond), timeout=20)
        except requests.RequestException:
            time.sleep(1 + attempt)
            continue
        if r.status_code == 200:
            v = r.json().get("seconds_delay")
            del r  # drop the rest of the metadata before anything else happens
            return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        time.sleep(1 + attempt)
    return None


def main() -> None:
    conds = sorted({x["condition"] for x in json.loads(MAP.read_text()).values()})
    rows = []
    for c in conds:
        d = fetch_delay(c)
        rows.append((c, "" if d is None else d, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        time.sleep(0.2)
    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["market_id", "seconds_delay", "fetched_at_utc"])
        w.writerows(rows)
    cnt = Counter("missing" if d == "" else ("3" if d == 3 else "1" if d == 1 else "other") for _, d, _ in rows)
    print(f"{OUT}: {len(rows)} markets, sha256 {hashlib.sha256(OUT.read_bytes()).hexdigest()[:16]}")
    print({k: cnt.get(k, 0) for k in ("3", "1", "other", "missing")})
    others = Counter(d for _, d, _ in rows if d not in ("", 1, 3))
    if others:
        print("other values:", dict(others))


if __name__ == "__main__":
    main()
