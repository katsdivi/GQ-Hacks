# CME event-contract data: cost quotes (NOT spent)

Quoted 2026-10-04 ~06:20 ET with Databento `metadata.get_cost` / `get_billable_size` (free calls). Nothing was
purchased. Dataset GLBX.MDP3. Symbols are the 32 CME "game" contracts with a game date before 2026-08-01
(see map.csv), C0001 and P0001 legs (64 symbols).

| item | schema | window (UTC) | symbols | MB billable | cost |
|---|---|---|---|---|---|
| Order-book depth, all 32 game contracts | mbp-10 | 2026-01-08 to 2026-02-10 | 64 | 78.84 | $0.0367 |
| Every top-of-book change, all 32 | mbp-1 | 2026-01-08 to 2026-02-10 | 64 | 16.77 | $0.0281 |
| (already on disk) trades | trades | 2026-01-08 to 2026-02-10 | 64 | 2.28 | $0.0593 |
| (already on disk) 1 s BBO | bbo-1s | 2026-01-08 to 2026-02-10 | 64 | 8.72 | $0.1462 |
| Confirm whether ANY FG/CG contracts were listed in Dec 2025 (one weekday of all definitions) | definition | 2025-12-22 | ALL_SYMBOLS | 514.1 | $0.8140 |
| Same, whole Dec 6 to Jan 10 range (not recommended) | definition | 2025-12-06 to 2026-01-10 | ALL_SYMBOLS | 17,083.7 | $27.0477 |

Recommended spend, if approved: mbp-10 + mbp-1 for the 32 contracts ($0.0648) plus the one-day December
definition check ($0.8140). Total **$0.8788**.

Not quotable: CME trades/quotes for any game before 2026-01-11. Databento symbology resolves the FG/CG game
contracts only from 2026-01-11 (even the CFP semifinal contracts CGMIAF608/CGOLEF608/CGINDF609/CGOREF609, whose
games were Jan 8 and 9, resolve only from 2026-01-11, after their games), and a free brute-force resolve of 3,968
plausible NFL symbols for Dec 2025 to Jan 10 found none. So Dec 2025 NFL regular-season and bowl-game CME data
appears not to exist on Databento in this symbology; the $0.81 definition day would confirm or refute that.

Databento terms (public pages): new accounts get $125 of free historical credit, valid 6 months, one set per team;
billing is per byte only after credits are used. Whether the project account still has credit is not visible
from the API calls used here.
