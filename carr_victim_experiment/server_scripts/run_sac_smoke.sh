#!/bin/bash
# v1.10 Part A SAC pipeline smoke (NOT a battery run) — single SAC shield-on run
# Usage: run_sac_smoke.sh <clean|contrast> <outdir>
set -e
source ${CONDA_ROOT}/etc/profile.d/conda.sh
conda activate carr
cd ${ARTIFACT_ROOT}/safe_RL_POMDPs_patched
POISON=$1; OUTDIR=$2
export OMP_NUM_THREADS=1
export TF_NUM_INTRAOP_THREADS=1
export TF_NUM_INTEROP_THREADS=1
if [ "$POISON" = "clean" ]; then PNAME=clean; PDELTA=0.0; else PNAME=contrast; PDELTA=2.0; fi
python run_carr_victim.py --grid-model obstacle --constants N=6 \
  --learning-method SAC --max-runs 2000 --maxsteps 100 \
  --obs-level BELIEF_SUPPORT --valuations --goal-value 1000 \
  --seed 499 --switch-shield HARD --shield-episode 2000 \
  --at-retirement-eps 1000 --final-eval-eps 5000 \
  --poison-name "$PNAME" --poison-delta "$PDELTA" --poison-scope shield-on \
  --fname _VICTIM --no-overwrite --output-dir "$OUTDIR"
