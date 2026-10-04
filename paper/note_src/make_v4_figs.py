import json, re
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
S = "/private/tmp/claude-501/-Users-divyamkataria-GQ-HACKS/a2c1a2af-0f6a-4955-aa59-4abd26a10e17/scratchpad/note_v4"
F = f"{S}/note/figs"
BLUE, ORANGE, GREY, RED = "#0072B2", "#E69F00", "#999999", "#D55E00"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 200})

g = pd.read_csv(f"{S}/src/n_detail_games.csv")
tot = g.pnl60.sum(); top = g.nlargest(5, "pnl60"); ex = tot - top.pnl60.sum()
assert round(tot, 2) == 46.53, tot
s = g.sort_values("pnl60", ascending=False).reset_index(drop=True)
col = [ORANGE if i < 5 else (BLUE if v != 0 else GREY) for i, v in enumerate(s.pnl60)]
fig, ax = plt.subplots(figsize=(6.4, 2.8))
ax.bar(range(len(s)), s.pnl60, color=col, width=0.85)
ax.axhline(0, color="black", lw=0.6)
ax.set_xlabel("game (88, sorted by P&L; grey = no fills)"); ax.set_ylabel("P&L at +60 s ($)")
ax.text(0.98, 0.95, f"total +${tot:.2f}; top 5 (orange) +${top.pnl60.sum():.2f}\nexcl. top 5: +0.15 c/contract [-0.48, +0.77]\n38.6% of 88 games positive",
        transform=ax.transAxes, ha="right", va="top")
ax.set_title("Plain maker on polymarket.com, Oct 3: P&L by game", fontsize=9)
fig.tight_layout(); fig.savefig(f"{F}/v4_per_game.png"); plt.close(fig)

sp = pd.read_csv(f"{S}/src/n_detail_spread.csv")
assert round(sp.pnl60.sum(), 2) == 46.53
fig, ax = plt.subplots(figsize=(4.8, 2.6))
c = [RED if v < 0 else BLUE for v in sp.pnl60_c_per_contract]
b = ax.bar(sp.bucket, sp.pnl60_c_per_contract, color=c)
for r, (v, n) in zip(b, zip(sp.pnl60_c_per_contract, sp.fills)):
    ax.text(r.get_x() + r.get_width() / 2, v + (0.08 if v >= 0 else -0.08), f"{v:+.2f} c\n{n} fills",
            ha="center", va="bottom" if v >= 0 else "top", fontsize=8)
ax.axhline(0, color="black", lw=0.6); ax.set_ylim(-1.6, 3.6)
ax.set_xlabel("quoted spread at fill"); ax.set_ylabel("P&L per contract at +60 s (c)")
ax.set_title("Edge by spread width (basis for v4 Arm B, spread >= 3 c)", fontsize=9)
fig.tight_layout(); fig.savefig(f"{F}/v4_spread.png"); plt.close(fig)

n = json.load(open(f"{S}/src/n_check.json"))
parts = [("spread\ncaptured", n["spread_captured_usd"]), ("adverse\nselection", n["mark_to_mid_60s_usd"]), ("fills without\npre-fill mid", -1.00)]
assert round(sum(v for _, v in parts), 2) == 46.53
fig, ax = plt.subplots(figsize=(4.8, 2.6)); cum = 0
for i, (lab, v) in enumerate(parts):
    ax.bar(i, v, bottom=cum if v >= 0 else cum + v, color=BLUE if v >= 0 else RED)
    ax.text(i, max(cum, cum + v) + 1.5, f"{v:+.2f}", ha="center", fontsize=8); cum += v
ax.bar(3, cum, color=GREY); ax.text(3, cum + 1.5, f"{cum:+.2f}", ha="center", fontsize=8)
ax.set_xticks(range(4), [p[0] for p in parts] + ["total at\n+60 s"]); ax.set_ylabel("$"); ax.set_ylim(0, 72)
ax.set_title("Where the +$46.53 comes from", fontsize=9)
fig.tight_layout(); fig.savefig(f"{F}/v4_decomp.png"); plt.close(fig)

rows = []
for line in open(f"{S}/src/demo.log"):
    m = re.match(r"(\d\d:\d\d:\d\d) ET \| book bid ([\d.]+) x(\d+) / ask ([\d.]+) x(\d+) \| trades seen (\d+) \| fills (\d+)", line)
    if m: rows.append(m.groups())
d = pd.DataFrame(rows, columns=["t", "bid", "bsz", "ask", "asz", "trades", "fills"])
d["t"] = pd.to_datetime("2026-10-04 " + d.t); d[["bsz", "asz", "trades", "fills"]] = d[["bsz", "asz", "trades", "fills"]].astype(int)
assert d.fills.max() == 0
fig, ax = plt.subplots(figsize=(6.4, 2.6))
ax.plot(d.t, d.bsz / 1e6, color=BLUE, label="size at best bid 0.33"); ax.plot(d.t, d.asz / 1e6, color=ORANGE, label="size at best ask 0.34")
ax.set_ylabel("contracts (millions)"); ax.set_ylim(0, None)
ax2 = ax.twinx(); ax2.step(d.t, d.trades, color=GREY, where="post", label="trades seen (cumulative)"); ax2.set_ylabel("trades seen"); ax2.spines["top"].set_visible(False)
ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M")); ax.set_xlabel("ET, Oct 4 (kickoff 09:30)")
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels(); ax.legend(h1 + h2, l1 + l2, loc="center left", fontsize=7, frameon=False)
ax.set_title(f"Live paper demo, Colts at Commanders: {d.trades.iloc[-1]} trades, 0 fills for a 10-contract quote", fontsize=9)
fig.tight_layout(); fig.savefig(f"{F}/v4_demo.png"); plt.close(fig)
print("ok", round(tot, 2), round(ex, 2), len(d), d.t.iloc[0], d.t.iloc[-1], d.trades.iloc[-1])
