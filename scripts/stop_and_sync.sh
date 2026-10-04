#!/bin/bash
# The 00:30 sequence. Run ONLY on Divi's "stop recorders"; then stop and report. The one run starts only on
# "final test run".
#   VULTR_HOST=<ip> RUN_COMMIT=<main commit> scripts/stop_and_sync.sh       real, from the staleline/ checkout
#   scripts/stop_and_sync.sh --rehearse                                     throwaway rehearsal, see below
# The host is read from the environment and never written to a file.
#  1. confirm the last v2 Amendment 4 window has ended (last kept kickoff 20:00 ET + 4.5 h = 00:30 ET Oct 4)
#  2. stop gqh-collector on Vultr (systemctl stop: SIGTERM, flushes), the local Vultr watcher, and the Mac collector
#     (its supervise.sh restart loop first)
#  3. FREEZE INPUTS before touching git: Mac GAPS.md -> data/mac/GAPS_mac.md, Mac heartbeat logs -> data/mac/heartbeats/,
#     Vultr out/GAPS_vultr.md -> data/vultr/GAPS_vultr.md, Vultr heartbeat logs -> data/vultr/heartbeats/;
#     sha256 of each -> results/holdout_inputs_manifest.txt (the runner reads only these frozen copies)
#  4. rsync the Vultr recordings into data/vultr/data/live/; a second --checksum pass must list 0 files; file counts
#     per feed, Vultr vs local
#  5. commit the auto-logged GAPS.md / STATUS.md changes (never discarded), remove the ../wt-main worktree (code
#     only, already on main), check out main at RUN_COMMIT; tracked files clean; data/ file count unchanged; the
#     manifest re-verified
#  6. scripts/final_test_run.py --checklist-only (includes: manifest hashes = the files the runner reads)
# --rehearse: everything runs against throwaway copies in a temp dir: a clone of this repo at main (with a fake
# "t13" branch and a ../wt-main worktree), a local fake Vultr tree instead of ssh/rsync to the host, uniquely named
# fake collector processes, and fake recordings and heartbeats. The 00:30 gate is skipped. Nothing real is stopped
# and no real git state changes (the only real file read is data/live/holdout_seconds_delay.csv, copied for step 6;
# REHEARSE_DATA_FROM=<checkout with data/> when rehearsing from a checkout without data, e.g. ../wt-main).
set -euo pipefail
cd "$(dirname "$0")/.."
REH=0
# rehearsal fake processes never outlive the script
trap '[ "${REH:-0}" = 1 ] && [ -n "${T:-}" ] && pkill -f "$T/fake" 2>/dev/null; true' EXIT
[ "${1:-}" = "--rehearse" ] && REH=1
END_ET="2026-10-04 00:30:00"
FEEDS="kalshi polymarket polymarket_us"
datacount() { find data -type f | wc -l | tr -d ' '; }

