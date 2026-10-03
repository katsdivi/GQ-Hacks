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
| Sat Oct 03 11:57:07 | Sat Oct 03 12:14:52 | polymarket_us | no heartbeat for > 60 s; duration 1065 s; recovered | auto-logged by collector |
| Sat Oct 03 11:57:08 | Sat Oct 03 12:14:53 | kalshi_ws | no heartbeat for > 60 s; duration 1065 s; recovered | auto-logged by collector |
| Sat Oct 03 12:31:31 | Sat Oct 03 12:31:32 | kalshi_ws | websocket error ConnectionClosedError; duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 11:57:08 | Sat Oct 03 12:34:40 | polymarket | no heartbeat for > 60 s; duration 2252 s; recovered | auto-logged by collector |
| Sat Oct 03 12:31:35 | Sat Oct 03 12:38:10 | kalshi_ws | no heartbeat for > 60 s; duration 395 s; recovered | auto-logged by collector |
| Sat Oct 03 12:34:48 | Sat Oct 03 12:38:32 | polymarket | no heartbeat for > 60 s; duration 224 s; recovered | auto-logged by collector |
| Sat Oct 03 12:38:34 | Sat Oct 03 12:38:39 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 12:38:51 | Sat Oct 03 12:40:30 | polymarket_us | no heartbeat for > 60 s; duration 100 s; recovered | auto-logged by collector |
| Sat Oct 03 12:38:53 | Sat Oct 03 12:41:01 | polymarket | no heartbeat for > 60 s; duration 129 s; recovered | auto-logged by collector |
| Sat Oct 03 12:38:53 | Sat Oct 03 12:41:07 | kalshi_ws | no heartbeat for > 60 s; duration 134 s; recovered | auto-logged by collector |
| Sat Oct 03 12:41:03 | Sat Oct 03 12:41:08 | polymarket | websocket error ConnectionClosedError; duration 5 s; recovered | auto-logged by collector |
| Sat Oct 03 12:41:13 | Sat Oct 03 12:41:14 | kalshi_ws | websocket error ConnectionClosedError; duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 12:44:54 | Sat Oct 03 12:50:11 | kalshi_ws | no heartbeat for > 60 s; duration 317 s; recovered | auto-logged by collector |
| Sat Oct 03 12:51:45 | Sat Oct 03 13:04:55 | polymarket_us | no heartbeat for > 60 s; duration 790 s; recovered | auto-logged by collector |
| Sat Oct 03 12:51:45 | Sat Oct 03 13:04:55 | kalshi_ws | no heartbeat for > 60 s; duration 790 s; recovered | auto-logged by collector |
| Sat Oct 03 13:05:26 | Sat Oct 03 13:08:59 | polymarket_us | no heartbeat for > 60 s; duration 213 s; recovered | auto-logged by collector |
| Sat Oct 03 13:05:27 | Sat Oct 03 13:09:15 | kalshi_ws | no heartbeat for > 60 s; duration 228 s; recovered | auto-logged by collector |
| Sat Oct 03 12:44:54 | Sat Oct 03 13:09:21 | polymarket | no heartbeat for > 60 s; duration 1467 s; recovered | auto-logged by collector |
| Sat Oct 03 13:09:30 | Sat Oct 03 13:11:32 | polymarket_us | no heartbeat for > 60 s; duration 121 s; recovered | auto-logged by collector |
| Sat Oct 03 13:09:31 | Sat Oct 03 13:11:35 | kalshi_ws | no heartbeat for > 60 s; duration 124 s; recovered | auto-logged by collector |
| Sat Oct 03 13:11:44 | Sat Oct 03 13:11:45 | kalshi_ws | websocket error ConnectionClosedError; duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 13:09:31 | Sat Oct 03 13:13:27 | polymarket | no heartbeat for > 60 s; duration 236 s; recovered | auto-logged by collector |
| Sat Oct 03 13:13:28 | Sat Oct 03 13:13:38 | polymarket | websocket error ConnectionClosedError; duration 9 s; recovered | auto-logged by collector |
| Sat Oct 03 13:27:51 | Sat Oct 03 13:27:52 | kalshi_ws | websocket error ConnectionClosedError; duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 13:13:51 | Sat Oct 03 13:30:06 | polymarket | no heartbeat for > 60 s; duration 974 s; recovered | auto-logged by collector |
| Sat Oct 03 13:59:47 | Sat Oct 03 13:59:56 | polymarket | websocket error ConnectionClosedError; duration 8 s; recovered | auto-logged by collector |
| Sat Oct 03 14:00:09 | Sat Oct 03 14:00:16 | polymarket | websocket error ConnectionClosedError; duration 7 s; recovered | auto-logged by collector |
| Sat Oct 03 14:00:43 | Sat Oct 03 14:04:37 | polymarket_us | no heartbeat for > 60 s; duration 235 s; recovered | auto-logged by collector |
| Sat Oct 03 14:05:40 | Sat Oct 03 14:05:42 | kalshi_ws | websocket error ConnectionClosedError; duration 2 s; recovered | auto-logged by collector |
| Sat Oct 03 14:15:42 | Sat Oct 03 14:15:43 | kalshi_ws | websocket error ConnectionClosedError; duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 14:00:44 | Sat Oct 03 14:16:56 | polymarket | no heartbeat for > 60 s; duration 972 s; recovered | auto-logged by collector |
| Sat Oct 03 14:00:44 | Sat Oct 03 14:18:30 | all (Mac) | CPU starvation: a synthetic power simulation (8 worker processes) pushed load average to 182 on 8 cores; polymarket heartbeat gap 972 s logged above; Mac also on battery (53%, 56 min) | simulation killed 14:18 ET; no heavy compute on the recorder machines during games |
| Sat Oct 03 14:23:54 | Sat Oct 03 14:23:55 | kalshi_ws | resubscribe (market set changed); duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 15:01:10 | Sat Oct 03 15:01:15 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 15:01:46 | Sat Oct 03 15:01:51 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 15:04:06 | Sat Oct 03 15:04:07 | kalshi_ws | resubscribe (market set changed); duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 15:08:27 | Sat Oct 03 15:08:33 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 15:09:57 | Sat Oct 03 15:10:03 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 15:10:08 | Sat Oct 03 15:10:15 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 15:10:51 | Sat Oct 03 15:10:57 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 15:11:24 | Sat Oct 03 15:11:29 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 15:16:45 | Sat Oct 03 15:16:51 | polymarket | websocket error ConnectionClosedError; duration 7 s; recovered | auto-logged by collector |
| Sat Oct 03 15:23:05 | Sat Oct 03 15:23:12 | polymarket | websocket error ConnectionClosedError; duration 7 s; recovered | auto-logged by collector |
| Sat Oct 03 15:24:18 | Sat Oct 03 15:24:19 | kalshi_ws | resubscribe (market set changed); duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 15:31:08 | Sat Oct 03 15:31:14 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 15:34:29 | Sat Oct 03 15:34:31 | kalshi_ws | resubscribe (market set changed); duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 15:43:41 | Sat Oct 03 15:43:42 | kalshi_ws | resubscribe (market set changed); duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 15:51:19 | Sat Oct 03 15:51:33 | polymarket | resubscribe (market set changed); duration 14 s; recovered | auto-logged by collector |
| Sat Oct 03 15:53:53 | Sat Oct 03 15:53:54 | kalshi_ws | resubscribe (market set changed); duration 2 s; recovered | auto-logged by collector |
| Sat Oct 03 15:59:48 | Sat Oct 03 15:59:54 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 15:59:59 | Sat Oct 03 16:00:05 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 16:01:01 | Sat Oct 03 16:01:06 | polymarket | websocket error ConnectionClosedError; duration 5 s; recovered | auto-logged by collector |
| Sat Oct 03 16:01:51 | Sat Oct 03 16:01:57 | polymarket | websocket error ConnectionClosedError; duration 5 s; recovered | auto-logged by collector |
| Sat Oct 03 16:08:18 | Sat Oct 03 16:09:20 | polymarket | websocket error ConnectionClosedError; duration 62 s; recovered | auto-logged by collector |
| Sat Oct 03 16:08:23 | Sat Oct 03 16:09:52 | kalshi_ws | no heartbeat for > 60 s; duration 90 s; recovered | auto-logged by collector |
| Sat Oct 03 16:10:01 | Sat Oct 03 16:10:02 | kalshi_ws | websocket error ConnectionClosedError; duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 16:15:00 | Sat Oct 03 16:15:08 | polymarket | websocket error ConnectionClosedError; duration 8 s; recovered | auto-logged by collector |
| Sat Oct 03 16:15:12 | Sat Oct 03 16:15:13 | kalshi_ws | resubscribe (market set changed); duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 16:18:04 | Sat Oct 03 16:18:11 | polymarket | websocket error ConnectionClosedError; duration 7 s; recovered | auto-logged by collector |
| Sat Oct 03 16:24:34 | Sat Oct 03 16:24:50 | polymarket | websocket error ConnectionClosedError; duration 17 s; recovered | auto-logged by collector |
| Sat Oct 03 16:34:55 | Sat Oct 03 16:35:09 | polymarket | resubscribe (market set changed); duration 15 s; recovered | auto-logged by collector |
| Sat Oct 03 16:35:33 | Sat Oct 03 16:35:34 | kalshi_ws | resubscribe (market set changed); duration 1 s; recovered | auto-logged by collector |
| Sat Oct 03 16:41:50 | Sat Oct 03 16:41:58 | polymarket | websocket error ConnectionClosedError; duration 8 s; recovered | auto-logged by collector |
| Sat Oct 03 16:43:00 | Sat Oct 03 16:47:47 | polymarket | no heartbeat for > 60 s; duration 287 s; recovered | auto-logged by collector |
| Sat Oct 03 16:42:03 | Sat Oct 03 16:47:51 | kalshi_ws | no heartbeat for > 60 s; duration 348 s; recovered | auto-logged by collector |
| Sat Oct 03 16:48:24 | Sat Oct 03 16:48:30 | polymarket | websocket error ConnectionClosedError; duration 5 s; recovered | auto-logged by collector |
| Sat Oct 03 16:48:43 | Sat Oct 03 16:48:48 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 16:49:19 | Sat Oct 03 16:49:25 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 16:49:33 | Sat Oct 03 16:49:38 | polymarket | websocket error ConnectionClosedError; duration 5 s; recovered | auto-logged by collector |
| Sat Oct 03 16:49:54 | Sat Oct 03 16:50:00 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 16:50:21 | Sat Oct 03 16:50:28 | polymarket | websocket error ConnectionClosedError; duration 7 s; recovered | auto-logged by collector |
| Sat Oct 03 16:51:13 | Sat Oct 03 16:51:19 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 16:51:27 | Sat Oct 03 16:51:32 | polymarket | websocket error ConnectionClosedError; duration 5 s; recovered | auto-logged by collector |
| Sat Oct 03 17:01:39 | Sat Oct 03 17:01:53 | polymarket | resubscribe (market set changed); duration 14 s; recovered | auto-logged by collector |
| Sat Oct 03 17:11:58 | Sat Oct 03 17:12:12 | polymarket | resubscribe (market set changed); duration 14 s; recovered | auto-logged by collector |
| Sat Oct 03 17:16:52 | Sat Oct 03 17:16:58 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 17:27:02 | Sat Oct 03 17:27:17 | polymarket | resubscribe (market set changed); duration 15 s; recovered | auto-logged by collector |
| Sat Oct 03 17:31:50 | Sat Oct 03 17:31:56 | polymarket | websocket error ConnectionClosedError; duration 6 s; recovered | auto-logged by collector |
| Sat Oct 03 17:32:31 | Sat Oct 03 17:32:37 | polymarket | websocket error ConnectionClosedError; duration 5 s; recovered | auto-logged by collector |
