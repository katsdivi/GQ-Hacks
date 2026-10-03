# Recorder gaps

| Start (ET) | End (ET) | Venue | Cause | Fixed by |
|---|---|---|---|---|
| Sat Oct 03 00:17:18 | Sat Oct 03 00:18:24 | kalshi | polling stalled (errors, rate limit or host asleep) | auto-logged by collector |
| Fri Oct 02 23:09 | open (Vultr expected ~7 h after Sat Oct 03 01:30 ET) | all | single recorder on Divi's Mac (Kalshi REST polling, polymarket.com websocket); Vultr delayed (MLH); Mac sleep or network drop would stop recording | second independent recorder on a teammate laptop (collector/teammate_setup.sh) + collector/merge_recordings.py; Vultr deploy when available |
