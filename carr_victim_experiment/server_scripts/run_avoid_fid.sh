#!/bin/bash
# v1.8 avoid-domain fidelity gate: single clean run at a given switch mode
# Usage: run_avoid_fid.sh <noshield|retained|sudden|smooth> <outdir>
set -e
source ${CONDA_ROOT}/etc/profile.d/conda.sh
conda activate carr
cd ${ARTIFACT_ROOT}/safe_RL_POMDPs_patched
MODE=$1; OUTDIR=$2
EXTRA=""
case "$MODE" in
  noshield) EXTRA="--noshield";;
  retained) EXTRA="--switch-shield RETAINED";;
  sudden)   EXTRA="--switch-shield HARD --shield-episode 1000";;
  smooth)   EXTRA="--switch-shield SOFT --shield-episode 1000";;
  *) echo "bad mode $MODE"; exit 1;;
esac
export OMP_NUM_THREADS=1
export TF_NUM_INTRAOP_THREADS=1
export TF_NUM_INTEROP_THREADS=1
python run_carr_victim.py --grid-model surveillance --constants N=6,RADIUS=3 \
  --learning-method REINFORCE --max-runs 5000 --maxsteps 100 \
  --obs-level BELIEF_SUPPORT --valuations --goal-value 1000 \
  --seed 1 $EXTRA \
  --at-retirement-eps 1000 --final-eval-eps 5000 \
  --poison-name clean --poison-delta 0.0 --poison-scope full \
  --fname _VICTIM --no-overwrite --output-dir "$OUTDIR"