if [ $REH = 1 ]; then
  REAL=$(pwd)
  T=$(mktemp -d "${TMPDIR:-/tmp}/stop_and_sync_rehearse.XXXXXX")
  echo "== rehearsal in $T (nothing real is touched)"
  git clone -q --no-hardlinks "$REAL" "$T/repo"
  # rehearse the code that will become main: the clone's main = this checkout's HEAD
  SRC_HEAD=$(git -C "$REAL" rev-parse HEAD)
  git -C "$T/repo" checkout -q --detach "$SRC_HEAD" && git -C "$T/repo" branch -f main "$SRC_HEAD"
  # fake Vultr host tree (/opt/gqh)
  V="$T/vultr"
  for f in $FEEDS; do mkdir -p "$V/data/live/$f/20261003"; for i in 1 2 3; do echo "fake $f $i" > "$V/data/live/$f/20261003/${i}_1.parquet"; done; done
  mkdir -p "$V/data/live/heartbeat" "$V/out"
  echo '{"venue": "kalshi_ws", "recv_utc": "2026-10-03T14:08:00+00:00", "connected": true, "last_ok_utc": "2026-10-03T14:08:00+00:00"}' > "$V/data/live/heartbeat/20261003.jsonl"
  printf '| Start (ET) | End (ET) | Venue | Cause | Fixed by |\n|---|---|---|---|---|\n' > "$V/out/GAPS_vultr.md"
  # fake collector processes with unique command lines
  mkdir -p "$T/fake"
  for n in watch_vultr_fake supervise_fake collector_run_fake; do
    printf '#!/bin/bash\ntrap "exit 0" TERM\nwhile true; do sleep 1; done\n' > "$T/fake/$n.sh"; chmod +x "$T/fake/$n.sh"
    nohup "$T/fake/$n.sh" >/dev/null 2>&1 &
  done
  sleep 1
  cd "$T/repo"
  git checkout -q -b rehearse-t13            # like staleline on t13 while main is checked out in ../wt-main
  git worktree add -q ../wt-main main
  mkdir -p results ../wt-main/results/dryrun && echo x > ../wt-main/results/dryrun/ignored.txt
  # fake Mac recordings, heartbeats and an auto-logged GAPS.md change; the real delay file for the hash check
  for f in $FEEDS; do mkdir -p "data/live/$f/20261003"; echo "fake mac $f" > "data/live/$f/20261003/1_1.parquet"; done
  mkdir -p data/live/heartbeat && cp "$V/data/live/heartbeat/20261003.jsonl" data/live/heartbeat/
  cp "${REHEARSE_DATA_FROM:-$REAL}/data/live/holdout_seconds_delay.csv" data/live/holdout_seconds_delay.csv
  echo "| Sun Oct 04 00:30:01 | Sun Oct 04 00:30:02 | kalshi_ws | rehearsal auto-logged row | rehearsal |" >> GAPS.md
  RUN_COMMIT=$(git rev-parse main)
  RSRC="$V"
  rcmd() { bash -c "${1//\/opt\/gqh/$V}"; }
  STOP_VULTR='echo "(rehearse) vultr: systemctl stop gqh-collector skipped"'
  WATCH_PAT="$T/fake/watch_vultr_fake.sh"; SUP_PAT="$T/fake/supervise_fake.sh"; COL_PAT="$T/fake/collector_run_fake.sh"
else
  : "${VULTR_HOST:?set VULTR_HOST in the environment (not in any file)}"
  : "${RUN_COMMIT:?set RUN_COMMIT to the main commit the run starts from}"
  SSH="ssh -o BatchMode=yes -o ConnectTimeout=15 root@${VULTR_HOST}"
  RSRC="root@${VULTR_HOST}:/opt/gqh"
  rcmd() { $SSH "$1"; }
  STOP_VULTR='systemctl stop gqh-collector; echo "vultr gqh-collector: $(systemctl is-active gqh-collector || true)"'
  WATCH_PAT="collector/watch_vultr.sh"; SUP_PAT="collector/supervise.sh"; COL_PAT="python -m collector.run"
fi

echo "== 1. last Amendment 4 window"
now=$(TZ=America/New_York date "+%Y-%m-%d %H:%M:%S")
if [ $REH = 1 ]; then echo "(rehearse) time gate skipped (now $now ET)"
elif [[ "$now" < "$END_ET" ]]; then echo "now $now ET is before $END_ET ET: not ended; stopping"; exit 1
else echo "now $now ET >= $END_ET ET: the last window (kickoff 20:00 ET + 4.5 h) has ended"; fi

echo "== 2. stop recorders"
if [ $REH = 1 ]; then eval "$STOP_VULTR"; else rcmd "$STOP_VULTR"; fi
pkill -f "$WATCH_PAT" || true
pkill -f "$SUP_PAT" || true
pkill -TERM -f "$COL_PAT" || true
for i in $(seq 1 30); do pgrep -f "$COL_PAT" >/dev/null || break; sleep 1; done
if pgrep -f "$COL_PAT" >/dev/null || pgrep -f "$SUP_PAT" >/dev/null; then echo "collector still running after 30 s"; exit 1; fi
echo "Mac collector, supervisor and watcher stopped"

