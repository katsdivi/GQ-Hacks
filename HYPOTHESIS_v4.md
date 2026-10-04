HYPOTHESIS_v4 (post-hoc origin, frozen before test data is examined).
Origin: posthoc-mm-signal N maker, polymarket.com, Oct 3 games kicking off by 20:00 ET (863eb69, f535256): +1.09 c per contract at +60 s [0.17, 2.12], concentrated in 5 games, matched round trips +0.52 c.
Rule: passive maker quoting both sides at the best bid and ask (join, never improve), 10 contracts, inventory cap +/- 50, no Kalshi signal. Arm A: always quote. Arm B: quote only while the spread is >= 3 c.
Venues: polymarket.com (recorded books and trades); Polymarket US (authenticated order-book websocket with venue timestamps, recorded live; test set 2 only).
Fills: strict trade-through only. Maker fee: each venue's published schedule at the time (cite). Kickoff cut [T - 2 min, T + 20 min].
Primary metric: P&L per contract marked to mid at +60 s, game-bootstrap 95% CI (2,000 reps, seed 20261011). Secondary: matched round-trip P&L; held to settlement; excluding the top 5 games.
Test set 1 (run once now, descriptive only, small n): Oct 3 games kicking off after 20:00 ET with complete polymarket.com books and trades on disk, never used by posthoc-mm-signal.
Test set 2 (confirmatory): all college and NFL games from 2026-10-08 00:00 ET to 2026-10-13 00:00 ET, run once after the window closes.
Decision (test set 2, per venue and arm, Holm across venues): supported only if (1) primary CI above zero, (2) point estimate above zero excluding the top 5 games, (3) settlement P&L point estimate above zero. Otherwise not supported. Report either way.
