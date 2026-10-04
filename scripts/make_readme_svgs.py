"""Build the animated SVGs used by README.md (assets/readme/*.svg).

Schematic SVGs about HYPOTHESIS_v4 (v4 timeline, story cards, pipeline). They quote only facts from committed files:
HYPOTHESIS_v4.md (main 94aa1a0), posthoc-mm-v4 1d3d68a, posthoc-mm-signal 863eb69.
"Before v4" graphics (story_v3, hero, stats, cache, latency) are about v1 to v3 and say v3 on their face. latency.svg
reads every plotted value from committed CSVs; stats.svg reads lead_decisions.json and numbers.json.

Usage: python scripts/make_readme_svgs.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "readme"

MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

# surfaces and ink (dark card; reads the same on GitHub light and dark)
BG, BG2, LINE, GRID = "#0d1117", "#161b22", "#30363d", "#21262d"
INK, INK2, INK3 = "#e6edf3", "#9da7b3", "#6e7681"
NEON_M, NEON_C = "#e040fb", "#00e5ff"  # decorative, matches the capsule banner
# chart series (validated: dataviz validate_palette.js, dark, surface #0d1117, all checks pass)
C_PM, C_US, C_CONF = "#ea580c", "#0891b2", "#c026d3"

BASE_CSS = f"""
text {{ font-family: {MONO}; }}
.sans {{ font-family: {SANS}; }}
.ink {{ fill: {INK}; }} .ink2 {{ fill: {INK2}; }} .ink3 {{ fill: {INK3}; }}
@keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(14px); }} to {{ opacity: 1; transform: translateY(0); }} }}
@keyframes draw {{ from {{ stroke-dashoffset: 1; }} to {{ stroke-dashoffset: 0; }} }}
@keyframes blink {{ 0%, 49% {{ opacity: 1; }} 50%, 100% {{ opacity: 0; }} }}
@keyframes pulse {{ 0%, 100% {{ opacity: .25; }} 50% {{ opacity: 1; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
"""


def frame(w: int, h: int, body: str, css: str = "", title: str = "") -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{title}">
<title>{title}</title>
<defs>
  <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
    <path d="M24 0H0V24" fill="none" stroke="{GRID}" stroke-width="1"/>
  </pattern>
  <linearGradient id="edge" x1="0" x2="1">
    <stop offset="0" stop-color="{NEON_M}"/><stop offset="1" stop-color="{NEON_C}"/>
  </linearGradient>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<style>{BASE_CSS}{css}</style>
<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="{BG}" stroke="{LINE}"/>
<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="url(#grid)" opacity=".55"/>
<rect x="24" y="1" width="{w-48}" height="2" fill="url(#edge)" opacity=".9"/>
{body}
</svg>
"""


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")



# ───────────────────────────── story (3 cards) ─────────────────────────────
def story() -> str:
    return _cards([
        ("01", "THE GAP", NEON_M, ["Taking liquidity does not", "pay after costs.", "Someone is paid to supply",
                                   "it. Is it a patient maker?"], "bolt"),
        ("02", "THE BET", "#ffb86b", ["Join the best bid and ask.", "Let recreational sports", "flow trade into us.",
                                      "Arm B waits for 3 c spreads."], "scope"),
        ("03", "THE TEST", NEON_C, ["Frozen on main Oct 4.", "Test set 2: Oct 8 to 12.", "Run once, Holm across venues.",
                                    "High risk, high reward."], "lock"),
    ], "HYPOTHESIS_v4: the gap, the bet, the test")


def story_v3() -> str:
    """Before v4 (not v4): the v1 to v3 lead-lag study in three cards. No numbers beyond lead_decisions.json."""
    return _cards([
        ("01", "v3 BET", NEON_M, ["A touchdown happens.", "One venue reprices first.", "If another lags by seconds,",
                                  "buy its stale price."], "bolt"),
        ("02", "v3 TEST", "#ffb86b", ["Record 3 venues live.", "Freeze every rule in git.", "Tune on games before Aug 1.",
                                      "Open the sealed holdout once."], "lock"),
        ("03", "v3 VERDICT", NEON_C, ["Kalshi = polymarket.com (0.0 s).", "Polymarket US 'lag' = a cache.",
                                      "Every v3 strategy lost after fees.", "566 trials. No real edge."], "scope"),
    ], "Before v4 (not v4): the v1 to v3 bet, test and verdict")


def _cards(cards, title) -> str:
    w, h = 1200, 330
    icons = {
        "bolt": '<path d="M14 0 L2 22 H12 L8 40 L22 14 H12 Z" fill="none" stroke-width="2.5" stroke-linejoin="round"/>',
        "lock": '<rect x="2" y="16" width="26" height="22" rx="4" fill="none" stroke-width="2.5"/>'
                '<path d="M8 16 V10 a7 7 0 0 1 14 0 V16" fill="none" stroke-width="2.5"/><circle cx="15" cy="27" r="3"/>',
        "scope": '<circle cx="15" cy="15" r="12" fill="none" stroke-width="2.5"/><path d="M24 24 L36 36" stroke-width="3" '
                 'stroke-linecap="round"/><path d="M9 15 L14 20 L22 10" fill="none" stroke-width="2.5"/>',
    }
    css = ".card { animation: fadeUp .8s cubic-bezier(.2,.7,.2,1) both; }"
    body = ""
    for i, (num, ttl, col, lines, icon) in enumerate(cards):
        x = 32 + i * 384
        txt = "".join(f'<text x="{x + 28}" y="{170 + j * 30}" font-size="17" class="ink sans">{esc(s)}</text>'
                      for j, s in enumerate(lines))
        body += f"""
<g class="card" style="animation-delay:{.15 + i * .45:.2f}s">
  <rect x="{x}" y="34" width="360" height="262" rx="14" fill="{BG2}" stroke="{LINE}"/>
  <rect x="{x}" y="34" width="360" height="4" rx="2" fill="{col}"/>
  <text x="{x + 28}" y="96" font-size="40" font-weight="800" fill="{col}" filter="url(#glow)">{num}</text>
  <text x="{x + 100}" y="92" font-size="18" font-weight="700" letter-spacing="3" class="ink">{ttl}</text>
  <g transform="translate({x + 300},62)" stroke="{col}" fill="{col}">{icons[icon]}</g>
  <line x1="{x + 28}" y1="124" x2="{x + 332}" y2="124" stroke="{LINE}"/>
  {txt}
</g>"""
    return frame(w, h, body, css, title)






# ───────────────────────────── pipeline ─────────────────────────────
def pipeline() -> str:
    w, h = 1200, 300
    css = f"""
.flow {{ stroke-dasharray: 6 10; animation: dash 1s linear infinite; }}
@keyframes dash {{ to {{ stroke-dashoffset: -16; }} }}
.node {{ animation: fadeUp .6s ease-out both; }}
"""
    src = [("Kalshi", "not a v4 input", NEON_M), ("polymarket.com", "websocket", "#ffb86b"), ("Polymarket US", "test set 2", NEON_C)]
    body = ""
    for i, (a, b, col) in enumerate(src):
        y = 46 + i * 72
        body += f"""
<g class="node" style="animation-delay:{i * .12:.2f}s">
  <rect x="30" y="{y}" width="170" height="58" rx="10" fill="{BG2}" stroke="{col}"/>
  <text x="115" y="{y + 26}" text-anchor="middle" font-size="14" font-weight="700" class="ink">{a}</text>
  <text x="115" y="{y + 45}" text-anchor="middle" font-size="12" class="ink2">{b}</text>
</g>
<path class="flow" d="M200,{y + 29} C240,{y + 29} 240,147 268,147" fill="none" stroke="{col}" stroke-width="2"/>"""
    stages = [
        (268, "RECORDERS", ["Mac + Vultr VPS", "heartbeats, ops checks"]),
        (468, "TICKS", ["parquet, UTC ns", "price = P(home wins)"]),
        (668, "v4 MAKER", ["join best bid and ask", "Arm A · Arm B"]),
        (868, "TEST SET 2", ["Oct 8 to 12", "run once"]),
    ]
    for i, (x, t, sub) in enumerate(stages):
        col = [NEON_M, "#ffb86b", NEON_C, "#7ee787"][i]
        body += f"""
<g class="node" style="animation-delay:{.4 + i * .15:.2f}s">
  <rect x="{x}" y="104" width="172" height="86" rx="12" fill="{BG2}" stroke="{LINE}"/>
  <rect x="{x}" y="104" width="172" height="4" rx="2" fill="{col}"/>
  <text x="{x + 86}" y="136" text-anchor="middle" font-size="14" font-weight="800" letter-spacing="2" fill="{col}">{t}</text>
  <text x="{x + 86}" y="160" text-anchor="middle" font-size="12" class="ink">{sub[0]}</text>
  <text x="{x + 86}" y="178" text-anchor="middle" font-size="12" class="ink2">{sub[1]}</text>
</g>"""
        if i < 3:
            body += f'<path class="flow" d="M{x + 172},147 L{x + 200},147" stroke="{INK2}" stroke-width="2"/>'
    body += f"""
<path class="flow" d="M1040,147 L1062,147" stroke="{INK2}" stroke-width="2"/>
<g class="node" style="animation-delay:1.1s">
  <circle cx="1112" cy="147" r="48" fill="{BG2}" stroke="url(#edge)" stroke-width="2"/>
  <text x="1112" y="143" text-anchor="middle" font-size="12" font-weight="800" class="ink">numbers</text>
  <text x="1112" y="160" text-anchor="middle" font-size="12" font-weight="800" class="ink">.json</text>
</g>
<text x="600" y="246" text-anchor="middle" font-size="13" class="ink2 sans">backward as-of joins only · fills only on a real trade through our price · fees in every number · every variant logged</text>
"""
    return frame(w, h, body, css, "StaleLine pipeline")


# ───────────────────────────── v4 timeline ─────────────────────────────
def v4() -> str:
    """HYPOTHESIS_v4 status. Facts from main 94aa1a0 (HYPOTHESIS_v4.md), posthoc-mm-v4 1d3d68a (LEDGER.md),
    posthoc-mm-signal 863eb69 (N_CHECK.md)."""
    w, h = 1200, 400
    css = f"""
.prog {{ stroke-dasharray: 1; animation: draw 2.4s ease-out .3s both; }}
.ev {{ animation: fadeUp .6s ease-out both; }}
.next {{ animation: pulse 1.4s ease-in-out infinite; }}
"""
    body = f"""
<text x="40" y="52" font-size="13" fill="{NEON_C}">$ cat HYPOTHESIS_v4.md   # frozen on main 94aa1a0, Oct 4 07:56 ET</text>
<text x="40" y="90" font-size="22" font-weight="800" class="ink">Passive maker on polymarket.com</text>
<text x="40" y="116" font-size="13" class="ink2 sans">join the best bid and ask (never improve) · 10 contracts · inventory cap ±50 · strict trade-through fills · no Kalshi signal</text>
<g class="ev" style="animation-delay:.1s">
  <rect x="770" y="66" width="190" height="58" rx="10" fill="{BG2}" stroke="{NEON_M}"/>
  <text x="865" y="90" text-anchor="middle" font-size="14" font-weight="800" fill="{NEON_M}">ARM A</text>
  <text x="865" y="110" text-anchor="middle" font-size="12" class="ink">always quote</text>
</g>
<g class="ev" style="animation-delay:.25s">
  <rect x="972" y="66" width="190" height="58" rx="10" fill="{BG2}" stroke="#ffb86b"/>
  <text x="1067" y="90" text-anchor="middle" font-size="14" font-weight="800" fill="#ffb86b">ARM B</text>
  <text x="1067" y="110" text-anchor="middle" font-size="12" class="ink">quote while spread ≥ 3 c</text>
</g>
<line x1="110" y1="200" x2="1090" y2="200" stroke="{LINE}" stroke-width="3"/>
<defs><linearGradient id="progG" gradientUnits="userSpaceOnUse" x1="110" y1="0" x2="763" y2="0"><stop offset="0" stop-color="{NEON_M}"/><stop offset="1" stop-color="{NEON_C}"/></linearGradient></defs>
<path class="prog" pathLength="1" d="M110,200 L763,200" stroke="url(#progG)" stroke-width="3" fill="none"/>
"""
    evs = [
        (110, "Oct 3", "ORIGIN", ["plain maker, 88 games", "descriptive, one day"], NEON_M, False),
        (437, "Oct 4 07:56", "FROZEN", ["HYPOTHESIS_v4", "committed to main"], NEON_C, False),
        (763, "Oct 4 07:58", "TEST SET 1", ["0 eligible games", "not run"], INK2, False),
        (1090, "Oct 8 to 12", "TEST SET 2", ["confirmatory, run once", "needs a live book recorder"], "#ffb86b", True),
    ]
    for i, (x, when, what, sub, col, nxt) in enumerate(evs):
        anchor = "start" if i == 0 else ("end" if i == len(evs) - 1 else "middle")
        ring = (f'<circle class="next" cx="{x}" cy="200" r="15" fill="none" stroke="{col}" stroke-width="2"/>' if nxt else "")
        body += f"""
<g class="ev" style="animation-delay:{.3 + i * .45:.2f}s">
  {ring}<circle cx="{x}" cy="200" r="9" fill="{BG}" stroke="{col}" stroke-width="3"/>
  <text x="{x}" y="174" text-anchor="{anchor}" font-size="13" class="ink2">{when}</text>
  <text x="{x}" y="240" text-anchor="{anchor}" font-size="14" font-weight="800" letter-spacing="1.5" fill="{col}">{what}</text>
  <text x="{x}" y="262" text-anchor="{anchor}" font-size="12" class="ink sans">{sub[0]}</text>
  <text x="{x}" y="280" text-anchor="{anchor}" font-size="12" class="ink2 sans">{sub[1]}</text>
</g>"""
    body += f"""
<g class="ev" style="animation-delay:1.2s">
  <rect x="40" y="310" width="1120" height="62" rx="10" fill="{BG2}" stroke="{LINE}"/>
  <text x="60" y="336" font-size="14" font-weight="800" class="ink">STATUS: live and untested.</text>
  <text x="300" y="336" font-size="13" class="ink2 sans">The Aug to Oct 2 holdout cannot test v4: historical data has trades only, no order books.</text>
  <text x="60" y="358" font-size="13" class="ink2 sans">Supported only if, per venue and arm (Holm): primary CI above 0, above 0 without the top 5 games, and settlement P&amp;L above 0.</text>
</g>"""
    return frame(w, h, body, css, "HYPOTHESIS_v4 status: frozen, test set 1 not run, test set 2 on Oct 8 to 12")


# ══════════════ Before v4 (not v4): v1 to v3 graphics. Every one is labelled v3. ══════════════
def hero() -> str:
    """Schematic (no data): the v1 to v3 lead-lag question and the Polymarket US cache artifact."""
    import math
    w, h = 1200, 440
    x0, x1, td, cache_x = 90, 1110, 520, 650
    lo, hi = 318, 168

    def noisy(points):
        return "M" + " L".join(f"{x:.0f},{y:.0f}" for x, y in points)

    k = [(x, lo + 5 * math.sin(x / 23)) for x in range(x0, td + 1, 10)]
    k += [(td + 6, hi + 10), (td + 20, hi - 4)] + [(x, hi + 4 * math.sin(x / 19)) for x in range(td + 40, x1 + 1, 10)]
    p = [(x, lo + 4 + 5 * math.sin(x / 27 + 1)) for x in range(x0, td + 1, 10)]
    p += [(td + 9, hi + 16), (td + 24, hi + 2)] + [(x, hi + 6 + 4 * math.sin(x / 21 + 2)) for x in range(td + 40, x1 + 1, 10)]
    u = [(x0, lo + 14), (330, lo + 14), (330, lo + 8), (cache_x, lo + 8), (cache_x, hi + 14), (960, hi + 14),
         (960, hi + 8), (x1, hi + 8)]
    path_u = "M" + " L".join(f"{x},{y}" for x, y in u)
    css = f"""
.trace {{ fill: none; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 1;
          animation: draw 3.2s cubic-bezier(.6,.05,.3,1) .3s both; }}
.td {{ animation: pulse 1.6s ease-in-out 1.6s infinite both; }}
.late {{ animation: fadeUp .7s ease-out 1.2s both; }}
.head {{ animation: fadeUp .8s ease-out .1s both; }}
.cursor {{ animation: blink 1s steps(1) infinite; }}
"""
    body = f"""
<g class="head">
  <text x="44" y="58" font-size="15" fill="{NEON_C}">$ staleline v3 --venues kalshi,polymarket.com,polymarket_us   # before v4</text>
  <rect class="cursor" x="826" y="45" width="9" height="17" fill="{NEON_C}"/>
  <text x="44" y="88" font-size="13" class="ink3">v3 lead-lag study (not v4): P(home team wins) around one touchdown · schematic, not data</text>
</g>
<g font-size="13">
  <line x1="{x0}" y1="{lo + 40}" x2="{x1}" y2="{lo + 40}" stroke="{LINE}"/>
  <text x="{x0}" y="{lo + 62}" class="ink3">time →</text>
  <text x="{x0 - 10}" y="{hi + 4}" text-anchor="end" class="ink3">58%</text>
  <text x="{x0 - 10}" y="{lo + 6}" text-anchor="end" class="ink3">42%</text>
</g>
<g class="td">
  <line x1="{td}" y1="120" x2="{td}" y2="{lo + 40}" stroke="{NEON_M}" stroke-width="2" stroke-dasharray="4 5"/>
  <text x="{td}" y="112" text-anchor="middle" font-size="14" font-weight="700" fill="{NEON_M}">🏈 TOUCHDOWN</text>
</g>
<path class="trace" pathLength="1" d="{noisy(k)}" stroke="{NEON_M}" filter="url(#glow)"/>
<path class="trace" pathLength="1" d="{noisy(p)}" stroke="#ffb86b" style="animation-delay:.45s"/>
<path class="trace" pathLength="1" d="{path_u}" stroke="{NEON_C}" style="animation-delay:.6s"/>
<g class="late" font-size="13">
  <path d="M{td},{lo + 24} L{td},{lo + 30} L{cache_x},{lo + 30} L{cache_x},{lo + 24}" fill="none" stroke="{INK2}"/>
  <text x="{(td + cache_x) / 2}" y="{lo + 50}" text-anchor="middle" class="ink">looks like a "lag"…</text>
  <rect x="{cache_x + 18}" y="{hi + 32}" width="300" height="56" rx="8" fill="{BG2}" stroke="{NEON_C}"/>
  <text x="{cache_x + 32}" y="{hi + 56}" class="ink" font-weight="700">…but it is a 30 s CDN cache</text>
  <text x="{cache_x + 32}" y="{hi + 76}" class="ink2">Cache-Control: public, max-age=30</text>
</g>
<g font-size="13" class="head">
  <rect x="{x1 - 268}" y="112" width="12" height="3" fill="{NEON_M}"/><text x="{x1 - 250}" y="118" class="ink">Kalshi</text>
  <rect x="{x1 - 186}" y="112" width="12" height="3" fill="#ffb86b"/><text x="{x1 - 168}" y="118" class="ink">polymarket.com</text>
  <rect x="{x1 - 268}" y="134" width="12" height="3" fill="{NEON_C}"/><text x="{x1 - 250}" y="140" class="ink">Polymarket US (as we polled it)</text>
</g>
<text x="{w / 2}" y="{h - 26}" text-anchor="middle" font-size="16" class="ink2">v3: same game · three order books · <tspan fill="{INK}" font-weight="700">who moves first?</tspan></text>
"""
    return frame(w, h, body, css, "Before v4 (not v4): the v3 lead-lag question; the Polymarket US lag was a cache")


def stats() -> str:
    """v1 to v3 headline tiles. Reads results/holdout/lead_decisions.json and results/numbers.json."""
    import json
    lead = json.loads((ROOT / "results/holdout/lead_decisions.json").read_text())
    nums = json.loads((ROOT / "results/numbers.json").read_text())
    pnl = nums["OOS.combined.pnl_total"]["value"]
    pm = lead["polymarket.com"]
    tiles = [
        ("3", "venues", "v3 study, recorded live", NEON_M),
        (f"{pm['median_corrected_lag_s']:.1f} s", "v3 median lag", "Kalshi vs polymarket.com", "#ffb86b"),
        ("30 s", "CDN cache", "behind the v3 7.5 s 'lead'", NEON_C),
        ("566", "trials", "v1 to v3 + post-hoc", NEON_M),
        ("0", "v3 edges", "that survived costs", "#ffb86b"),
        (f"-${abs(pnl):,.2f}", "v3 holdout P&L", "v3 strategies, paper", NEON_C),
    ]
    css = ".tile { animation: fadeUp .6s ease-out both; }"
    body = ""
    tw = 182
    for i, (big, lab, sub, col) in enumerate(tiles):
        x = 26 + i * (tw + 10)
        body += f"""
<g class="tile" style="animation-delay:{.1 + i * .18:.2f}s">
  <rect x="{x}" y="26" width="{tw}" height="150" rx="12" fill="{BG2}" stroke="{LINE}"/>
  <rect x="{x + 16}" y="26" width="{tw - 32}" height="3" rx="1.5" fill="{col}"/>
  <text x="{x + tw / 2}" y="94" text-anchor="middle" font-size="{38 if len(big) < 7 else 27}" font-weight="800" class="ink">{esc(big)}</text>
  <text x="{x + tw / 2}" y="124" text-anchor="middle" font-size="14" font-weight="700" letter-spacing="2" fill="{col}">{esc(lab.upper())}</text>
  <text x="{x + tw / 2}" y="150" text-anchor="middle" font-size="11.5" class="ink2 sans">{esc(sub)}</text>
</g>"""
    return frame(1200, 202, body, css, "Before v4 (not v4): v1 to v3 headline numbers")


def cache() -> str:
    """v3 Polymarket US laggard (not v4). Facts from results/holdout_diag/ (h1 headers, h2 to h5)."""
    w, h = 1200, 400
    css = f"""
.pkt {{ animation: flow 1.2s linear infinite; }}
@keyframes flow {{ from {{ transform: translateX(0); opacity: 0; }} 10% {{ opacity: 1; }} 90% {{ opacity: 1; }} to {{ transform: translateX(196px); opacity: 0; }} }}
.age {{ opacity: 0; animation: ageTick 6s steps(1) infinite; }}
@media (prefers-reduced-motion: reduce) {{ .age0 {{ opacity: 1; }} }}
@keyframes ageTick {{ 0% {{ opacity: 1; }} 16.6%, 100% {{ opacity: 0; }} }}
.ring {{ animation: pulse 2s ease-in-out infinite; }}
.chip {{ animation: fadeUp .6s ease-out both; }}
"""
    boxes = [
        (40, "POLYMARKET US", "matching engine", "quotes change every trade", NEON_M),
        (476, "CLOUDFLARE EDGE", "public, max-age=30", "serves the same body", "#ffb86b"),
        (912, "v3 RECORDER", "polled about every 1 s", "stores what it was served", NEON_C),
    ]
    body = f'<text x="40" y="44" font-size="14" class="ink2">v3 laggard on Polymarket US (not v4) · $ curl -sI gateway.polymarket.us/v1/markets?slug=… | grep -i age</text>'
    for x, t, s1, s2, col in boxes:
        body += f"""
<g>
  <rect x="{x}" y="70" width="248" height="128" rx="12" fill="{BG2}" stroke="{col}" stroke-width="1.5"/>
  <text x="{x + 124}" y="108" text-anchor="middle" font-size="16" font-weight="800" letter-spacing="1.5" fill="{col}">{t}</text>
  <text x="{x + 124}" y="140" text-anchor="middle" font-size="14" class="ink">{s1}</text>
  <text x="{x + 124}" y="166" text-anchor="middle" font-size="12.5" class="ink2 sans">{s2}</text>
</g>"""
    body += f'<rect class="ring" x="470" y="64" width="260" height="140" rx="15" fill="none" stroke="#ffb86b" stroke-width="1"/>'
    body += f"""
<line x1="288" y1="134" x2="476" y2="134" stroke="{LINE}" stroke-width="2"/>
<line x1="724" y1="134" x2="912" y2="134" stroke="{LINE}" stroke-width="2"/>
<text x="382" y="122" text-anchor="middle" font-size="12" class="ink2">fresh quotes</text>
<text x="818" y="122" text-anchor="middle" font-size="12" class="ink2">same snapshot, again</text>"""
    cols = [NEON_M, "#ffb86b", NEON_C, "#7ee787", NEON_M, "#ffb86b"]
    for i in range(6):
        body += f'<circle class="pkt" cx="290" cy="134" r="5" fill="{cols[i]}" style="animation-delay:{i * .2:.1f}s"/>'
        body += f'<circle class="pkt" cx="726" cy="134" r="5" fill="#ffb86b" style="animation-delay:{i * .2:.1f}s"/>'
    for i, a in enumerate(["Age: 4 s", "Age: 9 s", "Age: 14 s", "Age: 19 s", "Age: 24 s", "Age: 29 s · EXPIRED"]):
        body += (f'<text class="age age{i}" x="600" y="232" text-anchor="middle" font-size="15" font-weight="700" '
                 f'fill="#ffb86b" style="animation-delay:{i}s">{a}</text>')
    chips = [
        ("1 to 29 s", "Age header on the endpoint|the v3 recorder polled"),
        ("19.2 s", "v3 median receipt delay|vs the venue's own trade tape"),
        ("2.3%", "of v3 paper fills matched a|real print on both legs"),
        ("-4.09 c", "v3 laggard (not v4): confirmed|fills lost, the quotes were cached"),
    ]
    for i, (big, sub) in enumerate(chips):
        x = 40 + i * 284
        a, b = sub.split("|")
        body += f"""
<g class="chip" style="animation-delay:{.4 + i * .2:.1f}s">
  <rect x="{x}" y="268" width="268" height="96" rx="10" fill="{BG2}" stroke="{LINE}"/>
  <text x="{x + 20}" y="306" font-size="26" font-weight="800" class="ink">{esc(big)}</text>
  <text x="{x + 20}" y="332" font-size="12" class="ink2 sans">{esc(a)}</text>
  <text x="{x + 20}" y="349" font-size="12" class="ink2 sans">{esc(b)}</text>
</g>"""
    return frame(w, h, body, css, "Before v4 (not v4): the v3 Polymarket US lag came from a 30 second Cloudflare cache")


def r2(v) -> str:
    from decimal import Decimal, ROUND_HALF_UP
    return f"{Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):+}"


def latency() -> str:
    """v3 trade-the-laggard chart (not v4). Every plotted value is read from committed CSVs:
    results/holdout/laggard_latency_curve.csv and results/holdout_diag/h4_run_summary.csv."""
    import csv
    import io
    rows = list(csv.DictReader(open(ROOT / "results/holdout/laggard_latency_curve.csv")))
    pm = sorted([r for r in rows if r["venue"] == "polymarket"], key=lambda r: float(r["latency_s"]))
    us = sorted([r for r in rows if r["venue"] == "polymarket_us"], key=lambda r: float(r["latency_s"]))
    lines = (ROOT / "results/holdout_diag/h4_run_summary.csv").read_text().splitlines()
    h4 = [r for r in csv.DictReader(io.StringIO("\n".join(lines[1:]))) if r["set"] == "both legs confirmed"]

    w, h = 1200, 560
    L, R, T, B = 110, 800, 110, 470
    xmin, xmax, ymin, ymax = 0, 11.5, -7, 3

    def X(v):
        return L + (v - xmin) / (xmax - xmin) * (R - L)

    def Y(v):
        return B - (v - ymin) / (ymax - ymin) * (B - T)

    def series(rs, col, delay):
        pts = [(X(float(r["latency_s"])), Y(float(r["edge_cents_mean"]))) for r in rs]
        up = [(X(float(r["latency_s"])), Y(float(r["edge_ci_high"]))) for r in rs]
        dn = [(X(float(r["latency_s"])), Y(float(r["edge_ci_low"]))) for r in rs]
        band = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in up + dn[::-1]) + " Z"
        line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{col}" stroke="{BG}" stroke-width="2"/>' for x, y in pts)
        return (f'<path class="bandf" d="{band}" fill="{col}" opacity=".18" style="animation-delay:{delay}s"/>'
                f'<path class="ln" pathLength="1" d="{line}" fill="none" stroke="{col}" stroke-width="2.5" '
                f'stroke-linejoin="round" style="animation-delay:{delay}s"/><g class="fade" style="animation-delay:{delay + .8}s">{dots}</g>')

    css = """
.ln { stroke-dasharray: 1; animation: draw 2s ease-out both; }
.fade { animation: fadeIn .9s ease-out both; }
.bandf { animation: fadeBand .9s ease-out both; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes fadeBand { from { opacity: 0; } to { opacity: .18; } }
.lab { animation: fadeUp .6s ease-out both; }
"""
    g = ""
    for v in range(-6, 3, 2):
        g += (f'<line x1="{L}" y1="{Y(v):.1f}" x2="{R}" y2="{Y(v):.1f}" stroke="{GRID if v else INK3}" '
              f'stroke-width="{1 if v else 1.5}"/>'
              f'<text x="{L - 12}" y="{Y(v) + 4:.1f}" text-anchor="end" font-size="13" class="ink2">{v:+d}</text>'.replace("+0<", "0<"))
    for v in [0, 2, 4, 6, 8, 10]:
        g += f'<text x="{X(v):.1f}" y="{B + 24}" text-anchor="middle" font-size="13" class="ink2">{v} s</text>'
    g += f'<text x="{(L + R) / 2}" y="{B + 52}" text-anchor="middle" font-size="13" class="ink2 sans">reaction delay: decision to fill (seconds)</text>'
    g += f'<text x="{L - 70}" y="{(T + B) / 2}" font-size="13" class="ink2 sans" transform="rotate(-90 {L - 70} {(T + B) / 2})" text-anchor="middle">net cents per contract</text>'
    g += f'<text x="{R - 4}" y="{Y(0) - 8:.1f}" text-anchor="end" font-size="12" class="ink3">break-even</text>'

    s_us = series(us, C_US, .2)
    s_pm = series(pm, C_PM, .6)
    conf = ""
    for r in h4:
        x = X(float(r["latency_s"])) + 14
        y, yl, yh = Y(float(r["mean_net_c_per_contract"])), Y(float(r["ci95_low"])), Y(float(r["ci95_high"]))
        conf += (f'<line x1="{x:.1f}" y1="{yh:.1f}" x2="{x:.1f}" y2="{yl:.1f}" stroke="{C_CONF}" stroke-width="2"/>'
                 f'<line x1="{x - 6:.1f}" y1="{yh:.1f}" x2="{x + 6:.1f}" y2="{yh:.1f}" stroke="{C_CONF}" stroke-width="2"/>'
                 f'<line x1="{x - 6:.1f}" y1="{yl:.1f}" x2="{x + 6:.1f}" y2="{yl:.1f}" stroke="{C_CONF}" stroke-width="2"/>'
                 f'<rect x="{x - 6:.1f}" y="{y - 6:.1f}" width="12" height="12" transform="rotate(45 {x:.1f} {y:.1f})" '
                 f'fill="{C_CONF}" stroke="{BG}" stroke-width="2"/>'
                 f'<text x="{x:.1f}" y="{yl + 16:.1f}" font-size="12" text-anchor="middle" class="ink2">n {r["n_fills"]}</text>')
    c14 = h4[0]
    u1 = next(r for r in us if float(r["latency_s"]) == 1.0)
    cx, cy0, cy1 = X(1.0) + 14, Y(float(u1["edge_cents_mean"])) + 8, Y(float(c14["ci95_high"])) - 8
    conf = (f'<path d="M{X(1.0):.1f},{cy0:.1f} C{X(1.0) + 40:.1f},{(cy0 + cy1) / 2:.1f} {cx:.1f},{(cy0 + cy1) / 2:.1f} {cx:.1f},{cy1:.1f}" '
            f'fill="none" stroke="{C_CONF}" stroke-width="1.5" stroke-dasharray="4 4" marker-end="url(#arr)"/>'
            f'<text x="{X(1.0) + 52:.1f}" y="{Y(-1.05):.1f}" font-size="12" class="ink">same Polymarket US fills,</text>'
            f'<text x="{X(1.0) + 52:.1f}" y="{Y(-1.05) + 16:.1f}" font-size="12" class="ink">checked against real trades</text>') + conf
    lx = R + 34

    def leg(y, col, title, sub, shape="line"):
        mark = (f'<line x1="{lx}" y1="{y - 5}" x2="{lx + 22}" y2="{y - 5}" stroke="{col}" stroke-width="3"/>'
                f'<circle cx="{lx + 11}" cy="{y - 5}" r="4.5" fill="{col}"/>' if shape == "line" else
                f'<rect x="{lx + 5}" y="{y - 11}" width="12" height="12" transform="rotate(45 {lx + 11} {y - 5})" fill="{col}"/>')
        return (mark + f'<text x="{lx + 34}" y="{y}" font-size="14" font-weight="700" class="ink">{esc(title)}</text>'
                + "".join(f'<text x="{lx + 34}" y="{y + 20 + i * 18}" font-size="12" class="ink2 sans">{esc(s)}</text>'
                          for i, s in enumerate(sub)))

    first_us, first_pm = us[0], pm[0]
    legend = (
        leg(T + 10, C_US, "v3: Polymarket US, polled",
            [f"{float(first_us['edge_cents_mean']):+.2f} c at 0 s, {first_us['n_trades']} trades",
             "looks like free money…"])
        + leg(T + 110, C_CONF, "v3: same fills, real prints",
              [f"{r2(c14['mean_net_c_per_contract'])} c [{r2(c14['ci95_low'])}, {r2(c14['ci95_high'])}]",
               f"only {float(c14['share_both_confirmed']) * 100:.1f}% of fills were real"], "diamond")
        + leg(T + 210, C_PM, "v3: polymarket.com",
              [f"{float(first_pm['edge_cents_mean']):+.2f} c at 1 s, {first_pm['n_trades']} trades",
               "negative at every delay"])
    )
    title = (f'<text x="40" y="50" font-size="20" font-weight="800" class="ink">v3 trade-the-laggard (not v4): net edge vs reaction delay</text>'
             f'<text x="40" y="76" font-size="13" class="ink2 sans">v3 holdout, after Webull fees and spread · lines: run means with '
             f'95% CI (game bootstrap) · diamonds: partial sample, both legs confirmed by a real print</text>')
    foot = (f'<text x="40" y="{h - 18}" font-size="11" class="ink3">source: results/holdout/laggard_latency_curve.csv · '
            f'results/holdout_diag/h4_run_summary.csv · built by scripts/make_readme_svgs.py</text>')
    arrow = (f'<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
             f'<path d="M0,0 L10,5 L0,10 z" fill="{C_CONF}"/></marker></defs>')
    body = arrow + title + g + s_us + s_pm + f'<g class="lab" style="animation-delay:1.2s">{conf}</g>' \
        + f'<g class="lab" style="animation-delay:.4s">{legend}</g>' + foot
    return frame(w, h, body, css, "Before v4 (not v4): v3 laggard net edge vs latency")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in [("v4", v4), ("story", story), ("pipeline", pipeline), ("story_v3", story_v3), ("hero", hero),
                     ("stats", stats), ("cache", cache), ("latency", latency)]:
        (OUT / f"{name}.svg").write_text(fn())
        print("wrote", OUT / f"{name}.svg")


if __name__ == "__main__":
    main()
