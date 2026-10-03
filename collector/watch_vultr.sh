#!/bin/bash
# Read-only watchdog for the Vultr recorder, run on the Mac. Never restarts anything.
# Every INTERVAL_S seconds: is gqh-collector active, and how old is each feed's last_ok in the
# newest heartbeat file. Alerts (macOS notification + a line in out/vultr_watch.log) if the unit is
# not active, ssh fails, or any feed is older than MAX_AGE_S.
# Usage: VULTR_HOST=<ip> caffeinate -i collector/watch_vultr.sh [--once]
# The host comes from the environment only; it is never written to the repo or the log.
set -u
cd "$(dirname "$0")/.."
: "${VULTR_HOST:?set VULTR_HOST}"
INTERVAL_S=${INTERVAL_S:-120}
MAX_AGE_S=${MAX_AGE_S:-60}
LOG=out/vultr_watch.log
mkdir -p out

read -r -d '' REMOTE <<EOF
systemctl is-active gqh-collector
python3 - <<'PY'
import glob, json, datetime as dt
f = sorted(glob.glob("/opt/gqh/data/live/heartbeat/*.jsonl"))[-1]
last = {}
for line in open(f).readlines()[-200:]:
    try:
        r = json.loads(line)
    except ValueError:
        continue
    if r.get("last_ok_utc"):
        last[r["venue"]] = r["last_ok_utc"]
now = dt.datetime.now(dt.timezone.utc)
age = {v: (now - dt.datetime.fromisoformat(t)).total_seconds() for v, t in last.items()}
# Kalshi is alive if either the websocket or the REST fallback is
age["kalshi"] = min(age.pop("kalshi_ws", 1e9), age.pop("kalshi_rest", 1e9))
for v in ("kalshi", "polymarket", "polymarket_us"):
    print(f"{v} {age.get(v, 1e9):.0f}")
PY
EOF

alert() {
    echo "$(date '+%a %b %d %H:%M:%S %Z') ALERT $1" | tee -a "$LOG"
    osascript -e "display notification \"$1\" with title \"Vultr recorder\" sound name \"Basso\"" >/dev/null 2>&1
}

while true; do
    out=$(ssh -o ConnectTimeout=10 -o BatchMode=yes "root@$VULTR_HOST" "$REMOTE" 2>/dev/null)
    rc=$?
    stamp=$(date '+%a %b %d %H:%M:%S %Z')
    if [ $rc -ne 0 ] && [ -z "$out" ]; then
        alert "ssh failed (rc $rc)"
    else
        state=$(echo "$out" | head -1)
        ages=$(echo "$out" | tail -n +2 | tr '\n' ' ')
        line="$stamp unit=$state ages_s: $ages"
        echo "$line" | tee -a "$LOG"
        [ "$state" != "active" ] && alert "gqh-collector is $state"
        echo "$out" | tail -n +2 | while read -r v a; do
            [ "${a%.*}" -gt "$MAX_AGE_S" ] 2>/dev/null && alert "$v heartbeat ${a} s old"
        done
    fi
    [ "${1:-}" = "--once" ] && break
    sleep "$INTERVAL_S"
done
