#!/bin/bash
# Stop ONE teammate recorder started by collector/teammate_setup.sh, by its id.
# Only that recorder's own processes are signalled (its restart loop, its collector child and
# its caffeinate wrapper), found from the PID files the setup script writes. Any other recorder
# on the same machine, including Divi's main one, is left running.
#   bash collector/teammate_stop.sh <id>
set -euo pipefail
ID="${1:?usage: bash collector/teammate_stop.sh <recorder-id>}"
cd "$(dirname "$0")/.."
LOOP_PID_FILE="out/collector_$ID.loop.pid"
WRAP_PID_FILE="out/collector_$ID.pid"
[ -f "$LOOP_PID_FILE" ] || { echo "no $LOOP_PID_FILE: is recorder $ID running from this folder?"; exit 1; }
LOOP_PID="$(cat "$LOOP_PID_FILE")"
if kill -0 "$LOOP_PID" 2>/dev/null; then
  # Stop the collector child first (it flushes its buffer on SIGTERM), then the loop before it
  # can restart the child (the loop sleeps 5 s between restarts).
  pkill -TERM -P "$LOOP_PID" 2>/dev/null || true
  sleep 2
  kill -TERM "$LOOP_PID" 2>/dev/null || true
  echo "stopped recorder $ID (loop pid $LOOP_PID)"
else
  echo "recorder $ID loop (pid $LOOP_PID) is not running"
fi
if [ -f "$WRAP_PID_FILE" ]; then
  WRAP_PID="$(cat "$WRAP_PID_FILE")"
  [ "$WRAP_PID" != "$LOOP_PID" ] && kill -TERM "$WRAP_PID" 2>/dev/null || true
fi
rm -f "$LOOP_PID_FILE" "$WRAP_PID_FILE"
