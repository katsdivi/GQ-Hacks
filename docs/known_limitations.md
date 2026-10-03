# Known limitations

- Collector market discovery (collector/run.py refresh_markets) takes the team code with ticker.rsplit("-", 1), so a market whose Kalshi team code contains a hyphen (Miami (OH) is "M-OH") would be skipped live. 0 holdout games affected: none of the 126 Kalshi events of Oct 2 to 4, 2026 has a hyphenated code (audit 2026-10-03, 5:40 PM ET). Not changed or redeployed during the holdout.
