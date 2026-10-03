# Server .env layout (/opt/gqh/.env, mode 600)

Same variable names as `.env.example`. The recorder reads only these:

| Variable | Needed for | Notes |
|---|---|---|
| `KALSHI_API_KEY_ID` | Kalshi websocket | Without it the recorder uses REST polling (works, no key) |
| `KALSHI_PRIVATE_KEY_PATH` | Kalshi websocket | `deploy_vultr.sh` rewrites it to `/opt/gqh/keys/kalshi.pem` |
| `TIGER_DATABASE_URL` | Tiger Data writes | `postgres://tsdbadmin:<password>@<host>:<port>/tsdb?sslmode=require`; without it, local parquet only |

Local parquet backup lands in `/opt/gqh/data/live/<venue>/<YYYYMMDD>/`. The unit file runs as root
from `/opt/gqh` with `Restart=always`, `RestartSec=5`.

Restart test (T4 done-when): `collector.health --minutes 30`, then `systemctl restart gqh-collector`,
wait 30 min, `collector.health --minutes 30` again. With Tiger: `python -m store.timescale health`
before and after.
