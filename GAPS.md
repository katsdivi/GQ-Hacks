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
| Sat Oct 03 08:17:07 | Sat Oct 03 08:17:08 | kalshi_ws | websocket error ConnectionClosedError; duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 08:45:50 | Sat Oct 03 08:46:15 | polymarket | resubscribe (market set changed); duration 25 s; recovered | auto-logged by collector |
| Sat Oct 03 09:06:49 | Sat Oct 03 09:18:39 | polymarket_us | no heartbeat for > 60 s; duration 710 s; recovered | auto-logged by collector |
| Sat Oct 03 09:06:50 | Sat Oct 03 09:18:59 | kalshi_ws | no heartbeat for > 60 s; duration 730 s; recovered | auto-logged by collector |
| Sat Oct 03 09:06:50 | Sat Oct 03 09:21:30 | polymarket | no heartbeat for > 60 s; duration 880 s; recovered | auto-logged by collector |
| Sat Oct 03 09:19:06 | Sat Oct 03 09:29:26 | kalshi_ws | no heartbeat for > 60 s; duration 620 s; recovered | auto-logged by collector |
| Sat Oct 03 09:22:02 | Sat Oct 03 09:29:53 | polymarket | no heartbeat for > 60 s; duration 470 s; recovered | auto-logged by collector |
| Sat Oct 03 09:29:54 | Sat Oct 03 09:30:02 | polymarket | websocket error ConnectionClosedError; duration 8 s; recovered | auto-logged by collector |
| Sat Oct 03 09:32:45 | Sat Oct 03 09:37:10 | polymarket_us | no heartbeat for > 60 s; duration 266 s; recovered | auto-logged by collector |
| Sat Oct 03 09:30:02 | Sat Oct 03 09:37:51 | polymarket | no heartbeat for > 60 s; duration 470 s; recovered | auto-logged by collector |
| Sat Oct 03 09:38:04 | Sat Oct 03 09:38:11 | polymarket | websocket error ConnectionClosedError; duration 7 s; recovered | auto-logged by collector |
| Sat Oct 03 09:32:45 | Sat Oct 03 09:38:44 | kalshi_ws | no heartbeat for > 60 s; duration 359 s; recovered | auto-logged by collector |
| Sat Oct 03 09:40:40 | Sat Oct 03 09:44:34 | polymarket_us | no heartbeat for > 60 s; duration 233 s; recovered | auto-logged by collector |
| Sat Oct 03 09:38:50 | Sat Oct 03 09:44:41 | polymarket | no heartbeat for > 60 s; duration 351 s; recovered | auto-logged by collector |
| Sat Oct 03 09:38:50 | Sat Oct 03 09:44:47 | kalshi_ws | no heartbeat for > 60 s; duration 358 s; recovered | auto-logged by collector |
| Sat Oct 03 09:45:19 | Sat Oct 03 09:49:13 | kalshi_ws | no heartbeat for > 60 s; duration 235 s; recovered | auto-logged by collector |
| Sat Oct 03 09:45:19 | Sat Oct 03 09:49:15 | polymarket | no heartbeat for > 60 s; duration 236 s; recovered | auto-logged by collector |
| Sat Oct 03 10:13:19 | Sat Oct 03 10:14:37 | polymarket_us | no heartbeat for > 60 s; duration 78 s; recovered | auto-logged by collector |
| Sat Oct 03 10:13:19 | Sat Oct 03 10:15:11 | polymarket | no heartbeat for > 60 s; duration 112 s; recovered | auto-logged by collector |
| Sat Oct 03 10:13:19 | Sat Oct 03 10:15:15 | kalshi_ws | no heartbeat for > 60 s; duration 116 s; recovered | auto-logged by collector |
