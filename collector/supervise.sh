#!/bin/bash
# Local stand-in for systemd Restart=always: rerun the collector 5 s after it exits.
# Keeps the Mac awake while it runs (caffeinate -dims). On battery, -s is ignored and closing the lid still sleeps the Mac.
#   nohup collector/supervise.sh >> out/collector.log 2>&1 &
#   restart test: pkill -f "python -m collector.run"   (supervisor brings it back)
#   stop:         pkill -f collector/supervise.sh; pkill -f "python -m collector.run"
cd "$(dirname "$0")/.."
while true; do
  caffeinate -dims .venv/bin/python -m collector.run
  echo "$(date -u +%FT%TZ) collector exited with $?; restarting in 5 s"
  sleep 5
done
