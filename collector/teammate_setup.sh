#!/bin/bash
# StaleLine second recorder: one command to run an independent copy of the live recorder
# (python -m collector.run) on a teammate's own Mac or Linux laptop.
#
# It records public data only (Kalshi public REST + the public polymarket.com market
# websocket). No keys, no Tiger Data: this copy writes local parquet only, into its own
# folder, so Divi can merge it with the main recording later (collector/merge_recordings.py).
#
# Usage, from inside a repo copy:
#   bash collector/teammate_setup.sh                 # recorder id = short hostname
#   bash collector/teammate_setup.sh alden           # recorder id = alden
#   bash collector/teammate_setup.sh --id alden
#
# Usage, starting from the bundle or folder Divi sent you (clones/copies it first):
#   bash teammate_setup.sh ~/Downloads/staleline.bundle
#   bash teammate_setup.sh ~/Downloads/staleline --id alden --dest ~/staleline
#
# Options:
#   --id ID       recorder id (default: short hostname). Output goes to data/live_<ID>.
#   --from PATH   git bundle, git repo or plain folder to clone/copy first.
#                 A bare positional argument that is an existing file or folder means --from.
#   --dest DIR    where to put the clone/copy (default: ./staleline).
#
# What it does:
#   1. (optional) clone the bundle / copy the folder (never copies .env, keys, data or out)
#   2. create .venv and pip install -r requirements.txt
#   3. create .env from .env.example only if .env is missing (all keys left empty)
#   4. start the recorder in a restart loop with nohup (under caffeinate on macOS),
#      COLLECTOR_LIVE_DIR=data/live_<ID>, COLLECTOR_GAPS_MD=out/GAPS_<ID>.md,
#      log out/collector_<ID>.log
#   5. print the commands to check health, stop it and send the output back
set -euo pipefail

ID=""
SRC=""
DEST=""
while [ $# -gt 0 ]; do
  case "$1" in
    --id) ID="${2:?--id needs a value}"; shift 2 ;;
    --id=*) ID="${1#--id=}"; shift ;;
    --from) SRC="${2:?--from needs a path}"; shift 2 ;;
    --from=*) SRC="${1#--from=}"; shift ;;
    --dest) DEST="${2:?--dest needs a path}"; shift 2 ;;
    --dest=*) DEST="${1#--dest=}"; shift ;;
    -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *)
      if [ -e "$1" ] && [ -z "$SRC" ]; then SRC="$1"; else ID="$1"; fi
      shift ;;
  esac
done

if [ -z "$ID" ]; then
  ID="$(hostname -s 2>/dev/null || hostname)"
fi
# Keep the id safe for folder names: letters, digits, dash, underscore.
ID="$(printf '%s' "$ID" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_-' '_' | sed 's/_*$//')"
[ -n "$ID" ] || ID="teammate"

say() { printf '\n== %s\n' "$*"; }

# ---- 1. get a repo copy -------------------------------------------------------------
if [ -n "$SRC" ]; then
  [ -n "$DEST" ] || DEST="$PWD/staleline"
  if [ -e "$DEST" ]; then
    echo "destination already exists: $DEST (pass --dest somewhere else, or run collector/teammate_setup.sh inside it)" >&2
    exit 1
  fi
  if [ -f "$SRC" ]; then
    say "cloning bundle $SRC -> $DEST"
    git clone -q "$SRC" "$DEST" 2>/dev/null || git clone -q -b main "$SRC" "$DEST"
  elif git -C "$SRC" rev-parse --git-dir >/dev/null 2>&1; then
    say "cloning repo $SRC -> $DEST (committed files only, so no .env or data)"
    git clone -q "$SRC" "$DEST"
  else
    say "copying folder $SRC -> $DEST (skipping .env, keys, .venv, data, out)"
    mkdir -p "$DEST"
    rsync -a --exclude '.env' --exclude '*.pem' --exclude '*.key' --exclude '.venv' \
      --exclude 'data/live*' --exclude 'out/*' --exclude '__pycache__' "$SRC"/ "$DEST"/
  fi
  REPO="$(cd "$DEST" && pwd)"
else
  REPO="$(cd "$(dirname "$0")/.." && pwd)"
fi
cd "$REPO"
if [ ! -f collector/run.py ] || [ ! -f requirements.txt ]; then
  echo "$REPO does not look like a StaleLine repo (no collector/run.py)" >&2
  exit 1
fi

