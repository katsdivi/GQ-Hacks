#!/usr/bin/env bash
# Sim box driver (run on the sim box from /opt/sim under tmux): part (b) placebo design, then part (a) power.
# Usage: tests/sim_box_run.sh <out_dir> [reps] [procs]
set -u
OUT=${1:?out_dir}; REPS=${2:-500}; PROCS=${3:-8}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONWARNINGS=ignore
mkdir -p "$OUT/b" "$OUT/a"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$OUT/driver.log"; }
log "sha $(cat SIM_SHA 2>/dev/null || echo unknown) seed 20261003 reps $REPS procs $PROCS nproc $(nproc)"
t0=$(date +%s)
log "start (b) placebo design: M 3000"
.venv/bin/python tests/placebo_design_sim.py 3000 "$REPS" "$PROCS" "$OUT/b" > "$OUT/b/run.log" 2>&1
log "end (b) exit $? wall $(( $(date +%s) - t0 )) s"
t1=$(date +%s)
log "start (a) power: studies $REPS"
.venv/bin/python tests/power_sim_quotes.py "$REPS" "$PROCS" "$OUT/a" > "$OUT/a/run.log" 2>&1
log "end (a) exit $? wall $(( $(date +%s) - t1 )) s"
touch "$OUT/DONE"
