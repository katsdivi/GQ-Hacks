"""h1 (exploratory, post-run, LIVE): cache check of the Polymarket US endpoint the collector polled for book data.

Endpoint: GET https://gateway.polymarket.us/v1/markets?slug=...&limit=100 (collector/run.py PolymarketUS.poll_batch;
public, no key). Step 1: 3 requests with the collector's batch of slugs (the current data/live/polymarket_us_map.json),
all response headers printed. Step 2: one market polled every 2 s for 120 s; stops at the first HTTP 429.
Writes results/holdout_diag/h1_headers.txt, h1_poll.csv, h1_summary.md.

Usage: python scripts/holdout_diag_h1.py [--staleline ../staleline]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import pandas as pd
import requests

G = "https://gateway.polymarket.us"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "holdout_diag"
CACHE_HDRS = ("cache-control", "age", "expires", "etag", "last-modified", "cf-cache-status", "x-cache", "via",
              "x-cache-hits", "surrogate-control", "cdn-cache-control", "vary", "date", "server")
REDACT = ("authorization", "set-cookie", "cookie", "x-api-key")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staleline", type=Path, default=ROOT.parent / "staleline")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    slugs = sorted(json.load(open(a.staleline / "data" / "live" / "polymarket_us_map.json")))
    s = requests.Session()
    lines = [f"exploratory, post-run. GET {G}/v1/markets with {len(slugs)} slugs + limit=100 (the collector's batch call)"]
    for k in range(3):
        r = s.get(G + "/v1/markets", params=[("slug", x) for x in slugs] + [("limit", 100)], timeout=15)
        lines.append(f"\n== request {k + 1} at {pd.Timestamp.now(tz='America/New_York'):%H:%M:%S.%f} ET: HTTP {r.status_code}, "
                     f"{len(r.content)} bytes, elapsed {r.elapsed.total_seconds():.3f} s")
        for h, v in r.headers.items():
            lines.append(f"  {h}: {'<redacted>' if h.lower() in REDACT else v}")
        if k == 0 and r.ok:
            ms = r.json().get("markets", [])
            lines.append(f"  markets returned: {len(ms)}; top-level keys: {sorted(r.json().keys())}")
            if ms:
                lines.append(f"  market keys: {sorted(ms[0].keys())}")
                lines.append(f"  bestBidQuote: {ms[0].get('bestBidQuote')}; bestAskQuote: {ms[0].get('bestAskQuote')}")
        if r.status_code == 429:
            lines.append("  STOP: HTTP 429")
            break
        time.sleep(2)
    (OUT / "h1_headers.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    slug = "aec-nfl-ind-was-2026-10-04" if "aec-nfl-ind-was-2026-10-04" in slugs else slugs[0]
    rows, prev, t_end = [], None, time.monotonic() + 120
    while time.monotonic() < t_end:
        t0 = time.time_ns()
        try:
            r = s.get(G + "/v1/markets", params=[("slug", slug), ("limit", 100)], timeout=15)
        except requests.RequestException as e:
            rows.append({"t_send_ns": t0, "status": type(e).__name__})
            time.sleep(2)
            continue
        t1 = time.time_ns()
        body = r.content
        m = (r.json().get("markets") or [{}])[0] if r.ok else {}
        quote = (json.dumps(m.get("bestBidQuote"), sort_keys=True), json.dumps(m.get("bestAskQuote"), sort_keys=True))
        h = hashlib.sha256(body).hexdigest()[:16]
        rows.append({"t_send_ns": t0, "t_recv_ns": t1, "status": r.status_code, "elapsed_s": r.elapsed.total_seconds(),
                     "body_sha16": h, "body_changed": prev is not None and h != prev[0],
                     "quote_changed": prev is not None and quote != prev[1], "best_bid": quote[0], "best_ask": quote[1],
                     **{f"h_{k}": r.headers.get(k) for k in ("age", "cache-control", "etag", "cf-cache-status", "x-cache", "date")}})
        prev = (h, quote)
        if r.status_code == 429:
            print("STOP: HTTP 429 in the poll loop")
            break
        time.sleep(max(0.0, 2.0 - (time.time_ns() - t0) / 1e9))
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "h1_poll.csv", index=False)
    ok = d[d["status"] == 200]
    ch = ok[ok["body_changed"]]
    iv = ch["t_recv_ns"].diff().dropna() / 1e9
    qch = ok[ok["quote_changed"]]
    summ = [f"# h1 poll (exploratory, post-run, live {pd.Timestamp.now(tz='America/New_York'):%Y-%m-%d %H:%M} ET)", "",
            f"- market: {slug}; {len(d)} requests every 2 s for 120 s; statuses: {d['status'].value_counts().to_dict()}",
            f"- response time (elapsed) median {ok['elapsed_s'].median():.3f} s, max {ok['elapsed_s'].max():.3f} s",
            f"- body changed on {len(ch)} of {len(ok) - 1} consecutive pairs; best bid/ask changed on {len(qch)}",
            f"- intervals between body changes (s): " + (f"median {iv.median():.1f}, min {iv.min():.1f}, max {iv.max():.1f}, n {len(iv)}" if len(iv) else "n/a (fewer than 2 changes)"),
            f"- distinct Age header values: {sorted(ok['h_age'].dropna().unique().tolist())[:20]}",
            f"- Cache-Control values: {ok['h_cache-control'].dropna().unique().tolist()}",
            f"- CF-Cache-Status values: {ok['h_cf-cache-status'].dropna().unique().tolist()}; X-Cache: {ok['h_x-cache'].dropna().unique().tolist()}",
            f"- distinct ETags: {ok['h_etag'].nunique()}"]
    (OUT / "h1_summary.md").write_text("\n".join(summ) + "\n")
    print("\n".join(summ))


if __name__ == "__main__":
    main()