LIVE_DIR="$REPO/data/live_$ID"
GAPS_MD="$REPO/out/GAPS_$ID.md"
LOG="$REPO/out/collector_$ID.log"
TAG="staleline-recorder-$ID"

# ---- 2. venv + requirements ---------------------------------------------------------
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || { echo "python3 not found; install Python 3.11+ first" >&2; exit 1; }
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "warning: $("$PY" --version 2>&1) found; Python 3.11+ is recommended (set PYTHON=/path/to/python3.11)" >&2
fi
if [ ! -x .venv/bin/python ]; then
  say "creating .venv"
  "$PY" -m venv .venv
fi
say "installing requirements (a few minutes the first time)"
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt

# ---- 3. .env (keys stay empty) ------------------------------------------------------
if [ ! -f .env ]; then
  say "creating .env from .env.example (no keys needed for this recorder)"
  cp .env.example .env
  {
    echo ""
    echo "# Second recorder ($ID): local parquet only, public data only."
    echo "COLLECTOR_LIVE_DIR=$LIVE_DIR"
    echo "COLLECTOR_GAPS_MD=$GAPS_MD"
  } >> .env
else
  say ".env already exists; leaving it as is"
fi
if grep -Eq '^[[:space:]]*TIGER_DATABASE_URL[[:space:]]*=[[:space:]]*[^[:space:]#]' .env; then
  echo "note: .env has TIGER_DATABASE_URL set; this recorder ignores it (forced empty below), local parquet only"
fi

# ---- 4. start the restart loop ------------------------------------------------------
mkdir -p "$LIVE_DIR" "$REPO/out"
if [ ! -f "$GAPS_MD" ]; then
  printf '# Recorder gaps (%s)\n\n| Start (ET) | End (ET) | Venue | Cause | Fixed by |\n|---|---|---|---|---|\n' "$ID" > "$GAPS_MD"
fi

if pgrep -f "$TAG" >/dev/null 2>&1; then
  say "recorder $ID is already running (not starting a second copy)"
else
  # The ": $TAG" no-op tags the loop's command line so pkill -f can find exactly this loop.
  LOOP=": $TAG; cd \"$REPO\"; while true; do .venv/bin/python -m collector.run; echo \"\$(date -u +%FT%TZ) collector exited with \$?; restarting in 5 s\"; sleep 5; done"
  export COLLECTOR_LIVE_DIR="$LIVE_DIR" COLLECTOR_GAPS_MD="$GAPS_MD"
  # Second recorder never writes Tiger Data and never uses Kalshi keys (public REST is enough).
  export TIGER_DATABASE_URL="" KALSHI_API_KEY_ID="" KALSHI_PRIVATE_KEY_PATH=""
  echo "$(date -u +%FT%TZ) teammate_setup: starting recorder $ID" >> "$LOG"
  if [ "$(uname -s)" = "Darwin" ]; then
    # -i: no idle sleep, -s: no system sleep while on AC power. Closing the lid still sleeps the Mac.
    nohup caffeinate -i -s bash -c "$LOOP" >> "$LOG" 2>&1 &
  else
    nohup bash -c "$LOOP" >> "$LOG" 2>&1 &
  fi
  echo $! > "$REPO/out/collector_$ID.pid"
  say "recorder $ID started (pid $!), logging to out/collector_$ID.log"
  sleep 3
  tail -n 5 "$LOG" || true
fi

# ---- 5. how to check, stop and send back --------------------------------------------
STAMP='$(date +%Y%m%d_%H%M)'
cat <<EOF

==================================================================
Second recorder "$ID" is running from: $REPO
Output: data/live_$ID/<venue>/<YYYYMMDD>/*.parquet

KEEP THE LAPTOP PLUGGED IN WITH THE LID OPEN. Closing the lid or running on
battery lets it sleep, and a sleeping laptop records nothing. Stay on Wi-Fi.

Check health (row counts only, no prices), from $REPO:
  .venv/bin/python -m collector.health --dir data/live_$ID --minutes 10
  tail -n 20 out/collector_$ID.log
  cat out/GAPS_$ID.md

Stop it:
  pkill -f $TAG; pkill -f "python -m collector.run"

Restart later (same id, same folder):
  bash collector/teammate_setup.sh --id $ID

Send the output back to Divi (private team chat or shared drive, never git):
  cd "$REPO" && tar czf staleline_live_${ID}_$STAMP.tar.gz data/live_$ID out/GAPS_$ID.md out/collector_$ID.log
==================================================================
EOF
