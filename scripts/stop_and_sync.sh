#!/bin/bash
# The 00:30 sequence. Run ONLY on Divi's "stop recorders"; then stop and report. The one run starts only on
# "final test run".
#   VULTR_HOST=<ip> RUN_COMMIT=<main commit to run from> scripts/stop_and_sync.sh
# The host is read from the environment and never written to a file. Run from the staleline/ checkout.
#  1. confirm the last v2 Amendment 4 window has ended (last kept kickoff 20:00 ET + 4.5 h = 00:30 ET Oct 4)
#  2. stop gqh-collector on Vultr (systemctl stop: SIGTERM, flushes) and the Mac collector (supervise.sh loop first)
#  3. FREEZE INPUTS before touching git: Mac GAPS.md -> data/mac/GAPS_mac.md, Mac heartbeat logs -> data/mac/heartbeats/,
#     Vultr out/GAPS_vultr.md -> data/vultr/GAPS_vultr.md, Vultr heartbeat logs -> data/vultr/heartbeats/;
#     sha256 of each -> results/holdout_inputs_manifest.txt (the runner reads only these frozen copies)
#  4. rsync the Vultr recordings into data/vultr/data/live/; a second --checksum pass must list 0 files; file counts
#     per feed, Vultr vs local
#  5. commit the auto-logged GAPS.md / STATUS.md changes (never discarded), remove the ../wt-main worktree (code
#     only, already on main), check out main at RUN_COMMIT; git status clean for tracked files; data/ file count and
#     a hash of the frozen inputs unchanged before vs after
#  6. scripts/final_test_run.py --checklist-only (includes: manifest hashes = the files the runner reads)
set -euo pipefail
cd "$(dirname "$0")/.."
: "${VULTR_HOST:?set VULTR_HOST in the environment (not in any file)}"
: "${RUN_COMMIT:?set RUN_COMMIT to the main commit the run starts from}"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=15 root@${VULTR_HOST}"
END_ET="2026-10-04 00:30:00"
FEEDS="kalshi polymarket polymarket_us"
datacount() { find data -type f | wc -l | tr -d ' '; }

echo "== 1. last Amendment 4 window"
now=$(TZ=America/New_York date "+%Y-%m-%d %H:%M:%S")
if [[ "$now" < "$END_ET" ]]; then echo "now $now ET is before $END_ET ET: not ended; stopping"; exit 1; fi
echo "now $now ET >= $END_ET ET: the last window (kickoff 20:00 ET + 4.5 h) has ended"

echo "== 2. stop recorders"
$SSH 'systemctl stop gqh-collector; echo "vultr gqh-collector: $(systemctl is-active gqh-collector || true)"'
pkill -f "collector/watch_vultr.sh" || true    # the local Vultr watcher would alert on the planned stop
pkill -f "collector/supervise.sh" || true
pkill -TERM -f "python -m collector.run" || true
for i in $(seq 1 30); do pgrep -f "python -m collector.run" >/dev/null || break; sleep 1; done
if pgrep -f "python -m collector.run" >/dev/null; then echo "Mac collector still running after 30 s"; exit 1; fi
echo "Mac collector stopped"

echo "== 3. freeze inputs"
mkdir -p data/mac/heartbeats data/vultr/heartbeats results
cp -p GAPS.md data/mac/GAPS_mac.md
cp -p data/live/heartbeat/*.jsonl data/mac/heartbeats/
rsync -a "root@${VULTR_HOST}:/opt/gqh/out/GAPS_vultr.md" data/vultr/GAPS_vultr.md
rsync -a "root@${VULTR_HOST}:/opt/gqh/data/live/heartbeat/" data/vultr/heartbeats/
shasum -a 256 data/mac/GAPS_mac.md data/mac/heartbeats/*.jsonl data/vultr/GAPS_vultr.md data/vultr/heartbeats/*.jsonl \
  > results/holdout_inputs_manifest.txt
echo "manifest: $(wc -l < results/holdout_inputs_manifest.txt | tr -d ' ') files, sha256 $(shasum -a 256 results/holdout_inputs_manifest.txt | cut -c1-16)"

echo "== 4. rsync Vultr recordings"
mkdir -p data/vultr/data/live
rsync -a "root@${VULTR_HOST}:/opt/gqh/data/live/" data/vultr/data/live/
n=$(rsync -a --checksum --dry-run --itemize-changes "root@${VULTR_HOST}:/opt/gqh/data/live/" data/vultr/data/live/ | wc -l | tr -d ' ')
echo "checksum second pass: $n differing files (must be 0)"
[ "$n" = "0" ] || { echo "VERIFY FAILED"; exit 1; }
for f in $FEEDS; do
  r=$($SSH "find /opt/gqh/data/live/$f -type f | wc -l" | tr -d ' ')
  l=$(find "data/vultr/data/live/$f" -type f | wc -l | tr -d ' ')
  echo "$f: vultr $r, local $l $([ "$r" = "$l" ] && echo OK || echo MISMATCH)"
  [ "$r" = "$l" ] || exit 1
done

echo "== 5. git: keep auto-logged changes, move to main at RUN_COMMIT"
before=$(datacount); frozen_before=$(shasum -a 256 results/holdout_inputs_manifest.txt | cut -c1-64)
if ! git diff --quiet -- GAPS.md STATUS.md; then
  git add GAPS.md STATUS.md
  git commit -q -m "Auto-logged GAPS.md and STATUS.md at recorder stop (kept, not discarded)"
  echo "committed auto-logged changes on $(git branch --show-current): $(git log -1 --format=%h)"
fi
if [ -d ../wt-main ]; then
  rm -rf ../wt-main/results/dryrun ../wt-main/results/dryrun_gatefail   # ignored dry-run outputs only
  git worktree remove ../wt-main
fi
[ "$(git rev-parse main)" = "$(git rev-parse "$RUN_COMMIT")" ] || { echo "main is not at RUN_COMMIT"; exit 1; }
git checkout -q main
echo "checked out main at $(git rev-parse --short HEAD)"
[ -z "$(git status --porcelain --untracked-files=no)" ] && echo "tracked files clean" || { git status --short; exit 1; }
after=$(datacount)
echo "data/ files before $before, after $after $([ "$before" = "$after" ] && echo OK || echo CHANGED)"
[ "$before" = "$after" ] || exit 1
shasum -a 256 -c --quiet results/holdout_inputs_manifest.txt && echo "frozen inputs unchanged after checkout"

echo "== 6. checklist only"
python3 scripts/final_test_run.py --checklist-only
echo "done; the one run starts only on \"final test run\""
