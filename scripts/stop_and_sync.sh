#!/bin/bash
# The 00:30 sequence (run ONLY on Divi's "stop recorders"). Then stop and report; the one run starts only on
# "final test run".
#   VULTR_HOST=<ip> scripts/stop_and_sync.sh          (the host is read from the environment, never written to a file)
# Steps:
#   a. confirm the last v2 Amendment 4 window has ended (last kept kickoff 20:00 ET Oct 3 + 4.5 h = 00:30 ET Oct 4)
#   b. stop gqh-collector on Vultr (systemctl stop: SIGTERM, the collector flushes first) and the Mac collector
#      (stop the supervise.sh restart loop first, then SIGTERM the collector and wait for it to exit)
#   c. rsync Vultr /opt/gqh/data/live/ -> data/vultr/data/live/ and /opt/gqh/out/GAPS_vultr.md -> data/vultr/
#   d. verify: a second rsync pass with --checksum --dry-run must list 0 files; file counts per feed match
#   e. run the checklist part of scripts/final_test_run.py only (no lock, nothing evaluated)
set -euo pipefail
cd "$(dirname "$0")/.."
: "${VULTR_HOST:?set VULTR_HOST in the environment (not in any file)}"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=15 root@${VULTR_HOST}"
END_ET="2026-10-04 00:30:00"

echo "== a. last Amendment 4 window"
now=$(TZ=America/New_York date "+%Y-%m-%d %H:%M:%S")
if [[ "$now" < "$END_ET" ]]; then echo "now $now ET is before $END_ET ET: the last window has not ended; stopping"; exit 1; fi
echo "now $now ET >= $END_ET ET: last window (kickoff 20:00 ET + 4.5 h) has ended"

echo "== b. stop recorders"
$SSH 'systemctl stop gqh-collector; systemctl is-active gqh-collector || true'
pkill -f "collector/supervise.sh" || true
pkill -TERM -f "python -m collector.run" || true
for i in $(seq 1 30); do pgrep -f "python -m collector.run" >/dev/null || break; sleep 1; done
pgrep -f "python -m collector.run" >/dev/null && { echo "Mac collector still running after 30 s"; exit 1; } || echo "Mac collector stopped"

echo "== c. rsync Vultr -> data/vultr/"
mkdir -p data/vultr/data/live
rsync -a "root@${VULTR_HOST}:/opt/gqh/data/live/" data/vultr/data/live/
rsync -a "root@${VULTR_HOST}:/opt/gqh/out/GAPS_vultr.md" data/vultr/GAPS_vultr.md

echo "== d. verify"
n=$(rsync -a --checksum --dry-run --itemize-changes "root@${VULTR_HOST}:/opt/gqh/data/live/" data/vultr/data/live/ | wc -l | tr -d ' ')
echo "checksum second pass: $n differing files (must be 0)"
[ "$n" = "0" ] || { echo "VERIFY FAILED"; exit 1; }
for f in kalshi polymarket polymarket_us heartbeat; do
  r=$($SSH "find /opt/gqh/data/live/$f -type f | wc -l" | tr -d ' ')
  l=$(find "data/vultr/data/live/$f" -type f | wc -l | tr -d ' ')
  echo "$f: vultr $r, local $l $([ "$r" = "$l" ] && echo OK || echo MISMATCH)"
done

echo "== e. checklist only"
.venv/bin/python scripts/final_test_run.py --checklist-only 2>/dev/null || python3 scripts/final_test_run.py --checklist-only
echo "done; the one run starts only on \"final test run\""
