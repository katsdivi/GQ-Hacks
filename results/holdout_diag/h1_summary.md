# h1 poll (exploratory, post-run, live 2026-10-04 03:15 ET)

- market: aec-nfl-ind-was-2026-10-04; 60 requests every 2 s for 120 s; statuses: {200: 60}
- response time (elapsed) median 0.026 s, max 0.127 s
- body changed on 0 of 59 consecutive pairs; best bid/ask changed on 0
- intervals between body changes (s): n/a (fewer than 2 changes)
- distinct Age header values: ['1', '11', '12', '13', '15', '17', '18', '19', '2', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '3']
- Cache-Control values: ['public, max-age=30']
- CF-Cache-Status values: ['EXPIRED', 'HIT']; X-Cache: []
- distinct ETags: 0
- Header check (3 batch requests, 2 s apart): request 1 cf-cache-status EXPIRED; requests 2 and 3 HIT with Age 2 and 4, identical last-modified, Cache-Control "public, max-age=30", expires = last-modified + 30 s. Server: cloudflare. Also X-Pm-Server-Latency: 58 (ms, presumably origin time).
- Response fields with times that the collector did NOT record: headers Age, last-modified, expires, Date; body updatedAt (seconds; 07:07:53Z on a request at 07:16:18Z, so not a per-quote time), ep3SyncedAt, createdAt.
- Reading (facts only): the book endpoint the collector polled is served from a Cloudflare cache for up to 30 s (Age seen 1 to 29 s). No body change in 120 s at 03:14 ET (a quiet pre-game hour), so the change-interval distribution could not be measured live; h0 found the median gap between recorded quote changes in the Oct 3 game windows was about 31 to 32 s in most games.
