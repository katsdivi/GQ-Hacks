# Recorder gaps

| Start (ET) | End (ET) | Venue | Cause | Fixed by |
|---|---|---|---|---|
| Sat Oct 03 00:17:18 | Sat Oct 03 00:18:24 | kalshi | polling stalled (errors, rate limit or host asleep) | auto-logged by collector |
| Fri Oct 02 23:09 | open (Vultr expected ~7 h after Sat Oct 03 01:30 ET) | all | single recorder on Divi's Mac (Kalshi REST polling, polymarket.com websocket); Vultr delayed (MLH); Mac sleep or network drop would stop recording | second independent recorder on a teammate laptop (collector/teammate_setup.sh) + collector/merge_recordings.py; Vultr deploy when available |
| Sat Oct 03 05:51:48 | Sat Oct 03 05:51:55 | all | collector restart onto heartbeat code (pid 83673); duration 7 s | logged by hand (first heartbeat run) |
| Sat Oct 03 05:52:46 | Sat Oct 03 05:52:48 | kalshi_ws | TEST: induced disconnect; duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 05:52:46 | Sat Oct 03 05:53:15 | polymarket | TEST: induced disconnect; duration 29 s; recovered | auto-logged by collector |
| Sat Oct 03 05:52:44 | Sat Oct 03 05:54:02 | polymarket_us | no heartbeat for > 60 s; duration 78 s; recovered | auto-logged by collector |
| Sat Oct 03 05:54:55 | Sat Oct 03 05:55:01 | all | collector restart (pid 87295); duration 6 s since the last heartbeat | auto-logged by collector |