echo "== 3. freeze inputs"
mkdir -p data/mac/heartbeats data/vultr/heartbeats results
cp -p GAPS.md data/mac/GAPS_mac.md
cp -p data/live/heartbeat/*.jsonl data/mac/heartbeats/
rsync -a "$RSRC/out/GAPS_vultr.md" data/vultr/GAPS_vultr.md
rsync -a "$RSRC/data/live/heartbeat/" data/vultr/heartbeats/
shasum -a 256 data/mac/GAPS_mac.md data/mac/heartbeats/*.jsonl data/vultr/GAPS_vultr.md data/vultr/heartbeats/*.jsonl \
  > results/holdout_inputs_manifest.txt
echo "manifest: $(wc -l < results/holdout_inputs_manifest.txt | tr -d ' ') files, sha256 $(shasum -a 256 results/holdout_inputs_manifest.txt | cut -c1-16)"

echo "== 4. rsync Vultr recordings"
mkdir -p data/vultr/data/live
rsync -a "$RSRC/data/live/" data/vultr/data/live/
n=$(rsync -a --checksum --dry-run --itemize-changes "$RSRC/data/live/" data/vultr/data/live/ | wc -l | tr -d ' ')
echo "checksum second pass: $n differing files (must be 0)"
[ "$n" = "0" ] || { echo "VERIFY FAILED"; exit 1; }
for f in $FEEDS; do
  r=$(rcmd "find /opt/gqh/data/live/$f -type f | wc -l" | tr -d ' ')
  l=$(find "data/vultr/data/live/$f" -type f | wc -l | tr -d ' ')
  echo "$f: vultr $r, local $l $([ "$r" = "$l" ] && echo OK || echo MISMATCH)"
  [ "$r" = "$l" ] || exit 1
done

echo "== 5. git: keep auto-logged changes, move to main at RUN_COMMIT"
before=$(datacount)
if ! git diff --quiet -- GAPS.md STATUS.md; then
  git add GAPS.md STATUS.md
  git commit -q -m "Auto-logged GAPS.md and STATUS.md at recorder stop (kept, not discarded)"
  echo "committed auto-logged changes on $(git branch --show-current): $(git log -1 --format=%h)"
fi
if [ -d ../wt-main ]; then
  rm -rf ../wt-main/results/dryrun ../wt-main/results/dryrun_gatefail   # ignored dry-run outputs only
  git worktree remove ../wt-main
  echo "removed ../wt-main"
fi
[ "$(git rev-parse main)" = "$(git rev-parse "$RUN_COMMIT")" ] || { echo "main is not at RUN_COMMIT"; exit 1; }
git checkout -q main
echo "checked out main at $(git rev-parse --short HEAD) (RUN_COMMIT $(git rev-parse --short "$RUN_COMMIT"))"
if [ -z "$(git status --porcelain --untracked-files=no)" ]; then echo "tracked files clean"; else git status --short; exit 1; fi
after=$(datacount)
echo "data/ files before $before, after $after $([ "$before" = "$after" ] && echo OK || echo CHANGED)"
[ "$before" = "$after" ] || exit 1
shasum -a 256 -c --quiet results/holdout_inputs_manifest.txt && echo "frozen inputs unchanged after checkout"

echo "== 6. checklist only"
set +e
python3 scripts/final_test_run.py --checklist-only
rc=$?
set -e
if [ $REH = 1 ]; then
  echo "(rehearse) checklist exit $rc; fake processes left: $(pgrep -f "$T/fake" | wc -l | tr -d ' '); temp dir $T"
fi
[ $rc = 0 ] || exit $rc
echo "done; the one run starts only on \"final test run\""
