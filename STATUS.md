# STATUS

Updated by Claude Code at the end of every task. Divi pastes the block below into his planning chat.

```
STATUS  (last update: Fri Oct 2, ~10:45 PM ET)
Current task: T3 done (Kalshi ingest + overlay), waiting on Divi before T4
Done: T1; T2 CME data check = PASS for Jan 2026 playoffs only; T3 Kalshi ingest + first merged game
Verified numbers:
  CME FG/CG single-game contracts on Databento: 0 in Dec 2025, 30 in Jan 2026 (24 NFL, 6 CFB),
    2 in Feb 2026 (Super Bowl), 12 in Aug 2026 (CFB week 0, sealed), 0 in Sep 2026.
    Databento data starts 2026-01-11 00:00 UTC. All NFL games from then on have trades: 28,641 (Jan), 13,435 (Feb).
  T2 game LAR at CHI, 2026-01-18, FGCHIF618 C0001 (home): 1,421 trades, median 4/min in game, 351 price changes. PASS.
  Same window on Kalshi (KXNFLGAME-26JAN18LACHI-CHI): 189,475 trades, median 390/min. Overlay tracks, no flip.
  ROUGH diagnostic (not leadlag.py): Kalshi appears to LEAD CME by ~5 to 15 s on this game (bucketed xcorr peak at -1x10s, -3x5s).
Blockers: CME leading is in doubt on game 1; only ~16 training NFL games exist on CME; no CME games to record this weekend
  (no FG/CG listed in Sep 2026).
Next: Divi decides venue plan, then T4 recorder
Decisions pending: A (venue pair after T2 findings), B (Webull paper orders), D (Kalshi websocket)
```

## Task log

| Task | Status | Verified with | Notes |
|---|---|---|---|
| T1 Repo, fake game, hypothesis | done | clean clone loads 75,600 rows; regen gives identical data (parquet footer bytes differ, values equal) | |
| T2 CME data check | done: PASS (Jan to Feb 2026 only) | `out/cme_game_coverage.csv`; LAR at CHI 1,421 trades | $1.66 of Databento credit spent in total |
| T3 Kalshi same game | done | `out/nfl_20260118_lar_chi_overlay.png`; 189,475 Kalshi trades | kickoff 23:30Z is estimated from trade activity, confirm |
| T4 Live recorder | todo | | |
| T5 Lead/lag | todo | | |
| T6 First trades + costs | todo | | |
| T7 run.py, tag v0-made-it | todo | | |
| T8 Overnight download | todo | | |

## T2 findings (CME on Databento)

- Single-game contracts are options on Globex: raw symbol `FG<team><month><y><dd> C0001` (team wins, $0.01 to $0.99, scale 1) and `P0001`. Parent symbol `FG<team>.OPT` / `CG<school>.OPT`. Groups `NFLG` / `CFBG`; the future (group `0E`) never trades. Almost all volume is on the C0001 call.
- Team codes come from the season contracts (`FS<team>`, `CS<school>`, groups `NFLS`, `CFBS`). NFL codes are padded to 3 letters: GBX, KCX, LVX, NEX, NOX, SFX, TBX.
- Coverage: Dec 2025 has nothing on Databento (parent and guessed raw symbols both unresolved). First data 2026-01-11 00:00 UTC, so the Jan 9 to 10 CFP games have no trades. 2026 season: only the Aug 29 CFB week 0 games were listed (one counted: CGFSUQ629, 0 trades); nothing listed in Sep 2026, and the Sep 27 full definitions file has no FG/CG symbols.
- Databento side on LAR at CHI: 1,323 B (buy aggressor) vs 98 A. Looks lopsided; check before using CME trade side for anything.

## T3 notes (Kalshi)

- Data before `GET /historical/cutoff` (trades_created_ts, now 2026-08-03) is only on `/historical/markets` and `/historical/trades`; `/markets/trades` returns empty for those. `ingest/kalshi.py` switches automatically.
- Home/away from the event `sub_title` ("LA at CHI (Jan 18)"); team code is the market ticker suffix.
- Some Kalshi events are duplicated with zero volume (e.g. KXNFLGAME-26JAN17SFSEA, KXNFLGAME-26JAN25LASEA). Pick the market with volume.
